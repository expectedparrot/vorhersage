"""Maturity must be selected independently of outcome before estimating a prior."""

import tempfile
import unittest
from datetime import timedelta

from vorhersage import reference
from vorhersage.common import Error, now, time
from vorhersage.workflow import Workflow
from test_workflow import packet, question, response, run_spec, stamp


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.w = Workflow(self.tmp.name)
        self.w.store.init("reference")
        self.w.question(question())
        old = packet()
        old["information_as_of"] = stamp(-300)
        old["records"][0]["observed_at"] = stamp(-301)
        old["records"][0]["sources"][0]["retrieved_at"] = stamp(-301)
        self.refs = [self.w.import_packet(old)["records"][0]["evidence_ref"]]
        self.cutoff = time(now()) - timedelta(days=1)
        self.query = {"tags": ["test"], "horizon_days": 90, "known_as_of": self.cutoff.isoformat(),
                      "selection_rule": "Every synthetic episode tagged test."}

    def add(self, id, trigger, observed, event=None, known=0):
        ts = lambda offset: (self.cutoff + timedelta(days=offset)).isoformat()
        reference.add(self.w.store, {"id": id, "episode_id": id, "eligibility": "Synthetic cohort.",
                                    "description": "Synthetic episode", "tags": ["test"],
                                    "trigger_at": ts(trigger), "observed_until": ts(observed),
                                    "event_at": ts(event) if event is not None else None,
                                    "known_at": ts(known), "evidence_refs": self.refs})

    def test_early_successes_do_not_turn_immature_cohort_into_certain_prior(self):
        for i in range(100):
            self.add(str(i), -30, 0, -20 if i < 10 else None)
        result = reference.query(self.w.store, self.query)
        self.assertEqual(len(result["immature"]), 100)
        self.assertEqual(len(result["censored"]), 90)
        self.assertEqual(result["sample_size"], 0)
        self.assertEqual(result["resolved_case_frequency"]["probability"], 1)
        self.assertEqual(result["resolved_case_frequency"]["sample_size"], 10)
        self.assertIsNone(result["probability"])
        self.assertIsNone(result["prior_payload"])
        self.assertFalse(result["prior_eligible"])

    def test_mature_success_needs_no_followup_after_observed_event(self):
        # Horizon ends exactly at cutoff; the event also occurs exactly at its horizon.
        self.add("boundary", -90, 0, 0)
        self.add("early", -100, -99, -99)
        self.add("failure", -100, -10)
        self.add("late", -100, -1, -1)
        # Neither early success nor unresolved outcome from an immature cohort is included.
        self.add("young-success", -30, -20, -20)
        self.add("young-pending", -30, 0)
        result = reference.query(self.w.store, self.query)
        self.assertEqual(result["mature_cohort_size"], 4)
        self.assertEqual(result["probability"], 0.5)
        self.assertEqual({c["id"] for c in result["cases"]}, {"boundary", "early", "failure", "late"})
        self.assertTrue(result["prior_eligible"])
        run = self.w.start(run_spec())["run_id"]
        request = response(self.w.next(run), self.refs)
        request["payload"] = result["prior_payload"]
        self.w.submit(run, request)
        self.assertEqual(self.w.next(run)["context"]["current_probability"], 0.5)

    def test_incomplete_mature_outcomes_block_prior_and_manual_bypass(self):
        self.add("early", -100, -99, -99)
        self.add("lost", -100, -50)
        result = reference.query(self.w.store, self.query)
        self.assertEqual(result["unascertained_mature"], ["lost"])
        self.assertIsNone(result["prior_payload"])
        self.assertEqual(result["resolved_case_frequency"]["probability"], 1)
        run = self.w.start(run_spec())["run_id"]
        request = response(self.w.next(run), self.refs)
        request["payload"] = {"method": "reference_class", "probability": 1, "cases": result["cases"],
                              "reference_query": self.query, "selection_rule": self.query["selection_rule"],
                              "rationale": "Attempt to bypass eligibility", "limitations": [], "evidence_refs": self.refs}
        with self.assertRaisesRegex(Error, "incomplete_mature_outcomes"):
            self.w.submit(run, request)
        del request["payload"]["reference_query"]
        with self.assertRaisesRegex(Error, "require reference_query"):
            self.w.submit(run, request)
        self.assertEqual(self.w.next(run)["revision"], 0)

    def test_maturity_uses_query_cutoff_not_current_time(self):
        self.add("future-at-cutoff", -89.5, -1, -1)
        self.add("old-failure", -100, -10)
        self.add("later-known", -100, 0, -20, known=0.5)
        result = reference.query(self.w.store, self.query)
        self.assertEqual(result["immature"], ["future-at-cutoff"])
        self.assertEqual(result["excluded_after_cutoff"], ["later-known"])
        self.assertEqual(result["probability"], 0)

    def test_legacy_cases_without_episode_metadata_remain_descriptive(self):
        reference.add(self.w.store, {"id": "legacy", "description": "Old fixture", "tags": ["test"],
                                    "trigger_at": stamp(-100), "observed_until": stamp(-2), "known_at": stamp(-1.5),
                                    "event_at": stamp(-90), "evidence_refs": self.refs})
        result = reference.query(self.w.store, self.query)
        self.assertIsNone(result["prior_payload"])
        self.assertIn("missing_episode_metadata", result["prior_ineligibility_reasons"])
        self.assertEqual(result["resolved_case_frequency"]["probability"], 1)


if __name__ == "__main__":
    unittest.main()
