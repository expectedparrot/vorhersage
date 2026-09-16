import copy
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vorhersage import sessions as js
from vorhersage.common import Error, now
from vorhersage.evaluation import evaluate
from vorhersage.relations import add as add_relation
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_workflow import question, packet, stamp


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.w = Workflow(self.tmp.name)
        self.s = self.w.store
        self.s.init("Joint sessions")
        for name in ("early", "late", "latest"):
            self.w.question(question(name))
        self.p = self.w.import_packet(packet())
        self.refs = [self.p["records"][0]["evidence_ref"]]
        self.u = self.condition("unconditional", "unconditional")
        self.policy = self.condition("policy", "intervention")
        self.relations = [add_relation(self.s, {"antecedent": {"question_id": a, "version": 1},
                         "consequent": {"question_id": b, "version": 1}, "rationale": "Fictional nested horizons."})["relation_id"]
                          for a, b in (("early", "late"), ("late", "latest"))]

    def condition(self, id, kind, **extra):
        return js.add_condition(self.s, {"id": id, "version": 1, "kind": kind,
                                        "description": "Fictional " + id, **extra})["condition_id"]

    def spec(self, id="session-a", who="a", **extra):
        return {"id": id, "wave": "fixture-wave", "forecaster": who, "protocol": "joint-v1", "repetition": 1,
                "mode": "simulation", "information_as_of": stamp(-0.5),
                "questions": [{"question_id": q, "version": 1} for q in ("early", "late", "latest")],
                "condition_ids": [self.u, self.policy], "packet_ids": [self.p["packet_id"]],
                "relation_ids": self.relations, "numeric_forecasts": [], "bindings": [],
                "provenance": {"kind": "native", "source": "Synthetic test"}, "configuration": {}, **extra}

    def cells(self, u=0.2, policy=0.1):
        return [{"question_id": q, "version": 1, "condition_id": c, "probability": p, "evidence_refs": self.refs}
                for q in ("early", "late", "latest") for c, p in ((self.u, u), (self.policy, policy))]

    def submission(self, cells=None, revision=0, key="first", **extra):
        return {"expected_revision": revision, "idempotency_key": key, "cells": cells or self.cells(),
                "usage": {"searches": 10, "model_calls": 2, "cost_usd": 0.5}, "raw_record": {"text": "Original response"}, **extra}

    def complete(self, who="a", u=0.2, policy=0.1, **extra):
        id = js.start(self.s, self.spec("session-" + who, who, **extra))["session_id"]
        js.submit(self.s, id, self.submission(self.cells(u, policy)))
        js.finalize(self.s, id, {"expected_revision": 1, "idempotency_key": "finish", "rationale": "Fictional final."})
        return id

    def bundle(self, **extra):
        return {"session": self.spec(provenance={"kind": "external", "source": "Original export"}),
                "submissions": [{"submitted_at": stamp(-0.4), "cells": self.cells(),
                                 "usage": {"searches": 10, "model_calls": 2, "cost_usd": 0.5},
                                 "raw_record": {"original": {"text": "Unedited response", "extra_field": 123}}}],
                "finalized_at": stamp(-0.3), "rationale": "Source rationale", **extra}

    def test_condition_versions_and_session_registration_are_frozen(self):
        self.assertEqual(self.u, self.condition("unconditional", "unconditional"))
        with self.assertRaisesRegex(Error, "frozen"):
            self.condition("unconditional", "intervention")
        spec = self.spec()
        id = js.start(self.s, spec)["session_id"]
        self.assertEqual(js.start(self.s, spec)["session_id"], id)
        with self.assertRaisesRegex(Error, "frozen"):
            js.start(self.s, {**spec, "configuration": {"changed": True}})
        self.w.question({**question("early"), "text": "Changed question."}, expected_version=1)
        with self.s.connect() as c:
            pinned = Store.artifact(c, id, "joint_session")["questions"][0]
        self.assertNotEqual(pinned["specification"]["text"], "Changed question.")
        self.assertTrue(self.w.doctor()["ok"])

    def test_partial_replacement_retries_finalization_and_usage(self):
        id = js.start(self.s, self.spec())["session_id"]
        first = self.submission(self.cells()[:1])
        accepted = js.submit(self.s, id, first)
        self.assertTrue(js.submit(self.s, id, first)["duplicate"])
        with self.assertRaisesRegex(Error, "incomplete"):
            js.finalize(self.s, id, {"expected_revision": 1, "idempotency_key": "finish", "rationale": "Too soon"})
        second = self.submission(self.cells(0.3, 0.15), revision=1, key="replace")
        js.submit(self.s, id, second)
        state = js.status(self.s, id)
        self.assertEqual(state["revision"], 2)
        self.assertEqual(state["usage"], {"searches": 20, "model_calls": 4, "cost_usd": 1.0})
        self.assertEqual(len(state["cells"]), 6)
        self.assertEqual(state["submissions"][0]["cells"][0]["probability"], 0.2)
        final = {"expected_revision": 2, "idempotency_key": "finish", "rationale": "Complete"}
        js.finalize(self.s, id, final)
        self.assertTrue(js.finalize(self.s, id, final)["duplicate"])
        self.assertTrue(js.submit(self.s, id, first)["duplicate"])
        with self.assertRaisesRegex(Error, "finalized"):
            js.submit(self.s, id, {**second, "idempotency_key": "late", "expected_revision": 3})
        with self.s.connect() as c:
            saved = Store.artifact(c, js.status(self.s, id)["finalization"]["id"])
        self.assertIn(accepted["submission_id"], saved["input_manifest"])

    def test_invalid_submissions_are_atomic_and_cannot_reuse_keys(self):
        id = js.start(self.s, self.spec())["session_id"]
        for change, message in (({"probability": float("nan")}, "number"),
                                ({"probability": True}, "number"),
                                ({"condition_id": "absent"}, "outside"),
                                ({"version": 2}, "outside"),
                                ({"evidence_refs": [{"packet_id": "unknown", "record_id": "r"}]}, "registered")):
            cells = self.cells()
            cells[-1].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(Error, message):
                js.submit(self.s, id, self.submission(cells))
            self.assertEqual(js.status(self.s, id)["revision"], 0)
        with self.assertRaisesRegex(Error, "Duplicate cells"):
            js.submit(self.s, id, self.submission(self.cells() * 2))
        good = self.submission()
        js.submit(self.s, id, good)
        with self.assertRaisesRegex(Error, "Idempotency key"):
            js.submit(self.s, id, {**good, "raw_record": {"changed": True}})
        with self.assertRaisesRegex(Error, "Stale"):
            js.submit(self.s, id, {**good, "idempotency_key": "new"})

    def test_registration_rejects_bad_modes_grids_and_evidence(self):
        for update, message in (({"condition_ids": [self.policy]}, "exactly one"),
                                ({"condition_ids": [self.u, self.u]}, "Duplicate"),
                                ({"mode": "prospective"}, "mode disagree"),
                                ({"information_as_of": stamp(-2)}, "Packet cutoff"),
                                ({"information_as_of": stamp(1)}, "future"),
                                ({"questions": [{"question_id": "early", "version": 1}]}, "Relations")):
            with self.subTest(update=update), self.assertRaisesRegex(Error, message):
                js.start(self.s, self.spec(**update))

    def test_numeric_conditions_are_bound_to_own_ordered_quantiles(self):
        binding = {"variable": "capability", "unit": "index points", "target_at": stamp(180),
                   "vintage": "fixture-index-v1", "quantile": 0.9, "tolerance": 2}
        high = self.condition("high", "information", binding=binding)
        numeric = {k: binding[k] for k in ("variable", "unit", "target_at", "vintage")}
        numeric["quantiles"] = [{"level": 0.1, "value": 100}, {"level": 0.9, "value": 200}]
        spec = self.spec(condition_ids=[self.u, high], numeric_forecasts=[numeric],
                         bindings=[{"condition_id": high, "value": 200}])
        js.start(self.s, spec)
        for updates, message in (({"bindings": []}, "Bindings"),
                                 ({"bindings": [{"condition_id": high, "value": 201}]}, "own quantile"),
                                 ({"numeric_forecasts": []}, "matching numeric")):
            with self.subTest(updates=updates), self.assertRaisesRegex(Error, message):
                js.start(self.s, {**spec, "id": "invalid", **updates})
        bad = copy.deepcopy(spec)
        bad["id"] = "bad-quantiles"
        bad["numeric_forecasts"][0]["quantiles"][0]["value"] = 300
        with self.assertRaisesRegex(Error, "nondecreasing"):
            js.start(self.s, bad)
        with self.assertRaisesRegex(Error, "Unconditional"):
            self.condition("invalid-u", "unconditional", binding=binding)

    def test_external_import_retains_timestamps_raw_data_and_atomic_retries(self):
        bundle = self.bundle()
        result = js.import_session(self.s, bundle)
        self.assertTrue(js.import_session(self.s, bundle)["duplicate"])
        state = js.status(self.s, result["session_id"])
        self.assertEqual(state["finalization"]["finalized_at"], bundle["finalized_at"])
        self.assertEqual(state["finalization"]["timestamp_basis"], "source_reported")
        self.assertNotEqual(state["recorded_at"], bundle["finalized_at"])
        self.assertEqual(state["submissions"][0]["raw_record"], bundle["submissions"][0]["raw_record"])
        with self.s.connect() as c:
            self.assertEqual(Store.artifact(c, result["import_id"])["bundle"], bundle)
            self.assertEqual(Store.all(c, "forecast"), [])
            self.assertEqual(Store.all(c, "task_result"), [])
        changed = copy.deepcopy(bundle)
        changed["rationale"] = "Changed"
        with self.assertRaisesRegex(Error, "Idempotency key"):
            js.import_session(self.s, changed)
        self.assertTrue(self.w.doctor()["ok"])

    def test_incomplete_or_misdated_import_rolls_back_every_artifact(self):
        for problem in ("incomplete", "future", "out_of_order"):
            bundle = self.bundle()
            if problem == "incomplete":
                bundle["submissions"][0]["cells"].pop()
            elif problem == "future":
                bundle["finalized_at"] = stamp(1)
            else:
                bundle["finalized_at"] = stamp(-0.45)
            with self.subTest(problem=problem), self.assertRaises(Error):
                js.import_session(self.s, bundle)
            with self.s.connect() as c:
                for kind in ("joint_session", "joint_submission", "joint_finalization", "joint_import"):
                    self.assertEqual(Store.all(c, kind), [])

    def test_coherence_is_scoped_transitive_and_preserves_raw_violations(self):
        id = js.start(self.s, self.spec())["session_id"]
        cells = self.cells()
        cells[0]["probability"] = 0.8
        js.submit(self.s, id, self.submission(cells))
        report = js.coherence(self.s, id)
        self.assertEqual(len(report["comparisons"]), 6)  # Three implied pairs per condition.
        self.assertEqual(len(report["violations"]), 2)
        js.finalize(self.s, id, {"expected_revision": 1, "idempotency_key": "finish", "rationale": "Keep raw values"})
        self.complete("later", u=0.9)
        self.assertEqual(js.coherence(self.s, id)["comparisons"], report["comparisons"])
        self.assertEqual(js.status(self.s, id)["finalization"]["coherence"]["violations"], report["violations"])

    def test_panel_medians_paired_geometric_ratios_and_costs(self):
        ids = [self.complete(str(i), u, p) for i, (u, p) in enumerate(zip((0.01, 0.02, 0.2, 0.3), (0.02, 0.02, 0.1, 0.15)))]
        report = js.aggregate(self.s, {"session_ids": ids, "expected_forecasters": ["0", "1", "2", "3"]})
        row = next(r for r in report["rows"] if r["condition_id"] == self.policy)
        self.assertAlmostEqual(row["median_probability"], 0.06)
        self.assertAlmostEqual(row["multiplier"], math.sqrt(0.5))
        self.assertNotAlmostEqual(row["multiplier"], 0.06 / 0.11)
        self.assertEqual(report["usage"]["cost_usd"], 2)
        reverse = js.aggregate(self.s, {"session_ids": ids, "expected_forecasters": ["0", "1", "2", "3"],
                                       "baseline_condition_id": self.policy})
        reverse_row = next(r for r in reverse["rows"] if r["condition_id"] == self.u)
        self.assertAlmostEqual(reverse_row["multiplier"], math.sqrt(2))
        self.assertTrue(self.w.doctor()["ok"])

    def test_incomplete_panel_is_flagged_without_silently_reweighting(self):
        id = self.complete()
        report = js.aggregate(self.s, {"session_ids": [id], "expected_forecasters": ["a", "missing"]})
        self.assertFalse(report["complete_panel"])
        self.assertEqual(report["missing_forecasters"], ["missing"])
        self.assertTrue(all(r["median_probability"] is None and r["multiplier"] is None for r in report["rows"]))

    def test_panel_rejects_mixing_waves_repetitions_protocols_and_identities(self):
        a = self.complete()
        for change in ({"wave": "other"}, {"repetition": 2}, {"protocol": "other"}):
            who = str(len(js.status(self.s, a)["cells"])) + next(iter(change))
            b = self.complete(who, **change)
            with self.subTest(change=change), self.assertRaisesRegex(Error, "share wave"):
                js.aggregate(self.s, {"session_ids": [a, b], "expected_forecasters": ["a", who]})
        with self.assertRaisesRegex(Error, "Duplicate session"):
            js.aggregate(self.s, {"session_ids": [a, a], "expected_forecasters": ["a"]})
        with self.assertRaisesRegex(Error, "Unexpected"):
            js.aggregate(self.s, {"session_ids": [a], "expected_forecasters": ["b"]})

    def test_zero_probabilities_and_extreme_ratios_never_clip_or_emit_nonfinite_json(self):
        for who, u, p, reason, expected in (("zero-base", 0, 0.1, "zero_denominator", None),
                                           ("zero-both", 0, 0, "zero_denominator", None),
                                           ("zero-numerator", 0.2, 0, "defined", 0.0),
                                           ("overflow", 5e-324, 1, "unrepresentable_multiplier", None)):
            id = self.complete(who, u, p)
            report = js.aggregate(self.s, {"session_ids": [id], "expected_forecasters": [who]})
            row = next(r for r in report["rows"] if r["condition_id"] == self.policy)
            self.assertEqual(row["multiplier_status"], reason)
            self.assertEqual(row["multiplier"], expected)
            json.dumps(report, allow_nan=False)

    def test_hypothetical_and_imported_cells_do_not_enter_ordinary_scoring(self):
        self.complete()
        self.w.resolve({"question_id": "early", "question_version": 1, "outcome": "yes", "known_at": now(),
                        "reason": "Fictional outcome", "evidence_refs": self.refs,
                        "previous_resolution_id": None, "idempotency_key": "resolution"})
        report = evaluate(self.s, {"question_versions": [{"question_id": "early", "version": 1}],
                                  "forecasters": ["a"], "cutoff": now(), "resolution_as_of": now(), "mode": "simulation"})
        self.assertEqual(report["selected"], [])
        self.assertIsNone(report["summaries"]["a"]["matched_brier"])

    def test_prospective_source_dates_and_native_known_outcomes(self):
        from unittest.mock import patch
        for name in ("early", "late", "latest"):
            self.w.question(question(name, kind="real"), expected_version=1)
        spec = self.spec(mode="prospective", questions=[{"question_id": "early", "version": 2}], relation_ids=[])
        cells = [{**cell, "version": 2} for cell in self.cells() if cell["question_id"] == "early"]
        id = js.start(self.s, spec)["session_id"]
        js.submit(self.s, id, self.submission(cells))
        final = {"expected_revision": 1, "idempotency_key": "finish", "rationale": "Test eligibility"}
        with patch("vorhersage.sessions.now", return_value=stamp(3)):
            with self.assertRaisesRegex(Error, "event deadline"):
                js.finalize(self.s, id, final)
        self.w.resolve({"question_id": "early", "question_version": 2, "outcome": "yes", "known_at": now(),
                        "reason": "Early outcome", "evidence_refs": self.refs,
                        "previous_resolution_id": None, "idempotency_key": "resolved"})
        with self.assertRaisesRegex(Error, "already has a resolution"):
            js.finalize(self.s, id, final)
        bundle = self.bundle()
        bundle["session"] = {**spec, "id": "historical-source", "provenance": {"kind": "external", "source": "Archive"}}
        bundle["submissions"][0]["cells"] = cells
        imported = js.import_session(self.s, bundle)
        self.assertEqual(js.status(self.s, imported["session_id"])["finalization"]["timestamp_basis"], "source_reported")
        self.assertEqual(js.status(self.s, id)["disposition"], "open")

    def test_aggregation_retains_distinct_numeric_bindings_and_rejects_open_sessions(self):
        binding = {"variable": "capability", "unit": "points", "target_at": stamp(180),
                   "vintage": "fixture", "quantile": 0.9, "tolerance": 2}
        high = self.condition("high", "information", binding=binding)
        ids = []
        for who, value in (("a", 180), ("b", 190)):
            numeric = {k: binding[k] for k in ("variable", "unit", "target_at", "vintage")}
            numeric["quantiles"] = [{"level": 0.9, "value": value}]
            id = js.start(self.s, self.spec("bound-" + who, who, condition_ids=[self.u, high],
                          numeric_forecasts=[numeric], bindings=[{"condition_id": high, "value": value}]))["session_id"]
            with self.assertRaisesRegex(Error, "finalized"):
                js.aggregate(self.s, {"session_ids": [id], "expected_forecasters": [who]})
            cells = self.cells()
            for cell in cells:
                if cell["condition_id"] == self.policy:
                    cell["condition_id"] = high
            js.submit(self.s, id, self.submission(cells))
            js.finalize(self.s, id, {"expected_revision": 1, "idempotency_key": "final", "rationale": "Bound condition"})
            ids.append(id)
        report = js.aggregate(self.s, {"session_ids": ids, "expected_forecasters": ["a", "b"]})
        row = next(r for r in report["rows"] if r["condition_id"] == high)
        self.assertEqual([m["condition_value"] for m in row["members"]], [180, 190])

    def test_cli_walkthrough(self):
        root = Path(__file__).resolve().parents[1]
        project = Path(self.tmp.name) / "demo"
        result = subprocess.run([sys.executable, str(root / "examples/joint_sessions/walkthrough.py"), str(project)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((project / "summary.json").read_text())
        self.assertEqual(summary["finalized_sessions"], 4)
        self.assertEqual(summary["cells_per_session"], 6)
        self.assertAlmostEqual(summary["policy_multiplier"], math.sqrt(0.5))
        self.assertTrue(summary["doctor"]["ok"])


if __name__ == "__main__":
    unittest.main()
