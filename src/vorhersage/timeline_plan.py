"""Editable timeline plans compiled into immutable timeline models.

Plans are ordinary TOML working files. Incomplete graphs are allowed while
building; saving applies the full timeline validator and evidence rules.
"""

import copy
import json
import math
import os
import tempfile
import tomllib
from contextlib import contextmanager
from pathlib import Path

from .common import now, require, time, probability
from .schemas import TEXT, TIME, TIMELINE_SCENARIO, array, enum, obj, validate as validate_schema
from .store import Store
from . import timeline

STEP = obj({"id": TEXT, "description": TEXT, "kind": enum("date", "duration"),
            "after": array(), "rationale": TEXT})
PLAN = obj({"name": TEXT, "question": TEXT, "question_version": {"type": "integer", "minimum": 1},
            "as_of": TIME, "deadline": TIME, "deadline_rule": enum("before", "on_or_before"),
            "description": TEXT, "target": TEXT, "steps": array(STEP),
            "scenarios": array(TIMELINE_SCENARIO, 1), "partition_justification": TEXT},
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
    remaining = {s["id"]: set(s["after"]) for s in steps}
    while remaining:
        ready = {id for id, parents in remaining.items() if not parents & remaining.keys()}
        require(ready, "Timeline contains a cycle.")
        remaining = {id: parents for id, parents in remaining.items() if id not in ready}
    scenarios = plan.get("scenarios", [])
    require(len(scenarios) <= 500 and len({s["id"] for s in scenarios}) == len(scenarios),
            "Scenario names must be unique; at most 500 scenarios are allowed.")
    require(all("weight" not in s or s.get("weight_rationale") for s in scenarios),
            "Each scenario probability needs a rationale.")
    timeline.validate_assessments({s["id"]: {"kind": "date" if s["kind"] == "date" else "duration_days"}
                                   for s in steps}, scenarios, time(plan["as_of"]))
    return plan


def read(path):
    return validate(tomllib.loads(Path(path).read_text(encoding="utf-8")))


def text(plan):
    """Serialize our small TOML vocabulary without a runtime dependency."""
    def quote(value):
        if isinstance(value, dict):
            return "{ " + ", ".join(quote(k) + " = " + quote(v) for k, v in value.items()) + " }"
        if isinstance(value, list):
            return "[" + ", ".join(quote(v) for v in value) + "]"
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    lines = ["# Working plan: omitted inputs remain unknown; probabilities are declared judgments."]
    lines.extend(f"{key} = {quote(value)}" for key, value in plan.items() if key not in ("steps", "scenarios"))
    for step in plan.get("steps", []):
        lines += ["", "[[steps]]", *[f"{key} = {quote(value)}" for key, value in step.items()]]
    for scenario in plan.get("scenarios", []):
        lines += ["", "[[scenarios]]", *[f"{key} = {quote(value)}" for key, value in scenario.items() if key != "assessments"]]
        if not scenario["assessments"]:
            lines.append("assessments = []")
        for assessment in scenario["assessments"]:
            lines += ["", "[[scenarios.assessments]]", *[f"{key} = {quote(value)}" for key, value in assessment.items()]]
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


@contextmanager
def changing(path):
    """Validate and atomically replace a working file under its writer lock."""
    path = Path(path)
    lock = path.with_name(path.name + ".lock")
    with lock.open("x"):
        try:
            plan = read(path)
            yield plan
            validate(plan)
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


def step(path, id, description, *, after=(), date=False, target=False, rationale=None):
    with changing(path) as plan:
        item = {"id": id, "description": description, "kind": "date" if date else "duration",
                "after": list(after), "rationale": rationale or "Provisional dependency; verify during research."}
        existing = next((s for s in plan.get("steps", []) if s["id"] == id), None)
        require(existing is None or existing == item,
                "This step already has a different definition. Use timeline edit to change it.")
        if existing is None:
            plan.setdefault("steps", []).append(item)
        if target:
            require(plan.get("target", id) == id, "A target is already selected. Use timeline edit --target to change it.")
            plan["target"] = id
    return {"path": str(path), "plan": plan, "step": item}


def edit(path, id, *, rename=None, description=None, after=None, kind=None, target=False, rationale):
    require(rationale and rationale.strip(), "Explain the change with --rationale.")
    require(any(value is not None for value in (rename, description, after, kind)) or target,
            "Specify a change: --rename, --description, --after, --kind, or --target.")
    with changing(path) as plan:
        item = next((s for s in plan.get("steps", []) if s["id"] == id), None)
        require(item is not None, "Unknown step: " + id)
        if rename is not None:
            require(rename == id or all(s["id"] != rename for s in plan["steps"]), "Step names must be unique.")
            item["id"] = rename
            for other in plan["steps"]:
                other["after"] = [rename if name == id else name for name in other["after"]]
            if plan.get("target") == id:
                plan["target"] = rename
            for scenario in plan.get("scenarios", []):
                for assessment in scenario["assessments"]:
                    if assessment["parameter_id"] == id:
                        assessment["parameter_id"] = rename
        if description is not None:
            item["description"] = description
        if after is not None:
            item["after"] = [item["id"] if name == id else name for name in after]
        if kind is not None:
            item["kind"] = kind
        if target:
            plan["target"] = item["id"]
        item["rationale"] = rationale
    return {"path": str(path), "plan": plan, "step": item}


def probability_input(value):
    return probability(float(value[:-1]) / 100 if value.endswith("%") else float(value))


def scenario(path, id, description, *, weight=None, rationale, copy_from=None, partition=None):
    require(rationale and rationale.strip(), "Explain the scenario probability with --rationale.")
    with changing(path) as plan:
        cases = plan.setdefault("scenarios", [])
        item = next((s for s in cases if s["id"] == id), None)
        if item is None:
            assessments = []
            if copy_from:
                original = next((s for s in cases if s["id"] == copy_from), None)
                require(original is not None, "Unknown scenario to copy: " + copy_from)
                assessments = copy.deepcopy(original["assessments"])
            item = {"id": id, "description": description, "assessments": assessments, "evidence_refs": []}
            cases.append(item)
        else:
            require(copy_from is None, "Copy into a new scenario; existing estimates are not overwritten by a copy.")
        item.update(description=description, weight_rationale=rationale)
        if weight is not None:
            item["weight"] = probability(weight)
        if partition is not None:
            plan["partition_justification"] = partition
    return {"path": str(path), "plan": plan, "scenario": item}


def estimate(path, scenario_id, step_id, *, value=None, value_kind, basis="assumed", rationale, evidence_refs=()):
    require(rationale and rationale.strip(), "Explain the input with --rationale.")
    with changing(path) as plan:
        step = next((s for s in plan.get("steps", []) if s["id"] == step_id), None)
        require(step is not None, "Unknown step: " + step_id)
        case = next((s for s in plan.get("scenarios", []) if s["id"] == scenario_id), None)
        require(case is not None, "Unknown scenario: " + scenario_id)
        require(value_kind in ("unknown", "never", step["kind"]), "Use --date for a date milestone and --days for a duration step.")
        require(value_kind != "unknown" or basis == "assumed", "--unknown cannot be estimated or observed.")
        item = {"parameter_id": step_id, "basis": "unresolved" if value_kind == "unknown" else basis,
                "rationale": rationale, "evidence_refs": list(evidence_refs)}
        if value_kind != "unknown":
            item["value"] = "never" if value_kind == "never" else value
        case["assessments"] = [a for a in case["assessments"] if a["parameter_id"] != step_id] + [item]
    return {"path": str(path), "plan": plan, "scenario": case, "estimate": item}


def compile(plan, *, structure_only=False):
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
    if plan.get("scenarios") and not structure_only:
        spec["scenarios"] = copy.deepcopy(plan["scenarios"])
        spec["limitations"] = ["Dates, durations, dependencies and scenario probabilities are declared by the forecaster; validation does not establish their accuracy."]
        if plan.get("partition_justification"):
            spec["partition_justification"] = plan["partition_justification"]
    timeline.validate(spec)
    return spec


def save(store, path, name=None):
    spec = compile(read(path))
    if name is not None:
        spec["id"] = name
    return timeline.add(store, spec)


def scenario_progress(plan):
    cases = plan.get("scenarios", [])
    if not cases:
        return "No probability assigned. Research these inputs before estimating launch timing."
    total = math.fsum(s.get("weight", 0) for s in cases)
    missing = sum("weight" not in s for s in cases)
    lines = [f"Declared scenario probability: {total:.1%}"]
    if missing or not math.isclose(total, 1, abs_tol=1e-12, rel_tol=0):
        lines.append("Scenario probabilities are incomplete: assign every scenario a probability and make the total 100% before calculating a forecast.")
    elif not plan.get("partition_justification"):
        lines.append("Before calculating, use scenario --partition to explain how the cases are mutually exclusive and cover the possible outcomes.")
    else:
        lines.append("Use timeline analyze to check the complete model and calculate the forecast.")
    return "\n".join(lines)


def render(action, data):
    plan = data["plan"]
    if action == "new":
        return (f"Created {data['path']}\n{plan['description']}\n"
                "Add the steps that must happen. Dates and durations remain unknown until researched.")
    if action in ("step", "edit"):
        item = data["step"]
        return (("Updated " if action == "edit" else "Added ") + item["id"] + ": " + item["description"] + "\n"
                "Waits for: " + (", ".join(item["after"]) or "no other step in this plan") + "\n"
                "Input: " + ("completion date" if item["kind"] == "date" else "duration in elapsed days") +
                ("\nCompleting this step satisfies the question." if plan.get("target") == item["id"] else ""))
    if action in ("scenario", "estimate"):
        case = data["scenario"]
        if action == "scenario":
            assigned = f"{case['weight']:.1%}" if "weight" in case else "not assigned"
            detail = f"Scenario {case['id']}: {case['description']}\nAssigned probability: {assigned}\nReason: {case['weight_rationale']}"
        else:
            term = data["estimate"]
            detail = f"{case['id']} / {term['parameter_id']}: {term.get('value', 'unknown')} ({term['basis']})\nReason: {term['rationale']}"
        return detail + "\n\n" + scenario_progress(plan)
    lines = [plan["description"], "Deadline: " + plan["deadline"], ""]
    for item in plan.get("steps", []):
        lines += [item["id"] + " — " + item["description"],
                  "  Waits for: " + (", ".join(item["after"]) or "no other step in this plan"),
                  ("  Input: " if plan.get("scenarios") else "  Unknown: ") + ("completion date" if item["kind"] == "date" else "duration in elapsed days"),
                  "  Reason: " + item["rationale"]]
    for case in plan.get("scenarios", []):
        weight = f"{case['weight']:.1%}" if "weight" in case else "probability not assigned"
        lines += ["", f"{case['id']}: {case['description']} ({weight})", "  Probability rationale: " + case.get("weight_rationale", "not supplied")]
        terms = {a["parameter_id"]: a for a in case["assessments"]}
        for step in plan.get("steps", []):
            term = terms.get(step["id"], {})
            value = term.get("value", "unknown")
            unit = " days" if isinstance(value, (int, float)) and step["kind"] == "duration" else ""
            lines.append(f"  {step['id']}: {value}{unit} ({term.get('basis', 'unresolved')})")
            if term.get("rationale"):
                lines.append("    " + term["rationale"])
    lines += ["", "Finishing step: " + plan.get("target", "not selected"), scenario_progress(plan),
              "Working plan; full graph validation happens when you save or analyze it."]
    return "\n".join(lines)
