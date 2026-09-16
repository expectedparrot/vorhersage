"""Build an offline audit using fictional acquisition assumptions, without model calls."""

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vorhersage.common import now
from vorhersage.widget import export
from vorhersage.workflow import Workflow


def main(output):
    stamp = now()
    future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    with tempfile.TemporaryDirectory() as project:
        w = Workflow(project)
        w.store.init("Fictional acquisition odds ledger")
        w.question({"id": "fictional_acquisition", "text": "Will the fictional company be acquired within one year?",
                    "yes": "A qualifying acquisition closes within one year.", "no": "No qualifying acquisition closes.",
                    "void": "The simulation is withdrawn.", "event_deadline": future, "resolve_after": future,
                    "resolution_source": "urn:fictional:acquisition", "event_group": "fictional_acquisition",
                    "domain": "simulation", "profile": "general", "kind": "simulation"})
        definitions = [("board_refresh", "The fictional board adds a transactions specialist.", "board", 1.2, [0.8, 2]),
                       ("strategic_review", "The fictional board announces a strategic review.", "board", 1.5, [1, 3]),
                       ("no_filing", "A fictional filing search returns no acquisition announcement.", "filings", 0.7, [0.4, 1.2])]
        imported = w.import_packet({"schema_version": "vorhersage.evidence.v1", "kind": "manual",
                                   "information_as_of": stamp, "created_at": stamp,
                                   "limitations": ["Entirely fictional; no claims about any real company."],
                                   "records": [{"id": id, "claim": claim, "value": None, "entity_ids": ["fictional_company"],
                                                "observed_at": stamp, "sources": [{"id": id, "url": "urn:fictional:" + id,
                                                "title": "Synthetic observation", "excerpt": claim, "retrieved_at": stamp}],
                                                "provenance": {"synthetic": True}} for id, claim, *_ in definitions]})
        refs = [r["evidence_ref"] for r in imported["records"]]
        spec = {"anchor": {"probability": 0.12, "basis": "assumed", "rationale": "Illustrative assumed annual acquisition rate."},
                "entries": [{"finding_id": id, "evidence_refs": [ref], "dependence_group": group,
                             "lr": lr, "lr_range": bounds, "direction": "supports" if lr > 1 else "opposes",
                             "rationale": "Subjective illustration, not an estimated effect."}
                            for (id, _, group, lr, bounds), ref in zip(definitions, refs)],
                "joint_declarations": [{"dependence_group": "board", "finding_ids": ["board_refresh", "strategic_review"],
                                        "lr": 1.6, "lr_range": [0.8, 3], "direction": "supports",
                                        "rationale": "The two board signals overlap; this replaces both individual ratios."}],
                "independence_rationale": "Assume the board group and filing search are conditionally independent given each outcome; this is only a demo.",
                "comparison_probability": 0.2}
        run = w.start({"question_id": "fictional_acquisition", "forecaster": "demo", "method": "Declared odds ledger demo",
                       "mode": "simulation", "information_as_of": stamp, "max_searches": 0, "max_extra_tasks": 0})["run_id"]
        common = {"rationale": "Fictional illustration.", "limitations": ["Assumptions are not fitted."], "evidence_refs": refs}
        payloads = {
            "prior": {**common, "method": "judgment", "probability": 0.12},
            "drivers": {"drivers": [{"name": "Acquisition process", "mechanism": "A buyer and board must agree.", "evidence_refs": refs}],
                        "yes_path": "Agreement and closing.", "no_path": "No agreement or no closing.", "unknowns": ["Buyer interest."]},
            "research": {"disposition": "assessed", "interpretation": "Fictional observations only.", "evidence_refs": refs,
                         "sources_checked": ["Synthetic fixture"], "unknowns": ["All real-world inputs."], "conflicts": []},
            "assessment": {**common, "method": "odds_ledger", "odds_ledger": spec},
            "review": {"decision": "retain", "rationale": "Retain for demonstration.", "evidence_refs": [],
                       "objections": [{"direction": "too_high", "objection": "Board signals may be routine.", "response": "Try a lower joint ratio."},
                                      {"direction": "too_low", "objection": "Talks may be private.", "response": "Try a higher filing ratio."}]},
            "issue": {"stopping_reason": "Demonstration complete.", "review_at": future,
                      "triggers": [{"description": "New acquisition filing.", "evidence_refs": refs}]}}
        while (step := w.next(run))["disposition"] == "actionable":
            w.submit(run, {"task_id": step["task"]["id"], "expected_revision": step["revision"],
                           "idempotency_key": step["task"]["id"], "payload": payloads[step["task"]["kind"]]})
        print(json.dumps(export(w.store, step["forecast_id"], output), indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("demo.html"))
