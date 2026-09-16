"""Build hypothetical, unweighted deadline models in a separate example project.

No new research, probability, or forecast issuance. Run from an installed checkout:
    python examples/waymo_boston_2029/timeline/build.py
"""

import copy
import json
from pathlib import Path

from vorhersage import timeline
from vorhersage.timeline_reports import export
from vorhersage.workflow import Workflow

ROOT = Path(__file__).resolve().parent
CUTOFF = "2026-09-15T23:04:02Z"


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def build_model(question, sequential=False):
    def node(id, kind, condition, parents, rationale, parameter=None, **extra):
        return {"id": id, "kind": kind, "completion_condition": condition, "parents": parents,
                "state": "pending", "rationale": rationale, "evidence_refs": [],
                **({"parameter_id": parameter} if parameter else {}), **extra}

    parameters = [
        {"id": "authorization_date", "kind": "date", "description": "When usable permission for qualifying paid driverless service takes effect, including any required approvals."},
        {"id": "preparation_days", "kind": "duration_days", "description": "Elapsed time to complete Boston operational preparation from its permitted start."},
        {"id": "public_rollout_days", "kind": "duration_days", "description": "Elapsed time from permission and readiness to actual paid general-public service matching every YES criterion."},
    ]
    return {
        "id": "waymo_sequential" if sequential else "waymo_parallel", "version": 1,
        "question": {"question_id": question["id"], "version": 1},
        "information_as_of": CUTOFF, "deadline": question["event_deadline"], "deadline_rule": "before",
        "description": "Hypothetical preparation " + ("after authorization." if sequential else "in parallel with authorization.") + " Dates and durations are illustrative assumptions, not research findings.",
        "target": "public_launch", "parameters": parameters,
        "nodes": [
            node("authorization", "event", "Usable permission is effective.", [],
                 "Permission is compressed into one hypothetical effective date; actual routes require research.", "authorization_date"),
            node("preparation", "task", "Local operational preparation is complete.", ["authorization"] if sequential else [],
                 "Hypothesis: preparation waits for permission." if sequential else "Hypothesis: this preparation can occur before permission.",
                 "preparation_days", not_before="2028-03-01T00:00:00Z"),
            node("ready", "all", "Both permission and operational readiness are available.", ["authorization", "preparation"],
                 "This model requires both milestones before public rollout."),
            node("public_launch", "task", "Paid public driverless trips inside Boston meet the question's complete YES definition.", ["ready"],
                 "The rollout delay represents the gap to general public access, not merely selected-rider access.", "public_rollout_days"),
        ],
        "scenarios": [
            {"id": id, "description": description, "evidence_refs": [], "assessments": [
                {"parameter_id": pid, "basis": "assumed", "value": value, "evidence_refs": [],
                 "rationale": "Illustrative stress-test input; not estimated from Waymo or legislative history."}
                for pid, value in [("authorization_date", date), ("preparation_days", 184), ("public_rollout_days", 61)]
            ]}
            for id, description, date in [
                ("early", "Hypothetical July 2027 permission", "2027-07-01T00:00:00Z"),
                ("late", "Hypothetical July 2028 permission", "2028-07-01T00:00:00Z"),
                ("never", "Hypothetical route that never obtains permission", "never"),
            ]
        ],
        "limitations": [
            "Illustrative structural comparison, not a new Waymo probability or an endorsement of either dependency hypothesis.",
            "Scenarios are not an exhaustive partition and have no weights. Counts of successful cases have no probabilistic meaning.",
            "March 2028 preparation start and 184/61 elapsed-day durations are invented for this example; they are not calendar-month estimates.",
            "No new evidence was gathered. Authorization pathways, partial overlap, readiness, weather constraints and launch access need separate research.",
        ],
    }


def main():
    question = json.loads((ROOT.parent / "question.json").read_text())
    w = Workflow(ROOT / "project")
    if not (ROOT / "project/.vorhersage/state.sqlite").exists():
        w.store.init("Waymo deadline structure examples — no forecast")
        w.add_profile({"id": "robotaxi_launch", "description": "Model-parameter research example.", "domains": ["authorization", "preparation", "public_access"]})
        w.question(question)
    parallel, sequential = build_model(question), build_model(question, True)
    draft = copy.deepcopy(parallel)
    draft.update(id="waymo_unresolved", description="Starting structure with unresolved inputs and no probability.")
    for s in draft["scenarios"]:
        s["assessments"] = []
    ids = {}
    for name, model in [("draft", draft), ("parallel", parallel), ("sequential", sequential)]:
        write(name + ".json", model)
        ids[name] = timeline.add(w.store, model)["timeline_model_id"]
    write("models.json", ids)
    write("comparison.json", timeline.compare(w.store, ids["parallel"], ids["sequential"]))
    write("gaps.json", timeline.gaps(draft))
    write("run.json", {"question_id": question["id"], "question_version": 1, "forecaster": "timeline_reviewer",
                       "method": "timeline structure research", "workflow": "timeline", "mode": "prospective",
                       "information_as_of": CUTOFF, "cutoff_policy": "fixed", "research_status": "not_started",
                       "max_searches": 10, "max_extra_tasks": 2})
    export(w.store, ids["parallel"], ROOT / "comparison.html", ids["sequential"])
    assert w.doctor()["ok"]
    print(json.dumps({"models": ids, "report": str(ROOT / "comparison.html"), "forecasts_issued": 0}, indent=2))


if __name__ == "__main__":
    main()
