# Repeated forecasts on a broader blinded cohort

Completed September 18, 2026 in New York (September 19 UTC): **7 new contracts,
3 models × 2 conditions × 3 repetitions = 126 calls**. All 126 were accepted.
Reported inference cost: **$5.018284**; research/coordinator cost is unknown.

[Report PDF](report.pdf) · [Slope graphs with individual draws](figures/performance.pdf) ·
[Results](run/comparison.json) · [Frozen protocol](run/protocol.json)

## Findings

Primary distance averages each call's absolute distance from the sealed opening
Kalshi midpoint within question, then equally across the seven questions.
Repetitions do not count as additional independent events.

| Model | Question only (pp) | Research (pp) | Reduction |
| --- | ---: | ---: | ---: |
| GPT-6 Astra | 28.54 | 18.11 | 36.5% |
| Claude Fable 5.1 | 25.54 | 18.82 | 26.3% |
| Gemini 3.1 Pro | 40.01 | 22.92 | 42.7% |

Research improves agreement, but **the constant-50% control scores 15.16 pp,
better than all three research methods** on this cohort. Equal-weight averaging
of the three model research means scores 18.98 pp.

Average within-question research SD is Astra **1.31 pp**, Claude **1.16 pp**, and
Gemini **3.28 pp**. Averaging each model's three calls changes its research MAE
to 18.11, 18.82, and 22.63 pp respectively. Repetition reveals stable disagreement
rather than removing it. The largest shared gaps concern U.S. measles cases and
the annual NASA temperature index. These are market-distance results, not scores
against eventual outcomes or proof that either the market or a model is correct.

No fitted calibration or learned ensemble weights were used. This cohort has
seven distinct events but only five declared broader dependence groups: housing
and interest rates, infectious disease, global climate, daily weather, and film.
It extends domain coverage on the same collection date, not across independent
dates. Do not pool the calls as 126 independent examples for fitting a correction.

## Improvements implemented before inference

- Package helper `vorhersage.market_screen.screen_market_mentions`, policy
  `market-mentions-v2`, retains narrow complete denials as audit flags without
  automatically excluding them. Other references require recorded content review
  before any target reveal. Source screening remains strict. Prior studies retain
  their original rules and results.
- Package helper `vorhersage.market_evaluation.score_draws` separately measures
  expected single-call loss, loss of the averaged forecast, sample SD, range,
  RMSE, and outside-spread distance. Missing draws are never imputed.
- The new study requires all three repetitions in both conditions for every model
  in its matched cohort. Distinct administrative replicate IDs and `ep --fresh`
  prevent reuse of the same cached request. The audit found **126 distinct raw
  provider response IDs** and verified all actual model/system/user prompt receipts.
- Screening/review records and forecasts are sealed before prices are revealed.
  Registered hashes pin the exact study, transport, source, screening, and scoring
  implementations used in this run. The complete package suite passes **346 tests**.

There were no lexical market references in this batch's 537 screened rationale
and limitation fields, so no manual content decisions were needed. The new rule's
handling of denials is covered by regression tests; this batch does not by itself
measure an improvement in acceptance attributable to the rule.

## Selection and evidence

Eleven exact contract nominations were frozen before quote collection, with no
replacement after screening. Four failed the registered book checks: TSA travel
(top size), gasoline (empty side), Rocket Lab launches (spread), and Arctic sea
ice (empty side). All seven remaining contracts passed outcome checks:

| Question | Primary research | Declared group |
| --- | --- | --- |
| Sep 24 mortgage rate >7.01% | Freddie Mac weekly survey archive | Housing/interest rates |
| September housing starts >1.300M SAAR | Census August release; mortgage survey | Housing/interest rates |
| 2026 U.S. measles cases >6,000 | CDC current confirmed count and prior annual count | Infectious disease |
| 2026 NASA temperature index >1.28°C and 2025 | NASA monthly and annual LOTI data | Global climate |
| Miami Sep 19 maximum 88–89°F | NWS airport-point forecast | Daily weather |
| Austin Sep 19 maximum 98–99°F | NWS airport-point forecast | Daily weather |
| Dune: Part Three delayed past Dec 18 | Dedicated official film site | Film production |

The measles series' full terms clarify the U.S./CDC definition; that **definition
supplement was supplied to both conditions**, not treated as research evidence.
The current CDC count was 3,471, below the target. NASA's last four monthly and
annual 2026 values were missing. Neither weather target day had begun when the
forecasts were issued. The official film site still advertised December 18.

Miami's current forecast came from a preserved NWS search-index capture. Two
coordinate page opens failed, and another returned an older September 13 page.
That discrepancy is explicit in the packet. NWS forecasts are outside evidence;
weather settlement uses The Weather Company and can differ in rounding and
station/grid handling. Climate packets contain no ENSO forecast; measles packets
contain no weekly growth series. These evidence limitations can matter more than
sampling additional model calls.

Opening prices were held in the separate evaluator throughout research and
inference. Fresh model workers received only definitions, instructions, and the
assigned outside evidence. They had no browsing tools, other model forecasts, or
prior-study results. Quotes were revealed after screening and forecast seals.
The largest follow-up midpoint movement was **1 pp**; the model ranking is unchanged
using later quotes. Coordinator separation is procedural, not an independently
enforced security boundary.

## Artifacts and reproduction

`run/` contains the protocol, selection and outcome checks, immutable evidence
packets, six registered arms, exact tasks/jobs, raw model results, all attempts,
forecast and review seals, and subsequently revealed targets. All 126 calls have
known reported cost: Astra $1.35934, Claude $3.02187, Gemini $0.637074. The database
integrity check passed for **547 artifacts**. Raw job-level totals differ slightly
from summed response costs because of rounding. Provider reasoning settings
match the previous three-model study and are not equal compute budgets.

From the repository root:

```sh
.venv/bin/python examples/kalshi_repeated_20260918/batch.py verify
.venv/bin/python examples/kalshi_repeated_20260918/batch.py audit
.venv/bin/python examples/kalshi_repeated_20260918/audit.py
.venv/bin/python examples/kalshi_repeated_20260918/verify_results.py
.venv/bin/python -m pytest -q
Rscript examples/kalshi_repeated_20260918/plot_performance.R
.venv/bin/python examples/kalshi_repeated_20260918/write_report.py
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error examples/kalshi_repeated_20260918/report.tex
```

Verification and plotting use the saved records; no new provider calls or private
vault access are needed. The implementation audit expects the registered code
version. Do not rerun selection, preparation, or revelation to regenerate a
completed study. Source captures retain failures and indexed-page limitations.
The private evaluator and unneeded build files are ignored by Git.

The next informative test is a **new, preregistered evidence arm**: add a current
weekly incidence series for measles and a relevant scientific outlook for annual
temperature. The present cohort is now exploratory material, not an untouched
validation set. No further calls were made after its targets were revealed.
