import json
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from vorhersage import examples, timeline
from vorhersage.common import Error
from vorhersage.store import Store
from vorhersage.workflow import Workflow


class ExampleTests(unittest.TestCase):
    def test_complete_offline_project_preserves_research_and_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "waymo"
            result = examples.initialize(project, "waymo", "My example")
            self.assertEqual(result["name"], "My example")
            workflow = Workflow(project)
            with workflow.store.connect() as c:
                self.assertEqual(Store.all(c, "forecast"), [])
                source = timeline.read(c, timeline.resolve(c, "waymo@1"))["specification"]
                draft = timeline.read(c, timeline.resolve(c, "waymo-draft@1"))["specification"]
            self.assertEqual(timeline.analyze(source)["probability"], .39)
            self.assertIsNone(timeline.analyze(draft)["probability"])
            self.assertEqual(len(json.loads((project / "inputs/evidence.json").read_text())["records"]), 17)
            self.assertEqual(json.loads((project / "inputs/model.json").read_text()), source)
            self.assertTrue(workflow.doctor()["ok"])
            before = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}
            with self.assertRaisesRegex(Error, "already exists"):
                examples.initialize(project, "waymo")
            after = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_failed_example_leaves_no_partial_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "waymo"
            with patch("vorhersage.examples.timeline.add", side_effect=Error("test", "Registration failed")):
                with self.assertRaisesRegex(Error, "Registration failed"):
                    examples.initialize(project, "waymo")
            self.assertEqual(list(Path(tmp).iterdir()), [])
            project.mkdir()
            with self.assertRaisesRegex(Error, "already exists"):
                examples.initialize(project, "waymo")
            self.assertEqual(list(project.iterdir()), [])

    def test_bundled_snapshot_matches_original_inputs(self):
        bundle = json.loads(files("vorhersage").joinpath("example_data", "waymo.json").read_text())
        original = Path(__file__).resolve().parents[1] / "examples/waymo_boston_2029/independent_20260915"
        for key, path in (("profile", "walkthrough/profile.json"), ("question", "question.json"),
                          ("model", "walkthrough/model.json"), ("evidence", "outputs/evidence.json")):
            self.assertEqual(bundle[key], json.loads((original / path).read_text()), key)
        draft = json.loads((original / "outputs/structure_before_research.json").read_text())
        draft["id"] = "waymo-draft"
        self.assertEqual(bundle["draft"], draft)
