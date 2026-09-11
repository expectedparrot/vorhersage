"""Resumable polling and bounded agent execution using JSON subprocess adapters."""

try:
    import fcntl
except ImportError:  # Keep non-monitoring commands usable on non-POSIX systems.
    fcntl = None
import json
import subprocess
from datetime import timedelta

from .common import Error, canonical, digest, now, require, time
from .evidence import Epiq, capture_bundle, fingerprint, validate_packet
from .schemas import check
from .store import Store
from .workflow import Workflow


def configure(store, spec):
    check(spec, "watch")
    require(not spec.get("epiq_source") or spec.get("epiq_db"), "epiq_source needs epiq_db.")
    with store.connect(True) as c:
        Store.question(c, spec["question_id"])
        Store.put(c, "watch", {**spec, "enabled": True, "configured_at": now()})
    return {"watch_id": spec["id"]}


def configs(store):
    with store.connect() as c:
        # Use insertion order: artifact UUID order is not a chronology tie-breaker.
        rows = c.execute("SELECT body FROM artifacts WHERE kind='watch' ORDER BY rowid")
        latest = {}
        for row in rows:
            spec = json.loads(row[0])
            latest[spec["id"]] = spec
        return list(latest.values())


def disable(store, id):
    spec = next((s for s in configs(store) if s["id"] == id), None)
    require(spec is not None, "Unknown watch.")
    with store.connect(True) as c:
        Store.put(c, "watch", {**spec, "enabled": False, "configured_at": now()})
    return {"watch_id": id, "enabled": False}


def invoke(argv, request, timeout):
    # Configured executables only; source text never becomes shell code.
    result = subprocess.run(argv, input=canonical(request), capture_output=True, text=True, timeout=timeout)
    require(result.returncode == 0, "Configured worker failed (exit %s)." % result.returncode, "worker_failed")
    try:
        value = json.loads(result.stdout, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except ValueError as exc:
        raise Error("worker_invalid_json", "Worker must return one finite JSON object.") from exc
    require(isinstance(value, dict), "Worker response must be a JSON object.")
    return value


def latest_forecast(w, spec):
    rows = [f for f in w.report(spec["question_id"])["forecasts"]
            if f["forecaster"] == spec["forecaster"] and f["mode"] == "prospective"]
    return max(rows, key=lambda f: time(f["issued_at"])) if rows else None


def checkpoint(store, id):
    with store.connect() as c:
        rows = c.execute("SELECT body FROM artifacts WHERE kind='watch_check' ORDER BY rowid DESC")
        for row in rows:
            record = json.loads(row[0])
            if record["watch_id"] == id:
                return record
    return None


def resolve_answer(w, forecast, answer):
    resolution = answer.get("resolution", {})
    require(isinstance(resolution, dict), "Worker resolution must be an object.")
    require(resolution.get("question_id") == forecast["question_id"] and
            resolution.get("question_version") == forecast["question_version"], "Worker resolution targets the wrong event version.")
    return w.resolve(resolution)


def tick(project, watch_id=None, force=False):
    require(fcntl is not None, "Monitoring currently requires POSIX file locking (macOS/Linux).")
    w = Workflow(project)
    # One watcher per project at a time; a crash releases the OS lock. Ordinary
    # workflow writers still use SQLite optimistic concurrency and transactions.
    require(w.store.path.exists(), "Initialize the project before polling.")
    with (w.store.path.parent / "watch.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Error("watch_busy", "Another monitoring tick is active.")
        selected = [s for s in configs(w.store) if watch_id is None or s["id"] == watch_id]
        require(watch_id is None or selected, "Unknown watch.")
        results = []
        for spec in selected:
            if not spec["enabled"]:
                continue
            previous = checkpoint(w.store, spec["id"])
            if not force and previous and time(previous["next_check_at"]) > time(now()):
                results.append({"watch_id": spec["id"], "disposition": "not_due", "next_check_at": previous["next_check_at"]})
                continue
            try:
                result = _tick(w, spec, previous)
            except (Error, OSError, ValueError, subprocess.SubprocessError) as exc:
                # Preserve the previous successful fingerprint so a failed worker
                # cannot consume an update. Do not echo subprocess output/secrets.
                result = {"disposition": "error", "error": {"code": getattr(exc, "code", "worker_error"),
                          "message": str(exc) if isinstance(exc, Error) else "Monitoring operation failed; check the configured worker."},
                          "fingerprints": (previous or {}).get("fingerprints", []),
                          "epiq_change_digest": (previous or {}).get("epiq_change_digest")}
            result.update(watch_id=spec["id"], checked_at=now(),
                          next_check_at=(time(now()) + timedelta(seconds=spec["interval_seconds"])).isoformat())
            with w.store.connect(True) as c:
                Store.put(c, "watch_check", result)
            results.append(result)
        return {"checks": results, "checked_at": now()}


def _tick(w, spec, previous):
    forecast = latest_forecast(w, spec)
    if not forecast:
        return {"disposition": "no_prospective_forecast"}
    report = w.report(spec["question_id"])
    if report["question"]["version"] != forecast["question_version"]:
        return {"disposition": "question_version_changed", "forecast_id": forecast["id"]}
    resolutions = [r for r in report["resolutions"] if r["question_version"] == forecast["question_version"]]
    if resolutions and resolutions[-1]["outcome"] != "disputed":
        return {"disposition": "resolved", "forecast_id": forecast["id"]}
    timeout = spec.get("timeout_seconds", 30)
    with w.store.connect() as c:
        old_packets = [Store.artifact(c, id, "packet") for id in sorted({r["packet_id"] for r in forecast["evidence_refs"]})]
    fresh, changes = [], []
    if spec.get("research_command"):
        output = invoke(spec["research_command"], {"protocol": "vorhersage.research.v1", "forecast": forecast,
                        "evidence": old_packets, "previous_check": previous, "checked_at": now()}, timeout)
        require(set(output) <= {"packets", "bundles"} and bool(output) and
                all(isinstance(v, list) for v in output.values()), "Research worker must return packets and/or bundles arrays.")
        fresh.extend(validate_packet(p) for p in output.get("packets", []))
        fresh.extend(capture_bundle(b) for b in output.get("bundles", []))
    if spec.get("epiq_db"):
        client = Epiq(spec["epiq_db"], spec.get("epiq_source"))
        for packet in old_packets:
            if packet["kind"] != "epiq":
                continue
            found = client.changes(packet)["changes"]
            if found:
                changes.extend(found)
                if all(r["state"] == "Answered" for r in found):
                    fresh.append(client.freeze({"cells": packet["epiq"]["selection"]["cells"], "information_as_of": now()}))
    for packet in fresh:
        require(time(packet["information_as_of"]) <= time(now()), "Research packet cutoff cannot be in the future.")
    new_fingerprints = sorted({fingerprint(p) for p in fresh})
    old_fingerprints = {fingerprint(p) for p in old_packets}
    prior_fingerprints = set((previous or {}).get("fingerprints", []))
    unseen = set(new_fingerprints) - old_fingerprints - prior_fingerprints
    imported = [w.import_packet(p) for p in fresh]
    change_digest = digest(changes) if changes else None
    changed = bool(unseen or (changes and change_digest != (previous or {}).get("epiq_change_digest")))
    if changed:
        signature = digest([forecast["id"], new_fingerprints, changes])
        w.signal({"question_id": spec["question_id"], "reason": "Monitoring collected changed evidence; reassess including contradictions or retractions.",
                  "evidence_refs": forecast["evidence_refs"],
                  "idempotency_key": "watch-" + spec["id"] + "-" + signature})
    due = next((d for d in w.monitor()["due"] if d["forecast_id"] == forecast["id"]), None)
    result = {"forecast_id": forecast["id"], "fingerprints": new_fingerprints,
              "epiq_change_digest": change_digest, "changed": changed, "imported_packets": imported,
              "disposition": "unchanged", "epiq_changes": changes}
    if not due:
        return result
    if time(now()) >= time(forecast["question"]["event_deadline"]) or resolutions:
        result["disposition"] = "resolution_due"
        if spec.get("agent_command"):
            answer = invoke(spec["agent_command"], {"protocol": "vorhersage.agent.v1", "action": "resolve",
                            "forecast": forecast, "existing_resolutions": resolutions, "evidence": fresh + old_packets,
                            "imported_packets": imported, "research_changes": changes}, timeout)
            if answer.get("defer"):
                result["deferred"] = answer["defer"]
            else:
                result["resolution"] = resolve_answer(w, forecast, answer)
                result["disposition"] = "resolved"
        return result
    active = [r for r in w.status()["runs"] if r["run"].get("previous_forecast_id") == forecast["id"] and r["pending_tasks"]]
    if active:
        run_id = active[-1]["run"]["id"]
    else:
        run_id = w.start({"question_id": forecast["question_id"], "forecaster": forecast["forecaster"],
                          "method": forecast["method"], "mode": "prospective", "information_as_of": now(),
                          "previous_forecast_id": forecast["id"], "research_status": "in_progress",
                          "max_searches": spec.get("max_searches", 20), "max_extra_tasks": spec.get("max_extra_tasks", 2)})["run_id"]
    result.update(disposition="revision_ready", run_id=run_id)
    if spec.get("agent_command"):
        for _ in range(spec.get("max_tasks", 20)):
            step = w.next(run_id)
            if step["disposition"] != "actionable":
                result.update(disposition=step["disposition"], next=step)
                break
            answer = invoke(spec["agent_command"], {"protocol": "vorhersage.agent.v1", "action": "submit", "next": step,
                            "fresh_evidence": fresh, "imported_packets": imported, "research_changes": changes}, timeout)
            if answer.get("defer"):
                result["deferred"] = answer["defer"]
                break
            if "resolution" in answer:
                result["resolution"] = resolve_answer(w, forecast, answer)
                result["disposition"] = "resolved"
                return result
            require(set(answer) <= {"payload", "usage"} and "payload" in answer, "Agent worker must return payload and optional usage, or defer.")
            request = {"task_id": step["task"]["id"], "expected_revision": step["revision"],
                       "idempotency_key": "watch-task-" + step["task"]["id"], **answer}
            w.submit(run_id, request)
        result["next"] = w.next(run_id)
        if result["next"]["disposition"] != "actionable":
            result["disposition"] = result["next"]["disposition"]
    return result
