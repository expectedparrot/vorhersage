"""Editable, unweighted timeline plans compiled into immutable timeline models.

Plans are ordinary TOML working files. Incomplete graphs are allowed while
building; saving applies the full timeline validator and evidence rules.
"""

import json
import os
import tempfile
import tomllib
from pathlib import Path

from .common import now, require, time
from .schemas import TEXT, TIME, array, enum, obj, validate as validate_schema
from .store import Store
from . import timeline

STEP = obj({"id": TEXT, "description": TEXT, "kind": enum("date", "duration"),
            "after": array(), "rationale": TEXT})
PLAN = obj({"name": TEXT, "question": TEXT, "question_version": {"type": "integer", "minimum": 1},
            "as_of": TIME, "deadline": TIME, "deadline_rule": enum("before", "on_or_before"),
            "description": TEXT, "target": TEXT, "steps": array(STEP)},
           ["name", "question", "question_version", "as_of", "deadline", "deadline_rule", "description"])


def validate(plan):
    validate_schema(plan, PLAN)
    require(time(plan["as_of"]) < time(plan["deadline"]), "Plan cutoff must precede its deadline.")
    require(time(plan["as_of"]) <= time(now()), "Plan cutoff cannot be in the future.")
    steps = plan.get("steps", [])
    ids = {s["id"] for s in steps}
    require(len(ids) == len(steps), "Step names must be unique.")
    require(len(steps) <= 100, "A timeline supports at most 100 steps.")
    for step in steps:
        require(len(step["after"]) == len(set(step["after"])) and set(step["after"]) <= ids,
                "A prerequisite must name an existing step, without duplicates.")
        require(step["id"] not in step["after"], "A step cannot depend on itself.")
        require(step["kind"] != "date" or not step["after"],
                "A date milestone has no prerequisites; use a duration step after prerequisites.")
    require("target" not in plan or plan["target"] in ids, "The target must name an existing step.")
    return plan


def read(path):
    return validate(tomllib.loads(Path(path).read_text(encoding="utf-8")))


def text(plan):
    """Serialize our small TOML vocabulary without a runtime dependency."""
    quote = lambda value: json.dumps(value, ensure_ascii=False, allow_nan=False)
    lines = ["# Working plan: dates, durations and scenario weights are not assigned."]
    lines.extend(f"{key} = {quote(value)}" for key, value in plan.items() if key != "steps")
    for step in plan.get("steps", []):
        lines += ["", "[[steps]]", *[f"{key} = {quote(value)}" for key, value in step.items()]]
    return "\n".join(lines) + "\n"


def new(store, path, *, question_id=None, name=None, as_of=None, description=None, deadline_rule="before"):
    path = Path(path)
    require(path.suffix == ".toml", "Use a .toml filename for an editable plan.")
    with store.connect() as c:
        ids = [row[0] for row in c.execute("SELECT DISTINCT id FROM questions")]
        if question_id is None:
            require(len(ids) == 1, "Select --question when the project has zero or multiple questions.")
            question_id = ids[0]
        question = Store.question(c, question_id)
    spec = question["specification"]
    plan = validate({"name": name or path.stem, "question": spec["id"], "question_version": question["version"],
                     "as_of": as_of or now(), "deadline": spec["event_deadline"], "deadline_rule": deadline_rule,
                     "description": description or spec["text"], "steps": []})
    with path.open("x", encoding="utf-8") as f:
        f.write(text(plan))
    return {"path": str(path), "plan": plan}


def step(path, id, description, *, after=(), date=False, target=False, rationale=None):
    path = Path(path)
    # Serialize writers to the same working file; unlike saved models, it is editable.
    lock = path.with_name(path.name + ".lock")
    with lock.open("x"):
        try:
            plan = read(path)
            item = {"id": id, "description": description, "kind": "date" if date else "duration",
                    "after": list(after), "rationale": rationale or "Provisional dependency; verify during research."}
            existing = next((s for s in plan.get("steps", []) if s["id"] == id), None)
            require(existing is None or existing == item,
                    "This step already has a different definition. Edit the TOML file to change it.")
            if existing is None:
                plan.setdefault("steps", []).append(item)
            if target:
                require(plan.get("target", id) == id, "A target is already selected. Edit the TOML file to change it.")
                plan["target"] = id
            validate(plan)
            # Validate and serialize before replacing the original file.
            contents = text(plan)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
                    temporary = Path(f.name)
                    f.write(contents)
                os.replace(temporary, path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        finally:
            lock.unlink()
    return {"path": str(path), "plan": plan, "step": item}


def compile(plan):
    validate(plan)
    require(plan.get("steps"), "Add at least one step to the plan.")
    require(plan.get("target"), "Mark the step that satisfies the question with --target, or set target in the TOML file.")
    spec = {"id": plan["name"], "version": 1,
            "question": {"question_id": plan["question"], "version": plan["question_version"]},
            "description": plan["description"], "information_as_of": plan["as_of"],
            "deadline": plan["deadline"], "deadline_rule": plan["deadline_rule"], "target": plan["target"],
            "parameters": [{"id": s["id"], "description": s["description"],
                            "kind": "date" if s["kind"] == "date" else "duration_days"} for s in plan["steps"]],
            "nodes": [{"id": s["id"], "completion_condition": s["description"], "parents": s["after"],
                       "kind": "event" if s["kind"] == "date" else "task", "parameter_id": s["id"],
                       "state": "pending", "rationale": s["rationale"], "evidence_refs": []} for s in plan["steps"]],
            "scenarios": [{"id": "draft", "description": "Unresolved research plan; no probability assigned.",
                           "evidence_refs": [], "assessments": [
                               {"parameter_id": s["id"], "basis": "unresolved", "evidence_refs": [],
                                "rationale": "Research must establish this date or duration."} for s in plan["steps"]]}],
            "limitations": ["Provisional dependency structure. All dates and durations remain unknown; no weights assigned."]}
    timeline.validate(spec)
    return spec


def save(store, path):
    return timeline.add(store, compile(read(path)))


def render(action, data):
    plan = data["plan"]
    if action == "new":
        return (f"Created {data['path']}\n{plan['description']}\n"
                "Add the steps that must happen. Dates and durations remain unknown until researched.")
    if action == "step":
        item = data["step"]
        return ("Added " + item["id"] + ": " + item["description"] + "\n"
                "Waits for: " + (", ".join(item["after"]) or "no other step in this plan") + "\n"
                "Needs research: " + ("completion date" if item["kind"] == "date" else "duration in elapsed days") +
                ("\nCompleting this step satisfies the question." if plan.get("target") == item["id"] else ""))
    lines = [plan["description"], "Deadline: " + plan["deadline"], ""]
    for item in plan.get("steps", []):
        lines += [item["id"] + " — " + item["description"],
                  "  Waits for: " + (", ".join(item["after"]) or "no other step in this plan"),
                  "  Unknown: " + ("completion date" if item["kind"] == "date" else "duration in elapsed days"),
                  "  Reason: " + item["rationale"]]
    lines += ["", "Finishing step: " + plan.get("target", "not selected"),
              "No probability assigned. Research these inputs before estimating launch timing.",
              "Working plan; full graph validation happens when you save or analyze it."]
    return "\n".join(lines)
