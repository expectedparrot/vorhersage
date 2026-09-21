"""Widening searches and imperfect analogies, separate from empirical estimators."""

from .common import require, time
from .store import Store


def enabled(run):
    return run.get("reference_policy") == "widening_v1"


def validate_classes(classes, state, existing=()):
    ids = [row["id"] for row in classes]
    require(len(ids) == len(set(ids)) and not set(ids) & set(existing), "Reference class IDs must be unique.")
    inputs = {row["id"] for row in state.get("research_plan", {}).get("inputs", [])}
    for row in classes:
        if inputs:
            require(set(row["target_input_ids"]) <= inputs, "Reference classes must target declared intake inputs.")


def design(payload, run, state):
    require("classes" in payload and "search_allocation" in payload,
            "Widening research needs classes and a search_allocation.")
    validate_classes(payload["classes"], state)
    distances = {row["distance"] for row in payload["classes"]}
    require("close" in distances and distances & {"nearby", "mechanism"},
            "Plan a close class and at least one nearby or shared-mechanism class.")
    require(sum(payload["search_allocation"].values()) <= run["max_searches"] - state["used_searches"],
            "Search allocation exceeds the remaining budget; reduce it or extend the run budget.")
    state["reference_classes"] = {row["id"]: row for row in payload["classes"]}
    state["reference_searches"] = []


def record_search(c, payload, run, state, selected):
    require(payload["class_id"] == selected["class_id"], "Search must address the selected reference class.")
    require(payload["status"] != "searched" or payload["searches"],
            "A searched class needs recorded queries and retrievals or captured search evidence.")
    if payload["status"] != "searched":
        require(payload["limitations"], "Unfinished searches need an explicit limitation.")
    if payload["status"] == "budget_exhausted":
        require(state["used_searches"] >= run["max_searches"], "Search budget is not exhausted.")
    for search in payload["searches"]:
        require(search["retrieval_ids"] or search["evidence_refs"],
                "Link saved retrievals or captured search evidence, including unsuccessful searches.")
        for rid in search["retrieval_ids"]:
            saved = Store.artifact(c, rid, "research")
            require(saved["operation"] == "search" and saved["request"]["body"]["query"] == search["query"],
                    "Reference search query must match its saved retrieval.")
            observed = saved.get("snapshot_as_of") or saved["retrieved_at"]
            require(time(observed) <= time(run["information_as_of"]), "Reference retrieval is after the run cutoff.")
            state["artifact_ids"] = list(dict.fromkeys(state["artifact_ids"] + [rid]))
    ids = [row["id"] for row in payload["candidates"]]
    require(len(ids) == len(set(ids)), "Candidate IDs must be unique within a search round.")
    inputs = set(state["reference_classes"][payload["class_id"]]["target_input_ids"])
    for candidate in payload["candidates"]:
        require(set(candidate["target_input_ids"]) <= inputs, "Candidate targets must belong to its class.")
        if candidate["use"] != "excluded":
            require(candidate["evidence_refs"] and candidate["target_input_ids"],
                    "Usable candidates need captured evidence and target input IDs; partial outcomes are allowed.")
        if candidate["use"] == "base_rate":
            require(candidate["outcome_status"] == "verified", "Unverified outcomes are analogies, not base-rate cases.")
    state["reference_searches"].append(payload)
    return {"class_id": payload["class_id"], "status": payload["status"], "candidates": len(ids)}


def analyze(payload, run, state):
    require(payload["status"] != "blocked", "Use a specific reference research status instead of blocked.")
    require("class_results" in payload and "remaining_assumptions" in payload,
            "Assess every searched class and record remaining assumptions.")
    classes = state["reference_classes"]
    results = [row["class_id"] for row in payload["class_results"]]
    require(len(results) == len(set(results)) and set(results) == set(classes),
            "Reference analysis must assess every planned class exactly once.")
    latest = {row["class_id"]: row for row in state["reference_searches"]}
    require(set(latest) == set(classes), "Record a search disposition for every planned class.")
    usable = [case for case in current_candidates(state) if case["use"] != "excluded"]
    if payload["status"] == "no_usable_cases_found":
        require(all(row["status"] == "searched" for row in latest.values()) and not usable,
                "Unsearched classes or useful analogies cannot be reported as no usable cases.")
    if payload["status"] == "partial":
        require(usable, "A partial analysis needs usable cases or input analogies.")
    if payload["status"] == "budget_exhausted":
        require(state["used_searches"] >= run["max_searches"], "Search budget is not exhausted.")
    followups = payload.get("followups", [])
    additions = payload.get("additional_classes", [])
    require((bool(followups) or bool(additions)) == (payload["status"] == "continue_research"),
            "Use continue_research with followups or additional_classes to extend discovery or verify outcomes.")
    validate_classes(additions, state, classes)
    require(all(row["class_id"] in classes for row in followups), "Follow-up names an unknown class.")
    require(len({row["class_id"] for row in followups}) == len(followups), "Duplicate class follow-ups.")
    require(state["extra_tasks"] + len(followups) + len(additions) <= run["max_extra_tasks"],
            "Reference follow-up budget exhausted; extend the ordinary run budget or record incomplete research.")
    state["extra_tasks"] += len(followups) + len(additions)
    classes.update({row["id"]: row for row in additions})
    state.setdefault("reference_analysis_history", []).append(payload)
    return followups, additions


def current_candidates(state):
    """Later findings can revise a candidate without erasing earlier observations."""
    latest = {}
    for search in state.get("reference_searches", []):
        for case in search["candidates"]:
            latest[(search["class_id"], case["id"])] = {"class_id": search["class_id"], **case}
    return list(latest.values())


def summary(state):
    searches = state.get("reference_searches", [])
    candidates = [case for row in searches for case in row["candidates"]]
    return {"design": state.get("reference_class_design"),
            "classes": list(state.get("reference_classes", {}).values()),
            "searches": searches, "candidates": current_candidates(state), "analysis": state.get("reference_class_analysis"),
            "analysis_history": state.get("reference_analysis_history", []),
            "artifact_status": ("verified_empirical_export" if state.get("flyvbjerg_analysis") else
                                "no_verified_empirical_export"),
            "candidate_episode_count": len({row["episode_id"] for row in candidates}),
            "qualification": "Candidates and analogies are not automatically an empirical denominator. "
                             "Partial outcomes remain useful input evidence; missing outcomes are not failures."}


def priorities(state):
    """Surface weak influential inputs; these are research leads, not VOI estimates."""
    sensitivity = state.get("sensitivity") or {}
    swings = {"scenarios/" + row["scenario_id"] + "/probability": row["swing"]
              for row in sensitivity.get("conditional_sensitivity", [])}
    for row in sensitivity.get("weight_transfers", []):
        for sid in (row["from"], row["to"]):
            key = "scenarios/" + sid + "/weight"
            swings[key] = max(swings.get(key, 0), abs(row["probability_change"]))
    result = []
    for support in state.get("parameter_support", []):
        if support["basis"] not in ("assumed", "extrapolated"):
            continue
        path = support["model_input"]
        swing = swings.get(path)
        if swing is None and path == "probability" and sensitivity.get("bounded_range"):
            low, high = sensitivity["bounded_range"]
            swing = high - low
        result.append({"model_input": path, "input_id": support["input_id"], "basis": support["basis"],
                       "target": support["target"], "probability_swing": swing,
                       "transfer_assumptions": support["transfer_assumptions"],
                       "action": "Seek nearby cases or measurements for this input; retain partial evidence and investigate missing outcomes."})
    return sorted(result, key=lambda row: (row["probability_swing"] is None, -(row["probability_swing"] or 0), row["model_input"]))
