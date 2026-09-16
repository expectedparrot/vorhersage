# Federal Reserve cut: independent paper forecast

**Estimate: 21% YES.** Prospective, information cutoff **2026-09-16T01:20:26+00:00** (September 15, 2026, US Eastern).

Forecast ID: `forecast_53a67eeee1e54ab3b5ea`. No market-event probabilities or prices were used.

## Exact event and eligibility

At least one FOMC announcement reducing its target federal funds range between February 26 and December 31, 2026. A cut after a hike counts; discount-rate adjustments and dissents favoring a cut do not. Deadline is January 1, 2027 at 00:00 Eastern, exclusive.

The January baseline and March 18, April 29, June 17 and July 29 statements all show 3.50–3.75% holds. The July report confirms the range was maintained since year start. No unscheduled qualifying cut was found in supplementary official indexes. The question is eligible; it is not already known. The historical change table is stale and the general release index omits some scheduled statements, so neither absence alone was treated as decisive.

## Scenario partition

Every path belongs to one dominant regime, in priority order: acute disruption, material labor deterioration, material disinflation, then persistence. Within regimes, branches identify the first qualifying cut or no cut in the window. These are subjective joint weights, not independently sampled events.

| Joint scenario | Weight | First cut / outcome |
|---|---:|---|
| persistent_none | 58.0% | never |
| disinflation_sep | 1.0% | 2026-09-16T14:00:00-04:00 |
| disinflation_oct | 4.0% | 2026-10-28T14:00:00-04:00 |
| disinflation_dec | 7.0% | 2026-12-09T14:00:00-05:00 |
| disinflation_none | 13.0% | never |
| labor_oct | 1.0% | 2026-10-28T14:00:00-04:00 |
| labor_dec | 5.0% | 2026-12-09T14:00:00-05:00 |
| labor_none | 6.0% | never |
| shock_cut | 3.0% | 2026-11-15T12:00:00-05:00 |
| shock_none | 2.0% | never |

The emergency branch date is a representative of any first unscheduled cut before expiry. `never` means no cut within this contract, not no cut forever. Scheduled announcement times are modeling assumptions on observed meeting dates.

## Drivers and contrary evidence

The July decision had three dissents favoring a hike. Chairman Warsh emphasized inflation in August. July core PCE remained 3.3% annually, favoring continued restraint. Against that, annual core CPI eased to 2.4%, June/July job gains were weak, and July real consumption was nearly flat. August payroll growth and stable unemployment resist an immediate downturn interpretation. Core CPI and PCE differ in coverage and weights; their rates are not interchangeable.

## Subjective sensitivity

Baseline regime weights are persistence 58%, disinflation 25%, labor deterioration 12%, and acute shock 5%. Within-regime probabilities of a qualifying cut are respectively 0%, 48%, 50%, and 60%; these are judgments, not fitted frequencies.

| Weight stress | Result |
|---|---:|
| baseline | 21.0% |
| more_persistence | 12.5% |
| more_easing_and_shocks | 32.8% |

Halving within-regime easing responses gives 10.5%. Raising those responses to 70%, 75% and 80% for disinflation, labor and shock gives 30.5%. Moving all December-success paths into January gives 9%. These are stress tests, not confidence intervals.

## Review, triggers and limits

Review challenged the estimate both upward and downward and retained the model-derived result. Main triggers: September 16 FOMC announcement; any emergency reduction; new CPI/PCE and employment evidence; material financial disruption. Any qualifying announcement makes this already known and ends prospective forecasting of this window.

This is a small paper pilot, not a calibrated macroeconomic model. Procedural completeness does not establish predictive accuracy. The timeline engine evaluates supplied assumptions; it does not infer them from evidence. No starting probability was supplied. The original unweighted structure, post-research refinement, workflow clone, parameter revision and final weighted version remain preserved.

External costs and model calls are **unmetered**. Numeric zeros in package usage fields are placeholders. Seven web calls, including two search queries, are documented. One incorrect official archive URL failed; a valid official archive was used. The Chair speech incidentally mentioned qualitative inflation-market expectations, but no event probabilities or numeric market prices were seen.

## Sources

- [Official target rate change history](https://www.federalreserve.gov/monetarypolicy/openmarket.htm) — Latest listed change is the December 2025 reduction to 3.50–3.75%; the page has no 2026 change and is marked updated December 12, 2025.
- [FOMC meeting calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) — 2026 scheduled decision dates are January 28, March 18, April 29, June 17, July 29, September 16, October 28 and December 9. Links are available through July; September has no statement yet.
- [January 28 FOMC statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm) — January decision maintained the target range at 3.50–3.75%. Two members preferred a quarter-point cut.
- [March 18 FOMC statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318a.htm) — March decision maintained the 3.50–3.75% target range. One member preferred a quarter-point cut.
- [April 29 FOMC statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260429a.htm) — April decision maintained 3.50–3.75%. One dissenter favored a cut; three supported holding but objected to the easing bias.
- [June 17 FOMC statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260617a.htm) — June decision unanimously maintained 3.50–3.75%. The statement described solid activity, stable unemployment and elevated inflation partly due to supply shocks.
- [July 29 FOMC statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm) — July decision maintained 3.50–3.75%. Three dissenters preferred a quarter-point increase. The majority continued to characterize inflation as elevated and activity as solid.
- [August 2026 Employment Situation](https://www.bls.gov/news.release/empsit.nr0.htm) — August payrolls rose 162,000; unemployment held at 4.1%. Prior-year average monthly hiring was 31,000. Revised June and July gains were 31,000 and 21,000. Annual wage growth was 3.1%.
- [August 2026 CPI](https://www.bls.gov/news.release/cpi.nr0.htm) — August headline CPI rose 0.4% monthly and 3.4% annually; core rose 0.3% monthly and 2.4% annually. Annual core eased from 2.5%; energy rose 16.3% annually.
- [July 2026 Personal Income and Outlays](https://www.bea.gov/news/2026/personal-income-and-outlays-july-2026) — July PCE prices rose 0.2% monthly and 3.7% annually. Core rose 0.2% monthly and 3.3% annually. Real consumption rose less than 0.1% monthly.
- [2026 Federal Reserve press-release index](https://www.federalreserve.gov/newsevents/pressreleases/2026-press.htm) — Index shows releases through September 11 and no additional rate-cut announcement after July. August monetary releases concern July minutes and discount-rate minutes.
- [July 2026 Monetary Policy Report summary](https://www.federalreserve.gov/monetarypolicy/2026-07-mpr-summary.htm) — The report says the FOMC maintained 3.50–3.75% since the beginning of the year. It describes broadly stable labor markets and elevated inflation.
- [Chairman Warsh Jackson Hole remarks](https://www.federalreserve.gov/newsevents/speech/warsh20260828a.htm) — Warsh viewed employment as consistent with full employment and said prices should be the predominant policy focus. Better summer inflation readings had not convinced him the underlying trend had improved. He avoided committing to a decision.

## Reproduce

Run `PYTHONPATH=src python3 build.py` from this workspace to verify the saved analysis and dates without reissuing or changing the sealed record. `--issue` refuses to overwrite the existing project. The database is in `project/.vorhersage`; `forecast.html` is the offline export. Source evidence consists of short paraphrases, not full page archives.
