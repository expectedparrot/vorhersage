#!/usr/bin/env python3
"""Offline joint session acceptance example. All forecasts and costs are fictional."""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "factory"))
from walkthrough import Walkthrough, timestamp


def run(project):
    demo = Walkthrough(project)
    demo.call("init", "--name", "Offline joint elicitation")
    evidence = demo.evidence("readiness", "Fictional factory faces uncertain shipment delays.")
    questions = []
    for name, horizon in (("early", 1), ("late", 2)):
        demo.call("question", "add", data={
            "id": name, "text": f"Will the fictional factory ship within {horizon} days?",
            "yes": "At least one shipment occurs by the deadline.", "no": "No shipment occurs by the deadline.",
            "void": "The fixture is withdrawn.", "event_deadline": timestamp(horizon), "resolve_after": timestamp(horizon + 1),
            "resolution_source": "urn:vorhersage:fixture", "event_group": "same_factory",
            "domain": "operations", "profile": "general", "kind": "simulation"})
        questions.append({"question_id": name, "version": 1})
    relation = demo.call("relation", data={"antecedent": questions[0], "consequent": questions[1],
                         "rationale": "Shipping by the earlier deadline implies shipping by the later deadline."})["relation_id"]
    target = timestamp(0.5)
    binding = {"variable": "readiness", "unit": "index points", "target_at": target,
               "vintage": "fictional-v1", "quantile": 0.9, "tolerance": 2}
    conditions = {}
    for name, kind, description in (
            ("unconditional", "unconditional", "Forecast normal operations."),
            ("policy", "intervention", "Assume an exogenous shipping restriction is imposed."),
            ("high", "information", "Learn that readiness reaches this model's own 90th percentile.")):
        spec = {"id": name, "version": 1, "kind": kind, "description": description}
        if name == "high":
            spec["binding"] = binding
        conditions[name] = demo.call("condition", "add", data=spec)["condition_id"]
    cutoff = timestamp()
    session_ids = []
    for index, (unconditional, policy) in enumerate(zip((0.01, 0.02, 0.2, 0.3), (0.02, 0.02, 0.1, 0.15))):
        own_high = 180 + index * 5
        numeric = {k: binding[k] for k in ("variable", "unit", "target_at", "vintage")}
        numeric["quantiles"] = [{"level": 0.1, "value": 150}, {"level": 0.5, "value": 170}, {"level": 0.9, "value": own_high}]
        spec = {"id": f"fixture-session-{index}", "wave": "fixture-wave", "forecaster": f"model-{index}",
                "protocol": "fictional-joint-v1", "repetition": 1, "mode": "simulation", "information_as_of": cutoff,
                "questions": questions, "condition_ids": list(conditions.values()), "packet_ids": [evidence["packet_id"]],
                "relation_ids": [relation], "numeric_forecasts": [numeric],
                "bindings": [{"condition_id": conditions["high"], "value": own_high}],
                "provenance": {"kind": "native" if index == 0 else "external", "source": "Synthetic offline fixture"},
                "configuration": {"synthetic": True}}
        cells = [{**q, "condition_id": conditions[name], "probability": p, "evidence_refs": [evidence]}
                 for q in questions for name, p in (("unconditional", unconditional), ("policy", policy), ("high", unconditional * 2))]
        usage = {"searches": 0, "model_calls": 0, "cost_usd": 0}
        if index == 0:
            id = demo.call("session", "start", data=spec)["session_id"]
            partial = {"expected_revision": 0, "idempotency_key": "partial", "cells": [{**cells[0], "probability": 0.9}],
                       "usage": usage, "raw_record": {"note": "Deliberately provisional fixture value."}}
            demo.call("session", "submit", id, data=partial)
            demo.save("partial.json", demo.call("session", "show", id))
            demo.save("retry.json", demo.call("session", "submit", id, data=partial))
            demo.call("session", "submit", id, data={"expected_revision": 1, "idempotency_key": "complete",
                      "cells": cells, "usage": usage, "raw_record": {"note": "Replace the provisional value and complete the grid."}})
            demo.call("session", "finalize", id, data={"expected_revision": 2, "idempotency_key": "final",
                                                       "rationale": "Fictional complete session."})
        else:
            record = {"session": spec, "submissions": [{"submitted_at": timestamp(), "cells": cells,
                      "usage": usage, "raw_record": {"original_model": f"model-{index}", "original_text": "Synthetic exported record."}}],
                      "finalized_at": timestamp(), "rationale": "Original fixture rationale."}
            imported = demo.call("session", "import", data=record)
            id = imported["session_id"]
            if index == 1:
                demo.save("import-retry.json", demo.call("session", "import", data=record))
        session_ids.append(id)
        demo.save(f"sessions/model-{index}.json", demo.call("session", "show", id))
        demo.save(f"coherence/model-{index}.json", demo.call("session", "coherence", id))
    policy = {"session_ids": session_ids, "expected_forecasters": [f"model-{i}" for i in range(4)]}
    panel = demo.call("session", "aggregate", data=policy)
    demo.save("aggregation.json", panel)
    demo.save("incomplete-panel.json", demo.call("session", "aggregate", data={**policy, "session_ids": session_ids[:3]}))
    row = next(r for r in panel["rows"] if r["condition_id"] == conditions["policy"])
    if not math.isclose(row["median_probability"], 0.06) or not math.isclose(row["multiplier"], math.sqrt(0.5)):
        raise RuntimeError("Unexpected fixture aggregation")
    summary = {"finalized_sessions": 4, "cells_per_session": 6, "unconditional_median": 0.11,
               "policy_median": row["median_probability"], "policy_multiplier": row["multiplier"],
               "usage": panel["usage"], "doctor": demo.call("doctor"),
               "limitations": "Fictional software acceptance fixture; no AIRO data, research, or model calls."}
    demo.save("summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    print(json.dumps(run(parser.parse_args().project), indent=2))
