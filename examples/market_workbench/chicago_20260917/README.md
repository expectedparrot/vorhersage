# Chicago Midway: September 17, 2026 high temperature

**Our sealed forecast: 24.4%. Opening Kalshi midpoint: 36.5% (35–38% quote).**

[Read the full report](full-report.html), including its methodology flowchart,
or download the [PDF](full-report.pdf). [LaTeX](full-report.tex) and the
[complete JSON record](full-report.json) are also available.

The question is whether the final Chicago Midway (CLIMDW) maximum for September 17
will be 76–77°F, under Kalshi contract `KXHIGHCHI-26SEP17-B76.5`.
The Weather Company determines settlement. The event was unresolved at sealing.

## What happened

| Stage | Probability | Gap below opening midpoint |
|---|---:|---:|
| Initial NBS model | 22.3% | 14.2 points |
| Predeclared residual model | 24.4% | 12.1 points |
| Opening Kalshi midpoint | 36.5% | — |
| Later Kalshi midpoint | 35.0% | Different snapshot |

We froze the opening quote at **14:59:25 UTC on September 16**, recorded the
initial estimate and plan at **15:01**, sealed at **15:04**, then revealed at
**15:17:29**. Selection required a spread no wider than five cents and at least
ten contracts at each best quote. The first candidate (78–79°F) failed depth;
the second (76–77°F) passed unchanged requirements. See [selection notes](selection.md).

The opening book had 24.02 contracts at the best bid and 20 at the best ask.
The later best ask had only four contracts, below the opening screen. These
snapshots do not establish sustained liquidity or market calibration.

## Model fixed before collecting historical outcomes

- Use all 60 target days July 18–September 15, 2026.
- Match MDW station daily highs to previous-day KMDW NBS 06 UTC forecasts;
  the next-day maximum appears at 42-hour lead.
- Set mean to current NBS high plus mean historical residual.
- Set variance to sample residual variance × (1 + 1/n) + 1°F².
- Approximate a reported 76–77°F maximum by a normal-distribution interval
  from 75.5°F to 77.5°F.
- Report empirical residual frequency, a chronological 40/20 diagnostic,
  and sensitivity to the center and the subjective extra spread.

All 60 days matched, without exclusions. Residual mean was +0.083°F and SD
2.513°F. Current NBS high was 78°F. The final distribution has mean 78.083°F,
SD 2.724°F, and band probability 24.3743%. The empirical frequency was 13/60,
or 21.7%. NWS predicted 76°F; substituting that raw center gives 28.2%.
The 40/20 chronological check found slightly worse RMSE with bias correction
(2.596°F versus 2.559°F), not evidence of improvement.

## What this teaches us

Research brought the forecast 2.1 points closer to the opening market target,
but a substantial disagreement remains. **With SD 2.724°F, even an optimally
centered normal distribution puts at most 28.65% into a two-degree interval.**
The discrepancy therefore concerns dispersion or distribution shape as well as
the point forecast. This observation was made after reveal and is saved as a
[separate diagnostic](post-reveal-diagnostic.json); it does not revise the forecast.

On a fresh case, test a predeclared method that calibrates uncertainty by
forecast horizon, model dispersion or weather regime, with a larger sample and
chronological validation. Specify the latest available forecast cycle and seek
exact settlement observations. Do not choose parameters to fit this revealed quote.

## Limits

The 1°F source/window allowance, normality and nearest-integer approximation are
assumptions. IEM daily highs are proxies for TWC settlement; the public TWC page
check did not establish exact history or rounding. Adjacent summer days may not
represent tomorrow's cloudy, showery conditions. The 06 UTC forecast was already
several hours old at quote capture. Market agreement is not forecast accuracy.

The same assistant context as NYC performed the research. Evaluator storage
was separate and uninspected until sealing, but not protected by an access
barrier. This is not independently verified blinding. Usage costs are unmetered.

## Reproduce

The numerical calculation works offline from the frozen downloads:

```bash
.venv/bin/python examples/market_workbench/chicago_20260917/analyze.py
```

Inspect the [calculation and all 60 pairs](research/inputs/calculation.json),
[original plan](research/inputs/01-plan.json),
[sealed journal](sealed-journal.json), [reveal](reveal.json),
[source bundle](research/inputs/research-evidence.json), and
[retrieval record](retrievals.json).
The calculation records raw-file hashes. The narrative is pinned to the exported
record's hash. Reports and calculations can be read without the local databases.

The local working projects can also be inspected with:

```bash
.venv/bin/python -m vorhersage \
  --project examples/market_workbench/chicago_20260917/research \
  workbench show workbench_99b666aae9114c089f49
.venv/bin/python -m vorhersage \
  --project examples/market_workbench/chicago_20260917/research doctor
```

Those commands require the local SQLite projects, which are ignored by Git.
