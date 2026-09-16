# Live workbench case: New York high temperature, September 16, 2026

**Final forecast: 28.6%. Opening Kalshi midpoint: 28%.**

[Read the published report](https://expectedparrot.github.io/vorhersage/examples/nyc-2026-09-16/)
or [download the PDF](https://expectedparrot.github.io/vorhersage/examples/nyc-2026-09-16/full-report.pdf).

Full exports: [HTML](full-report.html), [LaTeX](full-report.tex), and
[JSON](full-report.json), including the saved calculation as a labeled supplement.

Question: Will the maximum reported for New York City (CLINYC) on September 16
be 79–80°F? Contract: `KXHIGHNY-26SEP16-B79.5`. The Weather Company final report
controls settlement. The event was unresolved when the forecast was sealed.

Open the [CLI-generated report](comparison.html), or inspect its
[JSON export](comparison.json). The [sealed journal](sealed-journal.json) was
saved before revealing the quote. Plans, evidence citations, immutable revisions,
and the post-reveal reflection are included in the report.

## Results

| Stage | Estimate | Distance from opening midpoint |
|---|---:|---:|
| Initial point-forecast model | 25.8% | 2.24 percentage points |
| Morning observations and forecast discussion | 25.8% | 2.24 points |
| Local forecast-error reference class | 28.6% | 0.61 points |

The opening quote at **08:18:15 EDT** was **27–29%** (midpoint 28%).
Research was sealed at **08:26:32 EDT**. The follow-up quote at **08:30:37 EDT**
was **31–32%** (midpoint 31.5%). Both quotes are preserved; the later quote does
not replace the original development target. These are market-agreement results,
not resolution scores or evidence of general forecasting accuracy.

## What research contributed

The initial model used the NWS high of 80°F and an assumed 3°F error standard
deviation. Checking morning observations and the regional forecast discussion
did not justify a numerical update.

Before collecting the historical outcomes, the research plan selected every date
from August 16 through September 15, using the KNYC NBS 06 UTC forecast. All 31
dates were available. Against IEM station daily highs, forecasts averaged **1.03°F
too warm**, with an error standard deviation of **1.82°F**. Current NBS and NWS
forecasts were 79°F. These sources are correlated, not independent confirmations.

The final model corrects the 79°F forecast by the sample bias and uses:

```
mean = 79 - 1.032258 = 77.967742°F
variance = 1.816294² × (1 + 1/31) + 1²
standard deviation = 2.098891°F
P(79–80°F reported) ≈ P(78.5 ≤ Gaussian temperature < 80.5) = 28.6089%
```

The additional 1°F standard deviation is a **subjective allowance** for provider
and measurement-window differences. Gaussian errors, stable bias, and nearest-
integer reporting are also assumptions. The raw empirical residual estimate is
7/31 = **22.6%**. Moving the final model's mean by ±1°F gives **18.6–35.5%**;
that is a sensitivity range, not a confidence interval. The close market match
does not establish that our distributional choices were right.

Sources: [IEM forecast archive](https://mesonet.agron.iastate.edu/mos/),
[IEM daily-summary definitions](https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py?help=),
[NOAA model product definitions](https://vlab.noaa.gov/web/mdl/nbm-textcard-v5.0),
and [NWS point forecast](https://api.weather.gov/gridpoints/OKX/34,45/forecast).
Exact dated requests and captured data are in the case artifacts.

## Limits and next experiment

- The historical observations are **a proxy for TWC settlements**. NBM's daytime
  maximum window and station daily-summary windows differ. Exact TWC reporting
  and rounding were not verified. Thirty-one adjacent days are a small, potentially
  correlated sample, with no independent validation.
- Market movement between snapshots was 3.5 points, larger than our 2.84-point
  revision. Agreement improvement on this case cannot establish a causal research
  benefit.
- Screening was opportunistic; see [selection notes](selection.md). An earlier
  depth check failed at a ten-contract minimum. The successful retry used a
  one-contract minimum; its actual opening sizes were 24 bid and 23.66 ask
  contracts. Follow-up bid size was six. This is not a demonstrated thick-market
  benchmark.
- Prices were kept hidden until sealing, but this used the existing assistant
  context and separate stores, not a fresh context or enforced filesystem isolation.
  The initial estimate already incorporated screening research. Costs are unmetered.

Next case: declare the residual estimator and treatment of provider differences
before reading the historical sample, and seek observations from the exact
settlement source. Test that process on a fresh hidden target; do not tune this
case toward the revealed prices.

## Reproduce and inspect

From the repository root:

```bash
.venv/bin/python examples/market_workbench/nyc_20260916/analyze.py
.venv/bin/python -m vorhersage \
  --project examples/market_workbench/nyc_20260916/research \
  workbench show workbench_306959beccd8453c97fb
.venv/bin/python -m vorhersage \
  --project examples/market_workbench/nyc_20260916/research doctor
```

[analyze.py](analyze.py) recomputes the arithmetic from frozen downloads without
network access. [calculation.json](research/inputs/calculation.json) retains every
paired observation, exclusions, sensitivity scenarios and raw-file hashes.
Database integrity and all 12 stored artifacts passed `doctor` after reflection.
The JSON and HTML exports remain readable without the local SQLite projects.

## Publish the report

GitHub Pages serves `docs/` from `main`. After regenerating the full exports,
refresh the published copies from the repository root and commit them:

```bash
cp examples/market_workbench/nyc_20260916/full-report.html docs/examples/nyc-2026-09-16/index.html
cp examples/market_workbench/nyc_20260916/full-report.pdf docs/examples/nyc-2026-09-16/full-report.pdf
cp examples/market_workbench/nyc_20260916/full-report.tex docs/examples/nyc-2026-09-16/full-report.tex
```
