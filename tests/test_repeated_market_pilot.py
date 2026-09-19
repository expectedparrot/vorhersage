import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "examples/kalshi_repeated_20260918"
spec = importlib.util.spec_from_file_location("repeated_market_pilot", ROOT / "batch.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_registered_repetitions_have_distinct_prompts_and_shared_model_inputs():
    reg, _ = pilot.verify_inputs()
    assert len(reg["trials"]) == 126
    assert reg["specification"]["repetitions"] == 3
    for model in pilot.MODELS:
        job = pilot.load(ROOT / "run" / model / "jobs.json")
        assert len({s["prompt"] for s in job["scenarios"]}) == 42
        assert all("Replicate identifier" in s["prompt"] for s in job["scenarios"])


def pair(cid, draws):
    return {"id": cid, "target": .5, "bid": .49, "ask": .51,
            "dependence_cluster": "one event group", "followup_quote": None,
            "draws": {k: {c: draws[:] for c in pilot.CONDITIONS} for k in pilot.MODELS}}


def test_calls_do_not_inflate_question_counts_and_mean_loss_is_primary():
    r = pilot.summarize([pair("one", [0, .5, 1]), pair("two", [.5, .5, .5])])
    m = r["common_metrics"]["astra"]["question_only"]
    assert m["questions"] == 2
    assert m["mean_draw_mae_pp"] == pytest.approx(100 / 6)
    assert m["three_draw_mean_mae_pp"] == 0


def test_missing_draw_removes_question_from_entire_matched_cohort():
    missing = pair("missing", [0, .5, 1])
    missing["draws"]["fable"]["outside_research"] = [.5, .5]
    r = pilot.summarize([pair("complete", [.5, .5, .5]), missing])
    assert r["common_question_ids"] == ["complete"]
    assert r["common_metrics"]["astra"]["question_only"]["questions"] == 1
    assert missing["cell_scores"]["fable"]["outside_research"]["draws"] == 2


def test_empty_matched_cohort_reports_missing_scores_not_zero():
    p = pair("missing", [])
    r = pilot.summarize([p])
    assert r["common_metrics"]["astra"]["question_only"]["mean_draw_mae_pp"] is None
    assert r["equal_weight_research_metrics"] == {"contracts": 0}


def test_review_cannot_clear_a_different_output_or_omit_a_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(pilot, "OUT", tmp_path)
    screening = {"screened_at": "2026-09-18T20:00:00Z", "records": [
        {"trial_id": "x", "requires_review": True, "row_sha256": "original"}]}
    pilot.write(tmp_path / "astra/screening.json", screening)
    with pytest.raises(ValueError, match="Every flagged"):
        pilot.review_check("astra")
    pilot.write(tmp_path / "astra/content-reviews.json", {"reviews": [
        {"trial_id": "x", "row_sha256": "wrong", "decision": "accept", "category": "explicit_non_use",
         "rationale": "Denial only.", "reviewed_at": "2026-09-18T20:01:00Z"}]})
    with pytest.raises(ValueError, match="different output"):
        pilot.review_check("astra")


def test_denial_exception_does_not_apply_to_source_evidence():
    source_spec = importlib.util.spec_from_file_location("repeated_sources_test", ROOT / "sources.py")
    sources = importlib.util.module_from_spec(source_spec)
    source_spec.loader.exec_module(sources)
    with pytest.raises(ValueError):
        sources.check_text("No Kalshi prices were used.")
