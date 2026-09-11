#!/usr/bin/env python3
"""Exercise versioned methods, repeated trials, resume, and scoring through the CLI."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "factory"))
from walkthrough import Walkthrough, timestamp


def run(project):
    demo = Walkthrough(project)
    demo.call("init", "--name", "Offline methodology comparison")
    evidence = demo.evidence("readiness", "Fictional factories are preparing to dispatch; shipment is uncertain.")
    questions = []
    for location in ("east", "west"):
        qid = "factory_" + location
        demo.call("question", "add", data={
            "id": qid, "text": f"Will fictional factory {location} ship by tomorrow?",
            "yes": "A shipment occurs by the deadline.", "no": "No shipment occurs by the deadline.",
            "void": "The fixture is withdrawn.", "event_deadline": timestamp(1), "resolve_after": timestamp(2),
            "resolution_source": "urn:vorhersage:fixture", "event_group": qid,
            "domain": "operations", "profile": "general", "kind": "simulation"})
        questions.append({"question_id": qid, "version": 1, "packet_ids": [evidence["packet_id"]]})
    methods = {}
    for name, calculation, config in (("direct", "judgment", {"probability": 0.5}),
                                      ("decomposition", "conditional_path", {"ready": 0.8, "dispatch_given_ready": 0.75})):
        method = {"id": name, "version": 1, "description": "Fictional " + name + " procedure.",
                  "instructions": "Use only the supplied fictional evidence. Complete each workflow task.",
                  "task_instructions": {"assessment": "Apply the registered assessment calculation."},
                  "prior_method": "judgment", "assessment_method": calculation, "research_domains": ["readiness", "contrary_evidence"],
                  "worker": {"command": [sys.executable, str(Path(__file__).with_name("worker.py").resolve())],
                             "config": config, "timeout_seconds": 10},
                  "budget": {"max_searches": 0, "max_extra_tasks": 0, "max_model_calls": 20, "max_cost_usd": 0}}
        methods[name] = demo.call("method", "add", data=method)["method_id"]
    experiment = demo.call("experiment", "add", data={
        "id": "factory_methods", "version": 1, "description": "Offline software acceptance example, not a skill benchmark.",
        "questions": questions, "method_ids": list(methods.values()), "repetitions": 2,
        "mode": "simulation", "information_as_of": timestamp(), "forecast_cutoff": timestamp(0.5),
        "evidence_policy": "frozen_packets", "order_seed": "factory-demo-1"})["experiment_id"]
    demo.save("started.json", demo.call("experiment", "start", experiment))
    demo.save("partial.json", demo.call("experiment", "run", experiment, "--max-tasks", "3"))
    completed = demo.call("experiment", "run", experiment, "--max-tasks", "100")
    demo.save("completed.json", completed)
    if completed["status"]["issued_trials"] != 8:
        raise RuntimeError("Fixture did not issue all eight forecasts: " + json.dumps(completed))
    for q, outcome in zip(questions, ("yes", "no")):
        resolution = demo.evidence("resolution_" + q["question_id"], "Synthetic outcome: " + outcome)
        demo.call("resolve", data={"question_id": q["question_id"], "question_version": 1, "outcome": outcome,
                  "known_at": timestamp(), "reason": "Fictional outcome for software verification.",
                  "evidence_refs": [resolution], "previous_resolution_id": None, "idempotency_key": q["question_id"]})
    scored = demo.call("experiment", "evaluate", experiment, "--resolution-as-of", timestamp())
    demo.save("evaluation.json", scored)
    summary = {"experiment_id": experiment, "issued_trials": 8,
               "matched_brier": {name: scored["method_scores"][id]["matched_brier"] for name, id in methods.items()},
               "doctor": demo.call("doctor"), "limitations": "Deterministic fictional inputs; not evidence of forecasting skill."}
    demo.save("summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    print(json.dumps(run(parser.parse_args().project), indent=2))
