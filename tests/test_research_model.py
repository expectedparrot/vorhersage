"""Regression coverage for research, revision, and reporting failures seen in agent use."""

import copy
import json
import subprocess
import sys

import pytest

from vorhersage import evidence, reports, research_model, study, study_text
from vorhersage.common import Error, now
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_workflow import packet, payload, question, stamp
from test_study import intake, study_payload, support


def begin(tmp_path):
    w = Workflow(tmp_path / "study")
    q = question(kind="real")
    study.start(w.store.root, q["text"], q, forecaster="tester", research_contract="structured_v1", research_effort="standard")
    return w


def submit(w, answer, usage=None):
    task = study.next_task(w)
    task["submission"]["payload"] = answer
    if usage:
        task["submission"]["usage"] = usage
    return study.submit(w, task)


def finish(w, refs):
    while (task := study.next_task(w))["disposition"] == "actionable":
        submit(w, study_payload(task["task"]["kind"], refs))
    return task["forecast_id"]


def test_intake_routes_user_facts_before_estimate_and_records_actual_timing(tmp_path):
    w = begin(tmp_path)
    unknown = {"id": "ready", "question": "Has QA passed?", "input_ids": ["outcome"],
               "route": "ask_user", "why_it_matters": "QA gates public access.", "action": "Ask the release owner."}
    bad = intake([dict(unknown, input_ids=["absent"])])
    with pytest.raises(Error, match="declared input"):
        submit(w, bad)
    submit(w, intake([unknown]))
    task = study.next_task(w)
    assert task["task"]["kind"] == "inquiry"
    assert task["context"]["current_probability"] is None
    assert "Has QA passed?" in study_text.render(study.show(w.store))
    with pytest.raises(Error, match="captured finding"):
        submit(w, {"status": "answered", "answer": "Owner says yes.", "evidence_refs": []})
    captured = evidence.capture_finding("Owner reports QA passed.", url="urn:user:release-owner", title="Owner answer",
                                         excerpt="QA passed today.", claim_type="observation")
    imported = w.import_packet(captured)
    refs = [imported["records"][0]["evidence_ref"]]
    submit(w, {"status": "answered", "answer": "QA passed, according to the owner.", "evidence_refs": refs})
    assert study.next_task(w)["task"]["kind"] == "prior"
    with pytest.raises(Error, match="research_status_at_estimate"):
        submit(w, payload("prior", []))
    submit(w, study_payload("prior", []))
    timing = study.next_task(w)["context"]["prior_record"]
    assert timing["research_status_at_run_start"] == "not_started"
    assert timing["timing"] == "after_research_started"
    assert timing["recorded_research_before_estimate"]
    assert captured["records"][0]["sources"][0]["retrieved_at"] == captured["created_at"]
    assert w.doctor()["ok"]


def test_revision_keeps_original_and_exposes_pending_and_issued_versions(tmp_path):
    w = begin(tmp_path)
    refs = [w.import_packet(packet())["records"][0]["evidence_ref"]]
    first = finish(w, refs)
    old_task = study.next_task(w)
    with w.store.connect() as c:
        original = Store.artifact(c, first)
    fresh = evidence.capture_finding("Owner reports a delay.", url="urn:user:release-owner", title="New answer",
                                      excerpt="The launch has been delayed.", claim_type="observation")
    new_refs = [w.import_packet(fresh)["records"][0]["evidence_ref"]]
    signal = w.signal({"question_id": "factory", "reason": "New owner answer; reassess timing.",
                       "evidence_refs": new_refs, "idempotency_key": "delay-signal"})
    before = reports.question_data(w.store, "factory")
    assert before["signals"][0]["id"] == signal["signal_id"]
    assert new_refs[0]["packet_id"] in before["artifacts"]
    revised = study.revise(w, reason="New owner answer", refs=new_refs, expected_forecast=first)
    assert revised["previous_forecast"] == original
    assert revised["probability"] is None and not revised["issued"]
    assert len(w.status()["runs"]) == 2
    study.revise(w, reason="New owner answer", refs=new_refs, expected_forecast=first)
    assert len(w.status()["runs"]) == 2
    with pytest.raises(Error, match="Finish the active"):
        study.revise(w, reason="Another revision", refs=new_refs)
    with pytest.raises(Error, match="different forecast"):
        study.submit(w, old_task)
    pending_report = reports.question_data(w.store, "factory")
    for extension in ("html", "tex"):
        output = tmp_path / ("pending." + extension)
        reports.export(pending_report, output)
        assert "Working revision, not yet issued" in output.read_text()
        assert "New owner answer" in output.read_text()
    submit(w, intake())
    task = study.next_task(w)
    assert task["task"]["kind"] == "assessment"
    assert task["context"]["previous_forecast"]["probability"] == .6
    assert len(task["context"]["evidence"]) == 2
    answer = study_payload("assessment", new_refs, .4)
    submit(w, answer)
    submit(w, study_payload("review", new_refs))
    submit(w, study_payload("issue", new_refs))
    current = study.show(w.store)
    assert current["issued"] and current["probability"] == .4
    with w.store.connect() as c:
        assert Store.artifact(c, first) == original
        final = Store.artifact(c, current["forecast_id"])
    assert final["previous_forecast_id"] == first
    assert final["information_as_of"] >= fresh["information_as_of"]
    assert final["prior_record"]["timing"] == "not_applicable"
    assert "Previous issued forecast: 60.0%" in study_text.render(current)
    assert w.doctor()["ok"]


def test_model_support_is_bound_to_numbers_and_sensitivity_drives_review(tmp_path):
    w = begin(tmp_path)
    refs = [w.import_packet(packet())["records"][0]["evidence_ref"]]
    while (task := study.next_task(w))["task"]["kind"] != "assessment":
        submit(w, study_payload(task["task"]["kind"], refs))
    answer = {"method": "scenario_mixture", "rationale": "Four hypothetical cases.", "limitations": ["Assumptions only."],
              "evidence_refs": [], "partition_justification": "Distinct exhaustive fixture cases.", "scenarios": [
                  {"id": str(i), "description": "Fixture case " + str(i), "weight": weight, "probability": probability,
                   "rationale": "Illustrative assumptions.", "evidence_refs": [], "unknowns": [],
                   "weight_range": wr, "probability_range": pr}
                  for i, (weight, probability, wr, pr) in enumerate([
                      (.25, .75, [.15, .35], [.65, .85]), (.35, .55, [.25, .45], [.4, .65]),
                      (.30, .15, [.2, .4], [.05, .25]), (.10, .20, [.05, .15], [.1, .3])])]}
    with pytest.raises(Error, match="parameter_support"):
        submit(w, answer)
    answer["parameter_support"] = support(answer)
    for row in answer["parameter_support"]:
        _, sid, field = row["model_input"].split("/")
        row["plausible_range"] = answer["scenarios"][int(sid)][field + "_range"]
    for change in ("value", "basis", "model_input", "input_id"):
        bad = copy.deepcopy(answer)
        bad["parameter_support"][0][change] = {"value": .9, "basis": "measured", "model_input": "missing", "input_id": "missing"}[change]
        with pytest.raises(Error):
            submit(w, bad)
    submit(w, answer)
    task = study.next_task(w)
    assert task["context"]["sensitivity"]["bounded_range"] == pytest.approx([.2525, .6225])
    assert "25.2%–62.3%" in study_text.render(study.show(w.store))
    with pytest.raises(Error, match="sensitivity_review"):
        submit(w, payload("review", refs))
    review = study_payload("review", refs)
    with pytest.raises(Error, match="actual model_input"):
        submit(w, review)
    review["sensitivity_review"]["influential_inputs"] = ["scenarios/1/probability"]
    submit(w, review)
    for extension in ("html", "tex"):
        output = tmp_path / ("model." + extension)
        reports.export(reports.question_data(w.store, "factory"), output)
        text = output.read_text()
        assert "Evidence behind model inputs" in text
        assert "Assumption sensitivity" in text
        assert "not a confidence interval" in text
    assert w.doctor()["ok"]


def test_timestamps_errors_and_signal_target_are_explicit(tmp_path):
    w = begin(tmp_path)
    future = packet()
    future["information_as_of"] = stamp(1)
    with pytest.raises(Error, match="future-dated relative to current time"):
        w.import_packet(future)
    with pytest.raises(Error, match="observation cannot be later"):
        evidence.capture_finding("Future", url="urn:fixture", title="Fixture", excerpt="Future", observed_at=stamp(1))
    refs = [w.import_packet(packet())["records"][0]["evidence_ref"]]
    with pytest.raises(Error, match="Supply question_id"):
        w.signal({"reason": "Unlinked", "evidence_refs": refs, "idempotency_key": "unlinked"})
    from unittest.mock import patch
    with patch("vorhersage.workflow.now", return_value=stamp(-3)):
        with pytest.raises(Error, match="current time for signal registration"):
            w.signal({"question_id": "factory", "reason": "Cutoff test", "evidence_refs": refs, "idempotency_key": "early"})


def test_payload_only_submission_and_project_position_keep_task_immutable(tmp_path):
    w = begin(tmp_path)
    path = tmp_path / "task.json"
    study.next_task(w, path)
    original = path.read_bytes()
    answer = tmp_path / "answer.json"
    answer.write_text(json.dumps(intake()))
    def cli(*args):
        p = subprocess.run([sys.executable, "-m", "vorhersage", *map(str, args)], capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        return json.loads(p.stdout)["data"]
    for _ in range(2):
        result = cli("submit", "--task", path, "--answer", answer, "--project", w.store.root, "--json")
    assert result["duplicate"]
    assert path.read_bytes() == original
    imported = cli("evidence", "add", "Owner reports QA passed.", "--url", "urn:user:owner", "--title", "Owner",
                   "--excerpt", "QA passed.", "--claim-type", "observation", "--project", w.store.root)
    packet_id = imported["packet_id"]
    for args in (("--project", w.store.root, "packet", "show", packet_id),
                 ("packet", "--project", w.store.root, "show", packet_id),
                 ("packet", "show", packet_id, "--project", w.store.root)):
        assert cli(*args)["records"][0]["claim_type"] == "observation"


def test_unobservable_and_unanswered_questions_preserve_uncertainty(tmp_path):
    w = begin(tmp_path)
    unknowns = [{"id": str(i), "question": "Uncertain fact " + str(i), "input_ids": ["outcome"],
                 "route": route, "why_it_matters": "Changes rollout timing.", "action": "Record the information gap."}
                for i, route in enumerate(("ask_user", "unobservable"))]
    submit(w, intake(unknowns))
    submit(w, {"status": "unresolved", "answer": "The owner does not know yet.", "evidence_refs": []})
    with pytest.raises(Error, match="remains unresolved"):
        submit(w, {"status": "answered", "answer": "Pretend it is known.", "evidence_refs": []})
    submit(w, {"status": "unresolved", "answer": "The future queue cannot be observed today.", "evidence_refs": []})
    task = study.next_task(w)
    assert task["task"]["kind"] == "prior"
    assert all(a["status"] == "unresolved" for a in task["context"]["inquiry_answers"].values())
    assert task["context"]["current_probability"] is None


def test_review_judgment_needs_its_own_support_and_updates_visible_range(tmp_path):
    w = begin(tmp_path)
    refs = [w.import_packet(packet())["records"][0]["evidence_ref"]]
    while (task := study.next_task(w))["task"]["kind"] != "review":
        submit(w, study_payload(task["task"]["kind"], refs))
    review = study_payload("review", refs)
    review.update(decision="revise", probability=.35)
    with pytest.raises(Error, match="parameter_support"):
        submit(w, review)
    review["parameter_support"] = support({"method": "judgment", "probability": .35})
    review["parameter_support"][0]["plausible_range"] = [.2, .7]
    submit(w, review)
    assert study.show(w.store)["sensitivity"]["bounded_range"] == [.2, .7]
    submit(w, study_payload("issue", refs))
    with w.store.connect() as c:
        issued = Store.artifact(c, study.show(w.store)["forecast_id"])
    assert issued["probability"] == .35
    assert issued["parameter_support"][0]["value"] == .35
    assert issued["sensitivity"]["bounded_range"] == [.2, .7]
