"""The expanded batch keeps source and reveal boundaries intact."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "examples/kalshi_expansion_20260918"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


batch = module("expansion_batch_test", ROOT / "batch.py")
sources = module("expansion_sources_test", ROOT / "sources.py")


def test_all_models_receive_identical_registered_inputs():
    reg, _ = batch.verify_inputs()
    assert len(reg["cases"]) == 15
    assert len(reg["trials"]) == 90


def example_seals():
    reg = {"arm_info": {k: {"model_key": k} for k in batch.MODELS},
           "trials": [{"trial_id": k, "arm_id": k} for k in batch.MODELS]}
    seals = {k: {"attempts": [{"trial_id": k, "accepted": True}],
                 "forecasts": [{"trial_id": k}]} for k in batch.MODELS}
    return reg, seals


@pytest.mark.parametrize("defect", ["missing_model", "missing_attempt", "duplicate_attempt", "extra_forecast", "unissued"])
def test_reveal_gate_requires_every_terminal_attempt_and_exact_issued_set(defect):
    reg, seals = example_seals()
    batch.terminal_gate(reg, seals)
    bad = copy.deepcopy(seals)
    if defect == "missing_model":
        bad.pop("astra")
    elif defect == "missing_attempt":
        bad["astra"]["attempts"] = []
    elif defect == "duplicate_attempt":
        bad["astra"]["attempts"] *= 2
    elif defect == "extra_forecast":
        bad["astra"]["forecasts"].append({"trial_id": "unregistered"})
    else:
        bad["astra"]["forecasts"] = []
    with pytest.raises(ValueError):
        batch.terminal_gate(reg, bad)


@pytest.mark.parametrize("url", ["https://kalshi.com/test", "https://nfl.com.evil.example/x", "https://user:secret@bls.gov/x"])
def test_primary_source_boundary(url):
    with pytest.raises(ValueError):
        sources.check_url(url)


def test_nonmarket_forecasts_are_valid_evidence_but_quoted_odds_are_not():
    sources.check_url("https://www.atlantafed.org/research-and-data/data/gdpnow")
    sources.check_text("GDPNow estimates 5.1% annualized growth.")
    with pytest.raises(ValueError):
        sources.check_text("A sportsbook assigns betting odds to this game.")
