# Expanded blinded market comparison

Completed September 18, 2026 (New York; September 19 UTC): **15 contracts,
three models, two evidence conditions, 90 calls, $3.64371 reported inference cost**.
This extends the [original model comparison](../kalshi_models_20260918/README.md)
with new contracts and newly frozen evidence. No calibration function was fitted.

[Academic report](report.pdf) · [Faceted slope graphs](figures/performance.pdf) ·
[Primary results](run/comparison.json) · [Original candidate inventory](candidates.json)

## Results

On the **13 contracts with accepted research forecasts from every model**:

| Model | Mean absolute distance from opening midpoint (pp) | RMSE (pp) |
| --- | ---: | ---: |
| Claude Fable 5.1 | 8.92 | 11.28 |
| GPT-6 Astra | 11.08 | 13.84 |
| Gemini 3.1 Pro | 13.08 | 15.64 |
| Equal-weight average of the three research forecasts | 10.87 | 12.68 |
| Constant 50% | 19.38 | 22.41 |

For the **nine contracts with all six accepted forecasts**, research improves
mean absolute distance for every model:

| Model | Question only (pp) | Research (pp) | Reduction (pp) | Relative reduction |
| --- | ---: | ---: | ---: | ---: |
| GPT-6 Astra | 14.56 | 8.00 | 6.56 | 45.0% |
| Claude Fable 5.1 | 17.33 | 9.56 | 7.78 | 44.9% |
| Gemini 3.1 Pro | 15.33 | 9.44 | 5.89 | 38.4% |

These are different matched cohorts; do not subtract across tables. Excluding
NFL games from the research cohort leaves eight contracts and changes the ranking:
Astra 8.44 pp, Gemini 9.81 pp, Claude 10.44 pp. Related macroeconomic releases
and games are not independent observations. There is one draw per cell.

## Selection and blinding

The selection protocol froze the original 20 candidates, their order, and a
no-replacement rule before quote collection. Seventeen passed a maximum 10 pp
spread and minimum one contract on each side. Three had no usable two-sided book:
September SpaceX launches, Sam Altman for the Nobel Peace Prize, and *I Love
Boosters* for Best Picture.

Two further candidates were excluded before inference: annual SpaceX launches
because the current primary-source count was inaccessible, and earthquakes
because the supplied rules did not establish the event window's start. The 15
remaining contracts cover eight macroeconomic releases/decisions, major Atlantic
hurricanes, and six September 20 NFL games. No replacements or inference retries
were made. All 90 calls completed without provider-reported exceptions.

Each model received the same question and the same frozen evidence within each
condition. Fresh calls had no retrieval tools. Kalshi supplied only contract
definitions to forecasting workers; it supplied no research evidence or prices.
Actual user/system prompt receipts and model identities were checked for all 90
responses. Opening prices were stored separately, committed before research,
and revealed only after all three forecast batches and terminal attempts were
sealed. This is verified input separation, not an independently enforced sandbox
around the research coordinator. Unrevealed excluded targets remain private.

The primary benchmark is the sealed opening midpoint. Follow-up quotes moved by
at most 0.5 pp; using those later midpoints does not change the overall model
ranking. Prices provide a timely intermediate benchmark for unresolved events,
without using realized outcomes. Scores measure market agreement; this selected
cohort does not establish a population model ranking or a calibrated correction.
NFL ties pay half, so those prices approximate expected payout rather than exactly
P(win); the non-NFL sensitivity addresses that distinction.

## Output-screening diagnostic

The registered lexical rule accepted 25/30 Astra, 25/30 Claude, and 30/30 Gemini
responses. **Nine exclusions were explicit denials of using market odds**; one
Claude response referred to the Kalshi contract naming convention to infer the
home team. None of the ten reports numerical market odds. A mention alone is
not evidence of price exposure. These are false positives for the intended
price-leakage check, but the original registered exclusions remain in force.

A clearly **post-hoc** [diagnostic](run/output-review-sensitivity.json) uses all 90
original JSON probabilities without editing responses, issuing excluded
forecasts, or running additional calls. On all 15 contracts, question-only →
research MAE is Astra 15.67 → 11.73 pp, Claude 15.20 → 9.47 pp, and Gemini
17.60 → 13.13 pp. The research ensemble scores 11.31 pp. This supports the same
aggregate direction but does not replace the primary analysis. A future protocol
should distinguish explicit denials from claims of using odds before inference.

## Sources and records

Primary-source evidence came from BEA, BLS, the Federal Reserve, Atlanta Fed,
NHC, and NFL.com. GDP packets distinguish historical releases from GDPNow and
quarterly targets from annual projections. NFL packets contain one game's team
records/scoring plus injury and schedule information, not a comprehensive team
strength model. NHC direct page opens returned 403; the hurricane packet explicitly
records search-index captures of primary NHC material and that access limitation.

- `run/protocol.json`, `selection-attempts.json`, `outcome-eligibility.json`:
  selection, exclusions, and planned analysis.
- `run/research/`, `run/packets/`: source receipts and frozen evidence.
- `run/registration.json`, `arms/`, `tasks/`, `transport.json`: model/method/data
  arms and exact prompt commitments.
- `run/{astra,fable,gemini}/`: jobs, submission receipts, raw results, terminal
  attempts, accepted forecasts, and seals. Rejected calls remain in cost totals.
- `run/pre-reveal-audit.json`, `reveals/`, `revealed-targets/`: verified prompt
  receipts and subsequently disclosed target commitments.
- `run/comparison.json`: matched and available-case metrics, non-NFL sensitivity,
  equal-weight averaging, constant-50 control, follow-up quotes, and a passing
  database integrity check (415 artifacts).

Reported inference cost is Astra $0.99960, Claude $2.25114, Gemini $0.39297.
Research/coordinator cost is unknown and excluded from that total. Provider
reasoning settings differ, so these are not comparisons at equal compute.

## Reproduce the checks and report

From the repository root, using an environment with the project and study dependencies:

```sh
.venv/bin/python examples/kalshi_expansion_20260918/batch.py verify
.venv/bin/python examples/kalshi_expansion_20260918/batch.py audit
.venv/bin/python examples/kalshi_expansion_20260918/verify_results.py
.venv/bin/python -m pytest -q tests/test_expansion_market_pilot.py tests/test_fixed_data_model_pilot.py tests/test_blind_market_pilot.py
Rscript examples/kalshi_expansion_20260918/plot_performance.R
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error examples/kalshi_expansion_20260918/report.tex
```

The first three commands verify saved artifacts without new provider calls or
reading the private evaluator. `verify_results.py` independently recalculates the
reported distances and checks target commitments, source/registration timing,
and seal-before-reveal ordering. The targeted test suite passes **30 tests**.
Do not rerun `select`, `prepare`, or `reveal` to regenerate this completed study.
`discover.py`, `catalog/`, and `definitions/` retain the original discovery record.
The expansion reuses the package's existing workbench, experiment arms, packet
imports, immutable forecast artifacts, and the preceding study's transport;
no new core package dependency is introduced.
