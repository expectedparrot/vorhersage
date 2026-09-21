"""Readable views of recorded study progress, without additional judgments."""

import shlex

STAGES = {
    "reference_class_design": "Plan close and broader reference classes",
    "reference_class_search": "Find and verify comparable cases and useful analogies",
    "reference_class_analysis": "Assess reference evidence and decide whether to research further",
    "intake": "Identify missing facts and plan how to obtain them", "inquiry": "Answer a linked research question",
    "prior": "Establish a starting estimate", "drivers": "Map what could make it happen or prevent it",
    "research": "Collect and check evidence", "assessment": "Build the estimate",
    "model_challenge": "Check evidence transfers and model boundaries",
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
    reference = data.get("reference_research") or {}
    if reference.get("classes"):
        lines.append("Reference research:")
        latest_searches = {row["class_id"]: row for row in reference["searches"]}
        for row in reference["classes"]:
            search = latest_searches.get(row["id"], {})
            lines.append(f"  {row['population']} ({row['distance']}): {search.get('status', 'pending')}")
            for case in reference["candidates"]:
                if case["class_id"] != row["id"]:
                    continue
                lines.append(f"    {case['description']} [{case['use']}; outcome {case['outcome_status']}]")
                lines.append("      " + case["rationale"])
        if reference.get("analysis"):
            lines.append("  Analysis: " + reference["analysis"]["status"] + " — " + reference["analysis"]["result"])
        lines += ["  " + reference["qualification"], ""]
    if data.get("research_priorities") and not data["issued"]:
        lines.append("Research leads among assumed or extrapolated inputs:")
        for row in data["research_priorities"][:3]:
            impact = f"; tested probability swing {row['probability_swing']:.1%}" if row["probability_swing"] is not None else ""
            lines.append(f"  {row['target']} ({row['basis']}{impact})")
        lines.append("  These are research leads, not measured expected values of information.")
        lines.append("")
    if data.get("model_map"):
        mapping = data["model_map"]
        lines += [f"Research-to-model mapping, version {mapping['version']}: " + mapping["rationale"]]
    if data.get("model_challenge"):
        lines.append("Model challenge (forecaster's judgments):")
        for row in data["model_challenge"]["transfers"]:
            lines.append(f"  {row['model_input']}: {row['verdict']} — {row['reason']}")
        decisions = {r["concern_id"]: r for r in data.get("concern_resolutions", [])}
        for concern in data["model_challenge"]["concerns"]:
            decision = decisions.get(concern["id"], concern)
            lines.append(f"  {concern['question']} [{decision['disposition']}]: {decision['action']}")
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
                lines.append("    Source: " + source["title"] + " — " + source.get("url", source.get("attribution", "Private source")))
        lines.append("")
    # Show the latest submission for each task/topic, retaining its attribution.
    latest = {}
    for item in data["work"]:
        todo = item["task"]
        latest[(todo["kind"], todo.get("domain", todo.get("parameter_id", todo.get("class_id"))))] = item
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
        if todo.get("reference_class"):
            lines.append("Reference population: " + todo["reference_class"]["population"])
            lines.extend("  Search: " + query for query in todo["reference_class"]["search_plan"])
        if todo.get("action"):
            lines.append("Follow-up: " + todo["action"])
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
