# Six blinded Kalshi contracts: does outside research help?

Read the [academic report](report.pdf), edit the [LaTeX source](report.tex),
or download the performance figure as [PDF](figures/performance.pdf) or
[PNG](figures/performance.png). The report explains the blinded comparison and
includes an appendix on the package, source packets, and reproducibility. Its
main figure is a ggplot2 slope graph with one facet per forecasting question.
Each facet connects the question-only forecast on the left to the researched
forecast on the right. A labeled horizontal dashed line marks the opening
Kalshi midpoint, showing how research changes the forecast's distance from
the market. All panels share a 0–100% probability scale; aggregate deviations
remain in the text and tables. Each slope is labeled with the reduction in
absolute market deviation (percentage points) and the percentage reduction
relative to the question-only deviation.

**Outside research reduced the average absolute gap from the opening market
midpoint from 33.17 to 8.58 percentage points.** Five forecasts moved closer;
one was unchanged. All 12 model responses passed strict validation and were
issued before any target price was revealed. None were repaired or rerun.

This tests market agreement on six selected unresolved contracts. It does not
establish outcome accuracy, calibration, or superiority of an elaborate workflow.

| Contract (YES event) | Opening bid–ask | Midpoint | Question only | Outside research | Absolute gap after research |
| --- | ---: | ---: | ---: | ---: | ---: |
| LAX maximum 74–75°F, September 18 | 3–4% | 3.5% | 12% | 5% | 1.5 pp |
| September US unemployment above 4.4% | 1–2% | 1.5% | 50% | 3% | 1.5 pp |
| Fed maintains rates, October 28 | 48–49% | 48.5% | 55% | 55% | 6.5 pp |
| Neutron launches before 2027 | 4–8% | 6% | 65% | 20% | 14 pp |
| *Why Did I Get Married Again?* tops the September 22 US Netflix film chart | 61–64% | 62.5% | 0.5% | 40% | 22.5 pp |
| Milwaukee beats Baltimore, September 20 | 63–64% | 63.5% | 49% | 58% | 5.5 pp |

Opening snapshots were captured **September 18, 2026, 11:06:23–11:06:26 UTC**
(7:06 a.m. EDT), before outside research. All forecasts were sealed at
11:25:10 UTC. Targets were revealed at 11:40:25–11:40:27 UTC, alongside fresh
secondary quotes. All six midpoints were unchanged; Netflix's spread widened
from 3 to 7 cents. No case was removed from the paired comparison.

| Metric on the same six contracts | Question only | Outside research | Constant 50% |
| --- | ---: | ---: | ---: |
| Mean absolute gap | 33.17 pp | 8.58 pp | 27.75 pp |
| Root mean squared gap | 40.83 pp | 11.40 pp | 33.64 pp |
| Mean distance outside opening spread | 32.25 pp | 7.67 pp | 26.83 pp |

These are probability-distance metrics against a quote, **not Brier scores
against outcomes**. The spread is not a confidence interval. In particular,
Neutron's opening best bid had only five contracts of size, so its midpoint
should not be treated as a precise estimate of truth.

## What was held fixed

The [protocol](protocol.json) was saved before inspecting any target probability.
The two first-class arms share one method and model configuration. Only their
data differs: question definitions alone, or those definitions plus a frozen
packet of outside evidence. There is one independent model call per arm per
contract, using Gemini 3.1 Pro Preview with temperature 0.5, topK 40, topP 1,
maxOutputTokens 8192, and thinking_budget 2048. There is no model review stage.

The question-only condition was generated after research collection, in a fresh
context that received none of it. It is an information ablation, not a recorded
chronological prior. Both calls use identical instructions and output contracts.
An external coding agent chose and collected the research; this does not test
fully autonomous search by the forecasting model itself.

Selection was deliberately varied, not random: six contracts across weather,
employment, monetary policy, space technology, entertainment, and sports, with
one contract per event. We excluded previously revealed cases. Candidates and
ordered substitutes were recorded before fetching books. October's 25-basis-point
cut contract and the Yankees game failed quote eligibility; the predefined
substitutes were October's hold contract and the Brewers game. The researcher
saw only eligibility results, not rejected or accepted prices. Selection required
an active unresolved binary contract, an uncrossed non-extreme two-sided book,
at least one contract at each best quote, and a spread no wider than ten cents.

## How market information was withheld

1. Kalshi supplied only allowlisted **contract definitions** to the researcher.
   Those definitions include the event and settlement conditions. They were
   explicitly labeled as definitions, not evidence of likelihood.
2. The package fetched opening order books into a separate evaluator database,
   with hash commitments in the researcher project. No prices or volumes were
   displayed during selection or research.
3. Research used an allowlist of official/primary source domains. URL and redirect
   checks reject outside hosts; raw text is screened before display for market
   names and references to betting or prediction-market odds. Browser discovery
   responses received the same lexical check before being shown. No excluded
   content was detected in the selected sources.
4. Each hosted forecast call received only its question, common instructions,
   and assigned evidence. It had no browsing tools, filesystem access, evaluator
   fields, other forecasts, or coordinator conversation. All 12 prompts were
   audited against this boundary.
5. The reveal function requires an unchanged forecast seal and a recorded
   terminal attempt for every registered trial. Quotes were revealed only after
   that condition was met. The later audit checked opening commitments, issued
   forecast hashes, evidence hashes, and recorded timing.

**No Kalshi material was used as research evidence, and no target market
probabilities were supplied to the model.** Public fundamental quantities—such
as unemployment rates, baseball win records, or official rate projections—are
allowed evidence; they are not market probabilities for the target event.

This is auditable input separation, not proof of independent blinding. The
coordinator could technically read the vault but did not do so before sealing.
Lexical filters are incomplete, and unknown model pretraining exposure cannot
be ruled out. Contract selection and thresholds themselves remain part of the
question definition. No training-contamination certification is claimed.

## Research and failure analysis

Nine source records entered the six packets, from NWS, BLS, the Federal Reserve,
Rocket Lab, Netflix, and MLB. Dates, source URLs, captured text, hashes,
paraphrased facts, and limitations are preserved in [the packets](run/packets).
Several direct site requests failed; browser fallbacks are recorded separately.
No Exa or Firecrawl calls were made because their API keys were not configured.

- **Weather:** the current NWS high forecast was 79°F, outside the 74–75°F bin.
  Research helped, but the model still supplied an unvalidated forecast-error
  distribution implicitly. NWS and the contract's commercial settlement source
  can differ.
- **Employment:** the current BLS reading was 4.1%, making a one-month move to
  at least 4.5% much less likely than the question-only model's unanchored 50%.
  This is a strong demonstration of the value of current facts, not evidence
  that the model's 3% tail estimate is calibrated.
- **Fed:** both arms gave 55%. The researched explanation correctly used the
  latest hike and year-end projections; the baseline gave a different generic
  explanation. Identical probabilities concealed different factual grounding.
- **Neutron:** Q4 delivery to the pad was correctly distinguished from an actual
  launch. Research reduced the estimate from 65% to 20%, but it remained fourteen
  points above the market. The packet lacked a detailed current test/readiness
  record, so the remaining timing estimate is judgmental.
- **Netflix:** the baseline incorrectly identified the target as a 2010 film;
  the researched response also reasoned as if it were an older catalog title.
  Official discovery identified a new September 2026 release, but the packet
  preserved the previous week's #1 ranking without the release date. This is
  both a model entity-identification error and a research-packet omission. It was
  recorded in [pre-reveal diagnostics](run/pre-reveal-diagnostics.json), before
  knowing the 62.5% target. Both original forecasts remain in the scores.
- **Baseball:** official team records and run differentials moved Milwaukee's
  estimate from 49% to 58%. The missing starting pitchers, lineups, and bullpen
  context leave a material gap to the 63.5% midpoint.

The question-only baseline is intentionally weak when fresh facts matter.
Six purposively selected questions and one draw per condition cannot establish
general performance. Monetary policy and employment are related, so even the
six events should not be treated as six fully independent economic observations.

A useful next experiment would compare a **small current-facts packet** against
deeper targeted research on a fresh, unrevealed cohort. Include explicit entity
identity and publication/release dates in both arms, and use repeated forecasts
to separate sampling variation from research effects. These six targets should
not be reused as a fresh blind benchmark after this reveal.

## Cost and validation

- Twelve model calls: **$0.16835** in summed provider-reported costs; the provider
  job summary rounds to $0.1683. No model exceptions, rejected outputs, or retries.
- Fourteen explicit HTTP retrieval attempts: seven succeeded and seven failed.
- Six browser searches and six browser page-read operations across five tool
  calls. Provider-internal requests are not counted as known HTTP operations.
- Browser/research and coordinator dollar costs are **unknown**, not zero.
  The model cost is not a total system cost or an estimate of researcher effort.
- Fourteen focused tests passed for source restrictions, quoted-odds rejection,
  premature/tampered reveal prevention, and metric arithmetic. The live project
  passed SQLite and artifact integrity checks (82 artifacts).
- The full repository suite passed before committing this study: 299 tests.
  Exported protocol, registration, evidence, forecast, and target hashes were
  also rechecked without modifying the saved run.

## Inspect the run

- [Selection and ordered substitutes](run/selection.json), [eligibility attempts](run/selection-attempts.json)
- [Immutable experiment registration](run/registration.json), [shared method](run/method.json)
- [Question-only arm](run/question_only-arm.json), [outside-research arm](run/outside_research-arm.json)
- [Exact prompts and tasks](run/tasks), [serialized jobs](run/jobs.json), [provider completion](run/provider-status.json)
- [All attempts](run/attempts.json), [raw model responses](run/raw-records.json)
- [Forecast seal](run/sealed-forecasts.json), [seal commitment](run/seal-commitment.json)
- [Comparison and secondary quotes](run/comparison.json), [revealed original targets](run/revealed-targets)
- [Research ledger](run/research-ledger.json), [audit](run/audit.json)

`study.py` handles price-free discovery, selection, filtered retrieval, arm
registration, result import, sealing, reveal, and audit. `build_evidence.py`
documents the exact source-to-packet extraction. The local databases and quarantined
failed bodies are ignored by git; revealed target receipts and exported study
artifacts permit inspection without opening that vault. The audit command uses
the local databases as well as exported files.

This directory preserves one dated study. Do not overwrite its registrations or
rerun live forecasts against now-known prices. For a new experiment, use a new
directory, update the contract roster and protocol, and preserve the same
sequence: register → seal targets → research → register arms → forecast → seal
all attempts → reveal → compare.

## Rebuild the report

From this directory, with Python, R (ggplot2 >= 3.5.0 and jsonlite), and LaTeX installed:

```sh
python plot_performance.py
latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex
```

The plotting script independently recomputes and checks the summary metrics
against `run/comparison.json`, generates the LaTeX table rows, and invokes
[`plot_performance.R`](plot_performance.R) to render the vector figure and PNG.
The R script can also be run directly to rebuild only the figure; it independently
checks the metrics before plotting. Rebuilding uses saved artifacts and makes no network or model
calls. These optional report dependencies are separate from the package core.
