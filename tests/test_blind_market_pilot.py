"""Checks for the live pilot's source boundary, reveal gate, and score arithmetic."""

import importlib.util
from pathlib import Path

import pytest

from vorhersage.common import digest

SPEC = importlib.util.spec_from_file_location("blind_market_pilot", Path(__file__).resolve().parents[1] / "examples/kalshi_blind_20260918/study.py")
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


@pytest.mark.parametrize("url", [
    "https://kalshi.com/markets/test", "https://news.example/article",
    "https://bls.gov.evil.example/news", "https://evil.example/?url=https://bls.gov",
    "http://bls.gov/news", "https://user:secret@bls.gov/news",
    "https://www.netflix.com/tudum/kalshi-odds",
])
def test_source_boundary_rejects_markets_and_allowlist_bypasses(url):
    with pytest.raises(ValueError):
        pilot.source_url(url)


def test_redirect_is_checked_before_following():
    with pytest.raises(ValueError):
        pilot.SourceRedirects().redirect_request(None, None, 302, "Found", {}, "https://kalshi.com/")


@pytest.mark.parametrize("text", ["A newspaper cites Kalshi at 60%.", "Polymarket implies 72%.", "Embedded betting odds: 3/2."])
def test_third_party_quoted_odds_are_rejected(text):
    with pytest.raises(ValueError):
        pilot.source_text(text)


def test_real_world_rates_are_not_mistaken_for_market_odds():
    pilot.source_url("https://www.bls.gov/news.release/empsit.htm")
    pilot.source_text("Unemployment is 4.1%; the policy rate is 3.75–4.00%.")


def test_reveal_requires_all_attempts_and_unchanged_forecasts():
    trials = [{"trial_id": "a"}, {"trial_id": "b"}]
    seal = {"forecasts": [{"probability": .4}], "attempts": [{"trial_id": "a"}, {"trial_id": "b"}]}
    commitment = {"sha256": digest(seal)}
    pilot.verify_seal(seal, commitment, trials)
    changed = {**seal, "forecasts": [{"probability": .6}]}
    with pytest.raises(ValueError):
        pilot.verify_seal(changed, commitment, trials)
    missing = {**seal, "attempts": [{"trial_id": "a"}]}
    with pytest.raises(ValueError):
        pilot.verify_seal(missing, {"sha256": digest(missing)}, trials)
    duplicate = {**seal, "attempts": [{"trial_id": "a"}, {"trial_id": "a"}]}
    with pytest.raises(ValueError):
        pilot.verify_seal(duplicate, {"sha256": digest(duplicate)}, trials)


def test_metrics_use_midpoint_and_distance_outside_the_spread():
    rows = [{"target": .5, "bid": .45, "ask": .55, "estimate": .4},
            {"target": .5, "bid": .45, "ask": .55, "estimate": .52}]
    result = pilot.metrics(rows, "estimate")
    assert result["contracts"] == 2
    assert result["mae_pp"] == pytest.approx(6)
    assert result["rmse_pp"] == pytest.approx(100 * (.0052 ** .5))
    assert result["mean_outside_spread_pp"] == pytest.approx(2.5)
    assert pilot.metrics([], "estimate") == {"contracts": 0}
