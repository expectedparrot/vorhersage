import pytest

from vorhersage.market_evaluation import score_draws


def test_averaging_forecasts_and_averaging_losses_are_different_estimands():
    r = score_draws([0, 1], .5, bid=.4, ask=.6)
    assert r["mean_draw_absolute_error_pp"] == 50
    assert r["mean_forecast_absolute_error_pp"] == 0
    assert r["mean_draw_outside_spread_pp"] == 40
    assert r["sample_sd_pp"] == pytest.approx(70.710678)


def test_one_draw_does_not_claim_zero_variation():
    r = score_draws([.5], .4)
    assert r["sample_sd_pp"] is None
    assert r["mean_draw_absolute_error_pp"] == pytest.approx(10)


@pytest.mark.parametrize("draws", [[], [None], [float('nan')], [1.1], [True]])
def test_invalid_or_missing_draws_are_not_silently_imputed(draws):
    with pytest.raises((ValueError, TypeError)):
        score_draws(draws, .5)


def test_spread_and_midpoint_must_be_consistent():
    with pytest.raises(ValueError):
        score_draws([.4], .5, bid=.6, ask=.4)
    with pytest.raises(ValueError):
        score_draws([.4], .5, bid=.4)
