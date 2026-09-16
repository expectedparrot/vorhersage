# Waymo in Boston before 2029

**Forecast: about 55%** that paid, publicly accessible driverless Waymo service
launches within Boston before January 1, 2029. The ledger computes **55.56%**;
the extra digits reflect arithmetic, not forecasting precision.

Research snapshot: **September 15, 2026, 23:04:02 UTC**. This is a prospective,
unresolved forecast by one assistant.

**[Open the interactive odds ledger](forecast.html)** ·
[Frozen forecast and criteria](report.json) · [Evidence](evidence.json)

## What counts

Before midnight starting January 1, 2029, **America/New_York**, Waymo must have
actually launched passenger trips on public roads, charging fares, with no
in-vehicle safety driver, and with ordinary members of the public able to book
without an invitation or launch waitlist. Some trips must have both endpoints
within **Boston municipal boundaries**. A limited neighborhood service, restricted
hours, or booking through a partner such as Uber counts. Full city coverage,
Logan Airport access, and operation in every snowstorm are unnecessary.

Mapping, testing with a driver, free-only trials, invitation-only access, a launch
announcement without operations, and service only in surrounding municipalities
do not count. A qualifying launch still counts if subsequently suspended. The
exact contract is saved in [question.json](question.json).

## Why slightly more likely than not

**The delivery case is credible.** Waymo has explicitly named Boston as a future
market and returned to prepare for it. Its announcement also identifies local
roads and winter adaptation as work to do. That establishes intent, not a launch
date or completed Boston validation. [Waymo's Boston announcement](https://waymo.com/blog/shorts/back-to-boston/)

Waymo has demonstrated that it can extend service to multiple cities and has
capital to continue. Initial riders in Denver, San Diego and Tampa began in
September, while its February financing announcement reported $16 billion raised.
These are related company signals, counted together rather than independently.
[September rollout](https://waymo.com/blog/2026/09/ride-in-denver-san-diego-tampa/) ·
[Financing](https://waymo.com/blog/2026/02/waymo-raises-usd16-billion-investment-round/)

**Permission and timing are the largest obstacles.** The retrieved histories show
H.3634 going to a study order on April 6, 2026, and S.2379 on July 31. They do not
show enactment. My inference is that the forecast needs to allow substantial
probability of another prolonged policy delay. This is not proof that every
possible authorization route is closed.
[House history](https://malegislature.gov/Bills/194/H3634) ·
[Senate history](https://malegislature.gov/Bills/194/S2379)

Local opposition adds friction, but I found no basis in the checked city docket
to treat its proposal as an enacted ban. The official final ballot-certification
list also contains no autonomous-vehicle restriction. These counterweights are
included in the same permission group.
[Boston docket](https://boston.legistar.com/LegislationDetail.aspx?GUID=311445A0-001C-4CA7-ADB2-714EBFC16391&ID=7504068&Options=&Search=) ·
[Ballot certification](https://www.sec.state.ma.us/divisions/news/right-story.htm)

**A first ride is not necessarily this event.** Waymo's announcements distinguish
selected initial riders from later access for everyone. Dallas and Houston took
several months between those milestones in 2026. These are illustrative timing
examples, not a representative reference-class sample.
[Rider announcement history](https://support.google.com/waymo/announcements/12766613?hl=en)

## The declared calculation

| Assumption | Value | Interpretation |
| --- | ---: | --- |
| Starting probability | 50% | Assumed convention, not an empirical base rate |
| Delivery evidence, joint odds multiplier | ×2.5 | Boston preparation, resources and execution, discounted for remaining validation and public-access lag |
| Permission evidence, joint odds multiplier | ×0.5 | Legislative and local delay risk, net of countervailing evidence |
| Result | **55.56%** | Starting odds 1 × 2.5 × 0.5 = 1.25; probability = 1.25 / 2.25 |

Each group contains six findings. The joint ratio replaces its member ratios;
they are never multiplied separately. Cross-group dependence can remain. These
are subjective net weights, not likelihood ratios estimated from a dataset.
Research preceded registration, and the workflow records that fact.

As an explanatory cross-check, a **65%** chance of a workable permission path with
sufficient lead time, followed by an **85%** chance of qualifying rollout
conditional on that path, gives **55.25%**. Those are also judgments and use the
same information; this is not independent confirmation.

In the widget, changing only the permission ratio across its declared range moves
the estimate from **33% to 71%**. Changing only delivery moves it from **43% to 67%**.
These are assumption sensitivity ranges, not confidence intervals. The 50%
comparison marker means “more likely than not”; it is not a market price.

## What would change the estimate

- Early, workable authorization for driverless paid rides: raise it substantially.
- Another year without a workable permission path: lower it as rollout time shrinks.
- Boston driverless passenger operations, a firm public opening date, or permits:
  update the delivery and permission assumptions together.
- Binding safety-driver requirements, major restrictions, or a Boston withdrawal:
  lower it substantially.

A review date of **February 1, 2027** and event triggers are recorded. No background
monitoring process or automatic probability-decay rule is running.

## Reproduce and inspect

```sh
python examples/waymo_boston_2029/build_forecast.py
vorhersage --project examples/waymo_boston_2029/project doctor
vorhersage --project examples/waymo_boston_2029/project forecast list
```

The build script re-exports an existing issued forecast without issuing a duplicate.
It does **not** refresh research. The live SQLite project is ignored by Git;
[artifacts.json](artifacts.json), [events.json](events.json), and
[submissions.json](submissions.json) preserve portable records.

The evidence contains short manual paraphrases and URLs, not archived source
pages. Exact publication times remain unknown; date labels are retained where
available. One MassDOT observation uses an official search-index excerpt after
direct retrieval failed. The [evidence audit](evidence_audit.json) exposes these
provenance gaps. Sixteen search queries were recorded once; assistant/browsing
costs were unavailable. No separately metered model jobs were run.
