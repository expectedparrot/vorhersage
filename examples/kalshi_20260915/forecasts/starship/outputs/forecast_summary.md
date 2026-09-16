# Starship Flight 14: independent paper forecast

**Probability: 80%.** Eligible prospective forecast; event not already known.

Information cutoff: 2026-09-16T01:22:00.806628+00:00. Forecast issued: 2026-09-16T01:24:15.110575Z.

Exactly flight test 14 must lift off with sustained ascent after July 30 issuance and strictly before **October 1, 2026, 00:00 America/Chicago** (05:00 UTC), assuming the verified Starbase, Texas site. A subsequent flight failure counts. Static fires and scrubs do not. Frozen trading close is earlier than the event boundary and was not substituted for it.

## Joint scenarios

| Scenario | Subjective weight | Representative launch, Texas time | Meets deadline |
|---|---:|---|---|
| rapid | 55% | 2026-09-22T07:15:00-05:00 | Yes |
| moderate | 25% | 2026-09-28T07:15:00-05:00 | Yes |
| late | 15% | 2026-10-07T07:15:00-05:00 | No |
| no_launch | 5% | 2026-11-17T19:22:00.806628-06:00 | No |

Weights sum to one. Success weights sum to 0.80; dates computed by `timeline.py` and independently checked with Python calendar arithmetic. Readiness branches run in parallel; launch follows their maximum plus retry delay. In-progress work is modeled as remaining days from cutoff, not total historical duration. Scenario date bins are exclusive and exhaustive, but representative dates and weights are judgments rather than measured frequencies.

## Evidence and drivers

[Official SpaceX mission content](https://content.spacex.com/api/spacex-website/missions/starship-flight-14) says Flight 14 is preparing for September 22, with regulatory approval pending; the [public mission page](https://www.spacex.com/launches/starship-flight-14) serves a JavaScript shell. This establishes that the event remains upcoming. SpaceX describes hardware filtering and software changes following Flight 13 booster relight difficulties.

The [FAA operational advisory](https://www.fly.faa.gov/adv/adv_spt) matches September 22 at 12:15 UTC and September 23 backup at Starbase. Earlier September 13 FAA planning listed September 18: the target has already slipped. Planning is not licensing. The [FAA environmental page](https://www.faa.gov/space/stakeholder_engagement/spacex_starship) shows relevant environmental work complete, but this does not establish final flight authorization.

## Uncertainty and review

All future completion dates and durations are estimates or assumptions. No independent complete hardware inventory, final launch license, local closures, or launch-day weather assessment was obtained. Static-fire reports found in search were not upgraded into primary-verified facts. The model's weights are subjective and partially equivalent to direct deadline judgment because bins straddle the deadline. This limits what the milestone formalism adds.

Alternative declared weights give 60%–90%; this is a stress range, **not a confidence interval**. Adding five days to every post-readiness delay drops success to 55%; adding nine days drops it to 0%. Such shifts test sensitivity of representative dates, not literal revisions to unchanged bins. Full tests are in sensitivity.json.

No market prices or numerical outside event probabilities were observed. Search snippets incidentally exposed community timing opinions and an unverified historical timing aggregate, logged in exposure.json; neither calibrated the weights. Source access failures and contradictory interpretations are retained in source_query_log.json. Costs and model calls are unmetered; package zero counters do not mean zero cost.

Review on September 19 or upon final authorization, hardware changes, schedule slips, scrubs, site change, or qualifying liftoff. No trading was performed. A clean doctor result confirms package integrity, not forecast accuracy.
