**Forecast: 64% YES.** [Will the Lincoln Memorial Reflecting Pool be fully repaired before September 2026?](https://www.metaculus.com/questions/44241/)

Information cutoff: **2026-07-07T17:00:00Z**. Retrospective forecast issued on **2026-09-20**, before checking the outcome.

The frozen working definition requires completed repairs, a refilled pool, and normal operation before **2026-09-01T00:00:00Z**, established by an official completion/opening statement or corroborated reporting. The Metaculus API did not supply the original resolution criteria, and a historical Snapshot fetch of the question returned no cached content. This is therefore a title-based pilot: check the original criteria and timezone before treating it as an exact contract score.

The strongest reason to expect completion was a repair process that appeared able to proceed without a new bidding round. AP reported that officials intended to retain the contractor and partly drain the pool shortly. The coating supplier described repairs taking weeks and said waterproofing remained intact. Together, those statements make completion within the remaining summer plausible. The supplier's account is an interested-party assessment, not an independent engineering diagnosis. [AP reporting](https://www.pbs.org/newshour/politics/trumps-administration-wont-seek-new-bids-to-repair-the-reflecting-pool), [supplier interview](https://www.eenews.net/articles/reflecting-pool-repairs-will-take-weeks-contractor-says/).

The main counterargument is that the new coating had already peeled after the initial restoration, while no firm repair date had been announced. This leaves substantial uncertainty about preparation, curing, and repeat failure. Litigation adds an interruption risk: plaintiffs reserved the right to seek further injunctive relief, but the retrieved filing does **not** establish that a court halted work. [AP reporting](https://www.pbs.org/newshour/politics/trumps-administration-wont-seek-new-bids-to-repair-the-reflecting-pool), [USA TODAY reporting](https://www.usatoday.com/story/news/politics/2026/07/06/lincoln-memorial-reflecting-pool-repairs-same-company/90818662007/), [plaintiffs' filing](https://storage.courtlistener.com/recap/gov.uscourts.dcd.292242/gov.uscourts.dcd.292242.21.0_1.pdf).

I supplied the following judgments to Vorhersage, which calculated their weighted average:

| Scenario | Scenario weight | P(YES given scenario) | Contribution to YES |
|---|---:|---:|---:|
| Local patching, cleaning, and recommissioning | 50% | 90% | 45% |
| Substantial coating rework or repeated repair | 35% | 50% | 17.5% |
| Material legal, procurement, or administrative interruption | 15% | 10% | 1.5% |

An external interruption takes precedence when classifying scenarios; otherwise the necessary physical repair scope determines the branch. Retaining the contractor and the supplier's account support the local-repair branch. The observed defects and absent schedule justify considerable weight on rework. The interruption branch represents a smaller, assumed risk. All weights and conditional probabilities are judgments, not measured frequencies.

Research did not recover a defensible cohort of comparable coating repairs with verified completion dates. An older [NPS repair notice](https://www.nps.gov/nama/learn/news/reflectingpool.htm) describes planned pipe repairs and cleaning; an [Interior Department notice](https://www.doi.gov/news/pressreleases/AMERICAS-GREAT-OUTDOORS-Salazar-Announces-Successful-Renovation-of-Lincoln-Memorial-Reflecting-Pool) concerns structural reconstruction. Neither provides a suitable empirical success rate. Vorhersage records an explicit reference-class exception.

The result is sensitive to repair scope: varying only completion probability in the rework branch from **25%** to **80%** moves the overall forecast from **55.25%** to **74.5%**. These are assumption tests, not confidence intervals. Verified repair commencement, an independent scope assessment, or an operative court order would be the most useful new evidence in a prospective forecast.

The pilot used **5 searches**, all through Exa Snapshot with the fixed cutoff and Metaculus excluded from search results. The separate failed definition fetch had no live fallback. Saved responses, evidence passages, assumptions, challenges, and the issued forecast are in this folder. No outcome was retrieved or scored. Snapshot limits retrieved content; current search ranking, model knowledge, and this existing conversation remain possible leakage routes. Interactive model usage and cost were not measured. Workflow validation and report checks establish internal consistency, not accuracy or absence of leakage.

The probability is frozen in [forecast.json](forecast.json); the audit trail is in [report-context.json](report-context.json), [submissions](submissions), and [retrievals](retrievals).
