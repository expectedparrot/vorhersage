# September 2026 CPI: above 0.2% month over month?

**Sealed forecast: 66.9%. Kalshi opening midpoint: 98.5% (98–99% quote).**

[Full HTML report](full-report.html) · [PDF](full-report.pdf) ·
[LaTeX](full-report.tex) · [JSON record](full-report.json)

This is a non-weather market: `KXCPI-26SEP-T0.2`. The event is the BLS
single-decimal, seasonally adjusted monthly all-items CPI-U increase for September.
An ordinary published value of **0.3% or higher** resolves Yes. The release is
scheduled for October 14 at 08:30 Eastern. Contract contingencies are preserved;
the numerical model assumes the ordinary release.

## Results

| Stage | Probability | Gap below opening target |
|---|---:|---:|
| Subjective initial model | 36.9% | 61.6 points |
| Three-month headline momentum | 18.8% | 79.7 points |
| After gasoline adjustment | 66.9% | 31.6 points |
| Kalshi opening midpoint | 98.5% | — |

The quote was captured September 16 at **16:41:57 UTC**. The forecast was sealed
at **16:47 UTC**, before reveal at **22:28:05 UTC**. The later quote remained
98–99%, with unchanged terms. Opening best-quote sizes were 595.01 bid and
2,954.5 ask contracts; both comfortably passed the declared ten-contract screen.
The outcome was unresolved at the research cutoff. These are market-agreement
results, not resolution scores or evidence of predictive superiority.

## Model and research

The [original plan](research/inputs/01-plan.json) specified the historical window,
normal error model, gasoline projection and seasonal approximation before data
collection. Two checkpoints isolate calculation stages within one research pass;
the momentum checkpoint was saved after gasoline data had already been collected.

1. Start with the mean of June–August headline monthly changes. Fit errors for
   that same rule across 48 target months, September 2022–August 2026.
2. Exclude five targets affected by the missing October 2025 CPI index, leaving
   43 observations. Do not interpolate the missing release.
3. Replace the historical gasoline contribution with a September projection from
   EIA weekly prices. Carry the latest observed price through month-end.
4. Approximate seasonality with the median September gasoline adjustment across
   2021–2025. Use the 3.770% weight published in the August CPI release,
   explicitly labeled as July relative importance.
5. Retain the momentum model's residual spread and integrate above the 0.25%
   effective unrounded threshold. Do not claim validated conditional uncertainty.

The FRED gasoline download was one week stale. EIA's original workbook supplied
September 14's all-grades price, **$4.455/gallon**. The projected monthly average
rises **4.22%**, or **6.44%** after the seasonal approximation. Replacing the prior
three-month gasoline trend adds **0.3515 percentage points** to headline CPI.
The final normal model has center **0.3662%**, spread **0.2655 percentage points**,
and probability **66.9%**. Full pairs, exclusions and sensitivities are in
[calculation.json](research/inputs/calculation.json).

## Why the result is provisional

A chronological diagnostic had 36 training observations but only seven usable
holdout forecasts because of the missing period. Its nominal 90% interval
covered only four of seven outcomes; held-out RMSE was 0.502 percentage points.
Using that RMSE as an alternative width gives **59.2%**, a pre-reveal diagnostic,
not a validated replacement. Remaining-month gasoline price shifts of ±5% give
**53.4–78.5%**. These are sensitivity ranges, not confidence intervals.

Against the user's market-target criterion, the final 31.6-point gap is a
substantial miss. Updating the mean with current gasoline information while
retaining errors from a much cruder model is an explicit limitation. Neither
shrinking that spread after seeing the quote nor declaring Kalshi wrong would
validate a better method.

The next fresh case should calibrate a complete component model against dated
partial-month inputs and original-release outcomes. This run uses revised
historical CPI, approximate seasonality and a lagged expenditure weight. It does
not separately forecast shelter/core, food, other energy, geopolitical shocks or
exceptional-release contingencies. The exact 2026 seasonal factors were not
extracted. Same assistant context; separate evaluator storage without enforced
isolation. Costs and usage are unmetered.

## Reproduce and inspect

Run the numerical analysis offline with only the Python standard library:

```bash
.venv/bin/python examples/market_workbench/cpi_202609/analyze.py
```

The original EIA workbook and its extracted recent CSV are both preserved.
`extract_eia.py` reproduces that extraction if the optional `xlrd` package is
available. The BLS table's relevant weight/index values were manually transcribed
from the official page after direct downloads returned HTTP 403; provenance is
saved in `research/raw/bls_weight.json`.

- [Source bundle](research/inputs/research-evidence.json)
- [Sealed journal](sealed-journal.json)
- [Market reveal](reveal.json)
- [Pre-reveal sensitivity](pre-reveal-diagnostics.json)
- [Post-reveal diagnostic](post-reveal-diagnostic.json), explicitly not a revised forecast
- [Narrative](narrative.json), pinned to the exported record hash

HTML, JSON and calculations are portable. Local SQLite projects are ignored by
Git. With those working databases present:

```bash
.venv/bin/python -m vorhersage \
  --project examples/market_workbench/cpi_202609/research \
  workbench show workbench_1ae01f8856bf4dc5926f
.venv/bin/python -m vorhersage \
  --project examples/market_workbench/cpi_202609/research doctor
```
