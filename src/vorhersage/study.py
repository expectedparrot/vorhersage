"""A single-question front end to the existing, validated forecasting workflow.

A brief is deliberately not a resolvable question. Definition binds it to one
question and run in a single transaction. Task files retain the workflow's
revision and retry guards; the human interface never chooses a latest run.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .common import digest, now, require
from .store import Store
from .workflow import Workflow, verify_refs
from . import timeline


BRIEF = "study_brief"
BINDING = "study_binding"


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
        return Store.artifact(c, BINDING, BINDING)


def brief(c):
    require(c.execute("SELECT 1 FROM artifacts WHERE id=?", (BRIEF,)).fetchone(),
            "This is a portfolio project. Use status and explicit --run or --question options; "
            "use start in a new folder for the single-question workflow.")
    return Store.artifact(c, BRIEF, BRIEF)


def define(workflow, question, *, forecaster="user", method="declared judgment",
           research_status="not_started", workflow_name="standard", max_searches=20, max_extra_tasks=2):
    store = workflow.store
    with store.connect(True) as c:
        saved = brief(c)
        require(question["text"] == saved["question"], "Definition must retain the original question.")
        request = {"question": question, "forecaster": forecaster, "method": method,
                   "research_status": research_status, "workflow": workflow_name,
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
            })
            Store.put(c, BINDING, {"question_id": question["id"], "question_version": 1,
                                  "run_id": run["run_id"], "definition": request}, id=BINDING)
    return show(store)


def next_task(workflow, output=None):
    linked = binding(workflow.store)
    result = workflow.next(linked["run_id"])
    if result["disposition"] == "actionable":
        result["submission"] = {
            "task_id": result["task"]["id"], "expected_revision": result["revision"],
            "idempotency_key": "study-" + digest([result["run_id"], result["revision"]])[:24],
            "payload": None,
        }
    if output:
        require(result["disposition"] == "actionable", "There is no research task to export: " + result["disposition"] + ".")
        # Never destroy an agent's in-progress answer.
        with Path(output).open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, allow_nan=False)
            f.write("\n")
        result["task_file"] = str(Path(output).resolve())
    return result


def submit(workflow, document):
    require(isinstance(document, dict), "A task file must contain a JSON object.")
    linked = binding(workflow.store)
    require(document.get("run_id") == linked["run_id"], "Task file belongs to a different forecast.")
    require(isinstance(document.get("submission"), dict),
            "Use the task file written by next --output; fill its submission.payload.")
    return workflow.submit(linked["run_id"], document["submission"])


def show(store):
    with store.connect() as c:
        saved = brief(c)
        result = {"project": str(store.root), "question": saved["question"], "stage": "definition",
                  "probability": None, "issued": False}
        if not c.execute("SELECT 1 FROM artifacts WHERE id=?", (BINDING,)).fetchone():
            return result
        linked = Store.artifact(c, BINDING, BINDING)
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
        if state.get("timeline_model_id"):
            model = timeline.read(c, state["timeline_model_id"])["specification"]
            result["model"] = {"specification": model, "analysis": timeline.analyze(model)}
    return result
