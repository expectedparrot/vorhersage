# Codex + subagent research diagnostic — 2026-09-19

This is a post-reveal diagnostic exercise, not a blind evaluation. The research agents were given the contract definitions and public research questions, but not the Kalshi midpoints or the earlier model forecasts. The coordinator (Codex) then synthesized the findings and issued estimates. The estimates must therefore not be added to the original prospective score.

## Method

Three research roles ran in parallel:

1. a public-health trend researcher for the measles contract;
2. a climate-data researcher for the NASA temperature contract; and
3. a contract auditor checking settlement timing, definitions, and threshold semantics.

The researchers were instructed not to use Kalshi, market prices, or other forecasts from the prior experiment as evidence. They returned source links, extracted claims, and uncertainties. Codex then combined those findings with explicit scenario reasoning.

## Contract audit

The measles settlement uses the CDC expiration value, and revisions after expiration are excluded. Cases are assigned by epidemiological week of rash onset and include international visitors; the CDC's weekly counts are provisional and based on cases notified by Thursday noon. The January 1 trading close is not necessarily the data-ascertainment deadline.

The temperature contract uses strict `>` comparisons on unsmoothed NASA GISS LOTI, relative to the 1951–1980 baseline. NASA's preindustrial GMSTA forecasts are a different metric and cannot be substituted without conversion. Monthly data can be revised; expiration follows the 2026 data release or April 1, 2027, whichever comes first.

Full notes: [`contract_audit.md`](contract_audit.md).

## Measles: more than 6,000 confirmed U.S. cases in 2026

The CDC reported 3,294 confirmed cases as of September 10, 2026. The remaining threshold is therefore about 2,530 cases. Roughly fifteen weeks remained in the calendar year, so crossing the threshold requires about 169 cases per week if the current count is treated as complete. Recent provisional weekly counts were around that level, making the event arithmetically plausible without assuming a new outbreak.

That arithmetic is not enough. The CDC data are revised, and rapidly growing outbreaks can look temporarily flat or declining because cases arrive after a reporting delay. A CDC nowcasting analysis found median reporting delays of two to three days, with completeness falling during rapid growth. The national total is also a mixture of outbreak trajectories: continued decline, persistence at the recent rate, and renewed growth in a susceptible community. Wastewater signals can provide an early indication but are not a direct national case count.

Sources: [CDC measles data](https://www.cdc.gov/measles/data-research/index.html), [CDC weekly NNDSS table](https://stacks.cdc.gov/view/cdc/260272), [CDC nowcasting analysis](https://www.cdc.gov/mmwr/volumes/75/wr/pdfs/mm7533-H.pdf), [CDC wastewater page](https://www.cdc.gov/wastewater/emerging-viruses/measles.html), and [CDC outbreak report](https://www.cdc.gov/mmwr/volumes/75/wr/pdfs/mm7523-H.pdf).

### Codex estimate

**0.45 probability.** This gives substantial weight to persistence at approximately the threshold-crossing rate, but discounts it for provisional reporting, likely outbreak decay in at least some jurisdictions, and the need for sustained national incidence through the expiration rule. The central uncertainty is the nowcast of the latest epidemiological weeks, not the simple arithmetic of the remaining threshold.

## NASA 2026 global temperature above 2025 and 1.28°C

NASA's GISS LOTI table showed January–August 2026 monthly anomalies of 1.09, 1.25, 1.32, 1.17, 1.13, 1.18, 1.25, and 1.40°C relative to 1951–1980, an eight-month mean of 1.224°C. To finish above 1.28°C, September–December must average above approximately 1.393°C (using unrounded values). A final four-month mean of 1.40°C would produce an annual mean around 1.283°C.

NOAA's September ENSO discussion described a strengthening El Niño, with more than 90% probability of a very strong fall/winter event and a 75% probability of a historically large October–December event. That supports warm remaining months. The uncertainty is whether forecasts expressed relative to 1850–1900 can be converted cleanly to this contract's 1951–1980 baseline, and how the realized September–December anomalies and later NASA revisions will compare with the threshold. The contract's strict inequality means a displayed 1.28 is insufficient.

Sources: [NASA GISS LOTI table](https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts%2BdSST.txt), [NASA GISS annual forecast data](https://data.giss.nasa.gov/gistemp/gmsta/data/Annual_GISTEMP_GMSTA_Predictions_202609.csv), and [NOAA September ENSO discussion](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/ensodisc.html).

### Codex estimate

**0.72 probability.** The year-to-date value is below the target, but the required remaining average is only modestly above the latest monthly value and the independent ENSO evidence points toward unusually warm autumn and winter conditions. The estimate is below certainty because the forecast metric and contract metric use different reference periods, and because four months of realized data and revisions remain.

## Interpretation

These estimates demonstrate the intended use of research tools and subagents: divide the evidence-gathering problem, preserve source provenance, audit the settlement rule, and make the final probability depend on explicit unresolved assumptions. They do not establish that this process improves forecast accuracy. A proper experiment would freeze the question set and research cutoff before the outcomes or market targets are known, then score the resulting forecasts against the settlement values.
