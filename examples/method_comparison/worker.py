#!/usr/bin/env python3
"""Deterministic offline worker: tests the experiment plumbing, not forecasting skill."""

import json
import sys
from datetime import datetime, timedelta, timezone


def answer(request):
    step = request["next"]
    run = step["context"]["run"]
    config = request["worker_config"]
    refs = [{"packet_id": id, "record_id": record["id"]} for id in run["packet_ids"]
            for record in step["context"]["artifacts"][id]["records"]]
    method = run["method_spec"]["assessment_method"]
    assessment = {"method": method, "rationale": "Preselected fictional inputs for a software demonstration.",
                  "limitations": ["No forecasting skill is measured."], "evidence_refs": refs}
    if method == "judgment":
        assessment["probability"] = config["probability"]
    elif method == "conditional_path":
        assessment.update(nested_events_justification="Fictional dispatch requires readiness.", components=[
            {"id": "ready", "conditional_on": None, "probability": config["ready"],
             "rationale": "Assumed readiness probability.", "evidence_refs": refs},
            {"id": "target", "conditional_on": "ready", "probability": config["dispatch_given_ready"],
             "rationale": "Assumed dispatch probability conditional on readiness.", "evidence_refs": refs}])
    else:
        raise ValueError("Fixture only implements judgment and conditional_path.")
    payload = {
        "prior": {"method": "judgment", "probability": 0.5, "rationale": "Fictional starting judgment.",
                  "limitations": ["Packets are already available; this is not a blind prior."], "evidence_refs": []},
        "drivers": {"drivers": [{"name": "Readiness", "mechanism": "Dispatch requires readiness.", "evidence_refs": refs}],
                    "yes_path": "Ready then dispatched.", "no_path": "Readiness or dispatch fails.", "unknowns": ["Timing."]},
        "research": {"disposition": "assessed" if refs else "unknown", "interpretation": "Review the registered fictional packet.",
                     "evidence_refs": refs, "sources_checked": ["Frozen fixture"] if refs else [],
                     "unknowns": ["Remaining execution risk."], "conflicts": []},
        "assessment": assessment,
        "review": {"decision": "retain", "rationale": "Retain this fixture estimate.", "evidence_refs": refs,
                   "objections": [{"direction": "too_high", "objection": "Dispatch can fail.", "response": "Failure remains possible."},
                                  {"direction": "too_low", "objection": "Preparation could suffice.", "response": "Success remains possible."}]},
        "issue": {"stopping_reason": "Offline fixture completed.",
                  "review_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                  "triggers": [{"description": "New fictional dispatch record.", "evidence_refs": refs}]},
    }[step["task"]["kind"]]
    return {"payload": payload, "usage": {"searches": 0, "model_calls": 0, "cost_usd": 0}}


if __name__ == "__main__":
    print(json.dumps(answer(json.load(sys.stdin))))
