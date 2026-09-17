import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vorhersage.store import Store
from vorhersage.workflow import Workflow


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "app-launch"
        self.question = ["--question", "Will our app launch before 2030?", "--deadline", "2030-01-01",
                         "--yes", "The app is publicly available before the deadline.", "--source", "Public release log"]

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable, "-m", "vorhersage", *map(str, args)],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
        return json.loads(result.stdout if success else result.stderr)

    def test_real_question_to_first_research_task_without_json_files(self):
        result = self.cli("init", self.project, *self.question)
        self.assertEqual(result["data"]["question_id"], "app-launch")
        spec = result["data"]["question"]
        self.assertEqual(spec["event_deadline"], "2030-01-01T00:00:00Z")
        self.assertEqual(spec["resolve_after"], spec["event_deadline"])
        self.assertEqual(spec["profile"], "general")
        self.assertEqual(spec["kind"], "real")
        self.assertEqual(spec["event_group"], "app-launch")
        self.assertEqual(result["next_actions"][0]["argv"][-3:], ["run", "start", "app-launch"])
        started = self.cli("--project", self.project, "run", "start", "app-launch")
        run_id = started["data"]["run_id"]
        task = self.cli("--project", self.project, "next", "--run", run_id)["data"]
        self.assertEqual(task["task"]["kind"], "prior")
        with Store(self.project).connect() as c:
            run, _, _ = Store.run(c, run_id)
        self.assertEqual(run["mode"], "prospective")
        self.assertEqual(run["research_status"], "not_started")
        self.assertEqual(run["max_searches"], 20)
        self.assertEqual(run["max_extra_tasks"], 2)
        self.assertTrue(Workflow(self.project).doctor()["ok"])

    def test_inline_overrides_and_another_question(self):
        result = self.cli("init", self.project, *self.question,
                          "--id", "launch", "--deadline", "2030-01-01T00:00:00-05:00",
                          "--no", "No qualifying release by the deadline.", "--void", "Resolution source irrecoverably lost.",
                          "--resolve-after", "2030-01-03", "--kind", "simulation", "--domain", "software",
                          "--event-group", "releases", "--name", "Release forecasts")
        spec = result["data"]["question"]
        self.assertEqual(result["data"]["name"], "Release forecasts")
        self.assertEqual(spec["id"], "launch")
        self.assertEqual(spec["event_deadline"], "2030-01-01T00:00:00-05:00")
        self.assertEqual(spec["resolve_after"], "2030-01-03T00:00:00Z")
        self.assertEqual(spec["no"], "No qualifying release by the deadline.")
        started = self.cli("--project", self.project, "run", "start", "launch", "--workflow", "timeline",
                           "--forecaster", "alice", "--method", "release milestones", "--max-searches", "8",
                           "--max-extra-tasks", "1", "--research-status", "in_progress")
        run_id = started["data"]["run_id"]
        step = self.cli("--project", self.project, "next", "--run", run_id)["data"]
        self.assertEqual(step["task"]["kind"], "timeline_structure")
        with Store(self.project).connect() as c:
            run, _, _ = Store.run(c, run_id)
        self.assertEqual(run["forecaster"], "alice")
        self.assertEqual(run["mode"], "simulation")
        self.assertEqual(run["max_searches"], 8)
        self.assertEqual(run["research_status"], "in_progress")
        added = self.cli("--project", self.project, "question", "add", "Will Android ship?",
                         "--deadline", "2030-02-01", "--yes", "Android release available.", "--source", "Release log")
        self.assertEqual(added["data"]["question_id"], "will-android-ship")

    def test_invalid_questions_leave_no_partial_project(self):
        cases = [self.question[:-2], self.question + ["--deadline", "not-a-date"],
                 self.question + ["--resolve-after", "2029-01-01"],
                 self.question + ["--profile", "missing"],
                 self.question + ["--deadline", "2030-01-01T00:00:00"],
                 ["--deadline", "2030-01-01"]]
        for options in cases:
            with self.subTest(options=options):
                self.cli("init", self.project, *options, success=False)
                self.assertFalse(self.project.exists())
                self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_files_are_preserved_and_existing_project_is_refused(self):
        self.project.mkdir()
        sentinel = self.project / "notes.txt"
        sentinel.write_text("My notes")
        self.cli("init", self.project, *self.question)
        self.assertEqual(sentinel.read_text(), "My notes")
        before = Workflow(self.project).status()
        self.cli("init", self.project, *self.question, success=False)
        self.assertEqual(Workflow(self.project).status(), before)

    def test_json_inputs_remain_supported_and_mixed_input_is_rejected(self):
        result = self.cli("init", self.project, *self.question)
        spec = result["data"]["question"]
        file = self.root / "question.json"
        file.write_text(json.dumps(spec))
        second = self.root / "second"
        self.assertEqual(self.cli("init", second, "--from", file)["data"]["question"], spec)
        spec["id"] = "another"
        file.write_text(json.dumps(spec))
        self.cli("--project", second, "question", "add", "--from", file)
        self.cli("--project", second, "question", "add", "Ambiguous input", "--from", file, success=False)
        self.cli("--project", second, "run", "start", "another", "--from", file, success=False)
        third = self.root / "third"
        self.cli("init", third, "--from", file, "--deadline", "2031-01-01", success=False)
        self.assertFalse(third.exists())

    def test_past_deadline_never_silently_becomes_retrospective(self):
        self.cli("init", self.project, *self.question, "--deadline", "2020-01-01")
        self.cli("--project", self.project, "run", "start", "app-launch", success=False)
        self.assertEqual(Workflow(self.project).status()["runs"], [])
