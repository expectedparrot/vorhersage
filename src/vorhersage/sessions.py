"""Joint binary elicitation records, lossless imports, and descriptive panels.

These artifacts deliberately do not have kind ``forecast``: a conditional cell
must never enter ordinary realized-outcome scoring by accident.
"""

import math
from statistics import median

from .common import canonical, digest, now, require, time
from .relations import implications, key as question_key
from .schemas import check
from .store import Store
from .workflow import verify_refs


def unique(values, label):
    require(len(set(values)) == len(values), "Duplicate " + label + ".")


def add_condition(store, spec):
    check(spec, "condition")
    require(spec["kind"] != "unconditional" or "binding" not in spec,
            "Unconditional conditions cannot have a binding.")
    with store.connect(True) as c:
        for item in Store.all(c, "condition"):
            old = item["specification"]
            if (old["id"], old["version"]) == (spec["id"], spec["version"]):
                require(canonical(old) == canonical(spec), "Condition version is frozen; use a new version.")
                return {"condition_id": item["id"]}
        id = "condition_" + digest(spec)[:24]
        Store.put(c, "condition", {"specification": spec, "recorded_at": now()}, id=id)
        return {"condition_id": id}


def numeric_key(value):
    return tuple(value[k] for k in ("variable", "unit", "target_at", "vintage"))


def validate_bindings(spec, conditions):
    forecasts = {}
    for f in spec["numeric_forecasts"]:
        k = numeric_key(f)
        require(k not in forecasts, "Duplicate numeric forecast.")
        levels = [q["level"] for q in f["quantiles"]]
        values = [q["value"] for q in f["quantiles"]]
        require(levels == sorted(set(levels)), "Quantile levels must be unique and increasing.")
        require(values == sorted(values), "Quantile values must be nondecreasing.")
        forecasts[k] = dict(zip(levels, values))
    unique([b["condition_id"] for b in spec["bindings"]], "condition bindings")
    bindings = {b["condition_id"]: b["value"] for b in spec["bindings"]}
    required = {id for id, d in conditions.items() if "binding" in d}
    require(set(bindings) == required, "Bindings must exactly match the conditions requiring a value.")
    for id in required:
        b = conditions[id]["binding"]
        quantiles = forecasts.get(numeric_key(b), {})
        require(b["quantile"] in quantiles, "Condition binding requires its matching numeric forecast quantile.")
        require(bindings[id] == quantiles[b["quantile"]], "Condition binding differs from the model's own quantile.")


def _create(c, spec, external=False):
    check(spec, "session")
    require(spec["provenance"]["kind"] == ("external" if external else "native"),
            "External sessions must use session import; native sessions use session start.")
    require(time(spec["information_as_of"]) <= time(now()), "Session information cutoff cannot be in the future.")
    for item in Store.all(c, "joint_session"):
        if item["specification"]["id"] == spec["id"]:
            require(canonical(item["specification"]) == canonical(spec), "Session identity is frozen; use a new ID.")
            return item["id"]
    unique([question_key(q) for q in spec["questions"]], "questions")
    for field in ("condition_ids", "packet_ids", "relation_ids"):
        unique(spec[field], field)
    questions = [Store.question(c, q["question_id"], q["version"]) for q in spec["questions"]]
    for q in questions:
        require((q["specification"]["kind"] == "simulation") == (spec["mode"] == "simulation"),
                "Session and question mode disagree.")
        if spec["mode"] == "prospective":
            cutoff = spec["information_as_of"] if external else now()
            require(time(cutoff) < time(q["specification"]["event_deadline"]), "Prospective event deadline passed.")
    inputs = {}
    conditions = {}
    for id in spec["condition_ids"]:
        artifact = Store.artifact(c, id, "condition")
        inputs[id] = digest(artifact)
        conditions[id] = artifact["specification"]
    require(sum(d["kind"] == "unconditional" for d in conditions.values()) == 1,
            "A session requires exactly one unconditional condition.")
    execution = spec.get("execution")
    if execution:
        require(not external, "Runtime execution contracts belong to native sessions.")
        unique(execution["research"]["domains"], "research domains")
        unique([r["id"] for r in execution["requirements"]], "protocol requirements")
    if not (execution and execution["defer_bindings"] and not spec["numeric_forecasts"] and not spec["bindings"]):
        validate_bindings(spec, conditions)
    for id in spec["packet_ids"]:
        packet = Store.artifact(c, id, "packet")
        require(time(packet["information_as_of"]) <= time(spec["information_as_of"]), "Packet cutoff follows session cutoff.")
        inputs[id] = digest(packet)
    refs = {question_key(q) for q in spec["questions"]}
    for id in spec["relation_ids"]:
        relation = Store.artifact(c, id, "relation")
        require(all(question_key(relation[k]) in refs for k in ("antecedent", "consequent")),
                "Relations must reference question versions in this session.")
        inputs[id] = digest(relation)
    id = "session_" + digest(spec)[:24]
    Store.put(c, "joint_session", {"specification": spec, "recorded_at": now(),
              "questions": [{**q, "sha256": digest(q)} for q in questions],
              "input_manifest": inputs}, id=id)
    return id


def start(store, spec):
    with store.connect(True) as c:
        id = _create(c, spec)
        return _status(c, id)


def _status(c, id):
    from .session_runtime import events as runtime_events, project
    session = Store.artifact(c, id, "joint_session")
    # Explicit revision order, independent of imported source timestamps.
    events = [Store.artifact(c, r["id"]) for r in c.execute(
        "SELECT id FROM artifacts WHERE run_id=? AND kind='joint_submission'", (id,))]
    events.sort(key=lambda e: e["revision"])
    final = c.execute("SELECT id FROM artifacts WHERE run_id=? AND kind='joint_finalization'", (id,)).fetchone()
    final = Store.artifact(c, final["id"]) if final else None
    cells = {}
    usage = {"searches": 0, "model_calls": 0, "cost_usd": 0}
    for event in events:
        for cell in event["cells"]:
            cells[cell_key(cell)] = {**cell, "submission_id": event["id"]}
        for field in usage:
            usage[field] += event["usage"][field]
    history = runtime_events(c, id)
    runtime = project(session["specification"], history)
    spec = runtime["specification"]
    usage = {k: v + runtime["attempt_usage"][k] for k, v in usage.items()}
    expected = {(q["question_id"], q["version"], condition)
                for q in spec["questions"] for condition in spec["condition_ids"]}
    return {**runtime, "session_id": id, "specification": spec, "registered_specification": session["specification"],
            "events": history, "recorded_at": session["recorded_at"],
            "revision": len(events) + len(history) + int(final is not None),
            "disposition": "finalized" if final else runtime["execution_disposition"],
            "expected_cells": len(expected), "cells": [cells[k] for k in sorted(cells)],
            "missing_cells": [dict(zip(("question_id", "version", "condition_id"), k)) for k in sorted(expected - cells.keys())],
            "usage": usage, "submissions": events, "finalization": final}


def status(store, id):
    with store.connect() as c:
        return _status(c, id)


def cell_key(cell):
    return cell["question_id"], cell["version"], cell["condition_id"]


def _append(c, id, spec, submitted_at, external=False):
    state = _status(c, id)
    session = state["specification"]
    require(session["provenance"]["kind"] == ("external" if external else "native"),
            "Imported sessions cannot accept native submissions.")
    require(state["disposition"] in ("open", "budget_exhausted"), "Session is finalized or not open.")
    require(state["revision"] == spec["expected_revision"], "Stale session revision.", "version_conflict")
    require(time(session["information_as_of"]) <= time(submitted_at) <= time(now()), "Invalid submission timestamp.")
    if state["submissions"]:
        require(time(submitted_at) >= time(state["submissions"][-1]["submitted_at"]), "Submission timestamps must be nondecreasing.")
    unique([cell_key(cell) for cell in spec["cells"]], "cells within submission")
    questions = {question_key(q) for q in session["questions"]}
    if "execution" in session:
        from .session_runtime import research_audit
        require(spec["usage"] == {"searches": 0, "model_calls": 0, "cost_usd": 0}, "Runtime usage belongs to attempts, not cell submissions.")
        require(research_audit(state)["ready"], "Session research requirements are incomplete.")
        conditions = {i: Store.artifact(c, i, "condition")["specification"] for i in session["condition_ids"]}
        validate_bindings(session, conditions)
    for cell in spec["cells"]:
        require(question_key(cell) in questions and cell["condition_id"] in session["condition_ids"],
                "Cell is outside the registered question/condition grid.")
        require(all(r["packet_id"] in session["packet_ids"] for r in cell["evidence_refs"]),
                "Cell evidence must use registered session packets.")
        verify_refs(c, cell["evidence_refs"], session["information_as_of"])
    revision = state["revision"] + 1
    artifact_id = "joint_submission_" + digest({"session_id": id, "revision": revision})[:24]
    body = {"id": artifact_id, "session_id": id, "revision": revision,
            "submitted_at": submitted_at, "recorded_at": now(),
            "cells": spec["cells"], "usage": spec["usage"], "raw_record": spec["raw_record"],
            "available_packet_ids": session["packet_ids"], "information_as_of": session["information_as_of"],
            "bindings": session["bindings"]}
    Store.put(c, "joint_submission", body, id=artifact_id, run_id=id)
    return {"session_id": id, "revision": revision, "submission_id": artifact_id}


def submit(store, id, spec):
    check(spec, "session_submit")
    with store.connect(True) as c:
        scope = id + ":submit"
        retry = Store.receipt(c, scope, spec["idempotency_key"], spec)
        if retry:
            return retry
        result = _append(c, id, spec, now())
        Store.remember(c, scope, spec["idempotency_key"], spec, result)
        return result


def _coherence(c, state):
    spec = state["specification"]
    relations = [{"id": id, **Store.artifact(c, id, "relation")} for id in spec["relation_ids"]]
    paths = implications(relations)
    cells = {cell_key(cell): cell for cell in state["cells"]}
    comparisons, missing = [], []
    for (left, right), path in sorted(paths.items()):
        for condition in spec["condition_ids"]:
            a, b = cells.get((*left, condition)), cells.get((*right, condition))
            item = {"antecedent": list(left), "consequent": list(right), "condition_id": condition, "relation_ids": path}
            if a is None or b is None:
                missing.append(item)
            else:
                comparisons.append({**item, "antecedent_probability": a["probability"],
                                    "consequent_probability": b["probability"],
                                    "antecedent_submission_id": a["submission_id"],
                                    "consequent_submission_id": b["submission_id"],
                                    "violation": a["probability"] > b["probability"] + 1e-12})
    return {"session_id": state["session_id"], "revision": state["revision"], "comparisons": comparisons,
            "violations": [r for r in comparisons if r["violation"]], "missing_comparisons": missing,
            "limitations": ["Only registered implications within each condition are checked, including transitive paths.",
                            "Raw probabilities are never repaired; logical relations are supplied by the caller."]}


def coherence(store, id):
    with store.connect() as c:
        return _coherence(c, _status(c, id))


def _finalize(c, id, spec, finalized_at, external=False):
    state = _status(c, id)
    session = state["specification"]
    require(session["provenance"]["kind"] == ("external" if external else "native"),
            "Imported sessions must finalize through import.")
    require(state["disposition"] in ("open", "budget_exhausted"), "Session is finalized or not open.")
    require(state["revision"] == spec["expected_revision"], "Stale session revision.", "version_conflict")
    require(not state["missing_cells"], "Cannot finalize an incomplete session.")
    require(time(state["submissions"][-1]["submitted_at"]) <= time(finalized_at) <= time(now()), "Invalid finalization timestamp.")
    if session["mode"] == "prospective":
        for q in session["questions"]:
            question = Store.question(c, q["question_id"], q["version"])["specification"]
            require(time(finalized_at) < time(question["event_deadline"]), "Prospective finalization follows event deadline.")
            if not external:
                known = [r for r in Store.all(c, "resolution") if
                         (r["question_id"], r["question_version"]) == question_key(q)]
                require(not known, "Question already has a resolution; use a retrospective session.")
    from .session_runtime import audit_state, research_audit
    if "execution" in session:
        require(not state["unknown_usage_attempts"], "Unknown attempt usage must be reconciled before finalization.")
        require(research_audit(state)["ready"], "Session research requirements are incomplete.")
        started = {a["request"].get("tool_request", {}).get("request_id") for a in state["attempts"].values()}
        require(all(r["request_id"] in started for r in state["tool_requests"]), "Pending tool requests prevent finalization.")
    inputs = [id, *[e["id"] for e in state["submissions"]], *[e["id"] for e in state["events"]]]
    artifact_id = "joint_finalization_" + digest(id)[:24]
    body = {"id": artifact_id, "session_id": id, "revision": state["revision"] + 1,
            "finalized_at": finalized_at, "recorded_at": now(), "rationale": spec["rationale"],
            "cells": state["cells"], "usage": state["usage"], "coherence": _coherence(c, state),
            "input_manifest": {i: digest(Store.artifact(c, i)) for i in inputs},
            "ordinary_evaluation_eligible": False,
            "timestamp_basis": "source_reported" if external else "locally_recorded",
            "effective_specification": session, "protocol_audit": audit_state({**state, "disposition": "finalized"})}
    Store.put(c, "joint_finalization", body, id=artifact_id, run_id=id)
    return {"session_id": id, "revision": body["revision"], "finalization_id": artifact_id,
            "disposition": "finalized", "cells": len(state["cells"]), "usage": state["usage"]}


def finalize(store, id, spec):
    check(spec, "session_finalize")
    with store.connect(True) as c:
        scope = id + ":finalize"
        retry = Store.receipt(c, scope, spec["idempotency_key"], spec)
        if retry:
            return retry
        result = _finalize(c, id, spec, now())
        Store.remember(c, scope, spec["idempotency_key"], spec, result)
        return result


def import_session(store, bundle):
    """Import an entire external session atomically, preserving the source record."""
    check(bundle, "session_import")
    with store.connect(True) as c:
        scope = "session_import"
        identity = bundle["session"]["id"]
        retry = Store.receipt(c, scope, identity, bundle)
        if retry:
            return retry
        id = _create(c, bundle["session"], external=True)
        for revision, record in enumerate(bundle["submissions"]):
            _append(c, id, {**record, "expected_revision": revision}, record["submitted_at"], external=True)
        result = _finalize(c, id, {"expected_revision": len(bundle["submissions"]), "rationale": bundle["rationale"]},
                           bundle["finalized_at"], external=True)
        import_id = "joint_import_" + digest(bundle)[:24]
        Store.put(c, "joint_import", {"bundle": bundle, "recorded_at": now(),
                  "input_manifest": {result["finalization_id"]: digest(Store.artifact(c, result["finalization_id"]))}},
                  id=import_id, run_id=id)
        result["import_id"] = import_id
        Store.remember(c, scope, identity, bundle, result)
        return result


def safe_exp(value):
    try:
        result = math.exp(value)
    except OverflowError:
        return None
    return result if result > 0 else None


def aggregate(store, spec):
    check(spec, "session_aggregation")
    unique(spec["session_ids"], "session IDs")
    unique(spec["expected_forecasters"], "expected forecasters")
    with store.connect(True) as c:
        states = [_status(c, id) for id in spec["session_ids"]]
        require(all(s["finalization"] is not None for s in states), "Only finalized sessions can be aggregated.")
        first = states[0]["specification"]
        for state in states:
            other = state["specification"]
            require(all(other[k] == first[k] for k in ("wave", "protocol", "repetition", "mode")),
                    "Panel sessions must share wave, protocol, repetition, and mode.")
            require({question_key(q) for q in other["questions"]} == {question_key(q) for q in first["questions"]}
                    and set(other["condition_ids"]) == set(first["condition_ids"]),
                    "Panel sessions must share exact question and condition versions.")
        members = [s["specification"]["forecaster"] for s in states]
        unique(members, "forecasters; select one session per forecaster")
        require(set(members) <= set(spec["expected_forecasters"]), "Unexpected panel forecaster.")
        missing = sorted(set(spec["expected_forecasters"]) - set(members))
        definitions = {i: Store.artifact(c, i, "condition")["specification"] for i in first["condition_ids"]}
        baseline = spec.get("baseline_condition_id", next(i for i, d in definitions.items() if d["kind"] == "unconditional"))
        require(baseline in definitions, "Baseline condition is outside the session grid.")
        cell_maps = {s["session_id"]: {cell_key(cell): cell for cell in s["cells"]} for s in states}
        rows = []
        for q in first["questions"]:
            for condition in first["condition_ids"]:
                estimates, logs, values = [], [], []
                for state in states:
                    cells = cell_maps[state["session_id"]]
                    cell = cells[(*question_key(q), condition)]
                    base = cells[(*question_key(q), baseline)]
                    p, b = cell["probability"], base["probability"]
                    log_ratio = None if b == 0 else (-math.inf if p == 0 else math.log(p) - math.log(b))
                    ratio = None if log_ratio is None else (0.0 if p == 0 else safe_exp(log_ratio))
                    logs.append(log_ratio)
                    values.append(p)
                    bindings = {x["condition_id"]: x["value"] for x in state["specification"]["bindings"]}
                    estimates.append({"session_id": state["session_id"], "forecaster": state["specification"]["forecaster"],
                                      "probability": p, "baseline_probability": b, "ratio": ratio,
                                      "ratio_status": "zero_denominator" if b == 0 else ("unrepresentable_ratio" if ratio is None else "defined"),
                                      "condition_value": bindings.get(condition), "baseline_condition_value": bindings.get(baseline),
                                      "submission_id": cell["submission_id"], "baseline_submission_id": base["submission_id"]})
                reason = "incomplete_panel" if missing else ("zero_denominator" if None in logs else "defined")
                multiplier = None
                if reason == "defined":
                    middle = median(logs)
                    multiplier = 0.0 if middle == -math.inf else safe_exp(middle)
                    if multiplier is None:
                        reason = "unrepresentable_multiplier"
                rows.append({**q, "condition_id": condition, "median_probability": None if missing else median(values),
                             "multiplier": multiplier, "multiplier_status": reason, "members": estimates})
        inputs = [s["finalization"]["id"] for s in states]
        body = {"policy": spec, "baseline_condition_id": baseline, "conditions": definitions,
                "missing_forecasters": missing, "complete_panel": not missing, "rows": rows,
                "sessions": [{"session_id": s["session_id"], "forecaster": s["specification"]["forecaster"],
                              "information_as_of": s["specification"]["information_as_of"],
                              "finalized_at": s["finalization"]["finalized_at"], "usage": s["usage"],
                              "bindings": s["specification"]["bindings"]} for s in states],
                "usage": {k: math.fsum(s["usage"][k] for s in states) for k in ("searches", "model_calls", "cost_usd")},
                "same_information_cutoff": len({time(s["specification"]["information_as_of"]) for s in states}) == 1,
                "input_manifest": {i: digest(Store.artifact(c, i)) for i in inputs}, "created_at": now(),
                "limitations": ["Descriptive medians, not accuracy or causal-effect estimates.",
                                "Ratios pair each condition with the same session's baseline; no clipping or imputation.",
                                "Bound conditions may represent different numeric values across models.",
                                "Usage is reported once per session, including superseded submissions."]}
        id = Store.put(c, "joint_aggregation", body)
        return {"aggregation_id": id, **body}
