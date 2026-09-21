"""Exercise widening, imperfect evidence and budget extensions through real runs."""
import json
import subprocess
import sys

import pytest

from vorhersage import reference_research, report_context, study
from vorhersage.common import Error, canonical, now
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_study import intake, study_payload
from test_workflow import packet, question, run_spec, stamp


def submit(w, rid, answer, searches=0):
    task = w.next(rid)
    return w.submit(rid, {"task_id": task["task"]["id"], "expected_revision": task["revision"],
                          "idempotency_key": task["task"]["id"], "payload": answer,
                          "usage": {"searches": searches, "cost_usd": 0, "model_calls": 0}})


def begin(tmp_path, **options):
    w = Workflow(tmp_path)
    w.store.init("Reference research")
    w.question(question())
    refs = [w.import_packet(packet())["records"][0]["evidence_ref"]]
    spec = run_spec(research_effort="deep", research_contract="structured_v2", max_searches=12, max_extra_tasks=6)
    spec.update(options)
    rid = w.start(spec)["run_id"]
    return w, rid, refs


def design(w, rid, unknowns=()):
    submit(w, rid, intake(unknowns))
    assert w.next(rid)["task"]["kind"] == "reference_class_design"
    submit(w, rid, study_payload("reference_class_design", []))


def search_answer(w, cid, refs, candidates=(), *, snapshot=stamp(-1)):
    query = "Synthetic " + cid + " repair outcomes"
    with w.store.connect(True) as c:
        aid = Store.put(c, "research", {"operation": "search", "request": {"body": {"query": query}},
                                        "snapshot_as_of": snapshot, "retrieved_at": now(), "sources": []})
    return {"class_id": cid, "status": "searched", "searches": [
        {"query": query, "retrieval_ids": [aid], "evidence_refs": refs, "finding": "Synthetic partial record"}],
        "candidates": list(candidates), "limitations": ["Incomplete synthetic data"], "next_action": "Verify missing outcomes"}


def candidate(refs):
    return {"id": "one", "episode_id": "repair-one", "description": "Coating repair with incomplete follow-up",
            "use": "input_analogy", "target_input_ids": ["outcome"], "similarities": "Shared repair mechanism",
            "differences": "Different scale and missing completion date", "outcome_status": "partial",
            "rationale": "Useful for preparation time, not whole-event frequency", "evidence_refs": refs}


def analyze(status="partial", **extra):
    return {"status": status, "analysis_id": "partial-fixture", "case_count": 0, "independent_episode_count": 0,
            "estimator": "No whole-event rate", "result": "Partial analogies inform input assumptions",
            "limitations": ["Missing outcomes"], "evidence_refs": [], "artifact_omission_reason": "No empirical export",
            "class_results": [{"class_id": cid, "assessment": "Partial timing evidence"} for cid in ("close", "nearby")],
            "remaining_assumptions": ["Transfer to this target is judgmental"], **extra}


def searched(w, rid, refs):
    design(w, rid)
    submit(w, rid, search_answer(w, "close", refs), 1)
    submit(w, rid, search_answer(w, "nearby", refs, [candidate(refs)]), 1)


def test_design_precedes_inquiries_and_broader_searches_are_actionable(tmp_path):
    w, rid, refs = begin(tmp_path)
    unknown = {"id": "status", "question": "Has work begun?", "input_ids": ["outcome"], "route": "search",
               "why_it_matters": "Remaining duration", "action": "Check project notices"}
    design(w, rid, [unknown])
    for cid in ("close", "nearby"):
        assert w.next(rid)["task"]["reference_class"]["id"] == cid
        submit(w, rid, search_answer(w, cid, refs), 1)
    assert w.next(rid)["task"]["kind"] == "inquiry"
    submit(w, rid, {"status": "unresolved", "answer": "Date unknown", "evidence_refs": []})
    assert w.next(rid)["task"]["kind"] == "reference_class_analysis"
    submit(w, rid, analyze("no_usable_cases_found"))
    assert w.next(rid)["task"]["kind"] == "prior"


def test_partial_analogies_survive_issuance_and_reporting(tmp_path):
    w, rid, refs = begin(tmp_path)
    searched(w, rid, refs)
    submit(w, rid, analyze())
    while (task := w.next(rid))["disposition"] == "actionable":
        submit(w, rid, study_payload(task["task"]["kind"], refs, context=task["context"]))
    with w.store.connect() as c:
        forecast = Store.artifact(c, task["forecast_id"])
    research = forecast["reference_research"]
    assert research["analysis"]["status"] == "partial"
    assert research["candidate_episode_count"] == 1
    assert research["searches"][1]["candidates"][0]["outcome_status"] == "partial"
    receipt = report_context.export(w.store, run_id=rid, output=tmp_path / "report.json")
    archive = json.loads(open(receipt["full_material"]["path"]).read())
    assert archive["material"]["methodology"]["reference_class_analysis"]["status"] == "partial"
    assert w.doctor()["ok"]
    with pytest.raises(Error, match="unfinished"):
        w.extend_budget(rid, max_searches=20, reason="Too late")


def test_additional_classes_and_followups_return_to_analysis(tmp_path):
    w, rid, refs = begin(tmp_path)
    searched(w, rid, refs)
    added = study_payload("reference_class_design", [])["classes"][1]
    added.update(id="mechanism", distance="mechanism", population="Other public repairs")
    submit(w, rid, analyze("continue_research", additional_classes=[added],
                           followups=[{"class_id": "nearby", "action": "Find actual completion dates"}]))
    assert w.next(rid)["task"]["action"] == "Find actual completion dates"
    submit(w, rid, search_answer(w, "nearby", refs, [candidate(refs)]), 1)
    assert w.next(rid)["task"]["reference_class"]["population"] == "Other public repairs"
    submit(w, rid, search_answer(w, "mechanism", refs), 1)
    answer = analyze()
    with pytest.raises(Error, match="every planned class"):
        submit(w, rid, answer)
    answer["class_results"].append({"class_id": "mechanism", "assessment": "No new cases"})
    submit(w, rid, answer)
    research = w.next(rid)["context"]["reference_research"]
    assert len(research["analysis_history"]) == 2
    assert research["candidate_episode_count"] == 1  # repeated observation, not another episode


def test_followup_can_reject_a_previously_promising_analogy_without_erasing_it(tmp_path):
    w, rid, refs = begin(tmp_path)
    searched(w, rid, refs)
    submit(w, rid, analyze("continue_research", followups=[{"class_id": "nearby", "action": "Verify scope"}]))
    rejected = candidate(refs)
    rejected.update(use="excluded", rationale="Follow-up found incompatible scope")
    submit(w, rid, search_answer(w, "nearby", refs, [rejected]), 1)
    submit(w, rid, analyze("no_usable_cases_found"))
    research = w.next(rid)["context"]["reference_research"]
    assert research["candidates"][0]["use"] == "excluded"
    assert research["searches"][1]["candidates"][0]["use"] == "input_analogy"


@pytest.mark.parametrize("status", ["blocked", "no_usable_cases_found", "budget_exhausted"])
def test_exception_cannot_hide_useful_analogies_or_unspent_budget(tmp_path, status):
    w, rid, refs = begin(tmp_path)
    searched(w, rid, refs)
    revision = w.next(rid)["revision"]
    with pytest.raises(Error):
        submit(w, rid, analyze(status))
    assert w.next(rid)["revision"] == revision


def test_unavailable_searches_remain_incomplete_but_allow_forecasting(tmp_path):
    w, rid, refs = begin(tmp_path)
    design(w, rid)
    for cid in ("close", "nearby"):
        submit(w, rid, {"class_id": cid, "status": "unavailable", "searches": [], "candidates": [],
                        "limitations": ["Archive unavailable"], "next_action": "Seek another archive later"})
    with pytest.raises(Error, match="Unsearched"):
        submit(w, rid, analyze("no_usable_cases_found"))
    submit(w, rid, analyze("search_incomplete"))
    assert w.next(rid)["task"]["kind"] == "prior"


@pytest.mark.parametrize("problem", ["wrong_query", "future", "no_receipt", "unverified_rate", "wrong_class"])
def test_search_evidence_validation(tmp_path, problem):
    w, rid, refs = begin(tmp_path)
    design(w, rid)
    answer = search_answer(w, "close", refs, [candidate(refs)], snapshot=stamp(1) if problem == "future" else stamp(-1))
    if problem == "wrong_query":
        answer["searches"][0]["query"] = "Different query"
    if problem == "no_receipt":
        answer["searches"][0].update(retrieval_ids=[], evidence_refs=[])
    if problem == "unverified_rate":
        answer["candidates"][0]["use"] = "base_rate"
    if problem == "wrong_class":
        answer["class_id"] = "nearby"
    with pytest.raises(Error):
        submit(w, rid, answer, 1)
    assert w.next(rid)["budget"]["searches_remaining"] == 12


def test_budget_extension_preserves_usage_invalidates_old_task_and_is_idempotent(tmp_path):
    w, rid, refs = begin(tmp_path, max_extra_tasks=0)
    searched(w, rid, refs)
    more = analyze("continue_research", followups=[{"class_id": "nearby", "action": "Verify outcomes"}])
    with pytest.raises(Error, match="extend"):
        submit(w, rid, more)
    before = w.next(rid)
    after = w.extend_budget(rid, max_searches=20, max_extra_tasks=4, reason="Broaden and verify analogies")
    assert after["revision"] == before["revision"] + 1
    assert after["budget"]["searches_remaining"] == 18
    assert after["budget"]["extra_tasks_remaining"] == 4
    assert w.extend_budget(rid, max_searches=20, reason="Retry")["revision"] == after["revision"]
    with pytest.raises(Error, match="stale"):
        w.submit(rid, {"task_id": before["task"]["id"], "expected_revision": before["revision"],
                       "idempotency_key": "stale", "payload": more})
    submit(w, rid, more)
    with w.store.connect() as c:
        original = json.loads(c.execute("SELECT body FROM runs WHERE id=?", (rid,)).fetchone()[0])
        assert original["max_searches"] == 12
        assert len(Store.all(c, "budget_amendment")) == 1
    assert w.doctor()["ok"]
    with pytest.raises(Error, match="lower"):
        w.extend_budget(rid, max_searches=5, reason="Invalid reduction")


def test_frozen_experiment_budget_cannot_be_extended(tmp_path):
    w, rid, _ = begin(tmp_path)
    with w.store.connect(True) as c:
        body = json.loads(c.execute("SELECT body FROM runs WHERE id=?", (rid,)).fetchone()[0])
        body["experiment_id"] = "frozen-fixture"
        c.execute("UPDATE runs SET body=? WHERE id=?", (canonical(body), rid))
    with pytest.raises(Error, match="Frozen experiment"):
        w.extend_budget(rid, max_searches=50, reason="Cannot change arm budget")


def test_default_study_budgets_and_cli_extension(tmp_path):
    q = question()
    study.start(tmp_path, q["text"], q)
    w = Workflow(tmp_path)
    task = study.next_task(w)
    assert task["budget"]["searches_remaining"] == 60
    assert task["budget"]["extra_tasks_remaining"] == 8
    result = subprocess.run([sys.executable, "-m", "vorhersage", "budget", "--project", str(tmp_path),
                             "--max-searches", "80", "--reason", "Verify partial outcomes"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["data"]["budget"]["searches_remaining"] == 80


def test_legacy_deep_run_remains_resumable(tmp_path):
    w, rid, _ = begin(tmp_path, reference_policy="legacy")
    with w.store.connect(True) as c:
        body = json.loads(c.execute("SELECT body FROM runs WHERE id=?", (rid,)).fetchone()[0])
        del body["reference_policy"]  # a run created before this feature
        c.execute("UPDATE runs SET body=? WHERE id=?", (canonical(body), rid))
    submit(w, rid, intake())
    answer = study_payload("reference_class_design", [])
    del answer["classes"], answer["search_allocation"]
    submit(w, rid, answer)
    answer = analyze("blocked")
    del answer["class_results"], answer["remaining_assumptions"]
    submit(w, rid, answer)
    assert w.next(rid)["task"]["kind"] == "prior"


def test_research_priorities_expose_influential_assumptions():
    state = {"parameter_support": [
        {"model_input": "scenarios/a/probability", "input_id": "timing", "basis": "assumed", "target": "Completion",
         "transfer_assumptions": "Borrow duration from smaller projects"}],
        "sensitivity": {"conditional_sensitivity": [{"scenario_id": "a", "swing": .3}]}}
    rows = reference_research.priorities(state)
    assert rows[0]["probability_swing"] == .3
    assert rows[0]["basis"] == "assumed"


@pytest.mark.parametrize("problem", ["no_broad_class", "undeclared_input", "overallocated"])
def test_design_rejects_narrow_or_unusable_plan(tmp_path, problem):
    w, rid, _ = begin(tmp_path)
    submit(w, rid, intake())
    answer = study_payload("reference_class_design", [])
    if problem == "no_broad_class":
        answer["classes"][1]["distance"] = "close"
    elif problem == "undeclared_input":
        answer["classes"][1]["target_input_ids"] = ["not_declared"]
    else:
        answer["search_allocation"]["discovery"] = 50
    with pytest.raises(Error):
        submit(w, rid, answer)
    assert w.next(rid)["revision"] == 1


def test_missing_estimator_artifact_has_explicit_honest_state(tmp_path):
    w, rid, refs = begin(tmp_path)
    searched(w, rid, refs)
    answer = analyze('outcomes_unavailable')
    answer.pop('estimator')
    submit(w, rid, answer)
    assert w.next(rid)['context']['reference_research']['artifact_status'] == 'no_verified_empirical_export'
    assert w.next(rid)['context']['reference_research']['analysis']['artifact_omission_reason']


def test_optional_artifact_is_validated_and_complete_requires_one(tmp_path):
    w, rid, refs = begin(tmp_path)
    searched(w, rid, refs)
    answer = analyze()
    answer.pop('artifact_omission_reason')
    with pytest.raises(Error, match='artifact_omission_reason'):
        submit(w, rid, answer)
    answer['analysis_path'] = str(tmp_path / 'nonexistent.json')
    with pytest.raises(Error, match='export not found'):
        submit(w, rid, answer)
    answer.pop('analysis_path')
    answer.update(status='complete', case_count=1, independent_episode_count=1)
    with pytest.raises(Error, match='requires analysis_path'):
        submit(w, rid, answer)


def test_partial_export_retains_verified_metadata(tmp_path):
    w, rid, refs = begin(tmp_path); searched(w, rid, refs)
    path = tmp_path / 'analysis.json'
    path.write_text(json.dumps({'analysis_id': 'partial-fixture', 'n_subjects': 1,
                               'metric': 'Completion', 'subject_ids': ['museum']}))
    answer = analyze(); answer.pop('artifact_omission_reason'); answer['analysis_path'] = str(path)
    submit(w, rid, answer)
    assert w.next(rid)['context']['reference_research']['artifact_status'] == 'verified_empirical_export'
