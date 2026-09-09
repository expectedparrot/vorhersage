import copy
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from vorhersage.common import Error, digest, now
from vorhersage.evaluation import evaluate
from vorhersage.schemas import SCHEMAS, check
from vorhersage.store import Store
from vorhersage.workflow import Workflow


def stamp(days=0):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def question(id="factory", kind="simulation"):
    return {"id": id, "text": "Will the fictional factory ship by tomorrow?",
            "yes": "A qualifying shipment is recorded by the deadline.", "no": "No qualifying shipment by the deadline.",
            "void": "The fixture is withdrawn.", "event_deadline": stamp(1), "resolve_after": stamp(2),
            "resolution_source": "urn:vorhersage:synthetic-fixture", "event_group": "factory_fixture",
            "domain": "operations", "profile": "general", "kind": kind}


def packet():
    return {"schema_version": "vorhersage.evidence.v1", "kind": "manual", "information_as_of": stamp(-1),
            "created_at": now(), "limitations": ["Synthetic fixture; not real-world evidence."],
            "records": [{"id": "factory_status", "claim": "Synthetic fixture reports factory status.",
                         "value": {"ready": True}, "entity_ids": ["factory"], "observed_at": stamp(-2),
                         "sources": [{"id": "fixture", "url": "urn:vorhersage:fixture", "title": "Synthetic factory record",
                                      "excerpt": "Fictional factory readiness and shipment record for software tests.", "retrieved_at": stamp(-2)}],
                         "provenance": {"synthetic": True}}]}


def run_spec(forecaster="agent:a", **extra):
    return {"question_id": "factory", "forecaster": forecaster, "method": "fixture judgment",
            "mode": "simulation", "information_as_of": now(), "max_searches": 5, "max_extra_tasks": 1, **extra}


def payload(kind, refs, estimate=0.6):
    return {
        "prior": {"method": "judgment", "probability": 0.3, "rationale": "Synthetic judgmental starting point.", "limitations": ["Not fitted."], "evidence_refs": []},
        "drivers": {"drivers": [{"name": "Readiness", "mechanism": "A ready factory can ship.", "evidence_refs": refs}],
                    "yes_path": "Readiness followed by dispatch.", "no_path": "A remaining dependency prevents dispatch.", "unknowns": ["Remaining delays."]},
        "research": {"disposition": "assessed", "interpretation": "The fixture supplies relevant status information.", "evidence_refs": refs,
                     "sources_checked": ["Synthetic fixture"], "unknowns": ["Timing remains uncertain."], "conflicts": []},
        "assessment": {"method": "judgment", "probability": estimate, "rationale": "Synthetic unfitted judgment after research.", "limitations": ["Not an accuracy claim."], "evidence_refs": refs},
        "review": {"decision": "retain", "rationale": "Uncertainty is already reflected.", "evidence_refs": refs,
                   "objections": [{"direction": "too_high", "objection": "Dispatch could fail.", "response": "Failure remains possible."},
                                  {"direction": "too_low", "objection": "Preparation may be complete.", "response": "It may, but no certainty follows."}]},
        "issue": {"stopping_reason": "Fixture research complete.", "review_at": stamp(0.5),
                  "triggers": [{"description": "New factory status information.", "evidence_refs": refs}]},
    }[kind]


def response(nxt, refs, estimate=0.6):
    return {"task_id": nxt["task"]["id"], "expected_revision": nxt["revision"],
            "idempotency_key": nxt["task"]["id"], "payload": payload(nxt["task"]["kind"], refs, estimate)}


def finish(w, id, refs, estimate=0.6):
    while (nxt := w.next(id))["disposition"] == "actionable":
        w.submit(id, response(nxt, refs, estimate))
    return nxt["forecast_id"]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.w = Workflow(self.tmp.name)
        self.w.store.init("Test")
        self.q = question()
        self.w.question(self.q)
        self.p = self.w.import_packet(packet())
        self.refs = [self.p["records"][0]["evidence_ref"]]
        self.id = self.w.start(run_spec())["run_id"]

    def advance(self, kind):
        while self.w.next(self.id)["task"]["kind"] != kind:
            self.w.submit(self.id, response(self.w.next(self.id), self.refs))

    def resolution(self, outcome="yes", previous=None, **extra):
        return self.w.resolve({"question_id": "factory", "question_version": 1, "outcome": outcome,
                               "known_at": now(), "reason": "Synthetic resolution.", "evidence_refs": self.refs,
                               "previous_resolution_id": previous, "idempotency_key": "resolve_" + outcome, **extra})

    def policy(self, forecasters=None, **extra):
        return {"question_versions": [{"question_id": "factory", "version": 1}],
                "forecasters": forecasters or ["agent:a"], "cutoff": now(), "resolution_as_of": now(),
                "mode": "simulation", **extra}

    def test_next_is_read_only_and_resumes_in_new_instance(self):
        before = self.w.next(self.id)
        self.assertEqual(before, Workflow(self.tmp.name).next(self.id))
        self.assertEqual(before, self.w.next(self.id))
        self.w.submit(self.id, response(before, self.refs))
        self.assertEqual(Workflow(self.tmp.name).next(self.id)["task"]["kind"], "drivers")

    def test_duplicate_retry_and_stale_submission_are_atomic(self):
        request = response(self.w.next(self.id), self.refs)
        self.w.submit(self.id, request)
        before = self.w.status()
        self.assertTrue(self.w.submit(self.id, request)["duplicate"])
        changed = copy.deepcopy(request)
        changed["payload"]["probability"] = 0.9
        with self.assertRaisesRegex(Error, "Idempotency"):
            self.w.submit(self.id, changed)
        changed = response(self.w.next(self.id), self.refs)
        changed["expected_revision"] = 0
        with self.assertRaisesRegex(Error, "stale"):
            self.w.submit(self.id, changed)
        self.assertEqual(self.w.status(), before)

    def test_missing_evidence_unknowns_and_budget(self):
        self.advance("research")
        request = response(self.w.next(self.id), [])
        with self.assertRaisesRegex(Error, "needs evidence"):
            self.w.submit(self.id, request)
        request["payload"]["disposition"] = "unknown"
        request["usage"] = {"searches": 6, "cost_usd": 0.1, "model_calls": 1}
        with self.assertRaisesRegex(Error, "budget exhausted"):
            self.w.submit(self.id, request)
        request["usage"]["searches"] = 5
        self.w.submit(self.id, request)
        self.assertEqual(self.w.next(self.id)["budget"]["searches_remaining"], 0)
        # Remaining topics can use already available evidence with no additional searches.
        finish(self.w, self.id, self.refs)

    def test_reference_class_uses_actual_cases_and_denominator(self):
        request = response(self.w.next(self.id), self.refs)
        request["payload"] = {"method": "reference_class", "rationale": "Illustrative comparable cases.",
                              "selection_rule": "All two listed fictional cases.", "limitations": ["Tiny sample."], "evidence_refs": [],
                              "cases": [{"id": "a", "outcome": 1, "evidence_refs": self.refs}, {"id": "b", "outcome": 0, "evidence_refs": self.refs}]}
        self.w.submit(self.id, request)
        self.assertEqual(self.w.next(self.id)["context"]["current_probability"], 0.5)

    def test_conditional_path_and_invalid_chain(self):
        self.advance("assessment")
        request = response(self.w.next(self.id), self.refs)
        p = request["payload"]
        p.pop("probability")
        p.update(method="conditional_path", nested_events_justification="Dispatch requires readiness.",
                 components=[{"id": "ready", "conditional_on": None, "probability": 0.8, "rationale": "Judgment.", "evidence_refs": self.refs},
                             {"id": "target", "conditional_on": "wrong", "probability": 0.75, "rationale": "Conditional judgment.", "evidence_refs": self.refs}])
        with self.assertRaisesRegex(Error, "nested chain"):
            self.w.submit(self.id, request)
        p["components"][1]["conditional_on"] = "ready"
        self.w.submit(self.id, request)
        self.assertAlmostEqual(self.w.next(self.id)["context"]["current_probability"], 0.6)

    def test_review_inserts_bounded_research_and_reassessment(self):
        self.advance("review")
        request = response(self.w.next(self.id), self.refs)
        request["payload"].update(decision="research", research_tasks=[{"domain": "dispatch", "purpose": "Check the dispatch dependency."}])
        self.w.submit(self.id, request)
        self.assertEqual(self.w.next(self.id)["task"]["domain"], "dispatch")
        self.advance("review")
        request = response(self.w.next(self.id), self.refs)
        request["payload"].update(decision="research", research_tasks=[{"domain": "again", "purpose": "More research."}])
        with self.assertRaisesRegex(Error, "budget exhausted"):
            self.w.submit(self.id, request)
        finish(self.w, self.id, self.refs)

    def test_two_sided_review_and_revised_probability(self):
        self.advance("review")
        request = response(self.w.next(self.id), self.refs)
        request["payload"]["objections"][1]["direction"] = "too_high"
        with self.assertRaisesRegex(Error, "both directions"):
            self.w.submit(self.id, request)
        request["payload"]["objections"][1]["direction"] = "too_low"
        request["payload"].update(decision="revise", probability=0.4)
        self.w.submit(self.id, request)
        fid = finish(self.w, self.id, self.refs)
        with self.w.store.connect() as c:
            self.assertEqual(Store.artifact(c, fid)["probability"], 0.4)

    def test_forecast_pins_inputs_and_database_rejects_history_mutation(self):
        fid = finish(self.w, self.id, self.refs)
        self.assertTrue(self.w.doctor()["ok"])
        with self.w.store.connect(True) as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE artifacts SET body='{}' WHERE id=?", (fid,))

    def test_signal_revision_preserves_forecast_and_clears_due_target(self):
        first = finish(self.w, self.id, self.refs, 0.2)
        self.w.signal({"reason": "New status information.", "idempotency_key": "change1", "evidence_refs": self.refs})
        self.assertEqual(self.w.monitor()["due"][0]["forecast_id"], first)
        second_run = self.w.start(run_spec(previous_forecast_id=first))["run_id"]
        second = finish(self.w, second_run, self.refs, 0.8)
        self.assertEqual(self.w.monitor()["due"], [])
        with self.w.store.connect() as c:
            self.assertEqual(Store.artifact(c, first)["probability"], 0.2)
            self.assertEqual(Store.artifact(c, second)["previous_forecast_id"], first)

    def test_question_revision_does_not_change_active_run(self):
        new = copy.deepcopy(self.q)
        new["text"] = "Changed event wording."
        self.w.question(new, expected_version=1)
        self.assertEqual(self.w.next(self.id)["context"]["run"]["question"], self.q)
        with self.assertRaisesRegex(Error, "stale"):
            self.w.question(new, expected_version=1)

    def test_resolution_corrections_and_evaluations_are_frozen(self):
        finish(self.w, self.id, self.refs, 0.6)
        first = self.resolution()
        evaluation = evaluate(self.w.store, self.policy())
        self.assertAlmostEqual(evaluation["summaries"]["agent:a"]["available_brier"], 0.16)
        self.resolution("no", previous=first["resolution_id"])
        corrected = evaluate(self.w.store, self.policy())
        self.assertAlmostEqual(corrected["summaries"]["agent:a"]["available_brier"], 0.36)
        with self.w.store.connect() as c:
            self.assertAlmostEqual(Store.artifact(c, evaluation["evaluation_id"])["summaries"]["agent:a"]["available_brier"], 0.16)

    def test_latest_forecast_selection_matched_scores_and_missingness(self):
        first = finish(self.w, self.id, self.refs, 0.2)
        revision = self.w.start(run_spec(previous_forecast_id=first))["run_id"]
        latest = finish(self.w, revision, self.refs, 0.8)
        b = self.w.start(run_spec("agent:b"))["run_id"]
        finish(self.w, b, self.refs, 0.4)
        self.resolution()
        report = evaluate(self.w.store, self.policy(["agent:a", "agent:b"]))
        self.assertEqual(len(report["selected"]), 2)
        self.assertEqual(report["selected"][0]["forecast_id"], latest)
        self.assertAlmostEqual(report["comparisons"][0]["mean_brier_difference"], -0.32)
        missing = evaluate(self.w.store, self.policy(["agent:a", "absent"]))
        self.assertEqual(missing["summaries"]["agent:a"]["matched_n"], 0)
        self.assertTrue(missing["exclusions"])

    def test_void_and_wrong_modes_are_not_scored(self):
        finish(self.w, self.id, self.refs)
        self.resolution("void")
        report = evaluate(self.w.store, self.policy())
        self.assertEqual(report["selected"], [])
        self.assertEqual(report["exclusions"][0]["reason"], "void")

    def test_forecast_after_known_outcome_is_excluded(self):
        finish(self.w, self.id, self.refs)
        self.resolution(known_at=stamp(-0.5))
        self.assertEqual(evaluate(self.w.store, self.policy())["selected"], [])

    def test_ensemble_rejects_repeated_or_stale_members(self):
        first = finish(self.w, self.id, self.refs, 0.2)
        revised = self.w.start(run_spec(previous_forecast_id=first))["run_id"]
        latest = finish(self.w, revised, self.refs, 0.8)
        b = self.w.start(run_spec("agent:b"))["run_id"]
        bf = finish(self.w, b, self.refs, 0.4)
        self.id = self.w.start(run_spec("ensemble"))["run_id"]
        self.advance("assessment")
        request = response(self.w.next(self.id), self.refs)
        p = request["payload"]
        p.pop("probability")
        p.update(method="ensemble", members=[first, bf])
        with self.assertRaisesRegex(Error, "latest eligible"):
            self.w.submit(self.id, request)
        p["members"] = [latest, bf]
        self.w.submit(self.id, request)
        self.assertAlmostEqual(self.w.next(self.id)["context"]["current_probability"], 0.6)

    def test_schema_rejects_nonfinite_boolean_and_unrecognized_fields(self):
        for bad in (True, float("nan"), float("inf"), -0.1, 1.1):
            p = payload("assessment", self.refs)
            p["probability"] = bad
            with self.assertRaises(Error):
                check(p, "assessment")
        p = payload("research", self.refs)
        p["pretend_done"] = True
        with self.assertRaises(Error):
            check(p, "research")

    def test_packet_cutoff_and_hash_are_enforced(self):
        source = packet()
        source["records"][0]["observed_at"] = stamp(1)
        with self.assertRaises(Error):
            self.w.import_packet(source)
        with self.w.store.connect() as c:
            frozen = Store.artifact(c, self.p["packet_id"])
        frozen["records"][0]["value"] = False
        with self.assertRaisesRegex(Error, "hash mismatch"):
            self.w.import_packet(frozen)

    def test_prospective_deadlines_and_existing_resolution_are_enforced(self):
        real = question("real_event", kind="real")
        self.w.question(real)
        spec = run_spec(question_id="real_event", mode="prospective")
        id = self.w.start(spec)["run_id"]
        pending = self.w.next(id)
        self.w.resolve({"question_id": "real_event", "question_version": 1, "outcome": "disputed",
                        "reason": "Test resolution blocks fresh prospective submissions.", "known_at": now(),
                        "evidence_refs": self.refs, "previous_resolution_id": None, "idempotency_key": "real_res"})
        with self.assertRaisesRegex(Error, "resolution"):
            self.w.start(spec)
        self.assertEqual(self.w.next(id)["disposition"], "blocked")
        with self.assertRaisesRegex(Error, "resolved while"):
            self.w.submit(id, response(pending, self.refs))
        expired = question("expired", kind="real")
        expired["event_deadline"] = stamp(-1)
        self.w.question(expired)
        with self.assertRaisesRegex(Error, "deadline has passed"):
            self.w.start(run_spec(question_id="expired", mode="prospective"))

    def test_concurrent_revision_cannot_overwrite_an_issued_successor(self):
        first = finish(self.w, self.id, self.refs)
        a = self.w.start(run_spec(previous_forecast_id=first))["run_id"]
        b = self.w.start(run_spec(previous_forecast_id=first))["run_id"]
        finish(self.w, a, self.refs, 0.8)
        while self.w.next(b)["task"]["kind"] != "issue":
            self.w.submit(b, response(self.w.next(b), self.refs))
        with self.assertRaisesRegex(Error, "Another revision has issued"):
            self.w.submit(b, response(self.w.next(b), self.refs))

    def test_explicit_evaluation_mode_excludes_simulation(self):
        finish(self.w, self.id, self.refs)
        self.resolution()
        report = evaluate(self.w.store, self.policy(mode="prospective"))
        self.assertEqual(report["selected"], [])

    def test_live_research_after_run_start_advances_cutoff_but_fixed_mode_rejects_it(self):
        self.w.question(question("live", kind="real"))
        initial = stamp(-0.25)
        live = self.w.start(run_spec(question_id="live", mode="prospective", information_as_of=initial))["run_id"]
        fixed = self.w.start(run_spec(question_id="live", mode="prospective", information_as_of=initial, cutoff_policy="fixed"))["run_id"]
        fresh = packet()
        fresh["information_as_of"] = now()
        imported = self.w.import_packet(fresh)
        refs = [imported["records"][0]["evidence_ref"]]
        for id in (live, fixed):
            request = response(self.w.next(id), refs)
            request["payload"]["evidence_refs"] = refs
            if id == fixed:
                with self.assertRaisesRegex(Error, "later than the run"):
                    self.w.submit(id, request)
            else:
                self.w.submit(id, request)
                state = self.w.next(id)["context"]["run"]
                self.assertEqual(state["initial_information_as_of"], initial)
                self.assertGreater(state["information_as_of"], initial)


if __name__ == "__main__":
    unittest.main()
