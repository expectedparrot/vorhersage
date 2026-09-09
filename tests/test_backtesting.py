import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vorhersage.backtesting import prepare_halawi, start_case, evaluate_replay, crowd_at
from vorhersage.common import Error, digest, now
from vorhersage.evaluation import evaluate
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_workflow import response

ROOT = Path(__file__).resolve().parents[1]


def source_row(index=1):
    return {"question": f"Will fictional device {index} ship in January 2020?",
            "url": f"https://example.com/question/{index}", "resolution": index % 2,
            "is_resolved": True, "question_type": "BINARY", "data_source": "fixture",
            "date_begin": "2020-01-01", "date_close": "2020-01-31", "date_resolve_at": "2020-02-01",
            "gpt_3p5_category": "Science & Tech", "resolution_criteria": "A documented shipment by January 31.",
            "background": "ANSWER_LEAK", "extracted_urls": ["https://example.com/ANSWER_LEAK"],
            "community_predictions": json.dumps([["2020-01-06", 0.2], ["2020-01-06", 0.4],
                                                  ["2020-01-08", 0.99], ["2020-02-02", 1.0]])}


class BacktestingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.json"
        self.source.write_text(json.dumps([source_row(1), source_row(2)]))
        self.bundle = self.root / "bundle"
        prepare_halawi(self.source, self.bundle, revision="fixture", split="validation", limit=2)
        self.cases = json.loads((self.bundle / "agent/cases.json").read_text())
        self.labels = json.loads((self.bundle / "evaluator/labels.json").read_text())
        self.manifest = json.loads((self.bundle / "manifest.json").read_text())
        self.w = Workflow(self.root / "project")
        self.w.store.init("Replay test")

    def policy(self, ids=(), forecasters=("baseline:half", "baseline:crowd")):
        return {"forecast_ids": list(ids), "forecasters": list(forecasters), "experiment": "test",
                "contamination_assessment": "synthetic fixtures"}

    def score(self, policy=None):
        return evaluate_replay(self.w.store, self.cases, self.labels, self.manifest, policy or self.policy())

    def finish(self, case, forecaster="agent:test", cutoff=None):
        result = start_case(self.w.store.root, self.cases, case["id"], forecaster, "fixture")
        run_id = result["run_id"]
        if cutoff:
            run_id = self.w.start({"question_id": case["id"], "forecaster": forecaster, "method": "wrong cutoff",
                                   "mode": "retrospective", "information_as_of": cutoff,
                                   "max_searches": 0, "max_extra_tasks": 0})["run_id"]
        while (nxt := self.w.next(run_id))["disposition"] == "actionable":
            body = response(nxt, [], 0.75)
            if nxt["task"]["kind"] == "research":
                body["payload"]["disposition"] = "unknown"
            self.w.submit(run_id, body)
        return nxt["forecast_id"]

    def test_import_allowlist_and_daily_crowd_cutoff(self):
        public = json.dumps(self.cases)
        self.assertNotIn("ANSWER_LEAK", public)
        self.assertNotIn("community_predictions", public)
        self.assertNotIn('"outcome"', public)
        self.assertNotIn('"resolution_date"', public)
        self.assertAlmostEqual(self.labels["labels"][0]["crowd"]["probability"], 0.3)
        self.assertEqual(self.labels["labels"][0]["crowd"]["observations"], 2)
        self.assertIsNone(crowd_at([["2020-01-08", 0.9]], "2020-01-08T12:00:00Z"))

    def test_import_reproducible_and_refuses_overwrite(self):
        other = self.root / "other"
        prepare_halawi(self.source, other, revision="fixture", split="validation", limit=2)
        self.assertEqual(self.cases, json.loads((other / "agent/cases.json").read_text()))
        with self.assertRaises(FileExistsError):
            prepare_halawi(self.source, self.bundle, revision="fixture", split="validation", limit=2)

    def test_import_reports_invalid_rows_without_cherry_picking_winners(self):
        rows = [source_row(1), source_row(2), {**source_row(3), "resolution": 0.6},
                {**source_row(4), "date_close": "2020-01-02"}]
        self.source.write_text(json.dumps(rows))
        out = self.root / "filtered"
        prepare_halawi(self.source, out, revision="fixture", split="validation", limit=2)
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["exclusion_counts"], {"not_binary_resolution": 1, "insufficient_open_window": 1})

    def test_labels_and_cases_are_bound_to_manifest(self):
        self.labels["labels"][0]["outcome"] ^= 1
        with self.assertRaisesRegex(Error, "Label bundle hash"):
            self.score()
        self.cases["cases"][0]["question"]["text"] = "Changed question"
        with self.assertRaisesRegex(Error, "Case bundle hash"):
            self.score()

    def test_scores_match_hand_calculation_and_missing_common_cohort(self):
        result = self.score()
        self.assertEqual(result["summaries"]["baseline:half"]["matched_brier"], 0.25)
        self.assertAlmostEqual(result["summaries"]["baseline:crowd"]["matched_brier"], 0.29)
        result = self.score(self.policy(forecasters=("baseline:half", "missing:agent")))
        self.assertEqual(result["summaries"]["baseline:half"]["matched_n"], 0)
        self.assertIsNone(result["summaries"]["missing:agent"]["matched_brier"])
        self.assertEqual(len(result["exclusions"]), 2)

    def test_historical_replay_keeps_real_issue_time_and_prospective_guard(self):
        case = self.cases["cases"][0]
        fid = self.finish(case)
        result = self.score(self.policy([fid], ("agent:test", "baseline:half")))
        self.assertEqual(result["summaries"]["agent:test"]["matched_n"], 1)
        selected = next(r for r in result["selected"] if r["forecaster"] == "agent:test")
        self.assertGreater(selected["issued_at"], "2020-02-01")
        self.assertEqual(selected["simulated_forecast_at"], case["information_as_of"])
        # A real past knowledge date still excludes this new forecast in the original evaluator.
        with self.w.store.connect(True) as c:
            Store.put(c, "resolution", {"question_id": case["id"], "question_version": 1,
                                       "known_at": "2020-02-01T00:00:00Z", "recorded_at": now(), "outcome": "yes"})
        regular = evaluate(self.w.store, {"question_versions": [{"question_id": case["id"], "version": 1}],
                                         "forecasters": ["agent:test"], "mode": "retrospective",
                                         "cutoff": now(), "resolution_as_of": now()})
        self.assertEqual(regular["summaries"]["agent:test"]["available_n"], 0)
        self.assertTrue(self.w.doctor()["ok"])

    def test_wrong_cutoff_and_duplicate_forecasts_rejected(self):
        fid = self.finish(self.cases["cases"][0], cutoff="2020-01-07T00:00:00Z")
        with self.assertRaisesRegex(Error, "wrong simulated cutoff"):
            self.score(self.policy([fid], ("agent:test",)))
        with self.assertRaisesRegex(Error, "Duplicate forecast ID"):
            self.score(self.policy([fid, fid], ("agent:test",)))

    def test_label_correction_cannot_rewrite_saved_evaluation(self):
        result = self.score()
        original = copy.deepcopy(result["labels_bundle"])
        self.labels["labels"][0]["outcome"] ^= 1
        self.manifest["labels_sha256"] = digest(self.labels)
        second = self.score()
        self.assertNotEqual(result["evaluation_id"], second["evaluation_id"])
        with self.w.store.connect() as c:
            self.assertEqual(Store.artifact(c, result["evaluation_id"])["labels_bundle"], original)

    def test_cli_smoke_exercises_full_workflow_and_separate_evaluator(self):
        out = self.root / "cli_project"
        proc = subprocess.run([sys.executable, str(ROOT / "examples/backtesting/smoke.py"), str(self.bundle), str(out)],
                              text=True, capture_output=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads((out / "summary.json").read_text())
        self.assertEqual(summary["model_calls"], 0)
        self.assertEqual(summary["summaries"]["control:workflow_half"]["matched_brier"], 0.25)
        self.assertEqual(summary["summaries"]["control:workflow_half"]["matched_n"], 2)
        self.assertTrue(summary["doctor"]["ok"])


if __name__ == "__main__":
    unittest.main()
