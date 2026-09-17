"""Readable views of recorded study progress, without additional judgments."""

import shlex

STAGES = {
    "prior": "Establish a starting estimate", "drivers": "Map what could make it happen or prevent it",
    "research": "Collect and check evidence", "assessment": "Build the estimate",
    "review": "Challenge the estimate", "issue": "Publish the forecast",
    "timeline_structure": "Map the steps required before the deadline",
    "timeline_research": "Research the model's uncertain inputs",
    "waiting": "Forecast issued; awaiting review or resolution", "complete": "Resolved",
    "blocked": "Research paused",
}


def render(data):
    """Readable progress, without administrative identifiers or schemas."""
    lines = [data["question"], ""]
    project = shlex.quote(data["project"])
    if data["stage"] == "definition":
        lines += ["Before researching, define what would count:",
                  "  • When is the deadline, including its timezone?",
                  "  • What exactly must happen for YES?",
                  "  • Which sources will settle the outcome?", "",
                  "Record your answers with:",
                  f"  vorhersage define --project {project} --deadline TIME --yes CRITERIA --source SOURCE",
                  "", "No probability has been assigned."]
        return "\n".join(lines)
    q = data["definition"]
    lines += ["Counts as YES: " + q["yes"], "Deadline: " + q["event_deadline"],
              "Outcome sources: " + q["resolution_source"],
              "Forecaster: " + data["forecaster"] + " · " + data["mode"], ""]
    p = data["probability"]
    lines.append(("Published forecast: " if data["issued"] else "Working estimate: ") +
                 (f"{p:.1%}" if p is not None else "not yet assigned"))
    lines += ["Stage: " + STAGES.get(data["stage"], data["stage"]), ""]
    if data.get("model"):
        model = data["model"]
        lines += ["Model: " + model["specification"]["description"]]
        value = model["analysis"]["probability"]
        lines.append("Model calculation: " + (f"{value:.1%}" if value is not None else "not yet determined"))
        if not data["issued"]:
            lines.append("The model calculation is not an issued forecast.")
        missing = sorted({r["parameter_id"] for r in model["analysis"]["gaps"]["unresolved"]})
        if missing:
            lines.append("Inputs needing research: " + ", ".join(missing))
        lines += ["Model limitations:", *["  • " + text for text in model["specification"]["limitations"]], ""]
    if data.get("findings"):
        lines.append("Evidence used:")
        for item in data["findings"]:
            record = item["record"]
            lines.append("  • " + record["claim"])
            for source in record["sources"]:
                lines.append("    Source: " + source["title"] + " — " + source["url"])
        lines.append("")
    # Show the latest submission for each task/topic, retaining its attribution.
    latest = {}
    for item in data["work"]:
        todo = item["task"]
        latest[(todo["kind"], todo.get("domain", todo.get("parameter_id")))] = item
    if latest:
        lines.append("Recorded reasoning:")
        for item in latest.values():
            todo, answer = item["task"], item["payload"]
            topic = todo.get("domain", todo.get("parameter_id", todo["kind"])).replace("_", " ")
            explanation = answer.get("interpretation", answer.get("rationale", answer.get("stopping_reason")))
            if explanation:
                lines.append("  " + topic.capitalize() + ": " + explanation)
            if todo["kind"] == "drivers":
                lines.append("  Paths to the outcome:")
                lines.append("    YES: " + answer["yes_path"])
                lines.append("    NO: " + answer["no_path"])
                lines.extend("    " + driver["name"] + ": " + driver["mechanism"] for driver in answer["drivers"])
            for key, label in (("unknowns", "Recorded unknown"), ("limitations", "Limitation")):
                for text in answer.get(key, []):
                    lines.append("    " + label + ": " + text)
            for objection in answer.get("objections", []):
                lines.append("    " + objection["direction"].replace("_", " ").capitalize() + ": " + objection["objection"])
                lines.append("    Response: " + objection["response"])
            for conflict in answer.get("conflicts", []):
                lines.append("    Conflict (" + conflict["status"] + "): " + conflict["description"])
                lines.append("    Decision: " + conflict["decision"])
            if todo["kind"] == "issue":
                lines.append("    Review on: " + answer["review_at"])
                lines.extend("    Revisit when: " + trigger["description"] for trigger in answer["triggers"])
        lines.append("")
    task = data["next"]
    if "task" in task:
        todo = task["task"]
        lines += ["Next: " + todo["instruction"]]
        if todo.get("domain"):
            lines.append("Research topic: " + todo["domain"].replace("_", " "))
        lines += ["", "Get the task, evidence, and answer template (use a new filename each time):",
                  f"  vorhersage next --project {project} --output task-{data['completed_tasks'] + 1}.json",
                  "Fill submission.payload using payload_schema, then submit the task file.",
                  "You can do this yourself or ask an agent to help."]
    elif task.get("reason"):
        lines.append(task["reason"])
    else:
        lines.append(f"Read the full report: vorhersage report --project {project}")
    return "\n".join(lines)
