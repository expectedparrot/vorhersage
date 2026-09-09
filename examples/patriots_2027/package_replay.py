#!/usr/bin/env python3
"""Run the researched Patriots judgments through the general package and Epiq."""

import argparse
import json
from pathlib import Path

from vorhersage.common import now
from vorhersage.evidence import Epiq
from vorhersage.workflow import Workflow


def run(project, db, source):
    here = Path(__file__).resolve().parent
    case = json.loads((here / "researched_case.json").read_text())
    w = Workflow(project)
    w.store.init("Patriots package regression")
    ids = list(case["captures"])
    finding_ids = [f["id"] for r in case["responses"].values() for f in r["payload"].get("findings", [])]
    packet = Epiq(db, source).freeze({"information_as_of": case["information_as_of"], "cells": [
        *[{"kind": "ResearchCapture", "subject": id, "question": "source_capture"} for id in ids],
        *[{"kind": "ResearchFinding", "subject": id, "question": "finding_record"} for id in finding_ids]]})
    imported = w.import_packet(packet)
    refs = {r["provenance"]["selection"]["subject"]: {"packet_id": imported["packet_id"], "record_id": r["id"]} for r in packet["records"]}
    q = case["responses"]["define"]["payload"]["question"]
    w.question({"id": "patriots_lxi", "text": q["text"], "yes": q["yes"] + " " + q["rescheduling"],
                "no": q["no"], "void": q["void"], "event_deadline": q["resolution_deadline"],
                "resolve_after": "2027-04-01T00:00:00Z", "resolution_source": q["resolution_source"],
                "event_group": "nfl_2026", "domain": "sports", "profile": "team_championship", "kind": "real"})
    # Replay is explicitly separated from the prospective track, even though the event is unresolved.
    id = w.start({"question_id": "patriots_lxi", "forecaster": "agent:recorded-patriots", "method": "researched conditional judgment replay",
                  "mode": "retrospective", "information_as_of": case["information_as_of"], "max_searches": 0, "max_extra_tasks": 0})["run_id"]
    assumptions = case["responses"]["update"]["payload"]["assumptions"]
    while (nxt := w.next(id))["disposition"] == "actionable":
        task = nxt["task"]
        kind = task["kind"]
        if kind == "prior":
            history = next(r["value"]["observation"]["super_bowl_results"] for r in packet["records"] if r["provenance"]["selection"]["subject"] == "c_history")
            by_season = {r["season"]: r for r in history}
            p = {"method": "reference_class", "selection_rule": "All 25 runners-up from seasons 2000–2024; outcome is next-season title.",
                 "rationale": "Descriptive context, not a calibrated team probability.", "limitations": ["Small selected cohort with repeated franchises."], "evidence_refs": [refs["c_history"]],
                 "cases": [{"id": str(y), "outcome": int(by_season[y]["runner_up"] == by_season[y+1]["winner"]), "evidence_refs": [refs["c_history"]]} for y in range(2000, 2025)]}
        elif kind == "drivers":
            p = {"drivers": [{"name": "Playoff path", "mechanism": "Qualification precedes the AFC title and Super Bowl.", "evidence_refs": [refs["f_season"]]}],
                 "yes_path": "Qualify and win the conference and championship game.", "no_path": "Miss qualification or lose in the postseason.", "unknowns": ["Parameters are unfitted judgments."]}
        elif kind == "research":
            domain = task["domain"]
            if domain == "health":
                coverage = {"disposition": "assessed", "interpretation": "Opening-game injuries are not established season-long impairments.", "finding_ids": ["f_opening_injuries"]}
            else:
                coverage = case["responses"]["fundamentals"]["payload"]["coverage"][domain]
            p = {"disposition": coverage["disposition"], "interpretation": coverage["interpretation"],
                 "evidence_refs": [refs[f] for f in coverage["finding_ids"]], "sources_checked": ["Previously recorded Epiq evidence"],
                 "unknowns": ["No fresh research or fitted team-strength model."], "conflicts": []}
        elif kind == "assessment":
            components = []
            for name, given, source_key in (("playoffs", None, "playoffs"), ("afc", "playoffs", "afc_given_playoffs"), ("target", "afc", "title_given_afc")):
                assumption = assumptions[source_key]
                components.append({"id": name, "conditional_on": given, "probability": assumption["value"], "rationale": assumption["rationale"],
                                   "evidence_refs": [refs[f] for f in assumption["finding_ids"]]})
            p = {"method": "conditional_path", "components": components, "nested_events_justification": "Winning the title requires winning the AFC, which requires playoff qualification.",
                 "rationale": "Preserve the recorded second-pass judgments, formed after seeing market odds.",
                 "limitations": case["responses"]["update"]["payload"]["limitations"], "evidence_refs": []}
        elif kind == "review":
            p = {"decision": "retain", "rationale": "Retain the recorded judgment for integration regression, not a new live forecast.", "evidence_refs": [],
                 "objections": [{"direction": "too_high", "objection": "Tougher opposition and protection problems could dominate.", "response": "The recorded judgment allows substantial failure probability."},
                                {"direction": "too_low", "objection": "Quarterback performance and roster upside could persist.", "response": "The forecast reflects contention without assuming dominance."}]}
        else:
            p = {"stopping_reason": "Completed the package regression using frozen evidence and recorded judgments.",
                 "review_at": case["responses"]["issue"]["payload"]["review_at"],
                 "triggers": [{"description": "A material source correction requires fresh research and reassessment.", "evidence_refs": [refs["f_protection"]]}]}
        w.submit(id, {"task_id": task["id"], "expected_revision": nxt["revision"], "idempotency_key": task["id"], "payload": p})
    result = {"run_id": id, "forecast_id": nxt["forecast_id"], "packet_id": imported["packet_id"],
              "report": w.report("patriots_lxi"), "doctor": w.doctor()}
    assert result["report"]["forecasts"][0]["probability"] == 0.06048
    Path(project, "package_report.json").write_text(json.dumps(result, indent=2) + "\n")
    return {"forecast_id": nxt["forecast_id"], "probability": 0.06048, "mode": "retrospective", "doctor": result["doctor"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--db", type=Path, default=Path(__file__).resolve().parent / "epiq_integration/patriots.sqlite")
    parser.add_argument("--epiq-source", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.project, args.db, args.epiq_source), indent=2))
