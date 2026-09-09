#!/usr/bin/env python3
"""Exercise the installed CLI in separate processes using a fictional portfolio.

Creates a fresh project and saves every authored input and next-task response.
No web access or model calls. This is a behavioral fixture, not a skill benchmark.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def timestamp(days=0):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class Walkthrough:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.inputs = self.root / "inputs"
        self.inputs.mkdir(parents=True, exist_ok=False)
        self.seq = 0

    def save(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n")
        return path

    def call(self, *args, data=None):
        if data is not None:
            path = self.save(f"inputs/{self.seq:03d}_{args[0]}.json", data)
            self.seq += 1
            args = (*args, "--from", str(path))
        p = subprocess.run([sys.executable, "-m", "vorhersage", "--project", str(self.root), *args],
                           text=True, capture_output=True, check=False)
        if p.returncode:
            raise RuntimeError(p.stderr or p.stdout)
        return json.loads(p.stdout)["data"]

    def evidence(self, id, claim):
        observed = timestamp()
        result = self.call("packet", "import", data={
            "schema_version": "vorhersage.evidence.v1", "kind": "manual", "information_as_of": observed,
            "created_at": timestamp(), "limitations": ["Entirely fictional walkthrough evidence."],
            "records": [{"id": id, "claim": claim, "value": claim, "entity_ids": ["fictional_factory"],
                         "observed_at": observed, "provenance": {"synthetic": True},
                         "sources": [{"id": id, "url": "urn:vorhersage:fictional:" + id,
                                      "title": "Fictional factory fixture", "excerpt": claim, "retrieved_at": observed}]}]})
        return result["records"][0]["evidence_ref"]

    def forecast(self, qid, forecaster, refs, estimate, previous=None):
        spec = {"question_id": qid, "forecaster": forecaster, "method": "documented synthetic judgment",
                "mode": "simulation", "information_as_of": timestamp(), "max_searches": 4, "max_extra_tasks": 1}
        if previous:
            spec["previous_forecast_id"] = previous
        run = self.call("run", "start", data=spec)["run_id"]
        while True:
            nxt = self.call("next", "--run", run)
            self.save(f"tasks/{run}_{nxt['revision']:02d}.json", nxt)
            if nxt["disposition"] != "actionable":
                return nxt["forecast_id"]
            kind = nxt["task"]["kind"]
            payload = {
                "prior": {"method": "judgment", "probability": 0.5, "rationale": "An assumed neutral starting point.",
                          "limitations": ["Not an empirical reference class."], "evidence_refs": []},
                "drivers": {"drivers": [{"name": "Readiness", "mechanism": "Dispatch needs a ready production line.", "evidence_refs": refs}],
                            "yes_path": "Readiness permits a shipment.", "no_path": "A remaining dependency blocks it.", "unknowns": ["Delay duration."]},
                "research": {"disposition": "assessed", "interpretation": "The fictional source informs this domain; uncertainty remains.",
                             "evidence_refs": refs, "sources_checked": ["Fictional fixture"], "unknowns": ["Execution risk."], "conflicts": []},
                "assessment": {"method": "judgment", "probability": estimate, "rationale": "An unfitted judgment supplied by this fixture.",
                               "limitations": ["Exercises software behavior only."], "evidence_refs": refs},
                "review": {"decision": "retain", "rationale": "Retain the fixture's probability after considering both directions.", "evidence_refs": refs,
                           "objections": [{"direction": "too_high", "objection": "Dispatch may fail.", "response": "The estimate allows failure."},
                                          {"direction": "too_low", "objection": "Readiness may suffice.", "response": "The estimate allows success."}]},
                "issue": {"stopping_reason": "Bounded fixture research completed.", "review_at": timestamp(0.5),
                          "triggers": [{"description": "New information about dispatch.", "evidence_refs": refs}]},
            }[kind]
            self.call("submit", "--run", run, data={"task_id": nxt["task"]["id"], "expected_revision": nxt["revision"],
                      "idempotency_key": nxt["task"]["id"], "payload": payload,
                      "usage": {"searches": 0, "cost_usd": 0, "model_calls": 0}})

    def run(self):
        self.call("init", "--name", "Fictional factory forecasting portfolio")
        initial = self.evidence("readiness", "Fictional initial status: preparation is underway; dispatch remains uncertain.")
        summaries = []
        for location, estimate, outcome in (("east", 0.4, "yes"), ("west", 0.3, "no")):
            qid = "factory_" + location
            self.call("question", "add", data={"id": qid, "text": f"Will fictional factory {location} ship by its deadline?",
                      "yes": "The fixture records a qualifying shipment by the deadline.",
                      "no": "The fixture establishes that no qualifying shipment will occur by the deadline.",
                      "void": "The fictional event is withdrawn.", "event_deadline": timestamp(1), "resolve_after": timestamp(2),
                      "resolution_source": "urn:vorhersage:fictional:dispatch", "event_group": qid,
                      "domain": "operations", "profile": "general", "kind": "simulation"})
            baseline = self.forecast(qid, "baseline:half", [initial], 0.5)
            first = self.forecast(qid, "agent:fixture", [initial], estimate)
            final = first
            if location == "east":
                changed = self.evidence("readiness_update", "Fictional update: the remaining readiness dependency was completed.")
                self.call("signal", data={"question_id": qid, "reason": "Readiness changed.", "idempotency_key": "readiness_update", "evidence_refs": [initial]})
                self.save("monitor_before_revision.json", self.call("monitor"))
                final = self.forecast(qid, "agent:fixture", [initial, changed], 0.75, previous=first)
            # Outcome evidence enters only after all forecasts for this question have issued.
            resolved = self.evidence("resolution_" + location,
                "Synthetic resolution: " + ("a qualifying shipment occurred." if outcome == "yes" else "the factory was permanently closed without shipping."))
            self.call("resolve", data={"question_id": qid, "question_version": 1, "outcome": outcome,
                      "known_at": timestamp(), "reason": "Fictional outcome under the stated criteria.", "evidence_refs": [resolved],
                      "previous_resolution_id": None, "idempotency_key": "resolve_" + qid})
            report = self.call("report", "--question", qid)
            self.save(qid + "_report.json", report)
            summaries.append({"question_id": qid, "baseline": baseline, "first_forecast": first, "final_forecast": final})
        evaluation = self.call("evaluate", data={"question_versions": [{"question_id": r["question_id"], "version": 1} for r in summaries],
                               "forecasters": ["agent:fixture", "baseline:half"], "cutoff": timestamp(),
                               "resolution_as_of": timestamp(), "mode": "simulation"})
        self.save("evaluation.json", evaluation)
        doctor = self.call("doctor")
        result = {"questions": summaries, "evaluation_id": evaluation["evaluation_id"], "doctor": doctor,
                  "matched_brier": {k: v["matched_brier"] for k, v in evaluation["summaries"].items()},
                  "limitations": "Fictional software acceptance fixture; scores do not demonstrate forecasting skill."}
        self.save("summary.json", result)
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    print(json.dumps(Walkthrough(parser.parse_args().project).run(), indent=2))
