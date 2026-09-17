import copy
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from vorhersage import timeline, timeline_plan
from vorhersage.common import Error
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_workflow import question, stamp


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.w = Workflow(self.root / "project")
        self.w.store.init("Plans")
        self.q = question()
        self.w.question(self.q)
        self.file = self.root / "my plan.toml"

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable, "-m", "vorhersage", "timeline", *map(str, args)],
                                cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
        return result.stdout if success else result.stderr

    def make(self):
        timeline_plan.new(self.w.store, self.file)
        timeline_plan.step(self.file, "legal", "Legal permission", date=True)
        timeline_plan.step(self.file, "prep", "Prepare the service")
        timeline_plan.step(self.file, "launch", "Public launch", after=["legal", "prep"], target=True)

    def test_cli_builds_inspects_and_saves_an_unknown_plan(self):
        self.assertIn("Created", self.cli("new", self.file, "--project", self.w.store.root))
        self.assertIn("not selected", self.cli("show", self.file))
        self.cli("step", self.file, "legal", "Legal permission", "--date")
        self.cli("step", self.file, "prep", "Prepare the service")
        output = self.cli("step", self.file, "launch", "Public launch", "--after", "legal", "prep", "--target")
        self.assertIn("Waits for: legal, prep", output)
        self.assertIn("satisfies the question", output)
        shown = self.cli("show", self.file)
        self.assertIn("Unknown: completion date", shown)
        self.assertIn("Unknown: duration in elapsed days", shown)
        self.assertIn("No probability assigned", shown)
        self.assertIn("Unresolved parameters: 3", self.cli("gaps", self.file))
        data = json.loads(self.cli("analyze", self.file, "--format", "json"))["data"]
        self.assertIsNone(data["probability"])
        self.assertIsNone(data["scenarios"][0]["meets_deadline"])
        saved = json.loads(self.cli("save", self.file, "--project", self.w.store.root, "--format", "json"))["data"]
        registered = saved["timeline_model_id"]
        text = self.cli("show", registered, "--project", self.w.store.root, "--format", "text")
        self.assertIn("Public launch", text)
        self.assertIn("Waits for: legal, prep", text)
        self.assertIn("unknown (unresolved)", text)
        self.assertEqual(json.loads(self.cli("show", registered, "--project", self.w.store.root))["data"]["specification"],
                         timeline_plan.compile(timeline_plan.read(self.file)))
        self.assertTrue(self.w.doctor()["ok"])

    def test_serialization_preserves_quotes_unicode_and_newlines(self):
        self.make()
        timeline_plan.step(self.file, "notes", 'Read "Boston" notes — première\nNext line.',
                           rationale='An explicit \\ path and "quote".')
        plan = timeline_plan.read(self.file)
        self.assertEqual(tomllib.loads(timeline_plan.text(plan)), plan)
        self.assertEqual(plan["steps"][-1]["description"], 'Read "Boston" notes — première\nNext line.')

    def test_invalid_steps_and_conflicting_retries_leave_file_intact(self):
        self.make()
        before = self.file.read_bytes()
        cases = [dict(id="bad", description="Bad", after=["absent"]),
                 dict(id="bad", description="Bad", after=["prep", "prep"]),
                 dict(id="bad", description="Bad", after=["prep"], date=True),
                 dict(id="prep", description="Changed definition"),
                 dict(id="other", description="Another target", target=True)]
        for options in cases:
            with self.subTest(options=options), self.assertRaises(Error):
                timeline_plan.step(self.file, **options)
            self.assertEqual(self.file.read_bytes(), before)
            self.assertFalse(self.file.with_name(self.file.name + ".lock").exists())
        timeline_plan.step(self.file, "launch", "Public launch", after=["legal", "prep"], target=True)
        self.assertEqual(self.file.read_bytes(), before)
        with self.assertRaises(FileExistsError):
            timeline_plan.new(self.w.store, self.file)
        self.assertEqual(self.file.read_bytes(), before)

    def test_lock_preserves_another_writers_file(self):
        self.make()
        lock = self.file.with_name(self.file.name + ".lock")
        lock.write_text("Other writer")
        before = self.file.read_bytes()
        with self.assertRaises(FileExistsError):
            timeline_plan.step(self.file, "other", "Other step")
        self.assertEqual(lock.read_text(), "Other writer")
        self.assertEqual(self.file.read_bytes(), before)

    def test_full_validation_rejects_cycles_disconnected_work_and_missing_target(self):
        self.make()
        original = timeline_plan.read(self.file)
        bad = []
        missing = copy.deepcopy(original); del missing["target"]; bad.append(missing)
        disconnected = copy.deepcopy(original); disconnected["steps"][-1]["after"] = ["legal"]; bad.append(disconnected)
        cycle = copy.deepcopy(original); cycle["steps"][1]["after"] = ["launch"]; bad.append(cycle)
        typo = copy.deepcopy(original); typo["steps"][1]["days"] = 30; bad.append(typo)
        for plan in bad:
            self.file.write_text(timeline_plan.text(plan))
            with self.subTest(plan=plan), self.assertRaises(Error):
                timeline_plan.save(self.w.store, self.file)
            with self.w.store.connect() as c:
                self.assertEqual(Store.all(c, "timeline_model"), [])

    def test_saved_models_are_immutable_and_question_version_is_pinned(self):
        self.make()
        first = timeline_plan.save(self.w.store, self.file)
        self.assertEqual(timeline_plan.save(self.w.store, self.file)["timeline_model_id"], first["timeline_model_id"])
        plan = timeline_plan.read(self.file)
        updated = dict(self.q, yes="A changed definition")
        self.w.question(updated, expected_version=1)
        self.assertEqual(plan["question_version"], 1)
        self.assertEqual(first["specification"]["question"]["version"], 1)
        plan["steps"][-1]["rationale"] = "Changed assumption"
        self.file.write_text(timeline_plan.text(plan))
        with self.assertRaisesRegex(Error, "frozen"):
            timeline_plan.save(self.w.store, self.file)
        with self.w.store.connect() as c:
            self.assertEqual(timeline.read(c, first["timeline_model_id"])["specification"], first["specification"])
        plan["name"] = "alternative"
        self.file.write_text(timeline_plan.text(plan))
        second = timeline_plan.save(self.w.store, self.file)
        self.assertNotEqual(second["timeline_model_id"], first["timeline_model_id"])
        self.assertTrue(self.w.doctor()["ok"])

    def test_question_selection_and_cutoffs_are_explicit(self):
        self.w.question(question(id="another"))
        with self.assertRaisesRegex(Error, "Select --question"):
            timeline_plan.new(self.w.store, self.file)
        with self.assertRaisesRegex(Error, "future"):
            timeline_plan.new(self.w.store, self.file, question_id="factory", as_of=stamp(.5))
        self.assertFalse(self.file.exists())
        created = timeline_plan.new(self.w.store, self.file, question_id="factory", as_of=stamp(-1))
        self.assertEqual(created["plan"]["deadline"], self.q["event_deadline"])


if __name__ == "__main__":
    unittest.main()
