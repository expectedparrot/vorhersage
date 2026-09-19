"""Reproduce this post-reveal diagnosis from saved, immutable study inputs.

No provider calls, network access, fitted recalibration, or new forecasts.
Run from any directory; writes only alongside this script.
"""

import csv
import hashlib
import json
from datetime import date
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
RUN = STUDY / "run"
FOCUS = {"measles", "global_heat"}


def read(path):
    return json.loads(path.read_text())


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def table(name, rows):
    with (HERE / name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    comparison = read(RUN / "comparison.json")
    registration = read(RUN / "registration.json")
    trials = {t["trial_id"]: t for t in registration["trials"]}
    excerpts, scores, contributions = [], [], []
    inputs = [RUN / "comparison.json", RUN / "registration.json",
              RUN / "method.json", RUN / "definition-notes.json",
              RUN / "research/other-search.json", STUDY / "batch.py",
              STUDY / "definitions/measles-terms.pdf"]
    for qid in sorted(FOCUS):
        inputs += [RUN / "packets" / f"{qid}.json",
                   RUN / "revealed-targets" / f"{qid}.json"]
    for model in ("astra", "fable", "gemini"):
        path = RUN / model / "raw-records.json"
        inputs.append(path)
        for row in read(path):
            trial = trials[row["scenario"]["trial_id"]]
            arm = registration["arm_info"][trial["arm_id"]]
            if trial["question_id"] in FOCUS and arm["condition"] == "outside_research":
                forecast = row["answer"]["forecast"]
                if isinstance(forecast, str):
                    forecast = json.loads(forecast)
                prompt = RUN / "tasks" / (trial["trial_id"] + ".txt")
                inputs.append(prompt)
                excerpts.append({"model": model, "question": trial["question_id"],
                                 "repetition": trial["repetition"], "trial_id": trial["trial_id"],
                                 "forecast": forecast})
        loss_parts = {"focus": [], "other": []}
        for pair in comparison["pairs"]:
            draws = pair["draws"][model]["outside_research"]
            loss = mean(abs(p - pair["target"]) * 100 for p in draws)
            control = abs(0.5 - pair["target"]) * 100
            loss_parts["focus" if pair["id"] in FOCUS else "other"].append(loss - control)
            scores.append({"model": model, "question": pair["id"],
                           "target_percent": pair["target"] * 100,
                           "research_mean_percent": mean(draws) * 100,
                           "research_mae_pp": loss, "constant_50_mae_pp": control})
        n = len(comparison["pairs"])
        contributions.append({"model": model,
                              "two_focus_contribution_pp": sum(loss_parts["focus"]) / n,
                              "other_five_contribution_pp": sum(loss_parts["other"]) / n,
                              "net_research_minus_control_mae_pp": sum(map(sum, loss_parts.values())) / n})
    assert len(excerpts) == 18
    write("forecast-excerpts.json", excerpts)
    table("scores.csv", scores)
    table("loss-contributions.csv", contributions)

    weekly_path = HERE / "research/MeaslesCasesWeekly.json"
    weekly = [dict(r, cases=int(r["cases"])) for r in read(weekly_path)
              if r["week_start"] >= "2026-01-04"]
    cases = read(RUN / "packets/measles.json")["records"][0]["value"]["2026_US_cases"]
    # CDC assigns Dec 28, 2025-Jan 3, 2026 to 2025; retain that convention.
    assert sum(r["cases"] for r in weekly) == cases == 3471
    table("measles-weekly.csv", weekly)
    remaining_days = (date(2026, 12, 31) - date(2026, 9, 17)).days
    elapsed_days = (date(2026, 9, 17) - date(2026, 1, 1)).days + 1
    needed = 6001 - cases
    recent = mean(r["cases"] for r in weekly if "2026-08-09" <= r["week_start"] <= "2026-08-30")
    earlier = mean(r["cases"] for r in weekly if "2026-07-12" <= r["week_start"] <= "2026-08-02")
    measles = {"additional_cases_needed": needed, "approx_calendar_days_remaining": remaining_days,
               "required_cases_per_week": needed / (remaining_days / 7),
               "calendar_ytd_cases_per_week": cases / (elapsed_days / 7),
               "four_weeks_ending_sep5_mean": recent,
               "previous_four_weeks_mean": earlier,
               "weekly_data_total_check": cases,
               "constant_recent_rate_scenario_year_end": cases + recent * remaining_days / 7,
               "scenario_is_not_a_probability_forecast": True,
               "cautions": ["Rash-onset counts are provisional; latest weeks are incomplete and delayed.",
                            "Calendar-day approximation is not exact CDC epidemiological-year accounting.",
                            "Four-week window selected after price reveal; not a validated smoothing rule."]}

    # These observations are independently checked against the original NASA capture.
    monthly = [1.09, 1.25, 1.32, 1.17, 1.13, 1.18, 1.25, 1.40]
    captured = json.dumps(read(RUN / "packets/global_heat.json"))
    assert "109  125  132  117  113  118  125  140" in captured
    total = sum(monthly)
    climate = {"jan_aug_sum": total, "jan_aug_mean": mean(monthly),
               "remaining_mean_to_exceed_unrounded_1_28": (12 * 1.28 - total) / 4,
               "remaining_mean_at_annual_1_285_rounding_boundary": (12 * 1.285 - total) / 4,
               "scenarios": [{"remaining_four_mean": x, "annual_equal_month_mean": (total + 4*x) / 12}
                             for x in (1.30, 1.40, 1.41, 1.50)],
               "approximate_baseline_offset": 0.19,
               "offset_source": "https://data.giss.nasa.gov/gistemp/faq/",
               "offset_caution": "NASA FAQ approximation as of Jan 2025; not an exact reconciliation of September 2026 vintages."}
    with (HERE / "research/Annual_GISTEMP_GMSTA_Predictions_202609.csv").open() as f:
        predictions = [{"method": r["method/model"], "year": int(r["year"]),
                        "mean_1850_1900": float(r["pred_GMSTA"]),
                        "published_95_interval_halfwidth": float(r["CI_95"]),
                        "approx_mean_1951_1980": float(r["pred_GMSTA"]) - 0.19}
                       for r in csv.DictReader(f) if r["year"] == "2026"]
    table("nasa-predictions.csv", predictions)
    write("arithmetic.json", {"measles": measles, "temperature": climate,
                              "loss_contributions": contributions})
    write("original-input-hashes.json", {str(p.relative_to(STUDY)): sha(p) for p in sorted(set(inputs))})
    write("research-file-hashes.json", {str(p.relative_to(HERE)): sha(p)
                                       for p in sorted((HERE / "research").iterdir()) if p.is_file()})
    print(json.dumps({"reviewed_research_forecasts": len(excerpts), "measles": measles,
                      "temperature": climate, "loss_contributions": contributions}, indent=2))


if __name__ == "__main__":
    main()
