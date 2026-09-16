"""Reproduce the pre-reveal calculation from frozen weather downloads."""
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist, mean, stdev

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "research" / "raw"


def band(mu, sigma):
    distribution = NormalDist(mu, sigma)
    return distribution.cdf(80.5) - distribution.cdf(78.5)


def analyze():
    observations = {
        row["day"]: float(row["max_temp_f"])
        for row in csv.DictReader((RAW / "observed_history.csv").open())
        if row["max_temp_f"] not in ("", "None", "M")
    }
    forecasts = {}
    for row in csv.DictReader((RAW / "nbs_history.csv").open()):
        runtime = dt.datetime.fromisoformat(row["runtime"])
        valid = dt.datetime.fromisoformat(row["ftime"])
        if (runtime.hour == 6
                and valid == runtime.replace(hour=0) + dt.timedelta(days=1)
                and row["txn"]):
            forecasts[runtime.date().isoformat()] = float(row["txn"])
    pairs, excluded = [], []
    for offset in range(31):
        date = (dt.date(2026, 8, 16) + dt.timedelta(days=offset)).isoformat()
        if date not in forecasts or date not in observations:
            excluded.append(date)
            continue
        pairs.append({"date": date, "forecast": forecasts[date],
                      "observed": observations[date],
                      "error": observations[date] - forecasts[date]})
    errors = [pair["error"] for pair in pairs]
    current = json.loads((RAW / "nbs_current.json").read_text())["data"]
    current = [row for row in current if row["ftime"] == "2026-09-17 00:00"]
    assert len(current) == 1 and current[0]["runtime"] == "2026-09-16 06:00"
    forecast, bias, sd = current[0]["txn"], mean(errors), stdev(errors)
    # Declared modeling assumptions, not estimated facts: Gaussian residuals,
    # nearest-integer settlement, and independent 1 F provider/window uncertainty.
    mu = forecast + bias
    sigma = math.sqrt(sd**2 * (1 + 1 / len(errors)) + 1.0**2)
    return {
        "selection": "All dates August 16 through September 15, 2026; KNYC NBS 06 UTC; next 00 UTC TXN",
        "pairs": pairs, "excluded_dates": excluded, "n": len(errors),
        "bias_observed_minus_forecast_f": bias, "residual_sample_sd_f": sd,
        "current_nbs_high_f": forecast, "current_nbs_xnd_f": current[0]["xnd"],
        "initial_probability": band(80, 3),
        "bias_corrected_gaussian_probability": band(mu, sd),
        "empirical_residual_probability": mean(79 <= forecast + e <= 80 for e in errors),
        "final_mean_f": mu, "final_sd_f": sigma,
        "assumed_extra_provider_window_sd_f": 1.0,
        "final_probability": band(mu, sigma),
        "sensitivity": [
            {"extra_sd_f": extra, "mean_shift_f": shift,
             "probability": band(mu + shift, math.sqrt(sd**2 * (1 + 1 / len(errors)) + extra**2))}
            for extra in (0, 1, 2) for shift in (-1, 0, 1)
        ],
        "limitations": [
            "IEM station daily highs are a proxy, not TWC contract settlement records.",
            "NBM maximum covers 12 UTC through 06 UTC; station daily summary windows can differ.",
            "31 adjacent days are a small, serially correlated sample; no out-of-sample validation.",
            "One-degree extra SD and normality are subjective; Gaussian smoothing differs from empirical frequency.",
            "No adjustment for weather-regime or seasonal differences; no exact TWC rounding verification.",
        ],
        "raw_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(RAW.iterdir()) if p.is_file()},
    }


if __name__ == "__main__":
    result = analyze()
    (ROOT / "research" / "inputs" / "calculation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "pairs"}, indent=2))
