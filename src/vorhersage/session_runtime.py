"""Immutable live-session events and a bounded, resumable worker contract.

Workers own provider/tool I/O. A durable attempt precedes that I/O; a process
crash without a receipt requires reconciliation, never blind resubmission.
"""

import copy
import subprocess

from .common import Error, digest, now, require, time
from .monitoring import fcntl, invoke
from .schemas import SESSION_PAYLOADS, USAGE, check, validate
from .store import Store


ZERO = {"searches": 0, "model_calls": 0, "cost_usd": 0}


def events(c, session_id):
    return sorted([Store.artifact(c, r["id"]) for r in c.execute(
        "SELECT id FROM artifacts WHERE run_id=? AND kind='joint_event'", (session_id,))],
        key=lambda e: e["revision"])


def project(spec, history):
    """Derive effective state without changing registered specifications."""
    effective = copy.deepcopy(spec)
    attempts, assessments, observations, receipts, requests = {}, {}, {}, [], []
    disposition = "open"
    for e in history:
        p, kind = e["payload"], e["kind"]
        if kind == "evidence":
            effective["packet_ids"] += p["packet_ids"]
            effective["information_as_of"] = p["information_as_of"]
        elif kind == "tool_request":
            requests.append({**p, "requested_revision": e["revision"]})
        elif kind == "bindings":
            effective.update(p)
        elif kind == "amendment":
            for k in ("budget", "research"):
                if k in p:
                    effective["execution"][k] = p[k]
            if "configuration" in p:
                effective["configuration"] = p["configuration"]
        elif kind == "attempt_start":
            attempts[p["attempt_id"]] = {**p, "status": "running", "usage": None,
                                           "started_at": e["recorded_at"], "started_revision": e["revision"], "continuation": {}}
            disposition = "running"
        elif kind == "attempt_result":
            attempts[p["attempt_id"]].update(p)
            disposition = {"completed": "open", "truncated": "failed", "error": "failed"}.get(p["status"], p["status"])
        elif kind == "usage":
            attempts[p["attempt_id"]]["usage"] = p["usage"]
        elif kind == "transition":
            disposition = p["status"]
        elif kind == "research":
            a = attempts[p["attempt_id"]]
            request = a["request"].get("tool_request", {})
            receipts.append({**p, "event_id": e["id"], "revision": e["revision"], "recorded_at": e["recorded_at"],
                             "requested_revision": request.get("requested_revision", a["started_revision"])})
        elif kind == "assessment":
            assessments[p["domain"]] = {**p, "event_id": e["id"]}
        elif kind == "observation":
            observations[p["requirement_id"]] = {**p, "event_id": e["id"]}
    usage = {k: sum(a["usage"][k] for a in attempts.values() if a["usage"] is not None) for k in ZERO}
    unknown = [a["attempt_id"] for a in attempts.values() if a["usage"] is None]
    return {"specification": effective, "execution_disposition": disposition, "attempts": attempts,
            "attempt_usage": usage, "unknown_usage_attempts": unknown, "research_receipts": receipts,
            "assessments": assessments, "observations": observations, "tool_requests": requests}


def research_audit(state):
    policy = state["specification"].get("execution", {}).get("research", {})
    successful = [r for r in state.get("research_receipts", []) if r["ok"]]
    pages = {r["url"] for r in successful if r["tool"] == "read_page" and r.get("url")}
    searches = [r for r in successful if r["tool"] == "web_search" and r.get("query")]
    reads = [r for r in successful if r["tool"] == "read_page"]
    counts = {"minimum_successful_tools": len(successful), "minimum_unique_pages": len(pages),
              "minimum_unique_searches": len({r["query"].strip().lower() for r in searches}),
              "minimum_recent_searches": len({r["query"].strip().lower() for r in searches if r.get("recent_days")}),
              "minimum_followup_searches": sum(any(p["revision"] < r["requested_revision"] for p in reads) for r in searches)}
    missing = {k: max(0, policy.get(k, 0) - v) for k, v in counts.items()}
    domains = [{"domain": d, **state.get("assessments", {}).get(d, {"disposition": "missing"})}
               for d in policy.get("domains", [])]
    return {"counts": counts, "missing": {k: v for k, v in missing.items() if v}, "domains": domains,
            "ready": not any(missing.values()) and all(d["disposition"] != "missing" for d in domains),
            "limitations": ["Receipts and assessments are caller-reported; counts do not establish research quality.",
                            "Unknown domain assessments count as explicit coverage, not evidence of knowledge."]}


def audit_state(state):
    original = state.get("registered_specification", state["specification"])
    rows = []
    for requirement in original.get("execution", {}).get("requirements", []):
        observation = state.get("observations", {}).get(requirement["id"])
        actual = observation["actual"] if observation else None
        status = "unverifiable" if actual is None else ("matched" if actual == requirement["expected"] else "changed")
        if observation and observation["failed"]:
            status = "failed"
        rows.append({**requirement, "status": status, "observation": observation})
    amendments = [e for e in state.get("events", []) if e["kind"] == "amendment"]
    statuses = {r["status"] for r in rows}
    fidelity = ("failed" if "failed" in statuses else "changed" if amendments or "changed" in statuses
                else "unverifiable" if "unverifiable" in statuses or not rows else "matched")
    return {"requirements": rows, "amendments": amendments, "protocol_fidelity": fidelity,
            "research": research_audit(state), "complete_grid": not state["missing_cells"],
            "disposition": state["disposition"], "usage": state["usage"],
            "unknown_usage_attempts": state.get("unknown_usage_attempts", []),
            "limitations": ["Matching is against registered requirements and reported observations, not independent certification.",
                            "Grid completeness, protocol fidelity, and predictive accuracy are separate properties."]}


def audit(store, session_id):
    from .sessions import status
    return audit_state(status(store, session_id))


def _validate_event(c, state, kind, p):
    from .sessions import unique, validate_bindings
    from .workflow import verify_refs
    spec = state["specification"]
    require("execution" in spec, "Session needs an execution contract for runtime events.")
    require(spec["provenance"]["kind"] == "native", "External records cannot accept live events.")
    require(state["finalization"] is None, "Session is finalized.")
    active = [a for a in state["attempts"].values() if a["status"] in ("running", "waiting")]
    if kind not in ("attempt_result", "usage"):
        require(not active, "Reconcile or finish the active attempt first.")
    if kind in ("evidence", "bindings", "research", "assessment", "observation", "tool_request"):
        require(state["disposition"] in ("open", "budget_exhausted"), "Session is not open.")
    refs = p.get("evidence_refs", [])
    require(all(r["packet_id"] in spec["packet_ids"] for r in refs), "Evidence references must use available session packets.")
    verify_refs(c, refs, spec["information_as_of"])
    manifest = {}
    if kind == "tool_request":
        require("tool_worker" in spec["execution"], "Tool requests need a registered tool worker.")
        require(p["request_id"] not in {r["request_id"] for r in state["tool_requests"]}, "Duplicate tool request ID.")
    elif kind == "evidence":
        require(spec["execution"]["evidence_policy"] == "live", "Fixed-evidence sessions cannot add packets.")
        unique(p["packet_ids"], "packets")
        require(not set(p["packet_ids"]) & set(spec["packet_ids"]), "Packet is already available.")
        require(time(spec["information_as_of"]) <= time(p["information_as_of"]) <= time(now()), "Invalid live evidence cutoff.")
        for id in p["packet_ids"]:
            packet = Store.artifact(c, id, "packet")
            require(time(packet["information_as_of"]) <= time(p["information_as_of"]), "Packet follows evidence cutoff.")
            manifest[id] = digest(packet)
    elif kind == "bindings":
        require(spec["execution"]["defer_bindings"], "Bindings are frozen at registration.")
        require(not state["submissions"], "Bindings cannot change after probability submission.")
        conditions = {id: Store.artifact(c, id, "condition")["specification"] for id in spec["condition_ids"]}
        validate_bindings(p, conditions)
    elif kind == "attempt_start":
        require(state["disposition"] == "open", "Session is not open for a new attempt.")
        require(p["attempt_id"] not in state["attempts"], "Duplicate attempt ID.")
        require(not state["unknown_usage_attempts"], "Reconcile unknown attempt usage before another call.")
        if spec["mode"] == "prospective":
            for q in spec["questions"]:
                require(time(now()) < time(Store.question(c, q["question_id"], q["version"])["specification"]["event_deadline"]),
                        "Prospective event deadline passed.")
                require(not any(r["question_id"] == q["question_id"] and r["question_version"] == q["version"]
                                for r in Store.all(c, "resolution")), "Question has a recorded resolution.")
        budget = spec["execution"]["budget"]
        require(state["usage"]["cost_usd"] < budget["max_cost_usd"], "Session cost budget exhausted.")
        counter = "model_calls" if p["kind"] == "model" else "searches"
        require(state["usage"][counter] < budget["max_" + counter], "Session call budget exhausted.")
    elif kind in ("attempt_result", "usage"):
        attempt = state["attempts"].get(p["attempt_id"])
        require(attempt is not None, "Unknown attempt.")
        if kind == "attempt_result":
            require(attempt["status"] in ("running", "waiting"), "Attempt already has a terminal result.")
            if p["status"] == "waiting":
                require(p["continuation"] and p["usage"] is None, "Waiting requires a receipt/continuation and unknown final usage.")
            if p["usage"] is not None:
                validate(p["usage"], USAGE)
                counter = "model_calls" if attempt["kind"] == "model" else "searches"
                require(p["usage"][counter] >= 1, "An attempted call must count even if it failed or used a cache.")
        else:
            require(attempt["status"] not in ("running", "waiting"), "Usage can only reconcile a terminal attempt.")
            require(attempt["usage"] is None, "Known usage is immutable.")
            counter = "model_calls" if attempt["kind"] == "model" else "searches"
            require(p["usage"][counter] >= 1, "Reconciled usage must count the attempt.")
    elif kind == "research":
        a = state["attempts"].get(p["attempt_id"])
        require(a and a["kind"] == "tool" and a["status"] not in ("running", "waiting"), "Research receipt needs a finished tool attempt.")
        require(not any(r["attempt_id"] == p["attempt_id"] for r in state["research_receipts"]), "Tool attempt already has a research receipt.")
        require(not p["ok"] or a["status"] == "completed", "A failed tool attempt cannot be a successful receipt.")
        request = a["request"].get("tool_request")
        if request:
            require(request["tool"] == p["tool"], "Receipt tool differs from requested tool.")
            for field in ("url", "query", "recent_days"):
                require(p.get(field) == request["arguments"].get(field), "Receipt differs from requested " + field + ".")
        if p["ok"] and p["tool"] == "read_page":
            require(p.get("url") and refs, "A successful page read needs its URL and captured evidence references.")
            for ref in refs:
                packet = Store.artifact(c, ref["packet_id"], "packet")
                record = next(r for r in packet["records"] if r["id"] == ref["record_id"])
                require(any(s["url"] == p["url"] for s in record["sources"]), "Read URL does not match evidence source.")
    elif kind == "assessment":
        require(p["domain"] in spec["execution"]["research"]["domains"], "Unregistered research domain.")
        require(p["disposition"] != "assessed" or refs, "An assessed domain needs cited evidence; use unknown otherwise.")
    elif kind == "observation":
        require(p["requirement_id"] in {r["id"] for r in spec["execution"]["requirements"]}, "Unknown protocol requirement.")
    elif kind == "amendment":
        require(state["disposition"] != "refused", "A refused session remains terminal; register a new session.")
        if "research" in p:
            unique(p["research"]["domains"], "research domains")
        require(set(p) != {"reason"}, "Amendment must declare changes.")
    elif kind == "transition":
        require(state["disposition"] != "refused", "A refused session remains terminal.")
        if p["status"] == "open":
            require(state["disposition"] in ("failed", "budget_exhausted"), "Only a stopped session can resume.")
            require(not state["unknown_usage_attempts"], "Reconcile unknown usage before resuming.")
    return manifest


def _event(c, session_id, spec):
    from .sessions import _status
    check(spec, "session_event")
    validate(spec["payload"], SESSION_PAYLOADS[spec["kind"]])
    scope = session_id + ":event"
    retry = Store.receipt(c, scope, spec["idempotency_key"], spec)
    if retry:
        return retry
    state = _status(c, session_id)
    require(state["revision"] == spec["expected_revision"], "Stale session revision.", "version_conflict")
    manifest = _validate_event(c, state, spec["kind"], spec["payload"])
    revision = state["revision"] + 1
    id = "joint_event_" + digest([session_id, revision])[:24]
    Store.put(c, "joint_event", {"id": id, "session_id": session_id, "revision": revision,
              "kind": spec["kind"], "payload": spec["payload"], "recorded_at": now(),
              "input_manifest": manifest}, id=id, run_id=session_id)
    result = {"session_id": session_id, "event_id": id, "revision": revision}
    Store.remember(c, scope, spec["idempotency_key"], spec, result)
    return result


def record(store, session_id, spec):
    with store.connect(True) as c:
        return _event(c, session_id, spec)


def _record_current(store, session_id, kind, payload, key):
    from .sessions import _status
    with store.connect(True) as c:
        return _event(c, session_id, {"kind": kind, "payload": payload, "idempotency_key": key,
                                     "expected_revision": _status(c, session_id)["revision"]})


def apply_actions(store, session_id, attempt_id, actions):
    """Accept one worker's actions atomically; the separately saved attempt survives rejection."""
    from . import sessions
    require(isinstance(actions, list), "Worker actions must be a list.")
    with store.connect(True) as c:
        marker = "joint_actions_" + digest([session_id, attempt_id])[:24]
        if c.execute("SELECT 1 FROM artifacts WHERE id=?", (marker,)).fetchone():
            return
        for index, action in enumerate(actions):
            require(isinstance(action, dict) and set(action) == {"kind", "payload"}, "Action needs kind and payload.")
            state = sessions._status(c, session_id)
            envelope = {"expected_revision": state["revision"], "idempotency_key": f"{attempt_id}:action:{index}"}
            if action["kind"] == "capture":
                from .evidence import validate_packet
                packet = validate_packet(action["payload"])
                packet_id = "pkt_" + packet["sha256"][:24]
                Store.put(c, "packet", packet, id=packet_id)
                _event(c, session_id, {**envelope, "kind": "evidence", "payload": {
                    "packet_ids": [packet_id], "information_as_of": max(
                        [state["specification"]["information_as_of"], packet["information_as_of"]], key=time)}})
            elif action["kind"] == "submit":
                require(set(action["payload"]) == {"cells", "raw_record"}, "Submit action needs cells and raw_record; usage belongs to attempts.")
                spec = {**envelope, **action["payload"], "usage": ZERO}
                check(spec, "session_submit")
                sessions._append(c, session_id, spec, now())
            elif action["kind"] == "finalize":
                spec = {**envelope, **action["payload"]}
                check(spec, "session_finalize")
                sessions._finalize(c, session_id, spec, now())
            else:
                require(action["kind"] in ("evidence", "bindings", "research", "assessment", "observation", "tool_request"),
                        "Worker cannot change protocol, resume failures, or manufacture attempts through actions.")
                _event(c, session_id, {**envelope, **action})
        Store.put(c, "joint_actions", {"attempt_id": attempt_id, "status": "applied", "recorded_at": now()}, id=marker, run_id=session_id)


def _accept_pending_actions(store, session_id, attempt):
    try:
        apply_actions(store, session_id, attempt["attempt_id"], attempt["raw_record"]["actions"])
        return True
    except (Error, ValueError, TypeError, KeyError) as exc:
        _record_current(store, session_id, "transition", {"status": "failed", "reason": "Worker actions rejected: " + str(exc)}, attempt["attempt_id"] + ":actions-rejected")
        with store.connect(True) as c:
            Store.put(c, "joint_actions", {"attempt_id": attempt["attempt_id"], "status": "rejected", "recorded_at": now()},
                      id="joint_actions_" + digest([session_id, attempt["attempt_id"]])[:24], run_id=session_id)
        return False


def execute(store, session_id, max_steps=1):
    """Drive bounded worker invocations. Waiting receipts poll once per invocation."""
    from . import sessions
    require(type(max_steps) is int and 1 <= max_steps <= 100, "max_steps must be 1..100.")
    require(fcntl is not None, "Session execution requires POSIX locking.")
    require(store.path.exists(), "Initialize the project first.")
    with (store.path.parent / ("session-" + digest(session_id)[:24] + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Error("session_busy", "Session already has an active worker.") from exc
        for _ in range(max_steps):
            state = sessions.status(store, session_id)
            execution = state["specification"].get("execution", {})
            require("worker" in execution, "Register a session worker before running.")
            if state["disposition"] not in ("open", "waiting"):
                break
            with store.connect() as c:
                handled = {a["attempt_id"] for a in Store.all(c, "joint_actions")}
            unapplied = [a for a in state["attempts"].values() if a["status"] == "completed"
                         and "actions" in a.get("raw_record", {}) and a["attempt_id"] not in handled]
            if unapplied:
                if not _accept_pending_actions(store, session_id, unapplied[0]):
                    break
                continue
            pending = [a for a in state["attempts"].values() if a["status"] == "waiting"]
            started_tools = {a["request"].get("tool_request", {}).get("request_id") for a in state["attempts"].values()}
            tool_queue = [r for r in state["tool_requests"] if r["request_id"] not in started_tools]
            kind = pending[0]["kind"] if pending else "tool" if tool_queue else "model"
            worker = execution["tool_worker" if kind == "tool" else "worker"]
            if pending:
                attempt = pending[0]
            else:
                if state["unknown_usage_attempts"]:
                    break
                budget = execution["budget"]
                counter = "searches" if kind == "tool" else "model_calls"
                if state["usage"][counter] >= budget["max_" + counter] or state["usage"]["cost_usd"] >= budget["max_cost_usd"]:
                    _record_current(store, session_id, "transition", {"status": "budget_exhausted", "reason": "Reported call or cost limit reached."}, "budget:" + str(state["revision"]))
                    break
                attempt_id = "attempt_" + digest([session_id, state["revision"]])[:24]
                with store.connect() as c:
                    packets = {p: Store.artifact(c, p, "packet") for p in state["specification"]["packet_ids"]}
                context = copy.deepcopy(state)
                for a in context["attempts"].values():
                    a.pop("request", None)
                for e in context["events"]:
                    if e["kind"] == "attempt_start":
                        e["payload"].pop("request", None)
                request = {"protocol": "vorhersage.session.worker.v1", "session_id": session_id,
                           "attempt_id": attempt_id, "context": context, "packets": packets,
                           "worker_config": worker["config"]}
                if kind == "tool":
                    request["tool_request"] = tool_queue[0]
                _record_current(store, session_id, "attempt_start", {"attempt_id": attempt_id, "kind": kind, "request": request}, attempt_id + ":start")
                attempt = sessions.status(store, session_id)["attempts"][attempt_id]
            attempt_id = attempt["attempt_id"]
            request = {**attempt["request"], "action": "poll" if pending else "execute", "continuation": attempt["continuation"]}
            try:
                answer = invoke(worker["command"], request, worker["timeout_seconds"])
                require(set(answer) == {"status", "usage", "continuation", "raw_record", "actions"}, "Invalid session worker response fields.")
                result = {k: answer[k] for k in ("status", "usage", "continuation", "raw_record")}
                result["attempt_id"] = attempt_id
                require(answer["status"] == "completed" or answer["actions"] == [], "Only completed attempts can supply actions.")
                # Keep actions with the response so a crash before acceptance can be reconciled.
                result["raw_record"] = {"worker_record": answer["raw_record"], "actions": answer["actions"]}
                _record_current(store, session_id, "attempt_result", result, attempt_id + ":result:" + str(state["revision"]))
            except (Error, OSError, ValueError, subprocess.SubprocessError) as exc:
                # stdout/stderr are not persisted: they may contain secrets. No blind retry.
                _record_current(store, session_id, "attempt_result", {"attempt_id": attempt_id, "status": "error", "usage": None,
                    "continuation": attempt["continuation"], "raw_record": {"error_code": getattr(exc, "code", type(exc).__name__)}},
                    attempt_id + ":worker-error:" + str(state["revision"]))
                break
            if answer["status"] != "completed":
                break
            saved = sessions.status(store, session_id)["attempts"][attempt_id]
            if not _accept_pending_actions(store, session_id, saved):
                break
    return sessions.status(store, session_id)
