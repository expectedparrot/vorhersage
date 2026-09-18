#!/usr/bin/env python3
"""Run two procedures x two model configurations x two data sets, offline."""

import json
import sys
from datetime import timedelta
from itertools import product
from pathlib import Path

from vorhersage import experiments
from vorhersage.common import now, time
from vorhersage.evidence import capture_finding
from vorhersage.workflow import Workflow


def main(directory):
    root = Path(directory).resolve()
    w = Workflow(root)
    w.store.init("Experimental arms example")

    def save(name, value):
        (root / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n")
        return value

    deadline = (time(now()) + timedelta(days=2)).isoformat()
    w.question(save("question", {"id": "fixture", "text": "Will the fictional factory dispatch by the deadline?",
        "yes": "A qualifying fictional dispatch is recorded.", "no": "No qualifying fictional dispatch.",
        "void": "The fixture is withdrawn.", "event_deadline": deadline, "resolve_after": deadline,
        "resolution_source": "urn:vorhersage:fixture", "event_group": "fictional-factory",
        "domain": "operations", "profile": "general", "kind": "simulation"}))
    packet = w.import_packet(capture_finding("Fictional factory reports readiness.", url="urn:vorhersage:fixture",
                                             title="Synthetic report", excerpt="The fictional factory is ready."))
    methods = {}
    for label, stages in (("direct", ["assessment", "issue"]), ("review", ["assessment", "review", "issue"])):
        spec = save("method-" + label, {"id": label, "version": 1, "description": "Synthetic " + label,
            "instructions": "Exercise the registered stages with fixture values.", "task_instructions": {},
            "stages": stages, "prior_method": "none", "assessment_method": "judgment", "research_domains": [],
            "worker": {"command": [sys.executable, str(Path(__file__).with_name("worker.py").resolve())],
                       "config": {}, "timeout_seconds": 5},
            "budget": {"max_searches": 0, "max_extra_tasks": 0, "max_model_calls": 10, "max_cost_usd": 1}})
        methods[label] = experiments.add_method(w.store, spec)["method_id"]
    arms = []
    for method, model, data in product(methods, ("model-a", "model-b"), ("question-only", "report")):
        name = "-".join((method, model, data))
        spec = save("arm-" + name, {"id": name, "version": 1, "description": "Offline fixture: " + name,
            "method_id": methods[method],
            "model": {"provider": "fixture", "name": model,
                      "parameters": {"fixture_probability": 0.3 if model == "model-a" else 0.7}},
            "data": {"label": data, "questions": [{"question_id": "fixture", "version": 1,
                      "packet_ids": [] if data == "question-only" else [packet["packet_id"]]}]}})
        arms.append(experiments.add_arm(w.store, spec)["arm_id"])
    spec = save("experiment", {"id": "arms-fixture", "version": 1, "description": "Two methods x two models x two data sets.",
        "questions": [{"question_id": "fixture", "version": 1}], "arm_ids": arms, "repetitions": 2,
        "mode": "simulation", "information_as_of": now(),
        "forecast_cutoff": (time(now()) + timedelta(days=1)).isoformat(),
        "evidence_policy": "frozen_packets", "order_seed": "arms-fixture-1"})
    experiment = experiments.add_experiment(w.store, spec)["experiment_id"]
    save("partial", experiments.execute(root, experiment, max_tasks=3))
    result = save("execution", experiments.execute(root, experiment, max_tasks=100))
    w.resolve({"question_id": "fixture", "question_version": 1, "outcome": "yes", "known_at": now(),
               "reason": "Declared synthetic outcome for the software example.",
               "evidence_refs": [packet["records"][0]["evidence_ref"]], "previous_resolution_id": None,
               "idempotency_key": "fixture-outcome"})
    report = save("evaluation", experiments.score(root, experiment, now()))
    summary = save("summary", {"experiment_id": experiment, "issued_trials": result["status"]["issued_trials"],
        "arms": [{"name": s["arm_name"], "brier": s["matched_brier"], "assessment_brier": s["matched_assessment_brier"]}
                 for s in report["arm_scores"].values()], "doctor": w.doctor(),
        "note": "Synthetic probabilities and outcomes exercise software only; no model or network calls."})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
