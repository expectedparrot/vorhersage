"""Readable views of recorded study progress, without additional judgments."""

import shlex

STAGES = {
    "intake": "Identify missing facts and plan how to obtain them", "inquiry": "Answer a linked research question",
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
    previous = data.get("previous_forecast")
    if previous:
        lines.append(f"Previous issued forecast: {previous['probability']:.1%} ({previous['issued_at']})")
        if not data["issued"]:
            lines.append("Revision in progress; the previous forecast remains issued until this review is complete.")
    lines.append(("Published forecast: " if data["issued"] else "Working estimate: ") +
                 (f"{p:.1%}" if p is not None else "not yet assigned"))
    lines += ["Stage: " + STAGES.get(data["stage"], data["stage"]), ""]
    analysis = data.get("sensitivity")
    if analysis and analysis.get("bounded_range"):
        low, high = analysis["bounded_range"]
        lines += [f"Declared assumption range: {low:.1%}–{high:.1%} (not a confidence interval)."]
        for row in analysis.get("conditional_sensitivity", [])[:3]:
            lines.append(f"  {row['scenario_id']}: varying its conditional probability moves the forecast by {row['swing']:.1%}.")
        lines.append("")
    if data.get("research_plan"):
        lines.append("Research questions and model inputs:")
        for q in data["research_plan"]["unknowns"]:
            answer = data.get("inquiry_answers", {}).get(q["id"])
            lines.append(f"  {q['question']} → {', '.join(q['input_ids'])} ({q['route']})")
            lines.append("    " + (answer["status"] + ": " + answer["answer"] if answer else q["action"]))
        lines.append("")
    if data.get("parameter_support"):
        lines.append("Model inputs and evidence basis:")
        for row in data["parameter_support"]:
            lines.append(f"  {row['model_input']}: {row['value']} ({row['basis']}); range {row['plausible_range']}")
            lines.append("    Evidence measures: " + row["evidence_measures"])
            lines.append("    Transfer assumptions: " + row["transfer_assumptions"])
        lines.append("")
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
            timing = (item.get("calculation") or {}).get("prior_record")
            if timing:
                lines.append("    Estimate timing: " + timing["timing"].replace("_", " "))
            if answer.get("sensitivity_review"):
                review = answer["sensitivity_review"]
                lines += ["    Sensitivity review: " + review["interpretation"],
                          "    Next evidence: " + review["next_evidence"]]
            if todo["kind"] == "drivers":
                lines.append("  Paths to the outcome:")
                lines.append("    YES: " + answer["yes_path"])
                lines.append("    NO: " + answer["no_path"])
                lines.extend("    " + driver["name"] + ": " + driver["mechanism"] for driver in answer["drivers"])
            for key, label in (("unknowns", "Recorded unknown"), ("limitations", "Limitation")):
                for text in answer.get(key, []):
                    if isinstance(text, str):
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
        if todo.get("inquiry"):
            inquiry = todo["inquiry"]
            lines += ["Question: " + inquiry["question"], "Action (" + inquiry["route"] + "): " + inquiry["action"],
                      "Why it matters: " + inquiry["why_it_matters"]]
        lines += ["", "Get the task, evidence, and answer template (use a new filename each time):",
                  f"  vorhersage next --project {project} --output task-{data['completed_tasks'] + 1}.json",
                  "Fill submission.payload using payload_schema, then submit the task file.",
                  "You can do this yourself or ask an agent to help."]
    elif task.get("reason"):
        lines.append(task["reason"])
    else:
        lines.append(f"Read the full report: vorhersage report --project {project}")
        if data["issued"]:
            lines.append(f"New evidence? vorhersage revise --project {project} --reason REASON --evidence PACKET:RECORD")
    return "\n".join(lines)
