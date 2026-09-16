"""One-question research journals with separately stored market targets."""

import json
import math
from pathlib import Path

from . import market_data
from .common import Error, digest, identifier, now, probability, require, time
from .schemas import check
from .store import Store
from .workflow import verify_refs


def _vault(store, path, create=False):
    vault = Store(path)
    require(store.root != vault.root and store.root not in vault.root.parents and vault.root not in store.root.parents,
            "Evaluator and researcher projects must be separate, non-nested directories.")
    if create and not vault.path.exists():
        vault.init("Private market targets")
    return vault


def _snapshot(spec, fixture=None):
    require((fixture is not None) == (spec["mode"] == "simulation"),
            "Simulation requires a fixture snapshot; prospective cases fetch live data and reject supplied snapshots.")
    value = fixture if fixture is not None else market_data.snapshot(spec["venue"], spec["market_id"])
    require(value["venue"] == spec["venue"] and value["market_id"] == spec["market_id"], "Snapshot belongs to another market.")
    terms = value["contract"]
    require(terms["venue"] == spec["venue"] and terms["market_id"] == spec["market_id"], "Contract identity mismatch.")
    require(value["contract_sha256"] == digest(terms), "Contract hash mismatch.", "integrity_error")
    require(time(value["captured_at"]) <= time(now()), "Snapshot cannot be from the future.")
    if spec["mode"] == "prospective":
        require((time(now()) - time(value["captured_at"])).total_seconds() <= 120, "Live snapshot is stale.")
    q = value["quote"]
    bid, ask = probability(q["bid"]), probability(q["ask"])
    require(0 < bid <= ask < 1, "Snapshot requires an uncrossed two-sided quote.")
    require(abs(probability(q["midpoint"]) - (bid + ask) / 2) < 1e-9
            and abs(probability(q["spread"]) - (ask - bid)) < 1e-9, "Inconsistent quote arithmetic.")
    for field in ("bid_size", "ask_size"):
        require(type(q[field]) in (int, float) and math.isfinite(q[field]) and q[field] > 0, "Both quote sizes must be positive.")
    return value


def _read(c, case_id):
    case = Store.artifact(c, case_id, "workbench")
    entries = []
    for row in c.execute("SELECT id,body FROM artifacts WHERE kind='workbench_entry'"):
        if json.loads(row["body"])["case_id"] == case_id:
            entries.append({"id": row["id"], **Store.artifact(c, row["id"], "workbench_entry")})
    entries.sort(key=lambda e: e["revision"])
    require([e["revision"] for e in entries] == list(range(1, len(entries) + 1)), "Journal sequence is broken.", "integrity_error")
    reveals = [r for r in Store.all(c, "workbench_reveal") if r["case_id"] == case_id]
    require(len(reveals) <= 1, "Multiple target reveals.", "integrity_error")
    reveal = Store.artifact(c, reveals[0]["id"], "workbench_reveal") if reveals else None
    return case, entries, reveal


def _finished(entries):
    return next((e for e in entries if e["kind"] == "finish"), None)


def _pending(entries):
    work = [e for e in entries if e["kind"] in ("plan", "checkpoint")]
    return work[-1] if work and work[-1]["kind"] == "plan" else None


def start(store, spec, vault_path, fixture=None):
    check(spec, "workbench_start")
    with store.connect() as c:
        question = Store.question(c, spec["question"]["question_id"], spec["question"]["version"])
        require(question["specification"]["kind"] == ("simulation" if spec["mode"] == "simulation" else "real"),
                "Question kind and workbench mode disagree.")
        require(time(question["specification"]["event_deadline"]) > time(now()), "Question deadline has passed.")
    vault = _vault(store, vault_path, create=True)
    snap = _snapshot(spec, fixture)
    require(snap["quote"]["spread"] <= spec.get("max_spread", .05) + 1e-9,
            "Spread exceeds this case's selection limit.", "unusable_market")
    require(min(snap["quote"]["bid_size"], snap["quote"]["ask_size"]) >= spec.get("min_contracts_each_side", 1),
            "Top-of-book size is below this case's selection limit.", "unusable_market")
    case_id = identifier("workbench")
    target = {"case_id": case_id, "nonce": identifier("nonce"), "baseline": snap}
    with vault.connect(True) as c:
        target_id = Store.put(c, "market_target", target)
    body = {"specification": spec, "question": question, "contract": snap["contract"],
            "created_at": now(), "baseline_captured_at": snap["captured_at"],
            "target_id": target_id, "target_sha256": digest(target),
            "limitations": ["Prices are separated from this project, not protected by an operating-system sandbox.",
                            "Selection checks spread and top-of-book size only; neither establishes market accuracy.",
                            "The agent must verify the event is still unknown; an open market alone cannot establish this."]}
    with store.connect(True) as c:
        Store.put(c, "workbench", body, id=case_id)
    return status(store, case_id)


def submit(store, case_id, spec):
    check(spec, "workbench_submit")
    kind, payload = spec["kind"], spec["payload"]
    check(payload, "workbench_" + kind)
    with store.connect(True) as c:
        scope = "workbench:" + case_id
        duplicate = Store.receipt(c, scope, spec["idempotency_key"], spec)
        if duplicate:
            return duplicate
        case, entries, revealed = _read(c, case_id)
        require(spec["expected_revision"] == len(entries), "Stale workbench revision.", "version_conflict")
        finished, pending = _finished(entries), _pending(entries)
        initial = next((e for e in entries if e["kind"] == "initial"), None)
        require(kind in ("reflection", "exposure") or (not finished and not revealed), "Research trajectory is sealed.")
        if kind not in ("reflection", "exposure", "finish"):
            require(time(now()) < time(case["question"]["specification"]["event_deadline"]), "Question deadline has passed.")
        if kind == "initial":
            require(not initial and not pending, "Initial assessment already exists.")
        elif kind == "plan":
            require(initial and not pending, "Record an initial estimate and finish the pending research step first.")
        elif kind == "checkpoint":
            require(initial and pending, "Declare a research plan before recording its findings.")
            require(payload["sources_checked"] or payload["evidence_refs"] or payload["limitations"],
                    "Record sources or explain why research yielded no evidence.")
        elif kind == "finish":
            require(initial and (not pending or payload["outcome_status"] != "unresolved"),
                    "Record an initial estimate and close any pending research step first.")
            require(time(now()) < time(case["question"]["specification"]["event_deadline"])
                    or payload["outcome_status"] != "unresolved",
                    "Deadline has passed; finish with known or uncertain outcome status.")
        elif kind == "reflection":
            require(revealed, "Reveal the target before recording a post-reveal reflection.")
        recorded_at = now()
        if kind == "exposure":
            require(time(payload["occurred_at"]) <= time(recorded_at), "Exposure cannot be from the future.")
        refs = payload.get("evidence_refs", [])
        records = verify_refs(c, refs, recorded_at)
        for item in records:
            for source in item["record"]["sources"]:
                if source.get("published_at"):
                    require(time(source["published_at"]) <= time(recorded_at), "Source assertion date is in the future.")
        models = {}
        for artifact_id in payload.get("model_artifact_ids", []):
            row = c.execute("SELECT kind FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
            require(row is not None and row["kind"] in ("timeline_model", "assessment", "belief_revision", "prior", "reference_case", "forecast"),
                    "Model links must reference research/calculation artifacts.")
            models[artifact_id] = digest(Store.artifact(c, artifact_id))
        body = {"case_id": case_id, "revision": len(entries) + 1, "kind": kind,
                "phase": "post_reveal" if revealed else "pre_reveal", "recorded_at": recorded_at,
                "payload": payload, "model_manifest": models,
                "evidence_manifest": {r["packet_id"]: digest(Store.artifact(c, r["packet_id"], "packet")) for r in refs}}
        if kind == "checkpoint":
            body["plan_id"] = pending["id"]
        if kind == "finish":
            body["trajectory_manifest"] = {e["id"]: digest(Store.artifact(c, e["id"], "workbench_entry")) for e in entries}
        entry_id = Store.put(c, "workbench_entry", body)
        result = {"case_id": case_id, "entry_id": entry_id, "revision": body["revision"], "kind": kind,
                  "recorded_at": recorded_at, "sealed": bool(finished) or kind == "finish"}
        Store.remember(c, scope, spec["idempotency_key"], spec, result)
        return result


def _comparison(case, entries, target, followup, followup_error):
    baseline = target["baseline"]
    p = baseline["quote"]["midpoint"]
    rows, last_error = [], None
    plans = {e["id"]: e["payload"]["uncertainty"] for e in entries if e["kind"] == "plan"}
    for e in entries:
        if e["kind"] not in ("initial", "checkpoint"):
            continue
        estimate = e["payload"]["probability"]
        error = (estimate - p) ** 2
        rows.append({"entry_id": e["id"], "label": "Initial" if e["kind"] == "initial" else "Research " + str(len(rows)) + ": " + plans[e["plan_id"]],
                     "recorded_at": e["recorded_at"], "probability": estimate,
                     "difference_pp": 100 * (estimate - p), "squared_market_error": error,
                     "improvement_from_previous": None if last_error is None else last_error - error,
                     "outside_spread_pp": 100 * max(baseline["quote"]["bid"] - estimate, estimate - baseline["quote"]["ask"], 0)})
        last_error = error
    finish = _finished(entries)
    reasons = []
    if case["specification"]["mode"] == "simulation":
        reasons.append("Fictional simulation, not a live forecasting result.")
    if finish["payload"]["market_exposure"] != "none":
        reasons.append("Market probability exposure was reported at finish.")
    if finish["payload"]["outcome_status"] != "unresolved":
        reasons.append("Outcome was known or uncertain at finish.")
    for e in entries:
        if e["kind"] == "exposure" and time(e["payload"]["occurred_at"]) <= time(finish["recorded_at"]):
            reasons.append("Exposure declared: " + e["payload"]["kind"] + ": " + e["payload"]["description"])
    changed = followup is not None and followup["contract_sha256"] != baseline["contract_sha256"]
    if changed:
        reasons.append("Contract terms changed between snapshots; inspect comparability.")
    return {"target": baseline["quote"], "target_captured_at": baseline["captured_at"],
            "target_method": "Opening order-book midpoint, frozen before initial assessment.",
            "rows": rows, "net_squared_error_improvement": rows[0]["squared_market_error"] - rows[-1]["squared_market_error"],
            "followup_quote": followup["quote"] if followup else None,
            "followup_captured_at": followup["captured_at"] if followup else None,
            "market_movement_pp": 100 * (followup["quote"]["midpoint"] - p) if followup and not changed else None,
            "followup_error": followup_error, "contract_changed": changed,
            "eligible_for_blind_comparison": not reasons, "qualification_reasons": reasons,
            "limitations": ["Market agreement is not an outcome score or proof of forecast accuracy.",
                            "Step improvements are descriptive; sequential research does not identify causal effects.",
                            "Research may include information arriving after the opening target. Inspect market movement and timestamps.",
                            "No exposure reported is an agent declaration, not independently verified isolation.",
                            "Bid-ask spread is not a confidence interval. Missing follow-up data does not replace the opening target."]}


def reveal(store, case_id, vault_path, fixture=None, skip_refresh=False):
    with store.connect() as c:
        case, entries, existing = _read(c, case_id)
        if existing:
            return status(store, case_id)
        require(_finished(entries), "Finish and seal the research trajectory before revealing prices.")
        revision = len(entries)
    vault = _vault(store, vault_path)
    with vault.connect() as c:
        target = Store.artifact(c, case["target_id"], "market_target")
        require(target["case_id"] == case_id and digest(target) == case["target_sha256"], "Frozen target commitment mismatch.", "integrity_error")
    followup, error = None, None
    require(not (skip_refresh and fixture is not None), "Cannot supply a snapshot and skip refresh.")
    if skip_refresh:
        error = "Follow-up quote intentionally not fetched. Opening target remains the scoring reference."
    else:
        try:
            followup = _snapshot(case["specification"], fixture)
            require(time(followup["captured_at"]) >= time(_finished(entries)["recorded_at"]), "Follow-up snapshot precedes finish.")
        except (Error, OSError, ValueError, KeyError, TypeError) as exc:
            if fixture is not None:
                raise
            error = "Follow-up unavailable: " + str(exc)
    result = {"case_id": case_id, "revealed_at": now(), "baseline": target["baseline"],
              "followup": followup, "followup_error": error,
              "comparison": _comparison(case, entries, target, followup, error)}
    with store.connect(True) as c:
        _, current, existing = _read(c, case_id)
        require(existing is None and len(current) == revision, "Case changed during reveal; retry.", "version_conflict")
        Store.put(c, "workbench_reveal", result)
    return status(store, case_id)


def status(store, case_id):
    with store.connect() as c:
        case, entries, revealed = _read(c, case_id)
        evidence, models = {}, {}
        for e in entries:
            for manifest in ("evidence_manifest", "model_manifest", "trajectory_manifest"):
                for artifact_id, expected in e.get(manifest, {}).items():
                    require(digest(Store.artifact(c, artifact_id)) == expected, "Research input integrity failure.", "integrity_error")
            for ref in e["payload"].get("evidence_refs", []):
                packet = Store.artifact(c, ref["packet_id"], "packet")
                record = next(r for r in packet["records"] if r["id"] == ref["record_id"])
                evidence[ref["packet_id"] + ":" + ref["record_id"]] = record
            for artifact_id in e.get("model_manifest", {}):
                models[artifact_id] = Store.artifact(c, artifact_id)
    finished = _finished(entries)
    pending = _pending(entries)
    state = "revealed" if revealed else "sealed" if finished else "researching" if entries else "awaiting_initial"
    result = {"case_id": case_id, "state": state, "revision": len(entries), **case, "journal": entries,
              "evidence": evidence, "models": models,
              "next_action": "reflection" if revealed else "reveal" if finished else "checkpoint" if pending else "plan_or_finish" if any(e["kind"] == "initial" for e in entries) else "initial"}
    if revealed:
        # Late disclosure must not leave a stale 'eligible' flag on the frozen reveal.
        result["comparison"] = _comparison(case, entries, {"baseline": revealed["baseline"]}, revealed["followup"], revealed["followup_error"])
        result["revealed_at"] = revealed["revealed_at"]
    return result


def export_case(store, case_id, path):
    result = status(store, case_id)
    require(result["state"] != "revealed", "A revealed case cannot be exported as a fresh hidden-target case.")
    result["research_instructions"] = (
        "Research this question using public evidence. Do not seek market prices or numerical outside forecasts of this event. "
        "Record an initial judgment, then declare each research plan before collecting its findings. Import sources with research capture; "
        "use their evidence_refs in each checkpoint. Record exposure immediately. Finish before asking the coordinator to reveal. "
        "This file does not grant database or network isolation; use a fresh context with access only to the research project.")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return {"case_id": case_id, "output": str(output.resolve()), "prices_included": False}


def report(store, case_id, path, format=None, attachments=(), narrative=None):
    from .reports import export
    result = status(store, case_id)
    written = export(result, path, format, attachments, narrative)
    return {"case_id": case_id, **written, "state": result["state"],
            "checkpoints": sum(e["kind"] in ("initial", "checkpoint") for e in result["journal"])}
