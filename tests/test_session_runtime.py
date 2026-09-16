import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_sessions as fixtures
from test_workflow import packet, stamp
from vorhersage import sessions, session_runtime as runtime, session_studies, session_reports
from vorhersage.common import Error, now
from vorhersage.store import Store


def execution(**changes):
    return {"evidence_policy": "live", "defer_bindings": True,
            "research": {"minimum_successful_tools": 0, "minimum_unique_pages": 0, "domains": []},
            "budget": {"max_model_calls": 10, "max_searches": 10, "max_cost_usd": 2},
            "requirements": [{"id": "effort", "description": "Provider effort", "expected": {"effort": "high"}}],
            "worker": {"command": [sys.executable, "unused.py"], "config": {}, "timeout_seconds": 5}, **changes}


class RuntimeTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    condition = fixtures.SessionTests.condition
    spec = fixtures.SessionTests.spec
    cells = fixtures.SessionTests.cells
    submission = fixtures.SessionTests.submission

    def start(self, **changes):
        return sessions.start(self.s, self.spec(execution=execution(**changes)))["session_id"]

    def event(self, id, kind, payload, **changes):
        revision = sessions.status(self.s, id)["revision"]
        return runtime.record(self.s, id, {"kind": kind, "payload": payload,
                                          "expected_revision": revision, "idempotency_key": str(revision), **changes})

    def attempt(self, id, aid="a", status="completed", usage=None, kind="model"):
        self.event(id, "attempt_start", {"attempt_id": aid, "kind": kind, "request": {}})
        self.event(id, "attempt_result", {"attempt_id": aid, "status": status,
            "usage": usage, "continuation": {}, "raw_record": {"provider_status": status}})

    def test_live_evidence_is_staged_and_each_submission_preserves_its_view(self):
        id = self.start()
        sessions.submit(self.s, id, self.submission(self.cells()[:1], usage=runtime.ZERO))
        new = packet()
        new["information_as_of"] = now()
        p = self.w.import_packet(new)
        self.event(id, "evidence", {"packet_ids": [p["packet_id"]], "information_as_of": now()})
        state = sessions.status(self.s, id)
        self.assertNotIn(p["packet_id"], state["submissions"][0]["available_packet_ids"])
        self.assertNotIn(p["packet_id"], state["registered_specification"]["packet_ids"])
        self.assertIn(p["packet_id"], state["specification"]["packet_ids"])
        self.assertEqual(state["revision"], 2)
        with self.assertRaisesRegex(Error, "already"):
            self.event(id, "evidence", {"packet_ids": [p["packet_id"]], "information_as_of": now()})
        self.assertTrue(self.w.doctor()["ok"])

    def test_fixed_evidence_and_future_cutoffs_are_rejected(self):
        id = self.start(evidence_policy="fixed")
        with self.assertRaisesRegex(Error, "Fixed-evidence"):
            self.event(id, "evidence", {"packet_ids": [self.p["packet_id"]], "information_as_of": now()})
        self.assertEqual(sessions.status(self.s, id)["revision"], 0)

    def test_deferred_bindings_block_cells_then_freeze_before_probabilities(self):
        binding = {"variable": "capability", "unit": "points", "target_at": stamp(30), "vintage": "fixture", "quantile": .5, "tolerance": 0}
        high = self.condition("high", "information", binding=binding)
        id = sessions.start(self.s, self.spec(condition_ids=[self.u, high], execution=execution()))["session_id"]
        cells = self.cells()
        for cell in cells:
            if cell["condition_id"] == self.policy:
                cell["condition_id"] = high
        with self.assertRaisesRegex(Error, "Bindings"):
            sessions.submit(self.s, id, self.submission(cells, usage=runtime.ZERO))
        numeric = {k: binding[k] for k in ("variable", "unit", "target_at", "vintage")}
        numeric["quantiles"] = [{"level": .5, "value": 180}]
        payload = {"numeric_forecasts": [numeric], "bindings": [{"condition_id": high, "value": 180}]}
        self.event(id, "bindings", payload)
        sessions.submit(self.s, id, self.submission(cells, revision=1, usage=runtime.ZERO))
        with self.assertRaisesRegex(Error, "after probability"):
            self.event(id, "bindings", payload)

    def test_unknown_failed_attempt_costs_require_reconciliation_and_explicit_resume(self):
        id = self.start()
        self.attempt(id, status="truncated")
        self.assertEqual(sessions.status(self.s, id)["disposition"], "failed")
        with self.assertRaisesRegex(Error, "unknown usage"):
            self.event(id, "transition", {"status": "open", "reason": "Retry"})
        self.event(id, "usage", {"attempt_id": "a", "usage": {**runtime.ZERO, "model_calls": 1, "cost_usd": .3}, "reason": "Provider receipt"})
        self.event(id, "amendment", {"reason": "Increase output headroom", "configuration": {"max_tokens": 64000}})
        self.event(id, "transition", {"status": "open", "reason": "Explicit retry after inspection"})
        self.assertEqual(sessions.status(self.s, id)["usage"]["cost_usd"], .3)
        self.assertEqual(runtime.audit(self.s, id)["protocol_fidelity"], "changed")

    def test_refusal_is_terminal_and_failed_cost_is_preserved(self):
        id = self.start()
        self.attempt(id, status="refused", usage={**runtime.ZERO, "model_calls": 1, "cost_usd": .25})
        with self.assertRaisesRegex(Error, "refused"):
            self.event(id, "transition", {"status": "open", "reason": "Retry"})
        self.assertEqual(sessions.status(self.s, id)["usage"]["cost_usd"], .25)
        self.assertEqual(session_reports.comparison(self.s, [id])["rows"][0]["probabilities"], [None])

    def test_research_requires_receipts_and_explicit_domain_assessment(self):
        id = self.start(research={"minimum_successful_tools": 1, "minimum_unique_pages": 1, "domains": ["base_rates"]})
        with self.assertRaisesRegex(Error, "research requirements"):
            sessions.submit(self.s, id, self.submission(usage=runtime.ZERO))
        self.attempt(id, aid="read", kind="tool", usage={**runtime.ZERO, "searches": 1})
        self.event(id, "research", {"attempt_id": "read", "tool": "read_page", "ok": True,
                   "url": "urn:vorhersage:fixture", "evidence_refs": self.refs, "note": "Read fixture"})
        self.assertFalse(runtime.audit(self.s, id)["research"]["ready"])
        self.event(id, "assessment", {"domain": "base_rates", "disposition": "unknown", "rationale": "No comparable cases", "evidence_refs": []})
        self.assertTrue(runtime.audit(self.s, id)["research"]["ready"])
        self.assertEqual(runtime.audit(self.s, id)["research"]["domains"][0]["disposition"], "unknown")
        with self.assertRaisesRegex(Error, "already has"):
            self.event(id, "research", {"attempt_id": "read", "tool": "web_search", "ok": True, "evidence_refs": [], "note": "Duplicate"})

    def test_event_retries_and_stale_revisions(self):
        id = self.start()
        event = {"kind": "observation", "payload": {"requirement_id": "effort", "actual": {"effort": "high"}, "basis": "provider_reported", "failed": False, "note": "Captured request", "evidence_refs": []}, "expected_revision": 0, "idempotency_key": "observation"}
        runtime.record(self.s, id, event)
        self.assertTrue(runtime.record(self.s, id, event)["duplicate"])
        self.assertEqual(runtime.audit(self.s, id)["protocol_fidelity"], "matched")
        with self.assertRaisesRegex(Error, "Stale"):
            runtime.record(self.s, id, {**event, "idempotency_key": "different"})
        event["payload"]["actual"] = None
        with self.assertRaisesRegex(Error, "different content"):
            runtime.record(self.s, id, event)

    def test_runner_polls_same_attempt_and_accepts_final_cells_once(self):
        id = self.start()
        waiting = {"status": "waiting", "usage": None, "continuation": {"job_id": "job-1"}, "raw_record": {}, "actions": []}
        done = {"status": "completed", "usage": {**runtime.ZERO, "model_calls": 1, "cost_usd": .1}, "continuation": {}, "raw_record": {},
                "actions": [{"kind": "submit", "payload": {"cells": self.cells(), "raw_record": {}}}, {"kind": "finalize", "payload": {"rationale": "Done"}}]}
        with patch.object(runtime, "invoke", side_effect=[waiting, done]) as worker:
            self.assertEqual(runtime.execute(self.s, id, 5)["disposition"], "waiting")
            final = runtime.execute(self.s, id, 5)
            self.assertEqual(final["disposition"], "finalized")
            self.assertEqual(worker.call_count, 2)
            a, b = [c.args[1] for c in worker.call_args_list]
            self.assertEqual(a["attempt_id"], b["attempt_id"])
            self.assertEqual(b["action"], "poll")
            self.assertEqual(b["continuation"], {"job_id": "job-1"})
            runtime.execute(self.s, id)
            self.assertEqual(worker.call_count, 2)
        self.assertEqual(final["usage"]["model_calls"], 1)
        self.assertTrue(self.w.doctor()["ok"])

    def test_crash_and_rejected_actions_never_trigger_blind_resubmission(self):
        id = self.start()
        self.event(id, "attempt_start", {"attempt_id": "crashed", "kind": "model", "request": {}})
        with patch.object(runtime, "invoke") as worker:
            self.assertEqual(runtime.execute(self.s, id)["disposition"], "running")
            worker.assert_not_called()
        self.event(id, "attempt_result", {"attempt_id": "crashed", "status": "completed", "usage": {**runtime.ZERO, "model_calls": 1, "cost_usd": .1}, "continuation": {}, "raw_record": {"actions": [{"kind": "submit", "payload": {"cells": self.cells(), "raw_record": {}}}, {"kind": "finalize", "payload": {"unexpected": True}}]}})
        with patch.object(runtime, "invoke") as worker:
            state = runtime.execute(self.s, id)
            worker.assert_not_called()
        self.assertEqual(state["disposition"], "failed")
        self.assertEqual(state["cells"], [])  # all actions rolled back, cost retained
        self.assertEqual(state["usage"]["cost_usd"], .1)

    def test_budget_stops_new_calls_and_timeout_retains_unknown_usage(self):
        id = self.start(budget={"max_model_calls": 0, "max_searches": 0, "max_cost_usd": 0})
        with patch.object(runtime, "invoke") as worker:
            self.assertEqual(runtime.execute(self.s, id)["disposition"], "budget_exhausted")
            worker.assert_not_called()
        self.event(id, "amendment", {"reason": "Authorize one attempt", "budget": {"max_model_calls": 1, "max_searches": 0, "max_cost_usd": 1}})
        self.event(id, "transition", {"status": "open", "reason": "Resume"})
        with patch.object(runtime, "invoke", side_effect=OSError("fixture")):
            state = runtime.execute(self.s, id)
        self.assertEqual(state["disposition"], "failed")
        self.assertEqual(len(state["unknown_usage_attempts"]), 1)

    def test_whole_session_study_is_atomic_and_repetition_isolation_is_explicit(self):
        spec = {"id": "study", "version": 1, "description": "Fixture", "session_template": self.spec(),
                "repetitions": 2, "order_seed": "fixed", "evidence_policy": "frozen",
                "arms": [{"id": a, "configuration": {"method": a}, "execution": execution(evidence_policy="fixed")} for a in ("a", "b")]}
        result = session_studies.add(self.s, spec)
        self.assertEqual(len(session_studies.status(self.s, result["study_id"])["trials"]), 4)
        self.assertEqual(session_studies.add(self.s, spec)["study_id"], result["study_id"])
        changed = copy.deepcopy(spec)
        changed["repetitions"] = 3
        with self.assertRaisesRegex(Error, "frozen"):
            session_studies.add(self.s, changed)
        self.assertTrue(self.w.doctor()["ok"])

    def test_distribution_scores_have_known_values(self):
        self.assertEqual(session_reports.distribution_score({"samples": [0, 2], "outcome": 1})["score"], .5)
        self.assertEqual(session_reports.distribution_score({"samples": [0], "outcome": 2})["score"], 2)
        with self.assertRaises(Error):
            session_reports.distribution_score({"samples": [float("nan")], "outcome": 0})
        self.assertEqual(session_reports.distribution_score({"samples": [1e15, 1e15+2], "outcome": 1e15+1})["score"], .5)
        forecast = {"variable": "capacity", "unit": "points", "target_at": stamp(1), "vintage": "fixture",
                    "quantiles": [{"level": .25, "value": 0}, {"level": .75, "value": 2}]}
        score = session_reports.distribution_score({"forecast": forecast, "outcome": 1})
        self.assertEqual(score["mean_loss"], .25)
        self.assertEqual(score["metric"], "quantile_loss")

    def test_scoring_excludes_conditional_cells_and_resolution_hindsight(self):
        id = self.start()
        sessions.submit(self.s, id, self.submission(usage=runtime.ZERO))
        sessions.finalize(self.s, id, {"expected_revision": 1, "idempotency_key": "final", "rationale": "Fixture"})
        cutoff = now()
        resolution = self.w.resolve({"question_id": "early", "question_version": 1, "outcome": "yes", "reason": "Fixture",
                        "known_at": now(), "evidence_refs": self.refs, "previous_resolution_id": None, "idempotency_key": "r1"})
        policy = {"session_ids": [id], "cutoff": cutoff, "resolution_as_of": now(), "allow_source_reported": False}
        score = session_reports.evaluate(self.s, policy)
        self.assertEqual(len(score["selected"]), 1)
        self.assertAlmostEqual(score["selected"][0]["brier"], .64)
        self.assertEqual(len(score["exclusions"]), 2)
        self.w.resolve({"question_id": "early", "question_version": 1, "outcome": "yes", "reason": "Earlier knowledge discovered",
                        "known_at": stamp(-.1), "evidence_refs": self.refs, "previous_resolution_id": resolution["resolution_id"], "idempotency_key": "r2"})
        amended = session_reports.evaluate(self.s, {**policy, "resolution_as_of": now()})
        self.assertEqual(amended["selected"], [])
        self.assertIn("not_before_resolution_knowledge", {r["reason"] for r in amended["exclusions"]})
        self.assertTrue(self.w.doctor()["ok"])

    def test_report_embedded_data_is_escaped(self):
        id = sessions.start(self.s, self.spec(who="</script><script>alert(1)</script>", execution=execution()))["session_id"]
        path = Path(self.tmp.name) / "report.html"
        session_reports.render(self.s, [id], path)
        text = path.read_text()
        self.assertNotIn("</script><script>alert(1)</script>", text)
        self.assertIn("\\u003c/script>", text)

    def test_followup_counts_require_a_search_requested_after_the_read(self):
        id = self.start(research={"minimum_successful_tools": 2, "minimum_unique_pages": 1, "domains": [],
                                "minimum_unique_searches": 1, "minimum_recent_searches": 1, "minimum_followup_searches": 1})
        self.attempt(id, aid="read", kind="tool", usage={**runtime.ZERO, "searches": 1})
        self.event(id, "research", {"attempt_id": "read", "tool": "read_page", "ok": True, "url": "urn:vorhersage:fixture", "evidence_refs": self.refs, "note": "Read"})
        self.attempt(id, aid="search", kind="tool", usage={**runtime.ZERO, "searches": 1})
        self.event(id, "research", {"attempt_id": "search", "tool": "web_search", "ok": True, "query": "recent readiness", "recent_days": 30, "evidence_refs": [], "note": "Search"})
        self.assertTrue(runtime.audit(self.s, id)["research"]["ready"])

    def test_study_worker_walkthrough_and_unconditional_scores(self):
        import subprocess
        path = Path(self.tmp.name) / "walkthrough"
        script = Path(__file__).resolve().parents[1] / "examples/live_sessions/walkthrough.py"
        result = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((path / "summary.json").read_text())
        self.assertEqual(summary["sessions"], 4)
        self.assertTrue(summary["doctor"]["ok"])
        self.assertEqual([a["mean_session_brier"] for a in summary["arms"]], [.5625, .0625])
        self.assertEqual(summary["usage"]["model_calls"], 8)
        self.assertEqual(summary["usage"]["searches"], 4)
        self.assertAlmostEqual(summary["usage"]["cost_usd"], .1)
        document = (path / "comparison.html").read_text()
        self.assertIn("application/json", document)
        self.assertNotIn("__DATA__", document)


if __name__ == "__main__":
    unittest.main()
