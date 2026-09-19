"""Declared milestone schedules and finite joint scenarios, with immutable versions."""

import copy
import math
from datetime import timedelta

from .common import Error, digest, now, require, time
from .schemas import check
from .store import Store

ENGINE_VERSION = "timeline.v1"
LIMITATIONS = [
    "Dates, durations, dependencies and scenario weights are supplied, not inferred from evidence.",
    "Each scenario is one joint assignment. No independent sampling or equal weighting is implicit.",
    "Unweighted scenario counts are not probabilities. Weighted scenarios require a declared exhaustive partition.",
    "Durations are elapsed days of 86400 seconds. Resource contention and working-day calendars are not modeled.",
    "schedule_as_of anchors start/remaining-duration calculations; a later evidence cutoff does not move that reference date.",
    "Sensitivity is a declared-input stress test, not a confidence interval or an estimate of research value.",
]


def _unique(rows, field, label):
    result = {r[field]: r for r in rows}
    require(len(result) == len(rows), "Duplicate " + label + ".")
    return result


def validate(spec):
    check(spec, "timeline_model")
    require(len(spec["nodes"]) <= 100 and len(spec["parameters"]) <= 100 and len(spec["scenarios"]) <= 500,
            "Timeline limits: 100 nodes, 100 parameters, 500 scenarios.")
    as_of = time(spec["information_as_of"])
    require(time(spec.get("schedule_as_of", spec["information_as_of"])) <= as_of,
            "Schedule reference date cannot follow the evidence cutoff.")
    require(as_of < time(spec["deadline"]), "Timeline cutoff must precede its deadline.")
    params = _unique(spec["parameters"], "id", "parameter ID")
    nodes = _unique(spec["nodes"], "id", "node ID")
    _unique(spec["scenarios"], "id", "scenario ID")
    require(spec["target"] in nodes, "Unknown target milestone.")
    used = set()
    for n in nodes.values():
        parents = n["parents"]
        require(len(set(parents)) == len(parents) and set(parents) <= nodes.keys(), "Duplicate or unknown milestone prerequisite.")
        require(n["id"] not in parents, "Timeline contains a cycle.")
        kind, state = n["kind"], n["state"]
        require(kind != "event" or not parents, "Calendar events cannot have prerequisites; use a task or join.")
        require(kind not in ("all", "any") or bool(parents), "Join milestones require prerequisites.")
        require(kind == "task" or state != "in_progress", "Only tasks can be in progress.")
        require(kind == "task" or "not_before" not in n, "Only tasks have earliest-start dates.")
        if state == "completed":
            require("completed_at" in n and "parameter_id" not in n and "started_at" not in n,
                    "Completed milestones need an observed date, without a duration/date parameter or start field.")
            require(time(n["completed_at"]) <= as_of and n["evidence_refs"], "Completed milestones need evidence dated by the cutoff.")
            require("not_before" not in n or time(n["not_before"]) <= time(n["completed_at"]),
                    "Completion precedes earliest start.")
        else:
            require("completed_at" not in n, "Only completed milestones have completion observations.")
            if kind in ("event", "task"):
                pid = n.get("parameter_id")
                require(pid in params, "Event/task needs a known parameter_id.")
                require(params[pid]["kind"] == ("date" if kind == "event" else "duration_days"), "Milestone parameter has the wrong type.")
                used.add(pid)
            else:
                require("parameter_id" not in n, "Joins compute dates without parameters.")
        if state == "in_progress":
            require("started_at" in n and time(n["started_at"]) <= as_of, "In-progress task needs an actual start by the cutoff.")
            require(time(n["started_at"]) <= time(spec.get("schedule_as_of", spec["information_as_of"])),
                    "In-progress duration is remaining work at schedule_as_of; revise the schedule reference date for a later start.")
            require(n["evidence_refs"], "In-progress task needs evidence of its start.")
            require("not_before" not in n or time(n["not_before"]) <= time(n["started_at"]), "Observed start precedes earliest start.")
        else:
            require("started_at" not in n, "Only in-progress tasks have start observations.")
    require(used == params.keys(), "Every parameter must be used by an unfinished milestone.")
    order, pending = [], set(nodes)
    while pending:
        ready = sorted(id for id in pending if set(nodes[id]["parents"]) <= set(order))
        require(ready, "Timeline contains a cycle.")
        order.extend(ready)
        pending.difference_update(ready)
    ancestors, todo = set(), [spec["target"]]
    while todo:
        id = todo.pop()
        if id not in ancestors:
            ancestors.add(id)
            todo.extend(nodes[id]["parents"])
    require(ancestors == nodes.keys(), "Every milestone must contribute to the target; remove disconnected work.")
    weighted = ["weight" in s for s in spec["scenarios"]]
    require(all(weighted) or not any(weighted), "Supply all scenario weights or none; partial weights are invalid.")
    if all(weighted):
        require(math.isclose(math.fsum(s["weight"] for s in spec["scenarios"]), 1, abs_tol=1e-12, rel_tol=0),
                "Scenario weights must sum to one; no normalization is implicit.")
        require(spec.get("partition_justification") and all(s.get("weight_rationale") for s in spec["scenarios"]),
                "Weighted scenarios need a partition justification and individual weight rationales.")
    validate_assessments(params, spec["scenarios"], as_of)
    # Observed parameter values describe facts shared by every scenario.
    for pid in params:
        assignments = [next((a for a in s["assessments"] if a["parameter_id"] == pid), None) for s in spec["scenarios"]]
        observed = [a for a in assignments if a and a["basis"] == "observed"]
        if observed:
            require(all(a and a["basis"] == "observed" and a["value"] == observed[0]["value"] for a in assignments),
                    "Observed parameters must agree across every scenario.")
    return nodes, params, order


def validate_assessments(params, scenarios, as_of):
    """Validate individual inputs, also while authoring incomplete scenario sets."""
    for s in scenarios:
        assessments = _unique(s["assessments"], "parameter_id", "scenario parameter assessment")
        require(assessments.keys() <= params.keys(), "Assessment references an unknown parameter.")
        for pid, a in assessments.items():
            if a["basis"] == "unresolved":
                require("value" not in a, "Unresolved assessments cannot supply values; unknown is different from never.")
                continue
            require("value" in a, "Resolved parameter assessment needs a value.")
            value = a["value"]
            if a["basis"] in ("observed", "estimated"):
                require(a["evidence_refs"], "Observed/estimated parameters need evidence; otherwise label them assumed.")
            require(a["basis"] != "observed" or value != "never", "Never completing cannot be an observed future outcome.")
            if value != "never":
                if params[pid]["kind"] == "date":
                    parsed = time(value)
                    if a["basis"] == "observed":
                        require(parsed <= as_of, "Observed event date is after the information cutoff.")
                else:
                    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 365250,
                            "Duration must be 0..365250 elapsed days, or never.")


def _schedule(spec, scenario, nodes, order):
    values = {a["parameter_id"]: a for a in scenario["assessments"]}
    rows, dates = {}, {}
    as_of = time(spec.get("schedule_as_of", spec["information_as_of"]))
    for id in order:
        n = nodes[id]
        parents = n["parents"]
        parent_dates = [dates[p] for p in parents]
        parent_states = [rows[p]["status"] for p in parents]
        join_any = n["kind"] == "any"
        if join_any:
            finite = [d for d in parent_dates if d is not None]
            status = "unresolved" if "unresolved" in parent_states else "finite" if finite else "never"
            ready_at = min(finite) if finite else as_of
        else:
            status = "never" if "never" in parent_states else "unresolved" if "unresolved" in parent_states else "finite"
            ready_at = max((d for d in parent_dates if d is not None), default=as_of)
        start = finish = None
        controlling = []
        if n["state"] in ("completed", "in_progress"):
            observed = time(n["completed_at"] if n["state"] == "completed" else n["started_at"])
            require(status == "finite" and (not parents or ready_at <= observed),
                    f"Scenario {scenario['id']}: observed {id} contradicts its prerequisites.")
        if n["state"] == "completed":
            finish, status = time(n["completed_at"]), "finite"
        elif status == "finite":
            if parents:
                controlling = [p for p in parents if dates[p] == ready_at]
            if n["kind"] in ("all", "any"):
                finish = ready_at
            else:
                a = values.get(n["parameter_id"])
                if a is None or a["basis"] == "unresolved":
                    status = "unresolved"
                elif a["value"] == "never":
                    status = "never"
                elif n["kind"] == "event":
                    finish = time(a["value"])
                else:
                    # In-progress task parameters explicitly mean remaining days at as_of.
                    start = as_of if n["state"] == "in_progress" else max(as_of, ready_at, time(n.get("not_before", spec["information_as_of"])))
                    if not parents or start > ready_at:
                        controlling = []
                    try:
                        finish = start + timedelta(days=a["value"])
                    except OverflowError as exc:
                        raise Error("invalid_input", "Timeline date exceeds the supported calendar.") from exc
        dates[id] = finish
        rows[id] = {"node_id": id, "status": status, "start_at": start.isoformat() if start else None,
                    "finish_at": finish.isoformat() if finish else None, "controlling_parents": controlling,
                    "duration_semantics": "remaining_at_cutoff" if n["state"] == "in_progress" else "after_prerequisites" if n["kind"] == "task" else None}
    target = rows[spec["target"]]
    finish = dates[spec["target"]]
    meets = None if target["status"] == "unresolved" else False if finish is None else (
        finish < time(spec["deadline"]) if spec["deadline_rule"] == "before" else finish <= time(spec["deadline"]))
    path, todo = set(), [spec["target"]]
    while todo:
        id = todo.pop()
        if id not in path:
            path.add(id)
            todo.extend(rows[id]["controlling_parents"])
    return {"scenario_id": scenario["id"], "description": scenario["description"],
            "weight": scenario.get("weight"), "status": target["status"], "launch_at": target["finish_at"],
            "meets_deadline": meets, "controlling_milestones": [id for id in order if id in path],
            "schedule": [rows[id] for id in order]}


def gaps(spec):
    nodes, params, _ = validate(spec)
    missing, assumptions = [], []
    for s in spec["scenarios"]:
        assigned = {a["parameter_id"]: a for a in s["assessments"]}
        for pid, p in params.items():
            a = assigned.get(pid)
            row = {"scenario_id": s["id"], "parameter_id": pid, "description": p["description"],
                   "affected_milestones": [n["id"] for n in nodes.values() if n.get("parameter_id") == pid],
                   "research_task": "Determine " + p["description"], "rationale": a["rationale"] if a else "No assessment supplied."}
            if a is None or a["basis"] == "unresolved":
                missing.append(row)
            elif a["basis"] == "assumed":
                assumptions.append(row)
    return {"unresolved": missing, "assumed_inputs": assumptions,
            "unweighted": "weight" not in spec["scenarios"][0],
            "structural_assumptions": [{"node_id": n["id"], "parents": n["parents"], "rationale": n["rationale"],
                                        "evidence_refs": n["evidence_refs"]} for n in nodes.values()],
            "note": "A complete declaration is not proof of adequate evidence or a correct dependency structure."}


def analyze(spec):
    nodes, _, order = validate(spec)
    rows = [_schedule(spec, s, nodes, order) for s in spec["scenarios"]]
    weighted = "weight" in spec["scenarios"][0]
    unresolved = any(r["meets_deadline"] is None for r in rows)
    p = math.fsum(r["weight"] for r in rows if r["meets_deadline"]) if weighted and not unresolved else None
    bounds = None
    if weighted:
        low = math.fsum(r["weight"] for r in rows if r["meets_deadline"] is True)
        bounds = [low, low + math.fsum(r["weight"] for r in rows if r["meets_deadline"] is None)]
    return {"engine_version": ENGINE_VERSION, "model_sha256": digest(spec), "question": spec["question"],
            "information_as_of": spec["information_as_of"], "schedule_as_of": spec.get("schedule_as_of", spec["information_as_of"]),
            "deadline": spec["deadline"], "deadline_rule": spec["deadline_rule"],
            "probability": p, "probability_bounds": bounds,
            "disposition": "incomplete" if unresolved else "weighted" if weighted else "unweighted",
            "scenarios": rows, "gaps": gaps(spec), "limitations": LIMITATIONS + spec["limitations"]}


def sensitivity(spec):
    """Swap one input through its declared scenario values, without reweighting."""
    base = analyze(spec)
    params = {p["id"]: p for p in spec["parameters"]}
    require(len(params) * len(spec["scenarios"]) ** 2 <= 20000,
            "Sensitivity exceeds 20000 assignments; analyze a smaller declared scenario set.")
    choices = {pid: {} for pid in params}
    for s in spec["scenarios"]:
        for a in s["assessments"]:
            if a["basis"] not in ("unresolved", "observed"):
                choices[a["parameter_id"]][str(a["value"])] = a["value"]
    rows = []
    nodes, _, order = validate(spec)
    for scenario, original in zip(spec["scenarios"], base["scenarios"]):
        assigned = {a["parameter_id"]: a for a in scenario["assessments"]}
        for pid in params:
            if assigned.get(pid, {}).get("basis") == "observed":
                continue
            for value in choices[pid].values():
                if assigned.get(pid, {}).get("value") == value:
                    continue
                modified = copy.deepcopy(scenario)
                modified["assessments"] = [a for a in modified["assessments"] if a["parameter_id"] != pid]
                modified["assessments"].append({"parameter_id": pid, "basis": "assumed", "value": value, "evidence_refs": [], "rationale": "Sensitivity substitution."})
                try:
                    result = _schedule(spec, modified, nodes, order)
                    row = {"scenario_id": scenario["id"], "parameter_id": pid, "value": value,
                           "launch_at": result["launch_at"], "meets_deadline": result["meets_deadline"],
                           "changes_outcome": original["meets_deadline"] is not None and result["meets_deadline"] is not None and original["meets_deadline"] != result["meets_deadline"]}
                except Error as exc:
                    row = {"scenario_id": scenario["id"], "parameter_id": pid, "value": value,
                           "invalid_combination": str(exc), "changes_outcome": False}
                rows.append(row)
    return {"substitutions": sorted(rows, key=lambda r: not r["changes_outcome"]),
            "note": "One-input substitutions may break scenario dependence; they are stress tests, never new probability samples. Inconsistent observations are flagged."}


def read(c, model_id):
    body = Store.artifact(c, model_id, "timeline_model")
    for id, sha in body["input_manifest"].items():
        require(digest(Store.artifact(c, id)) == sha, "Timeline input integrity check failed.", "integrity_error")
    q = body["specification"]["question"]
    require(digest(Store.question(c, q["question_id"], q["version"])) == body["question_sha256"],
            "Timeline question integrity check failed.", "integrity_error")
    return body


def resolve(c, reference):
    """Resolve an artifact ID or an explicit name@version; never choose latest."""
    row = c.execute("SELECT id FROM artifacts WHERE id=? AND kind='timeline_model'", (reference,)).fetchone()
    if row:
        read(c, row["id"])
        return row["id"]
    name, separator, version = reference.rpartition("@")
    require(separator and name and version.isdecimal() and int(version) > 0,
            "Use a timeline artifact ID or a versioned name, such as waymo@1.", "invalid_reference")
    matches = [r["id"] for r in Store.all(c, "timeline_model")
               if r["specification"]["id"] == name and r["specification"]["version"] == int(version)]
    require(len(matches) == 1, "Unknown timeline model: " + reference, "not_found")
    read(c, matches[0])
    return matches[0]


def shift(store, reference, parameter_id, days, name, rationale):
    """Save a duration stress test as a new family pinned to its source artifact.

    Shift every finite scenario assignment by the same number of elapsed days.
    Unknowns and observations require research or an explicit model edit, so this
    shortcut rejects them. A 'never' assignment remains a failure to complete.
    Validation and registration share one transaction: invalid variants leave no
    partial model or event behind.
    """
    require(type(days) in (int, float) and math.isfinite(days) and days != 0,
            "Supply a finite, nonzero number of elapsed days.")
    require(isinstance(rationale, str) and rationale.strip(), "Explain the duration change with --rationale.")
    require(isinstance(name, str) and name.strip(), "Supply a name for the alternative model.")
    with store.connect(True) as c:
        source_id = resolve(c, reference)
        spec = copy.deepcopy(read(c, source_id)["specification"])
        require(name != spec["id"], "Use a new model name for the alternative.")
        parameter = next((p for p in spec["parameters"] if p["id"] == parameter_id), None)
        require(parameter is not None, "Unknown parameter: " + parameter_id)
        require(parameter["kind"] == "duration_days", "Only duration parameters can be shifted.")
        changed = 0
        for scenario in spec["scenarios"]:
            term = next((a for a in scenario["assessments"] if a["parameter_id"] == parameter_id), None)
            require(term is not None and term["basis"] != "unresolved",
                    "Cannot shift an unresolved duration in scenario " + scenario["id"] + ".")
            require(term["basis"] != "observed", "Cannot shift an observed duration in scenario " + scenario["id"] + ".")
            if term["value"] == "never":
                continue
            original = term["value"]
            term.update(value=original + days, basis="assumed",
                        rationale=f"Sensitivity assumption: {original:g} {days:+g} elapsed days. {rationale} "
                                  f"Original rationale: {term['rationale']}")
            changed += 1
        require(changed > 0, "No finite duration assignments to shift.")
        spec.update(id=name, version=1, derived_from_model_id=source_id,
                    description=f"{parameter_id} {days:+g} elapsed days: {rationale}")
        spec.pop("previous_model_id", None)
        spec["limitations"].append("Duration sensitivity assumption; scenario weights and other inputs are unchanged. "
                                   "This is not new evidence or a confidence interval.")
        model_id = _add(c, spec)
        return {"timeline_model_id": model_id, **read(c, model_id)}


def _add(c, spec):
    # Imported lazily to keep the pure arithmetic usable without a workflow cycle.
    from .workflow import evidence_refs, verify_refs
    analyze(spec)
    require(time(spec["information_as_of"]) <= time(now()), "Timeline information cutoff cannot be in the future.")
    q = Store.question(c, spec["question"]["question_id"], spec["question"]["version"])
    require(time(spec["deadline"]) == time(q["specification"]["event_deadline"]), "Timeline deadline differs from its question version.")
    versions = [r for r in Store.all(c, "timeline_model") if r["specification"]["id"] == spec["id"]]
    for old in versions:
        if old["specification"]["version"] == spec["version"]:
            require(digest(old["specification"]) == digest(spec), "Timeline version is frozen; increment version.", "version_conflict")
            read(c, old["id"])
            return old["id"]
    previous = max(versions, key=lambda r: r["specification"]["version"]) if versions else None
    require(spec["version"] == (previous["specification"]["version"] + 1 if previous else 1), "Timeline versions must be consecutive.", "version_conflict")
    require(spec.get("previous_model_id") == (previous["id"] if previous else None), "Timeline revision must reference the latest model.", "version_conflict")
    if previous:
        old = previous["specification"]
        require(old["question"] == spec["question"] and old["deadline_rule"] == spec["deadline_rule"],
                "Timeline revisions must retain the question and deadline rule.")
        require(time(old["information_as_of"]) <= time(spec["information_as_of"]), "Timeline revision cannot move the information cutoff backward.")
        require(old.get("derived_from_model_id") == spec.get("derived_from_model_id"), "Timeline lineage cannot change within a version family.")
    origin = spec.get("derived_from_model_id")
    if origin:
        source = read(c, origin)["specification"]
        require(source["question"] == spec["question"] and source["deadline_rule"] == spec["deadline_rule"],
                "Derived timeline must retain its source question and deadline rule.")
        require(time(source["information_as_of"]) <= time(spec["information_as_of"]), "Derived timeline cutoff precedes its source.")
    refs = evidence_refs(spec)
    verify_refs(c, refs, spec["information_as_of"])
    ids = {r["packet_id"] for r in refs}
    if previous:
        ids.add(previous["id"])
    if origin:
        ids.add(origin)
    body = {"specification": spec, "registered_at": now(), "question_sha256": digest(q),
            "input_manifest": {id: digest(Store.artifact(c, id)) for id in sorted(ids)}}
    model_id = Store.put(c, "timeline_model", body)
    Store.event(c, "timeline.add", {"timeline_model_id": model_id, "specification_id": spec["id"], "version": spec["version"]})
    return model_id


def add(store, spec):
    with store.connect(True) as c:
        id = _add(c, spec)
        return {"timeline_model_id": id, **read(c, id)}


def compare_specs(left, right):
    for key in ("question", "deadline_rule"):
        require(left[key] == right[key], "Timeline comparison needs the same question and deadline rule.")
    for key in ("deadline", "information_as_of"):
        require(time(left[key]) == time(right[key]), "Timeline comparison needs a common deadline and information cutoff.")
    a, b = analyze(left), analyze(right)
    lrows = {r["scenario_id"]: r for r in a["scenarios"]}
    rrows = {r["scenario_id"]: r for r in b["scenarios"]}
    matched = []
    for id in sorted(lrows.keys() & rrows.keys()):
        l, r = lrows[id], rrows[id]
        matched.append({"scenario_id": id, "left_launch_at": l["launch_at"], "right_launch_at": r["launch_at"],
                        "left_meets_deadline": l["meets_deadline"], "right_meets_deadline": r["meets_deadline"],
                        "changes_outcome": l["meets_deadline"] is not None and r["meets_deadline"] is not None and l["meets_deadline"] != r["meets_deadline"]})
    return {"left": a, "right": b, "matched_scenarios": matched,
            "unmatched_left": sorted(lrows.keys() - rrows.keys()), "unmatched_right": sorted(rrows.keys() - lrows.keys()),
            "changed_fields": [k for k in ("nodes", "parameters", "scenarios", "partition_justification") if left.get(k) != right.get(k)],
            "note": "Scenario IDs provide matching labels, not proof of equal assumptions; inspect changed fields and declarations."}


def compare(store, left_id, right_id):
    with store.connect() as c:
        left, right = read(c, left_id), read(c, right_id)
    return {"left_model_id": left_id, "right_model_id": right_id,
            **compare_specs(left["specification"], right["specification"])}
