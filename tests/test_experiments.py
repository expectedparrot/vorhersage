import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vorhersage import experiments as ex
from vorhersage.common import Error, now
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_workflow import question, packet, run_spec, stamp, response, finish

ROOT = Path(__file__).resolve().parents[1]


def method(id="direct", **extra):
    return {"id": id, "version": 1, "description": "Offline test procedure.",
            "instructions": "Use only the frozen packets; explain uncertainty.",
            "task_instructions": {"prior": "Record a provisional estimate."},
            "prior_method": "judgment", "assessment_method": "judgment", "research_domains": ["readiness"],
            "worker": {"command": [sys.executable, str(ROOT / "examples/method_comparison/worker.py")],
                       "config": {"probability": 0.6}, "timeout_seconds": 5},
            "budget": {"max_searches": 0, "max_extra_tasks": 1, "max_model_calls": 20, "max_cost_usd": 1}, **extra}


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.w = Workflow(self.tmp.name)
        self.w.store.init("Experiments")
        self.w.question(question())
        self.p = self.w.import_packet(packet())
        self.refs = [self.p["records"][0]["evidence_ref"]]
        self.m = ex.add_method(self.w.store, method())["method_id"]

    def spec(self, **extra):
        return {"id": "comparison", "version": 1, "description": "Fictional comparison.",
                "questions": [{"question_id": "factory", "version": 1, "packet_ids": [self.p["packet_id"]]}],
                "method_ids": [self.m], "repetitions": 2, "mode": "simulation",
                "information_as_of": now(), "forecast_cutoff": stamp(0.5),
                "evidence_policy": "frozen_packets", "order_seed": "fixed", **extra}

    def register(self, **extra):
        return ex.add_experiment(self.w.store, self.spec(**extra))["experiment_id"]

    def finish_trial(self, run, estimate=0.6):
        while (step := self.w.next(run))["disposition"] == "actionable":
            result = response(step, self.refs, estimate)
            result["usage"] = {"searches": 0, "cost_usd": 0, "model_calls": 0}
            self.w.submit(run, result)
        return step["forecast_id"]

    def resolve(self):
        return self.w.resolve({"question_id": "factory", "question_version": 1, "outcome": "yes",
                               "known_at": now(), "reason": "Fictional outcome.", "evidence_refs": self.refs,
                               "previous_resolution_id": None, "idempotency_key": "resolve"})

    def test_registration_versions_are_immutable_and_retries_are_idempotent(self):
        self.assertEqual(ex.add_method(self.w.store, method())["method_id"], self.m)
        with self.assertRaisesRegex(Error, "frozen"):
            ex.add_method(self.w.store, method(instructions="Changed instructions."))
        other = ex.add_method(self.w.store, method(version=2))["method_id"]
        self.assertNotEqual(other, self.m)
        typed = method(version=3)
        typed["worker"]["config"]["flag"] = True
        ex.add_method(self.w.store, typed)
        typed["worker"]["config"]["flag"] = 1  # Equal in Python, distinct JSON configurations.
        with self.assertRaisesRegex(Error, "frozen"):
            ex.add_method(self.w.store, typed)
        spec = self.spec()
        first = ex.add_experiment(self.w.store, spec)
        self.assertEqual(first, ex.add_experiment(self.w.store, spec))
        with self.assertRaisesRegex(Error, "frozen"):
            ex.add_experiment(self.w.store, {**spec, "repetitions": 3})

    def test_registration_rejects_invalid_cohorts_packets_and_modes(self):
        spec = self.spec()
        for changed, message in (({"questions": spec["questions"] * 2}, "Duplicate questions"),
                                 ({"method_ids": [self.m, self.m]}, "Duplicate methods"),
                                 ({"information_as_of": stamp(-3)}, "Packet cutoff"),
                                 ({"mode": "prospective"}, "mode disagree")):
            with self.subTest(changed=changed), self.assertRaisesRegex(Error, message):
                ex.add_experiment(self.w.store, {**spec, **changed})
        with self.w.store.connect() as c:
            self.assertEqual(Store.all(c, "experiment"), [])

    def test_start_pins_versions_and_distinguishes_methods_and_repetitions(self):
        other = ex.add_method(self.w.store, method("other"))["method_id"]
        experiment = self.register(method_ids=[self.m, other])
        self.w.question({**question(), "text": "Revised event contract."}, expected_version=1)
        first = ex.start(self.tmp.name, experiment)
        again = ex.start(self.tmp.name, experiment)
        self.assertEqual({t["run_id"] for t in first["trials"]}, {t["run_id"] for t in again["trials"]})
        self.assertEqual(len(first["trials"]), 4)
        self.assertEqual(len({t["forecaster"] for t in first["trials"]}), 4)
        for trial in first["trials"]:
            step = self.w.next(trial["run_id"])
            run = step["context"]["run"]
            self.assertEqual(run["question_version"], 1)
            self.assertNotEqual(run["question"]["text"], "Revised event contract.")
            self.assertIn("Record a provisional estimate.", step["task"]["instruction"])
            self.assertEqual(run["profile"]["domains"], ["readiness"])
            self.assertIn(self.p["packet_id"], step["context"]["artifacts"])

    def test_manual_submissions_cannot_bypass_method_evidence_or_usage_limits(self):
        experiment = self.register()
        run = ex.start(self.tmp.name, experiment)["trials"][0]["run_id"]
        step = self.w.next(run)
        base = response(step, self.refs)
        with self.assertRaisesRegex(Error, "report usage"):
            self.w.submit(run, base)
        base["usage"] = {"searches": 0, "cost_usd": 0, "model_calls": 0}
        for usage in ({"searches": 1, "cost_usd": 0, "model_calls": 0},
                      {"searches": 0, "cost_usd": 1.01, "model_calls": 0},
                      {"searches": 0, "cost_usd": 0, "model_calls": 21}):
            with self.subTest(usage=usage), self.assertRaisesRegex(Error, "budget exhausted"):
                self.w.submit(run, {**base, "usage": usage})
        changed = copy.deepcopy(base)
        changed["payload"]["method"] = "reference_class"
        with self.assertRaisesRegex(Error, "registered method"):
            self.w.submit(run, changed)
        other = packet()
        other["records"][0]["claim"] = "Unregistered evidence."
        imported = self.w.import_packet(other)
        changed = copy.deepcopy(base)
        changed["payload"]["evidence_refs"] = [imported["records"][0]["evidence_ref"]]
        with self.assertRaisesRegex(Error, "registered frozen packets"):
            self.w.submit(run, changed)
        self.assertEqual(self.w.next(run)["revision"], 0)
        self.w.submit(run, base)
        next_result = response(self.w.next(run), self.refs)
        next_result["usage"] = base["usage"]
        with patch("vorhersage.workflow.now", return_value=stamp(2)):
            self.assertEqual(self.w.next(run)["disposition"], "blocked")
            with self.assertRaisesRegex(Error, "cutoff passed"):
                self.w.submit(run, next_result)

    def test_scoring_uses_trial_forecasts_and_averages_losses_not_probabilities(self):
        experiment = self.register()
        trials = ex.start(self.tmp.name, experiment)["trials"]
        trial_forecasts = [self.finish_trial(t["run_id"], p) for t, p in zip(trials, (0, 1))]
        # A later ordinary run using the same identity must not replace a trial's forecast.
        outsider = self.w.start(run_spec(forecaster=trials[0]["forecaster"]))["run_id"]
        finish(self.w, outsider, self.refs, 0.7)
        self.resolve()
        report = ex.score(self.tmp.name, experiment, now())
        self.assertEqual(report["method_scores"][self.m]["matched_brier"], 0.5)
        self.assertEqual({r["forecast_id"] for r in report["evaluation"]["selected"]}, set(trial_forecasts))
        self.assertTrue(self.w.doctor()["ok"])
        with self.w.store.connect() as c:
            forecast = Store.artifact(c, trial_forecasts[0], "forecast")
            for id in (experiment, self.m, self.p["packet_id"]):
                self.assertIn(id, forecast["input_manifest"])
            self.assertEqual(forecast["prior_record"]["timing"], "unspecified")

    def test_incomplete_repetition_excludes_question_from_matched_scores(self):
        experiment = self.register()
        trials = ex.start(self.tmp.name, experiment)["trials"]
        self.finish_trial(trials[0]["run_id"])
        initial = response(self.w.next(trials[1]["run_id"]), self.refs)
        initial["usage"] = {"searches": 0, "model_calls": 1, "cost_usd": 0.1}
        accepted = self.w.submit(trials[1]["run_id"], initial)
        self.resolve()
        report = ex.score(self.tmp.name, experiment, now())
        self.assertIsNone(report["method_scores"][self.m]["matched_brier"])
        self.assertEqual(report["method_scores"][self.m]["matched_questions"], 0)
        self.assertEqual(len(report["evaluation"]["exclusions"]), 1)
        self.assertEqual(report["method_scores"][self.m]["all_trials_reported_cost_usd"], 0.1)
        self.assertIn(accepted["artifact_id"], report["input_manifest"])

    def test_worker_failures_are_reported_without_stopping_other_trials(self):
        broken = method("broken", worker={"command": [sys.executable, "-c", "print('private worker output')"],
                                          "config": {}, "timeout_seconds": 5})
        bad = ex.add_method(self.w.store, broken)["method_id"]
        experiment = self.register(method_ids=[self.m, bad], repetitions=1)
        ex.execute(self.tmp.name, experiment, max_tasks=1)
        resumed = ex.execute(self.tmp.name, experiment, max_tasks=30)
        self.assertEqual(resumed["status"]["issued_trials"], 1)
        self.assertEqual(resumed["events"][0]["error"], "worker_invalid_json")
        self.assertNotIn("private worker output", json.dumps(resumed))
        self.assertEqual(ex.execute(self.tmp.name, experiment)["status"]["issued_trials"], 1)

    def test_cli_walkthrough_runs_two_methods_two_questions_and_two_repetitions(self):
        project = Path(self.tmp.name) / "cli"
        result = subprocess.run([sys.executable, str(ROOT / "examples/method_comparison/walkthrough.py"), str(project)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((project / "summary.json").read_text())
        self.assertEqual(summary["issued_trials"], 8)
        self.assertAlmostEqual(summary["matched_brier"]["direct"], 0.25)
        self.assertAlmostEqual(summary["matched_brier"]["decomposition"], 0.26)
        self.assertTrue(summary["doctor"]["ok"])
        partial = json.loads((project / "partial.json").read_text())
        self.assertEqual(partial["attempts"], 3)
        self.assertEqual(partial["status"]["issued_trials"], 0)

    def test_small_task_limits_do_not_starve_peers_of_a_failing_worker(self):
        broken = method("broken", worker={"command": [sys.executable, "-c", "print('invalid')"],
                                          "config": {}, "timeout_seconds": 5})
        bad = ex.add_method(self.w.store, broken)["method_id"]
        experiment = self.register(method_ids=[self.m, bad], repetitions=1)
        for _ in range(12):  # Six workflow tasks for the healthy worker, alternating with failures.
            result = ex.execute(self.tmp.name, experiment, max_tasks=1)
        self.assertEqual(result["status"]["issued_trials"], 1)
