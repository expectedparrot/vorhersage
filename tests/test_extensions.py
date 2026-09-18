import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vorhersage.common import Error, now
from vorhersage.evidence import audit, capture_bundle, fingerprint, validate_packet
from vorhersage.monitoring import configure, disable, tick
from vorhersage.reference import add as add_reference, query as query_reference
from vorhersage.relations import add as add_relation, audit as audit_relations
from vorhersage.scenarios import calculate
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_workflow import packet, question, run_spec, response, finish, stamp


def mixture():
    return {"partition_justification": "Ready and not ready partition the fixture at the forecast cutoff.",
            "scenarios": [{"id": id, "description": id, "weight": weight, "probability": p,
                           "rationale": "Fixture assumption.", "evidence_refs": [], "unknowns": ["Readiness unobserved."],
                           "weight_range": [0.2, 0.8], "probability_range": interval}
                          for id, weight, p, interval in [("ready", 0.6, 0.8, [0.7, 0.9]),
                                                          ("not_ready", 0.4, 0.1, [0, 0.2])]]}


class ScenarioTests(unittest.TestCase):
    def test_mixture_and_joint_extremes_preserve_mass(self):
        result = calculate(mixture())
        self.assertAlmostEqual(result["probability"], 0.52)
        self.assertAlmostEqual(result["bounded_range"][0], 0.14)
        self.assertAlmostEqual(result["bounded_range"][1], 0.76)
        for allocation in result["extreme_allocations"].values():
            self.assertAlmostEqual(sum(allocation["weights"].values()), 1)
        self.assertEqual(result["conditional_sensitivity"][0]["scenario_id"], "ready")
        self.assertAlmostEqual(abs(result["weight_transfers"][0]["probability_change"]), 0.07)

    def test_invalid_partitions_bounds_and_numbers(self):
        mutations = [lambda s: s["scenarios"][0].update(weight=0.7),
                     lambda s: s["scenarios"][1].update(id="ready"),
                     lambda s: s["scenarios"][0].update(weight_range=[0.7, 0.8]),
                     lambda s: s["scenarios"][0].update(probability_range=[0, 0.5, 1]),
                     lambda s: s["scenarios"][0].update(probability=True),
                     lambda s: s["scenarios"][0].update(weight=float("nan"))]
        for mutate in mutations:
            spec = mixture()
            mutate(spec)
            with self.subTest(spec=spec), self.assertRaises(Error):
                calculate(spec)

    def test_zero_weight_and_no_ranges(self):
        spec = mixture()
        for i, row in enumerate(spec["scenarios"]):
            row["weight"] = float(i)
            row.pop("weight_range")
            row.pop("probability_range")
        result = calculate(spec)
        self.assertEqual(result["probability"], 0.1)
        self.assertEqual(result["bounded_range"], [0.1, 0.1])
        self.assertEqual(result["weight_transfers"], [])


class EvidenceTests(unittest.TestCase):
    def test_capture_hash_quote_and_inference_metadata(self):
        source = packet()["records"][0]["sources"][0]
        source.update(excerpt="ready", excerpt_kind="quotation",
                      capture={"method": "fetched", "captured_at": stamp(-3), "content": "Factory is ready."})
        bundle = {"sources": [source], "findings": [{"id": "f", "claim": "Readiness supports shipment.",
                  "source_ids": [source["id"]], "claim_type": "inference"}], "limitations": ["Fixture"]}
        frozen = capture_bundle(bundle)
        self.assertEqual(audit(frozen)["inference_records"], ["f"])
        self.assertEqual(len(frozen["records"][0]["sources"][0]["capture"]["content_sha256"]), 64)
        bundle["sources"][0]["excerpt"] = "missing quotation"
        with self.assertRaisesRegex(Error, "does not occur"):
            capture_bundle(bundle)
        bundle["sources"][0]["excerpt_kind"] = "paraphrase"
        self.assertTrue(capture_bundle(bundle))
        bundle["sources"][0]["capture"]["content_sha256"] = "bad"
        with self.assertRaisesRegex(Error, "hash mismatch"):
            capture_bundle(bundle)

    def test_transitive_repetitions_and_false_independence(self):
        p = packet()
        p["records"] = [copy.deepcopy(p["records"][0]) for _ in range(4)]
        for i, r in enumerate(p["records"]):
            r["id"] = str(i)
            r["sources"][0]["url"] = "https://example.test/" + str(i)
        p["relationships"] = [{"from_record": a, "to_record": b, "relation": relation, "rationale": "Fixture."}
                              for a, b, relation in [("1", "0", "repeats"), ("2", "1", "repeats"),
                                                     ("2", "0", "independently_confirms"), ("3", "0", "contradicts")]]
        result = audit(p)
        self.assertIn(["0", "1", "2"], result["dependence_groups"])
        self.assertEqual(len(result["independence_conflicts"]), 1)
        self.assertEqual(len(result["contradictions"]), 1)
        p["relationships"][0]["to_record"] = "absent"
        with self.assertRaisesRegex(Error, "unknown record"):
            validate_packet(p)

    def test_fresh_timestamps_are_not_news_but_changed_claims_are(self):
        p = packet()
        q = copy.deepcopy(p)
        q["created_at"] = now()
        q["records"][0]["observed_at"] = now()
        q["records"][0]["sources"][0]["retrieved_at"] = now()
        self.assertEqual(fingerprint(p), fingerprint(q))
        q["records"][0]["claim"] = "Corrected status"
        self.assertNotEqual(fingerprint(p), fingerprint(q))


class ExtensionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.w = Workflow(self.tmp.name)
        self.w.store.init("Extension tests")
        self.w.question(question(kind="real"))
        self.imported = self.w.import_packet(packet())
        self.refs = [self.imported["records"][0]["evidence_ref"]]

    def run_start(self, **kw):
        return self.w.start(run_spec(mode="prospective", **kw))["run_id"]

    def test_prior_declaration_and_optional_scenario_in_workflow(self):
        id = self.run_start(research_status="completed")
        while (step := self.w.next(id))["task"]["kind"] != "assessment":
            self.w.submit(id, response(step, self.refs))
        self.assertEqual(step["context"]["prior_record"]["timing"], "after_research_started")
        self.assertTrue(step["context"]["evidence_audits"])
        request = response(step, self.refs)
        request["payload"].pop("probability")
        request["payload"].update(method="scenario_mixture", **mixture())
        self.w.submit(id, request)
        fid = finish(self.w, id, self.refs)
        with self.w.store.connect() as c:
            f = Store.artifact(c, fid)
            self.assertAlmostEqual(f["probability"], 0.52)
            self.assertEqual(f["prior_record"]["research_status_at_run_start"], "completed")
        self.assertTrue(self.w.doctor()["ok"])

    def test_legacy_prior_unspecified_and_pre_research_attestation(self):
        for status in (None, "not_started"):
            id = self.run_start(**({"research_status": status} if status else {}))
            self.w.submit(id, response(self.w.next(id), self.refs))
            timing = self.w.next(id)["context"]["prior_record"]["timing"]
            self.assertEqual(timing, "declared_before_research" if status else "unspecified")

    def test_transitive_coherence_strict_and_version_pinning(self):
        for id in ("intermediate", "larger"):
            self.w.question(question(id, kind="real"))
        for a, b in [("factory", "intermediate"), ("intermediate", "larger")]:
            add_relation(self.w.store, {"antecedent": {"question_id": a, "version": 1},
                                      "consequent": {"question_id": b, "version": 1}, "rationale": "Fixture implication."})
        finish(self.w, self.run_start(question_id="larger"), self.refs, 0.2)
        id = self.run_start(coherence_policy="strict")
        while (step := self.w.next(id))["task"]["kind"] != "issue":
            self.w.submit(id, response(step, self.refs, 0.8))
        with self.assertRaisesRegex(Error, "violates"):
            self.w.submit(id, response(step, self.refs))
        finish(self.w, self.run_start(), self.refs, 0.8)
        with self.w.store.connect() as c:
            result = audit_relations(c)
        self.assertEqual(len(result["violations"]), 1)
        self.assertEqual(len(result["violations"][0]["relation_ids"]), 2)
        self.w.question(question("larger", kind="real"), expected_version=1)
        finish(self.w, self.run_start(question_id="larger"), self.refs, 0.95)
        with self.w.store.connect() as c:
            self.assertEqual(len(audit_relations(c)["violations"]), 1)
        self.assertTrue(self.w.doctor()["ok"])

    def test_reference_horizons_censoring_and_historical_cutoff(self):
        # Capture available before all episode knowledge dates.
        base = packet()
        base["information_as_of"] = stamp(-20)
        base["records"][0]["observed_at"] = stamp(-21)
        base["records"][0]["sources"][0]["retrieved_at"] = stamp(-21)
        ref = self.w.import_packet(base)["records"][0]["evidence_ref"]
        for id, event, observed, known in [("fast", -8, -2, -1), ("late", -3, -2, -1),
                                            ("censored", None, -9, -8), ("later_known", None, -2, 0)]:
            add_reference(self.w.store, {"id": id, "description": "Fixture episode", "tags": ["fixture"],
                          "trigger_at": stamp(-10), "event_at": stamp(event) if event is not None else None,
                          "observed_until": stamp(observed), "known_at": stamp(known), "evidence_refs": [ref]})
        result = query_reference(self.w.store, {"tags": ["fixture"], "horizon_days": 3, "known_as_of": stamp(-0.5),
                                               "selection_rule": "All synthetic fixture episodes."})
        self.assertIsNone(result["probability"])
        self.assertIsNone(result["prior_payload"])
        self.assertEqual(result["resolved_case_frequency"]["probability"], 0.5)
        self.assertEqual(result["unascertained_mature"], ["censored"])
        self.assertEqual(result["censored"], ["censored"])
        self.assertEqual(result["excluded_after_cutoff"], ["later_known"])
        self.assertEqual(result["sample_size"], 2)

    def watch(self, **kw):
        return configure(self.w.store, {"id": "test", "question_id": "factory", "forecaster": "agent:a",
                                        "interval_seconds": 60, **kw})

    def test_monitor_change_detection_resumption_and_failure_recovery(self):
        fid = finish(self.w, self.run_start(), self.refs)
        self.watch(research_command=["fixture-research"])
        fresh = packet()
        fresh["records"][0]["value"] = {"ready": False}
        with patch('vorhersage.monitoring.invoke', return_value={"packets": [fresh]}):
            a = tick(self.tmp.name)["checks"][0]
            self.assertTrue(a["changed"])
            self.assertEqual(a["disposition"], "revision_ready")
            self.assertEqual(tick(self.tmp.name)["checks"][0]["disposition"], "not_due")
            b = tick(self.tmp.name, force=True)["checks"][0]
        self.assertFalse(b["changed"])
        self.assertEqual(a["run_id"], b["run_id"])
        with patch('vorhersage.monitoring.invoke', side_effect=Error('fixture', 'Failure')):
            self.assertEqual(tick(self.tmp.name, force=True)["checks"][0]["disposition"], "error")
        with patch('vorhersage.monitoring.invoke', return_value={"packets": [fresh]}):
            self.assertFalse(tick(self.tmp.name, force=True)["checks"][0]["changed"])
        self.assertEqual(self.w.report("factory")["forecasts"][0]["id"], fid)
        self.assertTrue(self.w.doctor()["ok"])

    def test_monitor_runs_real_subprocess_agent_to_issue_revision(self):
        first = finish(self.w, self.run_start(), self.refs, 0.2)
        self.w.signal({"question_id": "factory", "reason": "Review fixture", "evidence_refs": [], "idempotency_key": "test"})
        worker = Path(self.tmp.name) / 'worker.py'
        tests = str(Path(__file__).resolve().parent)
        worker.write_text('import sys,json\nsys.path.insert(0, ' + repr(tests) + ')\n'
                          'from test_workflow import payload\n'
                          'request=json.load(sys.stdin)\n'
                          'step=request["next"]\n'
                          'refs=step["context"]["run"]["previous_forecast_id"]\n'
                          'old=step["context"]["artifacts"][refs]\n'
                          'print(json.dumps({"payload":payload(step["task"]["kind"],old["evidence_refs"],0.8)}))\n')
        self.watch(agent_command=[sys.executable, str(worker)])
        result = tick(self.tmp.name)["checks"][0]
        self.assertEqual(result["disposition"], "waiting", result)
        forecasts = self.w.report("factory")["forecasts"]
        self.assertEqual(len(forecasts), 2)
        self.assertEqual(forecasts[-1]["previous_forecast_id"], first)
        self.assertEqual(forecasts[-1]["probability"], 0.8)
        self.assertFalse(self.w.monitor()["due"])

    def test_resolution_does_not_start_expired_prospective_run(self):
        finish(self.w, self.run_start(), self.refs)
        self.watch(agent_command=["resolver"])
        self.w.signal({"question_id": "factory", "reason": "Outcome available", "evidence_refs": [], "idempotency_key": "outcome"})
        with patch('vorhersage.monitoring.now', return_value=stamp(3)), patch('vorhersage.monitoring.invoke', return_value={"defer": "Need an official outcome"}):
            result = tick(self.tmp.name, force=True)["checks"][0]
        self.assertEqual(result["disposition"], "resolution_due")
        self.assertNotIn("run_id", result)

    def test_worker_can_resolve_an_early_outcome_and_stop_polling(self):
        finish(self.w, self.run_start(), self.refs)
        self.w.signal({"question_id": "factory", "reason": "Event occurred", "evidence_refs": [], "idempotency_key": "early"})
        self.watch(agent_command=["resolver"])
        resolution = {"question_id": "factory", "question_version": 1, "outcome": "yes",
                      "reason": "Synthetic early outcome.", "known_at": now(), "evidence_refs": self.refs,
                      "previous_resolution_id": None, "idempotency_key": "early-resolution"}
        with patch('vorhersage.monitoring.invoke', return_value={"resolution": resolution}) as worker:
            self.assertEqual(tick(self.tmp.name)["checks"][0]["disposition"], "resolved")
            worker.reset_mock()
            self.assertEqual(tick(self.tmp.name, force=True)["checks"][0]["disposition"], "resolved")
            worker.assert_not_called()
        self.assertEqual(self.w.status()["forecast_count"], 1)

    def test_watch_stop_and_cli_once(self):
        finish(self.w, self.run_start(), self.refs)
        self.watch()
        cmd = [sys.executable, '-m', 'vorhersage', '--project', self.tmp.name, 'watch', 'run', '--cycles', '1']
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["data"]["checks"][0]["disposition"], "unchanged")
        disable(self.w.store, "test")
        self.assertEqual(tick(self.tmp.name, force=True)["checks"], [])

    def test_calendar_trigger_is_actionable_before_review_date(self):
        id = self.run_start()
        while (step := self.w.next(id))["task"]["kind"] != "issue":
            self.w.submit(id, response(step, self.refs))
        req = response(step, self.refs)
        req["payload"]["triggers"][0]["at"] = stamp(0.1)
        self.w.submit(id, req)
        self.assertFalse(self.w.monitor()["due"])
        with patch('vorhersage.workflow.now', return_value=stamp(0.2)):
            reasons = self.w.monitor()["due"][0]["reasons"]
        self.assertTrue(any(r.startswith("Calendar trigger:") for r in reasons))
        self.assertNotIn("Scheduled review is due.", reasons)

    def test_monitor_retries_after_invalid_agent_output_without_duplicate_run(self):
        finish(self.w, self.run_start(), self.refs)
        self.w.signal({"question_id": "factory", "reason": "Review", "evidence_refs": [], "idempotency_key": "retry"})
        self.watch(agent_command=["fixture"])
        with patch('vorhersage.monitoring.invoke', return_value={"payload": {"bad": True}}):
            first = tick(self.tmp.name)["checks"][0]
        self.assertEqual(first["disposition"], "error")
        with patch('vorhersage.monitoring.invoke', return_value={"defer": "More research needed"}):
            second = tick(self.tmp.name, force=True)["checks"][0]
        self.assertEqual(second["disposition"], "revision_ready")
        self.assertEqual(len(self.w.status()["runs"]), 2)

    def test_cli_capture_audit_scenario_and_reference(self):
        def cli(*args, value=None):
            command = [sys.executable, '-m', 'vorhersage', '--project', self.tmp.name, *args]
            if value is not None:
                command += ['--from', '-']
            result = subprocess.run(command, input=json.dumps(value) if value is not None else None,
                                    text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)['data']
        self.assertAlmostEqual(cli('scenario', value=mixture())['probability'], 0.52)
        source = packet()['records'][0]['sources'][0]
        imported = cli('research', 'capture', value={'sources': [source], 'findings': [
            {'id': 'x', 'claim': 'A fixture', 'claim_type': 'observation', 'source_ids': [source['id']]}], 'limitations': ['Fixture']})
        self.assertIn('provenance_gaps', cli('packet', 'audit', imported['packet_id']))
        cli('reference', 'add', value={'id': 'case', 'episode_id': 'case', 'eligibility': 'The synthetic fixture.',
            'description': 'Fixture', 'tags': ['test'],
            'trigger_at': stamp(-3), 'event_at': stamp(-2), 'observed_until': stamp(-1), 'known_at': now(),
            'evidence_refs': [imported['records'][0]['evidence_ref']]})
        result = cli('reference', 'query', value={'tags': ['test'], 'horizon_days': 2,
            'known_as_of': now(), 'selection_rule': 'The synthetic fixture.'})
        self.assertEqual(result['probability'], 1)


if __name__ == '__main__':
    unittest.main()
