"""Exercise a research session study using only local deterministic workers."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vorhersage import sessions, session_studies, session_reports
from vorhersage.common import now
from vorhersage.workflow import Workflow


def run(path):
    w = Workflow(path)
    w.store.init("Synthetic live-session study")
    deadline = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    w.question({"id": "readiness", "text": "Will the fictional factory ship tomorrow?", "yes": "Shipment occurs.",
                "no": "No shipment occurs.", "void": "Fixture withdrawn.", "event_deadline": deadline,
                "resolve_after": deadline, "resolution_source": "urn:fixture", "event_group": "factory",
                "domain": "operations", "profile": "general", "kind": "simulation"})
    condition = sessions.add_condition(w.store, {"id": "unconditional", "version": 1, "kind": "unconditional", "description": "No added assumptions"})["condition_id"]
    worker = {"command": [sys.executable, str(Path(__file__).with_name("worker.py").resolve())], "config": {}, "timeout_seconds": 10}
    execution = {"evidence_policy": "live", "defer_bindings": True, "worker": worker, "tool_worker": worker,
                 "research": {"minimum_successful_tools": 1, "minimum_unique_pages": 1, "domains": ["readiness"]},
                 "budget": {"max_model_calls": 5, "max_searches": 5, "max_cost_usd": 1},
                 "requirements": [{"id": "fixture", "description": "No real network calls", "expected": {"network_calls": 0}}]}
    template = {"id": "template", "wave": "fixture", "forecaster": "fixture", "protocol": "synthetic-v1", "repetition": 1,
                "mode": "simulation", "information_as_of": now(), "questions": [{"question_id": "readiness", "version": 1}],
                "condition_ids": [condition], "packet_ids": [], "relation_ids": [], "numeric_forecasts": [], "bindings": [],
                "provenance": {"kind": "native", "source": "Local deterministic fixture"}, "configuration": {}}
    spec = {"id": "fixture-study", "version": 1, "description": "Two procedures, two independent repetitions", "session_template": template,
            "repetitions": 2, "order_seed": "fixture", "evidence_policy": "independent_live",
            "arms": [{"id": name, "configuration": {"fixture_probability": p}, "execution": {**execution,
                      "worker": {**worker, "config": {"probability": p}}}} for name, p in [("a", .25), ("b", .75)]]}
    Path(path, "study.json").write_text(json.dumps(spec, indent=2))
    study = session_studies.add(w.store, spec)["study_id"]
    partial = session_studies.run(w.store, study, 5)
    assert not partial["complete"]
    result = session_studies.run(w.store, study, 20)
    assert result["complete"], result
    ids = [t["session_id"] for t in result["trials"]]
    session_reports.render(w.store, ids, Path(path, "comparison.html"))
    cutoff = now()
    with w.store.connect() as c:
        first = sessions._status(c, ids[0])
        refs = first["cells"][0]["evidence_refs"]
    w.resolve({"question_id": "readiness", "question_version": 1, "outcome": "yes", "reason": "Synthetic test outcome",
               "known_at": now(), "evidence_refs": refs, "previous_resolution_id": None, "idempotency_key": "resolve-fixture"})
    evaluation = session_reports.evaluate(w.store, {"session_ids": ids, "cutoff": cutoff, "resolution_as_of": now(), "allow_source_reported": False})
    summary = {"study_id": study, "sessions": len(ids), "complete": result["complete"], "usage": result["usage"],
               "arms": evaluation["arms"], "doctor": w.doctor(), "actual_provider_calls": 0,
               "limitation": "All forecasts, receipts, and usage are synthetic software fixtures."}
    Path(path, "summary.json").write_text(json.dumps(summary, indent=2))
    Path(path, "evaluation.json").write_text(json.dumps(evaluation, indent=2))
    return summary


if __name__ == "__main__":
    print(json.dumps(run(Path(sys.argv[1])), indent=2))
