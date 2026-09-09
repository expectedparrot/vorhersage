# Patriots winning the Super Bowl in 2027: workflow simulation

The [general package regression](package_output/package_report.json) now runs the
researched judgments through Vorhersage 0.1 and its generic Epiq adapter. Reproduce
it with `.venv/bin/python examples/patriots_2027/package_replay.py /tmp/new-patriots-package
--epiq-source ../epiq/epiq/src` from the repository root. It preserves the 6.048%
estimate in retrospective mode; the original examples below remain unchanged.

The [Epiq integration](EPIQ_INTEGRATION.md) now stores the researched observations
and findings in Epiq, freezes their provenance, and replays the second assessment
from that packet. Its 6.048% matches the researched run with unchanged judgments.

This example asks whether New England will win **Super Bowl LXI, concluding the
2026 NFL season**, scheduled for February 14, 2027. The date follows the
[NFL calendar](https://operations.nfl.com/calendar-events/nfl-important-dates).
The exact resolution contract is stored in `case.json`.

The [researched second assessment](RESEARCHED_ASSESSMENT.md) adds last season,
quarterback performance, coaching continuity, roster changes, and schedule.
Its **6.05%** is an explicitly subjective conditional forecast, with a research
coverage gate and sensitivity scenarios. It is not a fitted or blind estimate.
See its [case](researched_case.json), [transcript](researched_output/TRANSCRIPT.md),
and [forecast](researched_output/forecast.json).

The original demonstration estimate below is **4.27%, or approximately 4.3%**, using
market observations inspected on September 9, 2026. It is a provisional,
market-informed baseline, with unknown quote-update times and no independently
estimated team-strength advantage. No forecast was submitted externally.

## What is real and what is simulated

The source observations come from actual pages inspected during this session.
The agent's research decisions, uncertainty assessments, and review responses
are recorded fixtures. The Python harness replays those responses, computes
probabilities, validates submissions, and saves workflow state. It neither calls
a model nor refreshes the web.

Captures are **structured observations transcribed from web results**, with
source URLs and content hashes. Full raw pages are not archived. Observation
times record the end of the research pass; exact market quote times are unknown.
Hashes identify the saved observations, not proof of historical publication.

The actual outcome remains unresolved. Separate hypothetical scoring examples
show both YES and NO, and a synthetic source-change example requests review.
Neither writes a real resolution nor changes the issued probability.

## Follow the run

- [Transcript](output/TRANSCRIPT.md): the ten tasks and recorded agent decisions.
- [Case and recorded responses](case.json): question, source observations, findings,
  drivers, objections, judgments, and monitoring triggers.
- [Saved state](output/state.json): accepted submissions and immutable artifacts.
- [Issued forecast](output/forecast.json): probability, exact input hashes, and triggers.
- [Next action](output/next.json): waiting, with a review time.
- [Hypothetical scores](output/hypothetical_scores.json): separate outcome scenarios.
- [Source-change demonstration](output/trigger_demo.json): dependency lookup.

The run follows this sequence:

```text
define → prior → drivers → market research
                            ↓ discrepancy found
                         reconcile → injury research → update
                                                         ↓
                                   waiting ← issue ← check ← review
```

The reconciliation task is inserted when the market-research response reports
conflicts. Both reconciliation and injury research finish inconclusively about
some questions, and the run still proceeds. Review retains the estimate.

## Where the estimate comes from

The demonstration starts with `1/32 = 3.125%`, explicitly labeled as an equal-team
symmetry assumption. It is not an empirical base rate for a team of New England's
strength. Market observations then replace that initial baseline.

For positive American odds `A`, the raw implied probability is `100 / (A + 100)`.
For each complete board, divide each team's raw implied probability by the sum
over all 32 teams. This proportional margin allocation is a transparent
assumption, not a uniquely correct recovery of fair probabilities.

| Captured board | NE odds | Raw implied | All-team implied sum | Normalized NE |
| --- | ---: | ---: | ---: | ---: |
| [BetUS](https://www.betus.com.pa/sportsbook/nfl/super-bowl/) | +2000 | 4.7619% | 119.9973% | 3.9683% |
| [FanDuel Research](https://www.fanduel.com/research/super-bowl-odds-for-every-team-entering-week-1) | +1700 | 5.5556% | 121.4615% | 4.5739% |

The selected synthesis is the arithmetic mean: **4.2711%**. The two sources draw
on overlapping information. Averaging them does not establish statistical
independence or justify a narrow confidence interval. No additional adjustment
is made after review.

## What the agent catches

**Source conflict:** BetUS's table and narrative disagree on New England's price.
The policy selects complete tables consistently while retaining uncertainty
about which page elements are most recent. FanDuel's table and header also
disagree on the Rams. The harness preserves those observations.

**An unmatched comparison:** [Covers](https://www.covers.com/sport/football/nfl/teams/main/new-england-patriots/odds)
displays +1400. The captured excerpt lacks a complete corresponding board and
verified quote time. It is retained as a discrepancy, excluded from the numerical
pool, and left as a follow-up for synchronized research.

**Evidence already reflected in prices:** The
[official injury report](https://www.patriots.com/news/week-1-injury-report-patriots-at-seahawks)
records opening-game absences. It does not establish return dates or season-level
probability effects. The agent retains it for monitoring, without inventing an
extra injury penalty or claiming the market has overlooked it.

**Missing component estimates:** The driver map records the path through the
playoffs, AFC championship, and Super Bowl. Their conditional probabilities are
left null. It states the probability identity but does not manufacture numbers
to make an independent-looking estimate agree with the market baseline.

## Run it

From the repository root, using Python 3.10 or later:

```bash
python3 examples/patriots_2027/simulate.py replay
python3 -m unittest discover -s examples/patriots_2027 -p 'test_*.py'
```

Replay the separate researched assessment with:

```bash
python3 examples/patriots_2027/simulate.py replay --case examples/patriots_2027/researched_case.json --out examples/patriots_2027/researched_output
```

Replay regenerates the example's `output/` directory contents. The issued time
records the actual replay execution; `information_as_of` stays pinned to the
recorded research. It does not pretend a later replay was issued in the past.

To operate one task at a time, initialize a fresh state path:

```bash
python3 examples/patriots_2027/simulate.py init --state /tmp/patriots-walkthrough.json
python3 examples/patriots_2027/simulate.py next --state /tmp/patriots-walkthrough.json
python3 examples/patriots_2027/simulate.py submit --state /tmp/patriots-walkthrough.json --result examples/patriots_2027/output/responses/00_define.json
python3 examples/patriots_2027/simulate.py next --state /tmp/patriots-walkthrough.json
```

Continue with the corresponding numbered response files, or author a response
using the schema returned by `next`. Recorded responses contain the expected
state revision. Duplicate identical submissions are idempotent; changed content
under the same key, stale state, and out-of-order submissions are rejected.

## What this prototype establishes

The example exercises structured state, deterministic arithmetic, a conditional
follow-up, inconclusive outcomes, an unchanged review, immutable forecast inputs,
dependency lookup, and hypothetical scoring. Tests verify these behaviors.

It is deliberately a single-case harness. Its payload checks implement this
case's required fields and numerical constraints, not a general JSON Schema
validator. Its budget counts accepted replay research tasks, not the searches
actually performed to prepare the fixtures. It supports one local writer;
concurrent submission control, a general task scheduler, automatic monitoring,
live resolution ingestion, and specialist sports models remain future work.
