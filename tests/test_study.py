"""Exercise the public single-question workflow across fresh CLI processes."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vorhersage import study, study_text, timeline, research_model
from vorhersage.common import Error
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_workflow import packet, payload, stamp
from test_timeline import model, weighted


def intake(unknowns=()):
    return {"rationale": "Fictional fixture supplies case facts; remaining uncertainty is represented in the model.",
            "inputs": [{"id": "outcome", "target": "Chance of the fictional launch by its deadline."}],
            "unknowns": list(unknowns)}


def support(answer, spec=None):
    return [{"input_id": "outcome", "model_input": path, "value": value,
             "target": "Fixture input: " + path, "evidence_measures": "No empirical estimate; synthetic fixture.",
             "transfer_assumptions": "Assume the declared fixture value.", "basis": "assumed",
             "plausible_range": [value, value], "evidence_refs": []}
            for path, value in research_model.model_inputs(answer, spec).items()]


def study_payload(kind, refs, estimate=.6):
    if kind == "intake":
        return intake()
    answer = payload(kind, refs, estimate)
    if kind == "prior":
        answer["research_status_at_estimate"] = "not_started"
    if kind == "assessment":
        answer["parameter_support"] = support(answer)
    if kind == "review":
        answer["sensitivity_review"] = {"interpretation": "Fixed synthetic inputs do not establish accuracy.",
                                        "influential_inputs": ["probability"], "next_evidence": "Obtain the fictional release log."}
    return answer


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "release forecast"
        self.text = "Will the fictional app launch on time?"
        self.rules = ["--deadline", stamp(10), "--yes", "Customers can use the public release.",
                      "--source", "Fictional release log", "--kind", "simulation"]
        self.w = Workflow(self.project)

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable, "-m", "vorhersage", *map(str, args)],
                                cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
        return result.stdout if success else result.stderr

    def data(self, command, *args):
        return json.loads(self.cli(command, "--project", self.project, *args, "--json"))["data"]

    def begin(self, *args):
        return self.data("start", self.text, *self.rules, *args)

    def test_question_only_then_definition_is_resumable_and_idempotent(self):
        output = self.cli("start", self.text, "--project", self.project)
        self.assertIn("Before researching", output)
        self.assertIn("No probability has been assigned", output)
        self.assertEqual(self.data("next")["stage"], "definition")
        self.assertEqual(self.w.status()["questions"], [])
        self.assertEqual(self.w.status()["runs"], [])
        self.assertIn("Define the question", self.cli("next", "--project", self.project,
                                                    "--output", self.root / "task.json", success=False))
        self.assertIn("Counts as YES", self.cli("define", "--project", self.project, *self.rules))
        before = self.w.status()
        self.data("define", *self.rules)
        self.assertEqual(self.w.status(), before)
        self.cli("define", "--project", self.project, *self.rules, "--yes", "Different event", success=False)
        self.assertEqual(self.w.status(), before)
        self.assertEqual(self.data("show")["stage"], "intake")
        self.assertTrue(self.w.doctor()["ok"])

    def test_complete_definition_starts_once_with_human_defaults(self):
        self.begin("--max-searches", "7", "--max-extra-tasks", "1", "--research-status", "completed")
        task = self.data("next")
        run = task["context"]["run"]
        self.assertEqual(run["forecaster"], "user")
        self.assertEqual(run["method"], "declared judgment")
        self.assertEqual(run["research_status"], "completed")
        self.assertEqual(task["budget"]["searches_remaining"], 7)
        before = self.w.status()
        self.cli("start", self.text, "--project", self.project, *self.rules, success=False)
        self.assertEqual(self.w.status(), before)
        # Both placements of --project choose the same study.
        output = self.cli("--project", self.project, "show")
        self.assertIn("Working estimate: not yet assigned", output)
        self.assertIn("user · simulation", output)
        self.assertNotIn("task_", output)

    def test_invalid_start_leaves_no_partial_database_or_lost_files(self):
        self.project.mkdir()
        notes = self.project / "notes.txt"
        notes.write_text("Existing notes")
        for extra in (["--deadline", "bad"], ["--profile", "missing"], ["--max-searches", "-1"],
                      ["--kind", "real", "--deadline", "2000-01-01"]):
            with self.subTest(extra=extra):
                self.cli("start", self.text, "--project", self.project, *self.rules, *extra, success=False)
                self.assertEqual(list(self.project.iterdir()), [notes])
                self.assertEqual(notes.read_text(), "Existing notes")
        self.cli("start", self.text, "--project", self.project, "--deadline", stamp(2), success=False)
        self.cli("start", self.text, "--project", self.project, "--workflow", "timeline", success=False)
        self.assertEqual(list(self.project.iterdir()), [notes])
        self.begin()
        self.assertEqual(notes.read_text(), "Existing notes")

    def test_failed_definition_rolls_back_question_and_run(self):
        self.data("start", self.text)
        self.cli("define", "--project", self.project, *self.rules,
                 "--kind", "real", "--deadline", "2000-01-01", success=False)
        self.assertEqual(self.w.status()["questions"], [])
        self.assertEqual(self.w.status()["runs"], [])
        self.assertEqual(self.data("show")["stage"], "definition")
        self.data("define", *self.rules)
        self.assertEqual(len(self.w.status()["runs"]), 1)

    def test_task_files_preserve_retry_and_stale_write_guards(self):
        self.begin()
        path = self.root / "answer.json"
        output = self.cli("next", "--project", self.project, "--output", path)
        self.assertIn("Task saved to", output)
        task = json.loads(path.read_text())
        before = self.w.status()
        self.cli("submit", "--project", self.project, "--from", path, success=False)
        self.assertEqual(self.w.status(), before)
        task["submission"]["payload"] = intake()
        path.write_text(json.dumps(task))
        self.cli("next", "--project", self.project, "--output", path, success=False)
        self.assertEqual(json.loads(path.read_text()), task)
        self.data("submit", "--from", path)
        accepted = self.w.status()
        self.assertTrue(self.data("submit", "--from", path)["duplicate"])
        task["submission"]["payload"]["rationale"] = "A changed answer."
        path.write_text(json.dumps(task))
        error = self.cli("submit", "--project", self.project, "--from", path, success=False)
        self.assertIn("Idempotency", error)
        task["submission"]["idempotency_key"] = "different-writer"
        path.write_text(json.dumps(task))
        self.assertIn("stale", self.cli("submit", "--project", self.project, "--from", path, success=False))
        self.assertEqual(self.w.status(), accepted)
        other = self.root / "other"
        self.cli("start", self.text, "--project", other, *self.rules)
        error = self.cli("submit", "--project", other, "--from", path, success=False)
        self.assertIn("different forecast", error)
        path.write_text("[]")
        self.assertIn("JSON object", self.cli("submit", "--project", self.project, "--from", path, success=False))

    def test_full_research_review_issue_and_reports(self):
        self.begin("--forecaster", "Alice", "--method", "Release review")
        self.cli("report", "--project", self.project)
        self.assertTrue((self.project / "report.html").exists())
        refs = [self.w.import_packet(packet())["records"][0]["evidence_ref"]]
        for index in range(10):
            path = self.root / f"task-{index}.json"
            self.cli("next", "--project", self.project, "--output", path)
            task = json.loads(path.read_text())
            task["submission"]["payload"] = study_payload(task["task"]["kind"], refs)
            task["submission"]["usage"] = {"searches": 0, "cost_usd": 0, "model_calls": 0}
            path.write_text(json.dumps(task))
            output = self.cli("submit", "--project", self.project, "--from", path)
            if index == 2:
                self.assertIn("Remaining delays.", output)
                self.assertIn("Synthetic factory record", output)
            if index == 7:
                self.assertIn("Working estimate: 60.0%", output)
                self.assertIn("Not an accuracy claim.", output)
        self.assertIn("Published forecast: 60.0%", output)
        self.assertIn("Dispatch could fail.", output)
        self.assertIn("Review on:", output)
        self.assertIn("New factory status information.", output)
        self.assertIn("Alice · simulation", output)
        self.assertEqual(self.data("next")["disposition"], "waiting")
        self.cli("next", "--project", self.project, "--output", self.root / "done.json", success=False)
        self.assertFalse((self.root / "done.json").exists())
        self.assertIn("Report saved to", self.cli("report", "--project", self.project))
        self.assertIn("Release review", (self.project / "report.html").read_text())
        self.cli("report", "--project", self.project, "--format", "latex")
        self.assertTrue((self.project / "report.tex").exists())
        self.assertEqual(len(self.data("report")["forecasts"]), 1)
        explicit = self.cli("report", "--project", self.project, "--question", "question")
        self.assertEqual(len(json.loads(explicit)["data"]["forecasts"]), 1)
        self.assertTrue(self.w.doctor()["ok"])

    def test_timeline_tasks_and_model_are_visible_without_issuing_early(self):
        self.begin("--workflow", "timeline", "--deadline", "2029-01-01")
        self.assertEqual(self.data("next")["task"]["kind"], "intake")
        spec = weighted(model())
        spec["question"]["question_id"] = "question"
        mid = timeline.add(self.w.store, spec)["timeline_model_id"]
        while (task := study.next_task(self.w))["disposition"] == "actionable":
            kind = task["task"]["kind"]
            if kind == "intake":
                answer = intake()
            elif kind == "timeline_structure":
                answer = {"timeline_model_id": mid, "rationale": "Synthetic dependency model."}
            elif kind == "timeline_research":
                current = task["task"]["timeline_context"]["model"]
                parameter = task["task"]["parameter_id"]
                answer = {"rationale": "Declared fixture assumptions.", "assessments": [
                    {"scenario_id": row["id"], "assessment": next(a for a in row["assessments"] if a["parameter_id"] == parameter)}
                    for row in current["scenarios"]]}
            elif kind == "assessment":
                answer = {"method": "timeline_model", "timeline_model_id": task["task"]["timeline_context"]["timeline_model_id"],
                          "rationale": "Calculate from declared scenarios.", "limitations": ["Synthetic assumptions."], "evidence_refs": []}
                answer["parameter_support"] = support(answer, task["task"]["timeline_context"]["model"])
            else:
                answer = study_payload(kind, [])
                if kind == "review":
                    answer["sensitivity_review"]["influential_inputs"] = list(task["context"]["model_inputs"])
            task["submission"]["payload"] = answer
            study.submit(self.w, task)
            output = self.cli("show", "--project", self.project)
            if kind != "intake":
                self.assertIn("Model calculation: 70.0%", output)
            if kind not in ("intake", "issue"):
                self.assertIn("not an issued forecast", output)
        self.assertIn("Published forecast: 70.0%", output)
        self.assertTrue(self.w.doctor()["ok"])

    def test_expired_live_run_is_blocked_and_no_task_file_is_written(self):
        self.begin("--kind", "real")
        from unittest.mock import patch
        with patch("vorhersage.workflow.now", return_value=stamp(11)):
            result = study.show(self.w.store)
            self.assertEqual(result["stage"], "blocked")
            self.assertIn("deadline passed", study_text.render(result))
            with self.assertRaisesRegex(Error, "no research task"):
                study.next_task(self.w, self.root / "blocked.json")
        self.assertFalse((self.root / "blocked.json").exists())

    def test_json_input_and_output_and_portfolio_compatibility(self):
        self.begin()
        spec = self.data("show")["definition"]
        file = self.root / "question.json"
        file.write_text(json.dumps(spec))
        second = self.root / "from-json"
        result = self.cli("start", "--project", second, "--from", file, "--json")
        self.assertEqual(json.loads(result)["data"]["definition"], spec)
        task = self.data("next")
        explicit = self.cli("--project", self.project, "next", "--run", task["run_id"])
        self.assertEqual(json.loads(explicit)["data"]["task"], task["task"])
        portfolio = self.root / "portfolio"
        self.cli("init", portfolio)
        self.assertIn("portfolio project", self.cli("show", "--project", portfolio, success=False))
        error = self.cli("show", "--project", portfolio, "--json", success=False)
        self.assertEqual(json.loads(error)["status"], "error")


if __name__ == "__main__":
    unittest.main()
