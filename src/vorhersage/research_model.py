"""Link research questions and declared evidence transfers to actual model inputs.

These checks establish coverage and consistency, not substantive truth. The
forecaster supplies the transfer assumptions and ranges; the package checks
their links and calculates their consequences.
"""

import copy

from .common import require, time


def validate_intake(plan):
    inputs = {r["id"] for r in plan["inputs"]}
    require(len(inputs) == len(plan["inputs"]), "Research input IDs must be unique.")
    questions = plan["unknowns"]
    require(len(questions) <= 100 and len({q["id"] for q in questions}) == len(questions),
            "Use at most 100 uniquely named research questions.")
    for q in questions:
        require(set(q["input_ids"]) <= inputs, "Research questions must link to declared input IDs.")


def model_inputs(payload, timeline_spec=None):
    """Stable paths identify each supplied number, not an inferred importance rank."""
    method = payload["method"]
    if method == "judgment":
        return {"probability": payload["probability"]}
    if method == "scenario_mixture":
        return {f"scenarios/{s['id']}/{field}": s[field]
                for s in payload["scenarios"] for field in ("weight", "probability")}
    if method == "conditional_path":
        return {f"components/{c['id']}/probability": c["probability"] for c in payload["components"]}
    if method == "odds_ledger":
        ledger = payload["odds_ledger"]
        values = {"anchor/probability": ledger["anchor"]["probability"]}
        values.update({f"entries/{e['finding_id']}/lr": e["lr"] for e in ledger["entries"]})
        values.update({f"joint/{e['dependence_group']}/lr": e["lr"] for e in ledger["joint_declarations"]})
        return values
    if method == "timeline_model":
        values = {}
        for s in timeline_spec["scenarios"]:
            if "weight" in s:
                values[f"scenarios/{s['id']}/weight"] = s["weight"]
            for a in s["assessments"]:
                if "value" in a:
                    values[f"scenarios/{s['id']}/inputs/{a['parameter_id']}"] = a["value"]
        return values
    weights = payload.get("weights", [1 / len(payload["members"])] * len(payload["members"]))
    return {f"members/{m}/weight": w for m, w in zip(payload["members"], weights)}


def validate_support(payload, plan, timeline_spec=None):
    expected = model_inputs(payload, timeline_spec)
    rows = payload.get("parameter_support", [])
    require(len({r["model_input"] for r in rows}) == len(rows) and
            {r["model_input"] for r in rows} == set(expected),
            "Supply parameter_support for every model input, separately for scenario weights and conditional probabilities. "
            "Expected model_input paths: " + ", ".join(expected))
    ids = {r["id"] for r in plan["inputs"]}
    for row in rows:
        require(row["input_id"] in ids, "Parameter support references an unknown intake input.")
        value = expected[row["model_input"]]
        require(row["value"] == value, "Parameter support value differs from the actual model input: " + row["model_input"])
        bounds = row["plausible_range"]
        require(len(bounds) == 2, "Plausible ranges need exactly two endpoints.")
        if isinstance(value, (int, float)):
            require(all(type(v) in (int, float) for v in bounds) and bounds[0] <= value <= bounds[1],
                    "Plausible range must contain the model input.")
            require(bounds[0] >= 0, "Model input ranges cannot be negative.")
            if row["model_input"].endswith("/lr"):
                require(bounds[0] > 0, "Likelihood-ratio ranges must be strictly positive.")
            if row["model_input"] == "probability" or row["model_input"].endswith(("/probability", "/weight")):
                require(bounds[1] <= 1, "Probability ranges cannot exceed one.")
        elif value == "never":
            require(bounds == ["never", "never"], "Use separate scenarios to represent never versus a completion date.")
        else:
            require(all(isinstance(v, str) for v in bounds) and time(bounds[0]) <= time(value) <= time(bounds[1]),
                    "Date range must contain the model date.")
        require(row["basis"] == "assumed" or row["evidence_refs"],
                "Measured, calculated, or extrapolated inputs require evidence references; use assumed when unsupported.")
    return rows


def mixture(payload):
    """Use the declared support ranges without silently replacing explicit ranges."""
    spec = {k: copy.deepcopy(payload[k]) for k in ("scenarios", "partition_justification")}
    support = {r["model_input"]: r for r in payload.get("parameter_support", [])}
    for row in spec["scenarios"]:
        for field in ("weight", "probability"):
            key = f"scenarios/{row['id']}/{field}"
            if key in support:
                bounds = support[key]["plausible_range"]
                require(field + "_range" not in row or row[field + "_range"] == bounds,
                        "Scenario range differs from its parameter support: " + key)
                row[field + "_range"] = bounds
    return spec
