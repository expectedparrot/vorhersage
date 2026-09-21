"""A single-question front end to the existing, validated forecasting workflow.

A brief is deliberately not a resolvable question. Definition binds it to one
question and run in a single transaction. Task files retain the workflow's
revision and retry guards; the human interface never chooses a latest run.
"""

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .common import canonical, digest, now, require
from .store import Store
from .workflow import Workflow, verify_refs
from . import timeline, reference_research


BRIEF = "study_brief"
BINDING = "study_binding"


def active_binding(c):
    require(c.execute("SELECT 1 FROM artifacts WHERE id=?", (BINDING,)).fetchone(),
            "Define what counts first: use vorhersage define --deadline TIME --yes CRITERIA --source SOURCE.")
    row = c.execute("SELECT id FROM artifacts WHERE kind='study_revision_binding' ORDER BY rowid DESC LIMIT 1").fetchone()
    return Store.artifact(c, row[0] if row else BINDING)


def start(project, question, specification=None, **options):
    require(isinstance(question, str) and question.strip(), "Enter the question you want to forecast.")
    target = Path(project).resolve()
    destination = target / ".vorhersage"
    require(not destination.exists() and not destination.is_symlink(),
            "This folder already contains a forecast project. Use show or choose another --project folder.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".vorhersage-start-", dir=target.parent) as tmp:
        store = Store(tmp)
        store.init(question)
        with store.connect(True) as c:
            Store.put(c, BRIEF, {"question": question, "created_at": now()}, id=BRIEF)
        if specification is not None:
            define(Workflow(tmp), specification, **options)
        target.mkdir(parents=True, exist_ok=True)
        require(not destination.exists() and not destination.is_symlink(), "Project already exists.")
        store.path.parent.rename(destination)
    return show(Store(target))


def binding(store):
    with store.connect() as c:
        brief(c)
        require(c.execute("SELECT 1 FROM artifacts WHERE id=?", (BINDING,)).fetchone(),
                "Define what counts first: use vorhersage define --deadline TIME --yes CRITERIA --source SOURCE.")
        return active_binding(c)


def brief(c):
    require(c.execute("SELECT 1 FROM artifacts WHERE id=?", (BRIEF,)).fetchone(),
            "This is a portfolio project. Use status and explicit --run or --question options; "
            "use start in a new folder for the single-question workflow.")
    return Store.artifact(c, BRIEF, BRIEF)


def define(workflow, question, *, forecaster="user", method="declared judgment",
           research_status="not_started", workflow_name="standard", max_searches=60, max_extra_tasks=8,
           research_contract="structured_v2", research_effort="deep"):
    store = workflow.store
    with store.connect(True) as c:
        saved = brief(c)
        require(question["text"] == saved["question"], "Definition must retain the original question.")
        request = {"question": question, "forecaster": forecaster, "method": method,
                   "research_status": research_status, "workflow": workflow_name,
                   "research_effort": research_effort,
                   "max_searches": max_searches, "max_extra_tasks": max_extra_tasks}
        if c.execute("SELECT 1 FROM artifacts WHERE id=?", (BINDING,)).fetchone():
            previous = Store.artifact(c, BINDING, BINDING)
            require(previous["definition"] == request,
                    "This forecast already has a different definition. Its research remains tied to that definition.")
        else:
            workflow._question(c, question)
            run = workflow._start(c, {
                "question_id": question["id"], "forecaster": forecaster, "method": method,
                "mode": "simulation" if question["kind"] == "simulation" else "prospective",
                "information_as_of": now(), "research_status": research_status,
                "workflow": workflow_name, "max_searches": max_searches, "max_extra_tasks": max_extra_tasks,
                "research_effort": research_effort,
                "research_contract": research_contract,
            })
            Store.put(c, BINDING, {"question_id": question["id"], "question_version": 1,
                                  "run_id": run["run_id"], "definition": request}, id=BINDING)
    return show(store)


def revise(workflow, *, reason, refs=(), expected_forecast=None):
    """Append an explicit study binding; never replace the original binding/run."""
    require(reason and reason.strip(), "Explain why the forecast needs revision.")
    store = workflow.store
    with store.connect(True) as c:
        brief(c)
        linked = active_binding(c)
        old_run, old_state, _ = Store.run(c, linked["run_id"])
        request = {"reason": reason, "evidence_refs": list(refs)}
        if not old_state["forecast_id"]:
            require(linked.get("revision_request") == request and
                    (expected_forecast is None or old_run.get("previous_forecast_id") == expected_forecast),
                    "Finish the active research/revision before starting another revision.")
        else:
            previous = old_state["forecast_id"]
            require(expected_forecast is None or previous == expected_forecast, "The issued forecast changed; inspect show before revising.")
            cutoff = now()
            verify_refs(c, refs, cutoff, context="new revision cutoff")
            spec = {k: old_run[k] for k in ("question_id", "question_version", "forecaster", "method", "mode", "max_searches", "max_extra_tasks")}
            spec.update(information_as_of=cutoff, previous_forecast_id=previous,
                        research_status="in_progress", research_contract=old_run.get("research_contract", "structured_v2"),
                        research_effort=old_run.get("research_effort", "standard"),
                        reference_policy=old_run.get("reference_policy", "legacy"),
                        model_semantics_version=old_run.get("model_semantics_version", 0),
                        evidence_transfer_version=old_run.get("evidence_transfer_version", 0),
                        workflow=old_run.get("workflow", "standard"))
            started = workflow._start(c, spec)
            run_id = started["run_id"]
            _, state, _ = Store.run(c, run_id)
            if spec["workflow"] == "standard":
                state["pending"] = [t for t in state["pending"] if t["kind"] in ("intake", "assessment", "review", "issue")]
                state["coverage"] = copy.deepcopy(old_state["coverage"])
            state["model_map"] = copy.deepcopy(old_state.get("model_map"))
            for key in ("reference_class", "reference_class_design", "reference_classes", "reference_searches",
                        "reference_class_analysis", "reference_analysis_history"):
                if key in old_state:
                    state[key] = copy.deepcopy(old_state[key])
            state["evidence_refs"] = list({canonical(r): r for r in old_state["evidence_refs"] + list(refs)}.values())
            state["prior_record"] = {"timing": "not_applicable", "qualification": "Revision of an issued forecast; new evidence is not a pre-research prior."}
            state["artifact_ids"] = list(dict.fromkeys(state["artifact_ids"] + old_state["artifact_ids"]))
            record = {**linked, "run_id": run_id, "previous_forecast_id": previous,
                      "revision_request": request, "created_at": cutoff}
            binding_id = Store.put(c, "study_revision_binding", record, run_id=run_id)
            state["artifact_ids"].append(binding_id)
            c.execute("UPDATE runs SET state=? WHERE id=?", (canonical(state), run_id))
            Store.event(c, "study.revise", record)
    return show(store)


def next_task(workflow, output=None, run_id=None):
    result = workflow.next(run_id or binding(workflow.store)["run_id"])
    if result["disposition"] == "actionable":
        result["submission"] = {
            "task_id": result["task"]["id"], "expected_revision": result["revision"],
            "idempotency_key": "study-" + digest([result["run_id"], result["revision"]])[:24],
            "payload": ({"method": "timeline_model", "timeline_model_id": result["task"]["timeline_context"]["timeline_model_id"]}
                        if result["task"]["kind"] == "assessment" and result["context"]["run"].get("workflow") == "timeline" else None),
        }
    if output:
        require(result["disposition"] == "actionable", "There is no research task to export: " + result["disposition"] + ".")
        # Never destroy an agent's in-progress answer.
        with Path(output).open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, allow_nan=False)
            f.write("\n")
        result["task_file"] = str(Path(output).resolve())
    return result


def submit(workflow, document, answer=None, usage=None, run_id=None):
    require(isinstance(document, dict), "A task file must contain a JSON object.")
    selected = run_id or binding(workflow.store)["run_id"]
    require(document.get("run_id") == selected, "Task file belongs to a different forecast.")
    require(isinstance(document.get("submission"), dict),
            "Use the task file written by next --output; fill its submission.payload.")
    submission = copy.deepcopy(document["submission"])
    if answer is not None:
        submission["payload"] = answer
    if usage is not None:
        submission["usage"] = usage
    return workflow.submit(selected, submission)


def show(store):
    with store.connect() as c:
        saved = brief(c)
        result = {"project": str(store.root), "question": saved["question"], "stage": "definition",
                  "probability": None, "issued": False}
        if not c.execute("SELECT 1 FROM artifacts WHERE id=?", (BINDING,)).fetchone():
            return result
        linked = active_binding(c)
        run, state, revision = Store.run(c, linked["run_id"])
        task = Workflow(store.root)._next(c, linked["run_id"])
        work = [Store.artifact(c, row[0], "task_result") for row in c.execute(
            "SELECT id FROM artifacts WHERE kind='task_result' AND run_id=? ORDER BY created_at,id", (linked["run_id"],))]
        work.sort(key=lambda item: item["revision"])
        result.update(definition=run["question"], probability=state["probability"],
                      issued=bool(state["forecast_id"]), workflow=run.get("workflow", "standard"),
                      mode=run["mode"], forecaster=run["forecaster"], method=run["method"],
                      completed_tasks=revision, coverage=state["coverage"],
                      findings=verify_refs(c, state["evidence_refs"], run["information_as_of"]),
                      work=work, next=task, stage=task.get("task", {}).get("kind", task["disposition"]))
        result.update(model_map=state.get("model_map"), model_challenge=state.get("model_challenge"),
                      reference_research=reference_research.summary(state),
                      research_priorities=reference_research.priorities(state),
                      concern_resolutions=state.get("concern_resolutions", []), reference_class=state.get("reference_class"),
                      research_plan=state.get("research_plan"), inquiry_answers=state.get("inquiry_answers", {}),
                      parameter_support=state.get("parameter_support", []), sensitivity=state.get("sensitivity"),
                      previous_forecast=Store.artifact(c, run["previous_forecast_id"], "forecast") if run.get("previous_forecast_id") else None,
                      forecast_id=state["forecast_id"])
        if state.get("timeline_model_id"):
            model = timeline.read(c, state["timeline_model_id"])["specification"]
            result["model"] = {"specification": model, "analysis": timeline.analyze(model)}
    return result
