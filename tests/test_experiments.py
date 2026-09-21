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


class ArmTests(unittest.TestCase):
    setUp = ExperimentTests.setUp
    spec = ExperimentTests.spec
    resolve = ExperimentTests.resolve
    finish_trial = ExperimentTests.finish_trial

    def minimal_method(self):
        return ex.add_method(self.w.store, method("minimal", prior_method="none", research_domains=[],
                             stages=["assessment", "issue"]))["method_id"]

    def arm(self, name="a", method_id=None, packets=None, **extra):
        return {"id": name, "version": 1, "description": "Synthetic arm.", "method_id": method_id or self.m,
                "model": {"provider": "fixture", "name": name, "parameters": {"temperature": 0}},
                "data": {"label": "synthetic data", "questions": [{"question_id": "factory", "version": 1,
                         "packet_ids": [self.p["packet_id"]] if packets is None else packets}]}, **extra}

    def experiment(self, arms, **extra):
        spec = self.spec(**{"arm_ids": arms, "questions": [{"question_id": "factory", "version": 1}], **extra})
        del spec["method_ids"]
        return ex.add_experiment(self.w.store, spec)["experiment_id"]

    def test_arm_cli_registration_immutable_versions_and_manifest(self):
        import contextlib
        import io
        from vorhersage.cli import main
        spec = self.arm()
        path = Path(self.tmp.name) / "arm.json"
        path.write_text(json.dumps(spec))
        def cli(*args):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main(["--project", self.tmp.name, "arm", *args])
            return json.loads(output.getvalue())["data"]
        arm = cli("add", "--from", str(path))
        self.assertEqual(cli("add", "--from", str(path)), arm)
        self.assertEqual(cli("show", arm["arm_id"])["specification"], spec)
        self.assertEqual(cli("list")[0]["id"], arm["arm_id"])
        self.assertEqual(set(arm["input_manifest"]), {self.m, self.p["packet_id"]})
        with self.assertRaisesRegex(Error, "frozen"):
            ex.add_arm(self.w.store, {**spec, "model": {"provider": "other", "name": "other", "parameters": {}}})
        self.assertNotEqual(ex.add_arm(self.w.store, {**spec, "version": 2})["arm_id"], arm["arm_id"])

    def test_models_data_and_repetitions_are_executed_and_scored_by_arm(self):
        minimal = self.minimal_method()
        a = ex.add_arm(self.w.store, self.arm("a", minimal))["arm_id"]
        b = ex.add_arm(self.w.store, self.arm("b", minimal, packets=[]))["arm_id"]
        experiment = self.experiment([a, b])
        trials = ex.start(self.tmp.name, experiment)["trials"]
        self.assertEqual(len({t["forecaster"] for t in trials}), 4)
        self.assertEqual({t["run_id"] for t in trials}, {t["run_id"] for t in ex.start(self.tmp.name, experiment)["trials"]})
        calls = []
        def worker(command, request, timeout):
            step, config = request["next"], request["worker_config"]
            run = step["context"]["run"]
            calls.append((run["arm_id"], step["task"]["kind"], config))
            self.assertEqual(config["provider"], "fixture")
            self.assertEqual(config["model_parameters"], {"temperature": 0})
            self.assertEqual(run["packet_ids"], [self.p["packet_id"]] if config["model"] == "a" else [])
            refs = self.refs if config["model"] == "a" else []
            answer = response(step, refs, 0.2 if config["model"] == "a" else 0.8)
            return {"payload": answer["payload"], "usage": {"searches": 0, "model_calls": 1, "cost_usd": 0.01}}
        with patch("vorhersage.experiments.invoke", side_effect=worker):
            first = ex.execute(self.tmp.name, experiment, max_tasks=3)
            self.assertEqual(first["status"]["issued_trials"], 0)
            result = ex.execute(self.tmp.name, experiment, max_tasks=20)
        self.assertEqual(result["status"]["issued_trials"], 4)
        self.assertEqual(len(calls), 8)
        self.assertEqual({kind for _, kind, _ in calls}, {"assessment", "issue"})
        self.resolve()
        report = ex.score(self.tmp.name, experiment, now())
        self.assertAlmostEqual(report["arm_scores"][a]["matched_brier"], 0.64)
        self.assertAlmostEqual(report["arm_scores"][b]["matched_brier"], 0.04)
        self.assertAlmostEqual(report["comparisons"][0]["mean_brier_difference"], 0.6)
        self.assertEqual(report["comparisons"][0]["changed_dimensions"], ["model", "data"])
        self.assertEqual(report["arm_scores"][a]["all_trials_reported_model_calls"], 4)
        self.assertAlmostEqual(report["arm_scores"][a]["all_trials_reported_cost_usd"], 0.04)
        self.assertNotIn("method_scores", report)  # Same method must not collapse distinct arms.
        with self.w.store.connect() as c:
            for row in report["evaluation"]["selected"]:
                f = Store.artifact(c, row["forecast_id"], "forecast")
                self.assertIn(f["arm_id"], f["input_manifest"])
                self.assertEqual(f["prior_record"]["timing"], "not_applicable")
                self.assertEqual(f["assessment_probability"], f["probability"])
        self.assertTrue(self.w.doctor()["ok"])

    def test_arm_packet_allowlist_cannot_be_bypassed(self):
        arm = ex.add_arm(self.w.store, self.arm(method_id=self.minimal_method(), packets=[]))["arm_id"]
        experiment = self.experiment([arm], repetitions=1)
        run = ex.start(self.tmp.name, experiment)["trials"][0]["run_id"]
        request = response(self.w.next(run), self.refs)
        request["usage"] = {"searches": 0, "model_calls": 0, "cost_usd": 0}
        with self.assertRaisesRegex(Error, "registered frozen packets"):
            self.w.submit(run, request)
        self.assertEqual(self.w.next(run)["revision"], 0)

    def test_invalid_arm_cohorts_and_ambiguous_specifications_rejected(self):
        spec = self.arm()
        invalid = copy.deepcopy(spec)
        invalid["data"]["questions"] *= 2
        with self.assertRaisesRegex(Error, "Duplicate questions"):
            ex.add_arm(self.w.store, invalid)
        arm = ex.add_arm(self.w.store, spec)["arm_id"]
        with self.assertRaisesRegex(Error, "exactly one"):
            ex.add_experiment(self.w.store, self.spec(arm_ids=[arm]))
        with self.assertRaisesRegex(Error, "take packets from"):
            ex.add_experiment(self.w.store, {k: v for k, v in self.spec(arm_ids=[arm]).items() if k != "method_ids"})
        self.w.question({**question(), "id": "second"})
        with self.assertRaisesRegex(Error, "cover exactly"):
            self.experiment([arm], questions=[{"question_id": "second", "version": 1}])
        with self.assertRaisesRegex(Error, "Duplicate arms"):
            self.experiment([arm, arm])
        with self.assertRaisesRegex(Error, "Packet cutoff"):
            self.experiment([arm], information_as_of=stamp(-3))

    def test_no_review_and_review_preserve_comparable_assessments(self):
        minimal = self.minimal_method()
        reviewed = ex.add_method(self.w.store, method("reviewed", prior_method="none", research_domains=[],
                             stages=["assessment", "review", "issue"]))["method_id"]
        a = ex.add_arm(self.w.store, self.arm("no-review", minimal))["arm_id"]
        bspec = self.arm("review", reviewed)
        bspec["model"] = self.arm("no-review")["model"]
        b = ex.add_arm(self.w.store, bspec)["arm_id"]
        experiment = self.experiment([a, b], repetitions=1)
        def worker(command, request, timeout):
            step = request["next"]
            answer = response(step, self.refs, 0.2)
            if step["task"]["kind"] == "review":
                answer["payload"].update(decision="revise", probability=0.8)
            return {"payload": answer["payload"], "usage": {"searches": 0, "model_calls": 0, "cost_usd": 0}}
        with patch("vorhersage.experiments.invoke", side_effect=worker):
            ex.execute(self.tmp.name, experiment)
        self.resolve()
        report = ex.score(self.tmp.name, experiment, now())
        self.assertEqual(report["comparisons"][0]["changed_dimensions"], ["method"])
        self.assertAlmostEqual(report["arm_scores"][b]["matched_assessment_brier"], 0.64)
        self.assertAlmostEqual(report["arm_scores"][b]["matched_brier"], 0.04)

    def test_incomplete_arm_keeps_cost_but_is_excluded_from_comparison(self):
        minimal = self.minimal_method()
        a = ex.add_arm(self.w.store, self.arm("a", minimal))["arm_id"]
        b = ex.add_arm(self.w.store, self.arm("b", minimal))["arm_id"]
        experiment = self.experiment([a, b], repetitions=1)
        trials = ex.start(self.tmp.name, experiment)["trials"]
        self.finish_trial(trials[0]["run_id"])
        run = trials[1]["run_id"]
        request = response(self.w.next(run), self.refs)
        request["usage"] = {"searches": 0, "model_calls": 1, "cost_usd": 0.2}
        self.w.submit(run, request)
        self.resolve()
        report = ex.score(self.tmp.name, experiment, now())
        self.assertEqual(report["comparisons"][0]["n"], 0)
        self.assertIsNone(report["comparisons"][0]["mean_brier_difference"])
        self.assertEqual(report["arm_scores"][trials[1]["arm_id"]]["all_trials_reported_cost_usd"], 0.2)

    def test_custom_stage_validation_and_full_structured_method(self):
        for stages in (["issue", "assessment"], ["assessment", "assessment", "issue"], ["prior", "issue"]):
            with self.assertRaisesRegex(Error, "ordered subset"):
                ex.add_method(self.w.store, method("bad", stages=stages))
        with self.assertRaisesRegex(Error, "prior_method=none"):
            ex.add_method(self.w.store, method("bad", stages=["assessment", "issue"], research_domains=[]))
        with self.assertRaisesRegex(Error, "empty research_domains"):
            ex.add_method(self.w.store, method("bad", stages=["assessment", "issue"], prior_method="none"))
        full = ex.add_method(self.w.store, method("structured", research_contract="structured_v2"))["method_id"]
        arm = ex.add_arm(self.w.store, self.arm(method_id=full))["arm_id"]
        experiment = self.experiment([arm], repetitions=1)
        run = ex.start(self.tmp.name, experiment)["trials"][0]["run_id"]
        self.assertEqual(self.w.next(run)["task"]["kind"], "intake")
        self.assertEqual(self.w.next(run)["context"]["run"]["research_contract"], "structured_v2")
        self.assertEqual(self.w.next(run)["context"]["run"]["model_semantics_version"], 1)

    def test_offline_factorial_walkthrough(self):
        project = Path(self.tmp.name) / "factorial"
        result = subprocess.run([sys.executable, str(ROOT / "examples/experimental_arms/walkthrough.py"), str(project)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((project / "summary.json").read_text())
        self.assertEqual(summary["issued_trials"], 16)
        self.assertEqual(len(summary["arms"]), 8)
        self.assertTrue(summary["doctor"]["ok"])
        scores = {s["name"]: s for s in summary["arms"]}
        self.assertAlmostEqual(scores["direct-model-a-question-only"]["brier"], 0.25)
        self.assertAlmostEqual(scores["review-model-b-report"]["brier"], 0.04)
        self.assertAlmostEqual(scores["review-model-b-report"]["assessment_brier"], 0.09)
