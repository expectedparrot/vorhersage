"""Create an inspectable project from a bundled, offline research snapshot."""

import json
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from .common import require
from . import timeline
from .workflow import Workflow


EXAMPLES = ("waymo",)


def initialize(project, example, name=None):
    """Build in a temporary directory, then publish the complete new project."""
    require(example in EXAMPLES, "Unknown example: " + example)
    target = Path(project).absolute()
    require(not target.exists() and not target.is_symlink(),
            "Example destination already exists; choose a new directory.", "existing_project")
    resource = files("vorhersage").joinpath("example_data", example + ".json")
    bundle = json.loads(resource.read_text(encoding="utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".vorhersage-example-", dir=target.parent) as tmp:
        staged = Path(tmp) / "project"
        workflow = Workflow(staged)
        project_name = name or bundle["name"]
        workflow.store.init(project_name)
        workflow.add_profile(bundle["profile"])
        question = workflow.question(bundle["question"])
        evidence = workflow.import_packet(bundle["evidence"])
        models = {}
        for key in ("draft", "model"):
            spec = bundle[key]
            models[f"{spec['id']}@{spec['version']}"] = timeline.add(workflow.store, spec)["timeline_model_id"]
        inputs = staged / "inputs"
        inputs.mkdir()
        for key in ("profile", "question", "draft", "evidence", "model"):
            (inputs / (key + ".json")).write_text(json.dumps(bundle[key], indent=2) + "\n", encoding="utf-8")
        require(not target.exists() and not target.is_symlink(),
                "Example destination already exists; choose a new directory.", "existing_project")
        staged.rename(target)
    return {"project": str(target), "database": str(target / ".vorhersage/state.sqlite"),
            "name": project_name, "example": example, **question,
            "packet_id": evidence["packet_id"], "models": models,
            "inputs": str(target / "inputs"), "description": bundle["description"], "source": bundle["source"]}
