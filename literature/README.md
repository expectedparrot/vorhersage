# AI forecasting literature review

This is the initial research collection for Vorhersage, covering literature
identified through September 8, 2026. It focuses on agents making probabilistic
forecasts about real-world events, with selected adjacent work on time series,
weather, and human–AI collaboration.

- [Review](REVIEW.md): the main synthesis, including benchmark comparisons,
  methodological concerns, and proposed experiments for Vorhersage.
- [Annotated bibliography](BIBLIOGRAPHY.md): 39 sources, each with a finding,
  limitation, reading depth, and package implication.
- [Search and extraction notes](SEARCH_LOG.md): scope, search approach, source
  issues, and the next reading priorities.
- [Backtesting opportunities](BACKTESTING.md): reusable datasets, access checks,
  a proposed comparison, and the implementation needed for historical replay.
- [JSON source records](sources.json) and [CSV source records](sources.csv):
  structured versions of the bibliography for agents and spreadsheet use.

The review is a substantial first pass, not an exhaustive systematic review.
Selected methods and result sections were checked for central comparisons;
several sources are included only at abstract level. Reading depth is explicit
in every record. Reported results have not been independently reproduced.

The design implication is to prioritize trustworthy measurement: immutable
forecast history, dated evidence, auditable resolution, and matched comparisons.
Aggregation, explicit belief updating, strategic review, and training are
candidate interventions whose value should be measured in that environment.

Related local notes: [package design](../DESIGN.md) and
[superforecasting capabilities](../SUPERFORECASTING.md).

## Maintaining the collection

Source IDs are stable and match the review's numbered notes. `sources.json` is
the structured master; keep the CSV and annotated bibliography synchronized
when editing records. Retain the version actually read when a preprint changes,
and record a deeper reading before strengthening a claim. The `year` field
describes the listed publication/version; first-submission dates appear in the
venue or locator when they differ. Author lists using “et al.” are intentionally
abbreviated, so these records are not a complete bibliographic metadata export.
