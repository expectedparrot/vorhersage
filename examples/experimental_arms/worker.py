#!/usr/bin/env python3
"""Synthetic arm worker. Makes no model or network calls and measures no skill."""

import json
import sys
from datetime import datetime, timedelta, timezone


def answer(request):
    step, config = request["next"], request["worker_config"]
    if config["provider"] != "fixture":
        raise ValueError("This example only implements the fixture provider.")
    run = step["context"]["run"]
    refs = [{"packet_id": id, "record_id": record["id"]} for id in run["packet_ids"]
            for record in step["context"]["artifacts"][id]["records"]]
    p = config["model_parameters"]["fixture_probability"] if refs else 0.5
    kind = step["task"]["kind"]
    if kind == "assessment":
        payload = {"method": "judgment", "probability": p, "rationale": "Preselected synthetic probability.",
                   "evidence_refs": refs, "limitations": ["Fixture arithmetic, not a real forecast."]}
    elif kind == "review":
        payload = {"decision": "revise", "probability": min(1, step["context"]["current_probability"] + 0.1),
                   "rationale": "Synthetic review adds 0.1 to exercise before/after scoring.", "evidence_refs": refs,
                   "objections": [{"direction": "too_high", "objection": "A fictional failure is possible.", "response": "Risk remains."},
                                  {"direction": "too_low", "objection": "Fictional readiness may help.", "response": "Apply the fixture adjustment."}]}
    elif kind == "issue":
        payload = {"stopping_reason": "Fixture completed.",
                   "review_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                   "triggers": [{"description": "New fictional status report.", "evidence_refs": refs}]}
    else:
        raise ValueError("Unsupported fixture stage.")
    return {"payload": payload, "usage": {"searches": 0, "model_calls": 0, "cost_usd": 0}}


if __name__ == "__main__":
    print(json.dumps(answer(json.load(sys.stdin))))
