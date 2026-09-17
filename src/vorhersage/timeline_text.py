"""Readable terminal views of timeline results; JSON remains the full record."""


def _probability(analysis):
    value = analysis["probability"]
    if value is not None:
        return f"{value:.1%}"
    if analysis["disposition"] == "unweighted":
        return "not assigned (scenarios have no weights)"
    bounds = analysis.get("probability_bounds")
    suffix = f"; unresolved-weight bounds {bounds[0]:.1%}–{bounds[1]:.1%}" if bounds else ""
    return "unresolved" + suffix


def _outcome(value):
    return "Unknown" if value is None else "Yes" if value else "No"


def _table(headers, rows):
    rows = [headers, *rows]
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    return "\n".join("  ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip()
                     for row in rows)


def render(action, data):
    """Render already-computed results without inventing additional estimates."""
    if action in ("add", "shift", "show"):
        spec = data["specification"]
        verb = "Model" if action == "show" else "Saved"
        return (f"{verb} {spec['id']}@{spec['version']}\n"
                f"Artifact: {data['timeline_model_id']}\n"
                f"{len(spec['scenarios'])} scenarios; {len(spec['parameters'])} parameters\n"
                f"{spec['description']}")
    if action == "list":
        return _table(["Model", "Artifact"], [
            [f"{r['specification']['id']}@{r['specification']['version']}", r["id"]] for r in data])
    if action == "gaps":
        # One research task can address a parameter across several scenarios.
        grouped = {}
        for row in data["unresolved"]:
            grouped.setdefault(row["parameter_id"], {"task": row["research_task"], "scenarios": []})["scenarios"].append(row["scenario_id"])
        lines = [f"Unresolved parameters: {len(grouped)}"]
        for parameter, row in grouped.items():
            lines.extend([f"  {parameter}: {row['task']}", "    Scenarios: " + ", ".join(row["scenarios"])])
        lines.append(f"Assumed scenario inputs: {len(data['assumed_inputs'])}")
        if data["unweighted"]:
            lines.append("Scenario weights: not assigned")
        lines.append(data["note"])
        return "\n".join(lines)
    if action == "analyze":
        lines = ["Probability: " + _probability(data),
                 f"Deadline: {data['deadline_rule'].replace('_', ' ')} {data['deadline']}", "",
                 _table(["Scenario", "Weight", "Launch (UTC)", "Meets deadline"], [
                     [r["scenario_id"], "—" if r.get("weight") is None else f"{r['weight']:.1%}",
                      r["launch_at"] or r["status"], _outcome(r["meets_deadline"])] for r in data["scenarios"]]),
                 "", "Computed from declared inputs; scenario weights are supplied by the forecaster."]
        if "sensitivity" in data:
            flips = [r for r in data["sensitivity"]["substitutions"] if r["changes_outcome"]]
            lines.extend(["", "Sensitivity substitutions that change the outcome:",
                          _table(["Scenario", "Parameter", "Substituted value", "Meets deadline"], [
                              [r["scenario_id"], r["parameter_id"], str(r["value"]), _outcome(r["meets_deadline"])] for r in flips]),
                          data["sensitivity"]["note"]])
        return "\n".join(lines)
    if action == "compare":
        lines = ["Left probability:  " + _probability(data["left"]),
                 "Right probability: " + _probability(data["right"]), "",
                 _table(["Scenario", "Left meets deadline", "Right meets deadline", "Changed"], [
                     [r["scenario_id"], _outcome(r["left_meets_deadline"]), _outcome(r["right_meets_deadline"]),
                      "Yes" if r["changes_outcome"] else "No"] for r in data["matched_scenarios"]]),
                 "", "Changed fields: " + (", ".join(data["changed_fields"]) or "none")]
        for side in ("left", "right"):
            if data["unmatched_" + side]:
                lines.append(f"Only in {side}: " + ", ".join(data["unmatched_" + side]))
        lines.append("Sensitivity comparison, not a confidence interval.")
        return "\n".join(lines)
    if action == "report":
        return "Report: " + data["path"]
    raise ValueError("Unsupported timeline view: " + action)
