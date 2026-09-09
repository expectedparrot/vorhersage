"""Run a constant-0.5 control through every workflow step; no model forecasts.

The caller prepares the bundle first. The workflow loop reads only agent/cases.json.
Labels are opened by the evaluator after all forecasts have been issued.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def payload(kind, cutoff, deadline):
    reason = "Constant-0.5 software control; no research or model judgment performed."
    limitations = ["This control does not measure agent forecasting skill."]
    return {
        "prior": {"method": "judgment", "probability": 0.5, "rationale": reason,
                  "limitations": limitations, "evidence_refs": []},
        "drivers": {"drivers": [{"name": "Control", "mechanism": reason, "evidence_refs": []}],
                    "yes_path": "Not researched in this control.", "no_path": "Not researched in this control.",
                    "unknowns": ["All event-specific mechanisms remain unassessed."]},
        "research": {"disposition": "unknown", "interpretation": reason, "evidence_refs": [],
                     "sources_checked": [], "unknowns": ["No archived research supplied."], "conflicts": []},
        "assessment": {"method": "judgment", "probability": 0.5, "rationale": reason,
                       "limitations": limitations, "evidence_refs": []},
        "review": {"decision": "retain", "rationale": reason, "evidence_refs": [],
                   "objections": [{"direction": "too_high", "objection": "The event may be rare.",
                                   "response": "The control deliberately remains constant."},
                                  {"direction": "too_low", "objection": "The event may be common.",
                                   "response": "The control deliberately remains constant."}]},
        "issue": {"stopping_reason": reason, "review_at": deadline,
                  "triggers": [{"description": "Replace this control with a separately labeled research experiment.",
                                "evidence_refs": []}]},
    }[kind]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    args.project.mkdir(parents=True, exist_ok=False)
    inputs = args.project / "inputs"
    inputs.mkdir()
    transcript = []

    def cli(*argv):
        result = subprocess.run([sys.executable, "-m", "vorhersage", "--project", str(args.project), *argv],
                                text=True, capture_output=True, check=True)
        envelope = json.loads(result.stdout)
        transcript.append({"argv": list(argv), "data": envelope["data"]})
        return envelope["data"]

    cli("init", "--name", "Halawi historical replay software control")
    cases_path = args.bundle / "agent/cases.json"
    cases = json.loads(cases_path.read_text())["cases"]
    forecasts = []
    for case in cases:
        run = cli("benchmark", "start", "--cases", str(cases_path), "--case", case["id"],
                  "--forecaster", "control:workflow_half", "--method", "constant-0.5 software control")
        while True:
            nxt = cli("next", "--run", run["run_id"])
            if nxt["disposition"] != "actionable":
                forecasts.append(nxt["forecast_id"])
                break
            task = nxt["task"]
            body = {"task_id": task["id"], "expected_revision": nxt["revision"],
                    "idempotency_key": task["id"],
                    "payload": payload(task["kind"], case["information_as_of"], case["question"]["event_deadline"])}
            path = inputs / (task["id"] + ".json")
            path.write_text(json.dumps(body, indent=2) + "\n")
            cli("submit", "--run", run["run_id"], "--from", str(path))
    policy = {"forecast_ids": forecasts,
              "forecasters": ["control:workflow_half", "baseline:half", "baseline:crowd"],
              "experiment": "Software smoke test on real historical questions; no model calls.",
              "contamination_assessment": "No model evaluated; historical wording and evidence remain unaudited."}
    policy_path = args.project / "evaluation_policy.json"
    policy_path.write_text(json.dumps(policy, indent=2) + "\n")
    result = cli("benchmark", "evaluate", "--cases", str(cases_path),
                 "--labels", str(args.bundle / "evaluator/labels.json"),
                 "--manifest", str(args.bundle / "manifest.json"), "--from", str(policy_path))
    (args.project / "evaluation.json").write_text(json.dumps(result, indent=2) + "\n")
    summary = {"kind": "software_control_only", "questions": len(cases), "model_calls": 0,
               "evaluation_id": result["evaluation_id"], "summaries": result["summaries"],
               "doctor": cli("doctor"), "limitations": result["limitations"]}
    (args.project / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.project / "transcript.json").write_text(json.dumps(transcript, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
