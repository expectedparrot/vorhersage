"""Guard the fixed-input boundary and strict returned model identities."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "fixed_data_models", Path(__file__).resolve().parents[1] / "examples/kalshi_models_20260918/compare.py")
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def fixture_row():
    job = {"models": [{"model": "test", "parameters": {"reasoning_effort": "high"}}],
           "agents": [{"instruction": "Fixed instruction"}], "edsl_version": "test-version"}
    scenario = {"trial_id": "a", "prompt": "Fixed original prompt"}
    payload = {"method": "judgment", "probability": .4, "rationale": "Uncertain event.",
               "limitations": [], "evidence_refs": []}
    row = {"model": job["models"][0], "agent": job["agents"][0],
           "scenario": {**scenario, "edsl_version": "test-version", "edsl_class_name": "Scenario"},
           "answer": {"forecast": json.dumps(payload)}}
    return copy.deepcopy(row), scenario, job


def test_original_inputs_and_registered_prompts_are_unchanged():
    pilot.verify_inputs()


def test_only_exact_serialization_metadata_is_accepted():
    row, scenario, job = fixture_row()
    assert pilot.validate_row(row, scenario, job)["probability"] == .4
    row["scenario"]["target_price"] = .6
    with pytest.raises(ValueError, match="identity"):
        pilot.validate_row(row, scenario, job)


@pytest.mark.parametrize("part", ["model", "agent", "scenario"])
def test_model_settings_instruction_and_prompt_cannot_change(part):
    row, scenario, job = fixture_row()
    row[part] = {**row[part], "unexpected": "changed"}
    with pytest.raises(ValueError, match="identity"):
        pilot.validate_row(row, scenario, job)


def test_market_mentions_stay_excluded_and_fences_are_not_repaired():
    row, scenario, job = fixture_row()
    payload = json.loads(row["answer"]["forecast"])
    payload["limitations"] = ["Prediction-market odds were not used."]
    row["answer"]["forecast"] = json.dumps(payload)
    with pytest.raises(ValueError, match="Excluded-content"):
        pilot.validate_row(row, scenario, job)
    row["answer"]["forecast"] = '```json\n' + json.dumps(payload) + '\n```'
    with pytest.raises(ValueError):
        pilot.validate_row(row, scenario, job)
