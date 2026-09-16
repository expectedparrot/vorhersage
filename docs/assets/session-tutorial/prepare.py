"""Prepare dated synthetic tutorial inputs; forecasting/execution use the CLI.

Run from an environment with this Vorhersage checkout installed. This helper only
writes input JSON and reads saved receipts/session records; it makes no model calls.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def write(project, name, value):
    path = project / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    return str(path)


def prepare(stage, project):
    if stage == "inputs":
        project.mkdir(parents=True, exist_ok=False)
        deadline = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        question = {"id": "readiness", "text": "Will the fictional factory ship by tomorrow's deadline?",
                    "yes": "A qualifying shipment is recorded by the deadline.", "no": "No qualifying shipment is recorded.",
                    "void": "The fictional event is withdrawn.", "event_deadline": deadline,
                    "resolve_after": deadline, "resolution_source": "urn:fixture:dispatch", "event_group": "factory",
                    "domain": "operations", "profile": "general", "kind": "simulation"}
        paths = [write(project, "question.json", question), write(project, "condition.json", {
            "id": "unconditional", "version": 1, "kind": "unconditional", "description": "No added assumptions"})]
    elif stage == "study":
        condition = json.loads((project / "condition-result.json").read_text())["data"]["condition_id"]
        worker = {"command": [sys.executable, str(Path(__file__).with_name("worker.py").resolve())],
                  "config": {}, "timeout_seconds": 10}
        execution = {"evidence_policy": "live", "defer_bindings": True,
                     "budget": {"max_model_calls": 5, "max_searches": 5, "max_cost_usd": 1},
                     "research": {"minimum_successful_tools": 1, "minimum_unique_pages": 1, "domains": ["readiness"]},
                     "requirements": [{"id": "fixture", "description": "No real network calls", "expected": {"network_calls": 0}}],
                     "worker": worker, "tool_worker": worker}
        template = {"id": "template", "wave": "tutorial", "forecaster": "fixture", "protocol": "synthetic-v1", "repetition": 1,
                    "mode": "simulation", "information_as_of": now(), "questions": [{"question_id": "readiness", "version": 1}],
                    "condition_ids": [condition], "packet_ids": [], "relation_ids": [], "numeric_forecasts": [], "bindings": [],
                    "provenance": {"kind": "native", "source": "Deterministic documentation fixture"}, "configuration": {}}
        study = {"id": "tutorial-study", "version": 1, "description": "Four sessions through research, resumption, and scoring",
                 "session_template": template, "repetitions": 2, "order_seed": "tutorial-1", "evidence_policy": "independent_live",
                 "arms": [{"id": name, "configuration": {"fixture_probability": p}, "execution": {**execution,
                           "worker": {**worker, "config": {"probability": p}}}} for name, p in [("a", .25), ("b", .75)]]}
        paths = [write(project, "study.json", study)]
    else:
        from vorhersage import sessions, session_studies
        from vorhersage.store import Store
        store = Store(project)
        study_id = json.loads((project / "study-result.json").read_text())["data"]["study_id"]
        trials = session_studies.status(store, study_id)["trials"]
        if stage == "resolution":
            assert all(t["disposition"] == "finalized" for t in trials), "Finish every session before preparing the synthetic outcome."
            cutoff = now()
            state = sessions.status(store, trials[0]["session_id"])
            paths = [write(project, "forecast-cutoff.json", {"cutoff": cutoff}), write(project, "resolution.json", {
                "question_id": "readiness", "question_version": 1, "outcome": "yes", "reason": "Authored synthetic outcome for the tutorial",
                "known_at": now(), "evidence_refs": state["cells"][0]["evidence_refs"],
                "previous_resolution_id": None, "idempotency_key": "tutorial-resolution"})]
        else:
            cutoff = json.loads((project / "forecast-cutoff.json").read_text())["cutoff"]
            paths = [write(project, "evaluation.json", {"session_ids": [t["session_id"] for t in trials],
                     "cutoff": cutoff, "resolution_as_of": now(), "allow_source_reported": False})]
    return {"stage": stage, "written": paths, "provider_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["inputs", "study", "resolution", "evaluation"])
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.stage, args.project), indent=2))
