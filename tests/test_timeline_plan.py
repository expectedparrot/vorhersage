import copy
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from vorhersage import timeline, timeline_plan, timeline_diagram
from vorhersage.common import Error
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_workflow import packet, question, stamp


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

    def test_edit_splits_permission_updates_references_and_keeps_saved_snapshot(self):
        self.make()
        saved = timeline_plan.save(self.w.store, self.file)
        self.cli("edit", self.file, "legal", "--rename", "state", "--description", "State permission",
                 "--rationale", "Separate state and local processes.")
        plan = timeline_plan.read(self.file)
        self.assertEqual(plan["steps"][-1]["after"], ["state", "prep"])
        self.cli("step", self.file, "local", "Local arrangements", "--after", "state")
        self.cli("edit", self.file, "launch", "--after", "local", "prep", "--rationale", "Public service requires local arrangements.")
        spec = timeline_plan.compile(timeline_plan.read(self.file))
        self.assertEqual(spec["nodes"][2]["parents"], ["local", "prep"])
        self.assertEqual(spec["nodes"][3]["parents"], ["state"])
        self.cli("edit", self.file, "launch", "--rename", "public", "--rationale", "Clarify the target name.")
        self.assertEqual(timeline_plan.read(self.file)["target"], "public")
        with self.w.store.connect() as c:
            self.assertEqual(timeline.read(c, saved["timeline_model_id"])["specification"], saved["specification"])

    def test_invalid_edits_leave_working_plan_unchanged(self):
        self.make()
        before = self.file.read_bytes()
        for name, options in [("prep", {"after": ["launch"]}), ("legal", {"rename": "prep"}),
                              ("launch", {"after": ["missing"]}), ("missing", {"description": "Absent"}),
                              ("legal", {"after": ["prep"]}), ("prep", {})]:
            with self.subTest(name=name, options=options), self.assertRaises(Error):
                timeline_plan.edit(self.file, name, rationale="Test change.", **options)
            self.assertEqual(self.file.read_bytes(), before)
        self.cli("edit", self.file, "launch", "--after", "--rationale", "Inspect an alternative with no prerequisites.")
        self.assertEqual(timeline_plan.read(self.file)["steps"][-1]["after"], [])
        with self.assertRaisesRegex(Error, "contribute"):
            timeline_plan.save(self.w.store, self.file)

    def test_diagram_formats_use_actual_edges_and_leave_model_unchanged(self):
        self.make()
        before = self.file.read_bytes()
        saved = timeline_plan.save(self.w.store, self.file)
        source = self.cli("diagram", self.file)
        self.assertTrue(source.startswith("flowchart TD\n"))
        self.assertEqual(source.count(" --> "), 2)
        self.assertIn("n0 --> n2", source)
        self.assertIn("n1 --> n2", source)
        for suffix in ("svg", "mmd", "md"):
            out = self.root / ("graph." + suffix)
            self.cli("diagram", self.file, "--output", out)
            self.assertTrue(out.exists())
            if suffix == "svg":
                xml = ET.fromstring(out.read_text())
                edges = [p for p in xml.iter("{http://www.w3.org/2000/svg}path") if p.get("marker-end")]
                self.assertEqual(len(edges), 2)
            else:
                self.assertIn(source, out.read_text())
        registered = self.cli("diagram", saved["timeline_model_id"], "--project", self.w.store.root)
        self.assertEqual(registered, source)
        result = json.loads(self.cli("diagram", self.file, "--format", "json"))["data"]
        self.assertEqual(result["diagram"], source)
        self.assertEqual(self.file.read_bytes(), before)
        self.cli("diagram", self.file, "--output", self.file, success=False)
        self.assertEqual(self.file.read_bytes(), before)

    def test_diagram_escapes_labels_and_marks_alternative_prerequisites(self):
        self.make()
        spec = timeline_plan.compile(timeline_plan.read(self.file))
        dangerous = '<script>alert("x")</script> & [end] # {{x}}'
        spec["description"] = dangerous
        spec["nodes"][-1]["completion_condition"] = dangerous
        svg = timeline_diagram.svg(spec)
        xml = ET.fromstring(svg)
        self.assertEqual(xml.find("{http://www.w3.org/2000/svg}title").text, dangerous)
        self.assertNotIn("<script>", svg)
        self.assertNotIn("<script>", timeline_diagram.mermaid(spec))
        spec["nodes"][-1]["kind"] = "any"
        del spec["nodes"][-1]["parameter_id"]
        spec["parameters"].pop()
        spec["scenarios"][0]["assessments"].pop()
        self.assertIn("any prerequisite", timeline_diagram.mermaid(spec))
        self.assertIn("any prerequisite", timeline_diagram.svg(spec))

    def test_scenario_inputs_and_copy_compute_declared_probability(self):
        self.make()
        saved = timeline_plan.save(self.w.store, self.file)
        self.cli("scenario", self.file, "early", "Quick opening", "--probability", "60%",
                 "--rationale", "Illustrative joint probability.")
        self.cli("estimate", self.file, "early", "legal", "--date", stamp(-.5), "--rationale", "Assumed early permission.")
        for step in ("prep", "launch"):
            self.cli("estimate", self.file, "early", step, "--days", "0", "--rationale", "Assume no remaining delay.")
        self.assertIn("incomplete", self.cli("show", self.file))
        self.cli("analyze", self.file, success=False)
        self.cli("scenario", self.file, "late", "Delayed opening", "--copy-from", "early", "--probability", "0.4",
                 "--rationale", "Residual delayed case.", "--partition", "The fixture either opens immediately or has a ten-day delay.")
        self.cli("estimate", self.file, "late", "launch", "--days", "10", "--rationale", "Delay exceeds the deadline.")
        plan = timeline_plan.read(self.file)
        self.assertEqual(tomllib.loads(timeline_plan.text(plan)), plan)
        self.assertEqual(plan["scenarios"][0]["assessments"][-1]["value"], 0)
        result = json.loads(self.cli("analyze", self.file, "--format", "json"))["data"]
        self.assertAlmostEqual(result["probability"], .6)
        self.assertTrue(result["scenarios"][0]["meets_deadline"])
        self.assertFalse(result["scenarios"][1]["meets_deadline"])
        self.cli("save", self.file, "--project", self.w.store.root, "--name", "researched")
        self.assertIn("60.0%", self.cli("show", "researched@1", "--project", self.w.store.root, "--format", "text"))
        with self.w.store.connect() as c:
            self.assertEqual(timeline.read(c, saved["timeline_model_id"])["specification"], saved["specification"])
        self.assertTrue(self.w.doctor()["ok"])

    def test_probability_and_incomplete_case_guards(self):
        self.make()
        for weight in ("22", "101%", "-1%", "nan", "inf"):
            self.cli("scenario", self.file, "early", "Early", "--probability", weight, "--rationale", "Test.", success=False)
        self.cli("scenario", self.file, "early", "Early", "--probability", "22%", "--rationale", "Test.")
        self.cli("scenario", self.file, "late", "Late", "--probability", "8%", "--rationale", "Test.")
        self.assertIn("30.0%", self.cli("show", self.file))
        with self.assertRaisesRegex(Error, "sum to one"):
            timeline_plan.compile(timeline_plan.read(self.file))
        self.cli("scenario", self.file, "late", "Late", "--probability", "78%", "--rationale", "Updated probability.")
        self.cli("analyze", self.file, success=False)  # missing partition justification
        self.cli("scenario", self.file, "late", "Late", "--rationale", "Updated probability.", "--partition", "All early or late cases.")
        result = json.loads(self.cli("analyze", self.file, "--format", "json"))["data"]
        self.assertIsNone(result["probability"])  # dates/durations still unknown
        self.assertEqual(result["probability_bounds"], [0, 1])
        self.cli("scenario", self.file, "unknown", "Unweighted case", "--rationale", "Unassigned.")
        self.cli("analyze", self.file, success=False)
        # Structure remains inspectable while probabilities are being authored.
        self.assertIn("flowchart TD", self.cli("diagram", self.file))

    def test_estimates_keep_types_evidence_unknowns_and_renames(self):
        self.make()
        self.cli("scenario", self.file, "case", "Unweighted case", "--rationale", "Explore one possibility.")
        before = self.file.read_bytes()
        for args in (("legal", "--days", "5"), ("launch", "--days", "-1"),
                     ("launch", "--days", "nan"), ("prep", "--date", "2027-01-01"),
                     ("prep", "--days", "10", "--basis", "estimated"),
                     ("legal", "--date", stamp(1), "--basis", "observed", "--evidence", "p:r")):
            self.cli("estimate", self.file, "case", *args, "--rationale", "Test.", success=False)
            self.assertEqual(self.file.read_bytes(), before)
        imported = self.w.import_packet(packet())
        ref = imported["records"][0]["evidence_ref"]
        self.cli("estimate", self.file, "case", "prep", "--days", "2", "--basis", "estimated",
                 "--evidence", ref["packet_id"] + ":" + ref["record_id"], "--rationale", "Evidence-informed estimate.")
        plan = timeline_plan.read(self.file)
        self.assertEqual(plan["scenarios"][0]["assessments"][0]["evidence_refs"], [ref])
        self.assertEqual(tomllib.loads(timeline_plan.text(plan)), plan)
        self.cli("edit", self.file, "prep", "--rename", "ready", "--rationale", "Clarify the input.")
        self.assertEqual(timeline_plan.read(self.file)["scenarios"][0]["assessments"][0]["parameter_id"], "ready")
        self.cli("save", self.file, "--project", self.w.store.root)
        self.cli("estimate", self.file, "case", "ready", "--unknown", "--rationale", "Reconsider the estimate.")
        term = timeline_plan.read(self.file)["scenarios"][0]["assessments"][0]
        self.assertEqual(term["basis"], "unresolved")
        self.assertNotIn("value", term)
        self.cli("estimate", self.file, "case", "ready", "--never", "--rationale", "A failure path.")
        self.assertEqual(timeline_plan.read(self.file)["scenarios"][0]["assessments"][0]["value"], "never")

    def test_copy_errors_and_unverified_evidence_do_not_save_a_model(self):
        self.make()
        self.cli("scenario", self.file, "case", "A case", "--rationale", "Test.")
        before = self.file.read_bytes()
        for name, source in (("case", "case"), ("second", "absent")):
            self.cli("scenario", self.file, name, "A case", "--copy-from", source, "--rationale", "Test.", success=False)
            self.assertEqual(self.file.read_bytes(), before)
        self.cli("estimate", self.file, "case", "prep", "--days", "2", "--basis", "estimated",
                 "--evidence", "missing:record", "--rationale", "Unverified citation.")
        self.cli("save", self.file, "--project", self.w.store.root, success=False)
        with self.w.store.connect() as c:
            self.assertEqual(Store.all(c, "timeline_model"), [])


if __name__ == "__main__":
    unittest.main()
