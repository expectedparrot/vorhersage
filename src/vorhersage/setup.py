"""Convenient setup inputs that feed the same validated workflow as JSON files."""

import re
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from .common import load, now, require, time
from .store import Store
from .workflow import Workflow


QUESTION_OPTIONS = {
    "question_id": "id", "deadline": "event_deadline", "yes": "yes", "no": "no",
    "void": "void", "source": "resolution_source", "resolve_after": "resolve_after",
    "profile": "profile", "domain": "domain", "kind": "kind", "event_group": "event_group",
}


def slug(text):
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80].rstrip("-")
    require(value, "Supply --id with a question identifier.")
    return value


def timestamp(value):
    """A bare calendar date explicitly means its start, at midnight UTC."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        value = date.fromisoformat(value).isoformat() + "T00:00:00Z"
    time(value)
    return value


def question_input(args, default_id=None):
    supplied = {field: getattr(args, option) for option, field in QUESTION_OPTIONS.items()
                if getattr(args, option) is not None}
    if args.input:
        require(not args.question and not supplied, "Use either --from or inline question options, not both.")
        return load(args.input)
    require(args.question and args.question.strip(), "Supply a question or --from question.json.")
    for field, flag in (("event_deadline", "--deadline"), ("yes", "--yes"), ("resolution_source", "--source")):
        require(supplied.get(field) and supplied[field].strip(), "A question requires " + flag + ".")
    deadline = timestamp(supplied["event_deadline"])
    question_id = supplied.get("id") or default_id or slug(args.question)
    return {
        "id": question_id, "text": args.question, "yes": supplied["yes"],
        "no": supplied.get("no", "The YES criteria have not been met by the event deadline."),
        "void": supplied.get("void", "The question cannot be resolved because its criteria or resolution evidence are materially defective. Delay, cancellation, or failure to meet the YES criteria is NO."),
        "event_deadline": deadline, "resolve_after": timestamp(supplied.get("resolve_after", deadline)),
        "resolution_source": supplied["resolution_source"],
        "event_group": supplied.get("event_group", question_id), "domain": supplied.get("domain", "general"),
        "profile": supplied.get("profile", "general"), "kind": supplied.get("kind", "real"),
    }


def initialize(project, name, question):
    """Validate a complete question before installing a new project's database.

    Existing ordinary files in the directory are preserved. A failed question
    registration leaves no initialized project, and an existing project is never
    replaced. The standard profile and question validators remain authoritative.
    """
    target = Path(project).resolve()
    database_dir = target / ".vorhersage"
    require(not database_dir.exists() and not database_dir.is_symlink(), "Project already exists.", "existing_project")
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".vorhersage-setup-", dir=target.parent) as tmp:
        workflow = Workflow(tmp)
        workflow.store.init(name)
        registered = workflow.question(question)
        target.mkdir(parents=True, exist_ok=True)
        require(not database_dir.exists() and not database_dir.is_symlink(), "Project already exists.", "existing_project")
        workflow.store.path.parent.rename(database_dir)
    return {"project": str(target), "database": str(database_dir / "state.sqlite"), "name": name,
            **registered, "question": question}


RUN_OPTIONS = ("forecaster", "method", "mode", "information_as_of", "workflow",
               "research_status", "max_searches", "max_extra_tasks", "research_contract", "cutoff_policy")


def run_input(args, workflow):
    supplied = {field: getattr(args, field) for field in RUN_OPTIONS if getattr(args, field, None) is not None}
    if args.input:
        require(not args.question_id and not supplied, "Use either --from or inline run options, not both.")
        return load(args.input)
    require(args.question_id, "Supply a question ID or --from run.json.")
    with workflow.store.connect() as connection:
        question = Store.question(connection, args.question_id)["specification"]
    spec = {"question_id": args.question_id, "forecaster": "agent", "method": "agent judgment",
            "mode": "simulation" if question["kind"] == "simulation" else "prospective",
            "information_as_of": now(), "research_status": "not_started", "workflow": "standard",
            "max_searches": 20, "max_extra_tasks": 2, **supplied}
    if "information_as_of" in supplied:
        spec["information_as_of"] = timestamp(supplied["information_as_of"])
    return spec
