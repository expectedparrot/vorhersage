"""Descriptive market-distance measures for repeated forecasts of one event."""
from math import sqrt
from statistics import mean, stdev

from .common import probability, require


def score_draws(draws, target, *, bid=None, ask=None):
    """Distinguish a randomly selected call's loss from loss of the mean forecast.

    Repetitions measure within-question variation; they do not increase the
    number of independent events. Sample SD is descriptive, not a confidence
    interval. Missing or invalid draws must be handled explicitly by the caller.
    """
    require(isinstance(draws, (list, tuple)) and len(draws) > 0, "Supply at least one forecast draw.")
    for p in [*draws, target]:
        probability(p)
    require((bid is None) == (ask is None), "Supply both bid and ask or neither.")
    if bid is not None:
        probability(bid)
        probability(ask)
        require(bid <= target <= ask, "Target must lie inside the uncrossed spread.")
    center = mean(draws)
    return {"draws": len(draws), "mean_probability": center,
            "sample_sd_pp": 100 * stdev(draws) if len(draws) > 1 else None,
            "min_probability": min(draws), "max_probability": max(draws),
            "mean_draw_absolute_error_pp": 100 * mean(abs(p - target) for p in draws),
            "root_mean_draw_squared_error_pp": 100 * sqrt(mean((p - target) ** 2 for p in draws)),
            "mean_forecast_absolute_error_pp": 100 * abs(center - target),
            "mean_draw_outside_spread_pp": None if bid is None else 100 * mean(max(bid - p, p - ask, 0) for p in draws)}
