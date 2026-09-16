# Three-question Kalshi paper pilot

Open [the comparison dashboard](comparison.html). Each row links to its complete
forecast, evidence and milestone model. Hypothetical YES/NO selectors show what
each outcome would do to the two Brier scores, without recording a resolution.

## Frozen starting comparison

Baseline captured **September 15, 2026, 9:15:42 p.m. Eastern**. All three model
forecasts were issued and sealed before 9:26 p.m. Eastern, before their workers
saw the baseline. Each worker reports no numerical event-price/probability exposure.

| Contract | Kalshi YES bid–ask | Frozen midpoint | Independent forecast | Difference |
| --- | ---: | ---: | ---: | ---: |
| [Starship Flight 14 before Oct. 1](https://kalshi.com/markets/kxspacexstarship) | 91–93¢ | 92% | **80%** | −12 pp |
| [GTA VI by Nov. 30](https://kalshi.com/markets/kxgta6) | 90–91¢ | 90.5% | **91%** | +0.5 pp |
| [Fed cut before 2027](https://kalshi.com/markets/kxratecut) | 7.8–8.6¢ | 8.2% | **21%** | +12.8 pp |

A later check on **September 16 at 5:51:09 a.m. Eastern** found midpoints of
92.5%, 90.5%, and 8.4%, respectively. That check happened after the forecasts and
an overnight pause; it is not their exact issuance-time market price. The original
baseline remains frozen for scoring. Last trades, sizes, spreads and timestamps
are retained separately in [baseline.json](baseline.json) and the raw snapshots.

All three questions remain unresolved in that later snapshot. **No accuracy winner
has been established.** Midpoints are comparison estimates, not executable prices;
the pilot computes no trading returns and places no orders.

## What differs

- **Starship, 80%:** the worker gives 20% mass to missing the deadline, including
  authorization/readiness delay and retries. The launch-site-local date and
  exactly Flight 14 matter; a subsequent flight failure still counts as a launch.
  [Full model and reasoning](forecasts/starship/outputs/forecast_summary.md).
- **GTA, 91%:** the worker concentrates mass on the announced release and a short
  delay, while modeling the contract's separate announced-date-without-delay
  clause. It is close to the market. [Full reasoning](forecasts/gta/outputs/forecast_summary.md).
- **Fed, 21%:** disinflation, labor deterioration and acute disruption receive
  explicit joint weights and first-cut dates. The elapsed part of the February
  26–December 31 window was checked before forecasting remaining decisions.
  [Full reasoning](forecasts/fed/outputs/forecast_summary.md).

The weights remain subjective. Starship's timing bins also embed direct judgment
about the deadline, limiting what the milestone formalism independently adds.
Disagreement with a market is a research question, not evidence of superior skill.

## Selection, isolation and evidence

This is a purposive pilot, selected before any model estimate: one spaceflight,
one product release, and one monetary-policy contract; all active with two-sided
quotes, identifiable rules and deadlines within 2026. The nearest deadline is about
two weeks away. It is not a representative sample of Kalshi or a claim about all
forecasting domains. Screening is preserved in [screening.json](screening.json).

Each worker received `fork_turns: none`, a separate clean directory, the frozen
question and contract text, and generic package source. Prices, volumes, order
books, earlier forecasts and this conversation were withheld. Each independently
saved an unresolved structure before research, then researched, registered a
timeline model and issued one forecast with the same forecaster identity across
the three questions. No starting probability was provided. General training
knowledge remains, and filesystem exclusions were instructions rather than a
separate operating-system security boundary. Incidental qualitative search
exposure is disclosed in each sealed result.

Each result was sealed before its probability was reported to the coordinator.
The coordinator verified original inputs and sealed outputs, independently
recomputed each scenario calendar and weighted sum, and ran database integrity
checks. Seals cover 51 Starship files, 22 GTA files and 45 Fed files; the databases
contain 16, 18 and 12 immutable artifacts respectively. Passing these checks
establishes arithmetic and provenance, not calibration or truth.

Costs and model calls were unmetered. Numeric zero counters in generic workflow
records are placeholders. No research or price data was backdated.

## Score after resolution

The policy in [evaluation_policy.json](evaluation_policy.json) was saved before
the workers began. Score the same frozen probabilities using binary Brier loss:
`(probability - outcome)^2`. YES is 1; NO is 0. Compare the model minus market
score on each matched question; negative differences favor the model.

From the repository root:

```bash
python3 examples/kalshi_20260915/capture.py --stage resolution
python3 examples/kalshi_20260915/compare.py
```

The first command makes public GET requests and appends a timestamped snapshot.
The second is offline and updates `comparison.json` and `comparison.html` from
the frozen baseline, sealed forecasts and latest saved resolution snapshot. It
does not silently replace the baseline with later prices. There is no background
poller or scheduled trade.

Only final binary exchange settlements enter the matched score. Unresolved,
nonbinary/canceled, materially changed-rule, and settled-before-forecast cases
remain excluded. A text change requires review rather than silent remapping.
If later contract PDFs, source designations or other settlement clarifications
change while the API text stays constant, review the frozen rules manually before
treating the comparison as matched. With three selected questions, scores will
remain descriptive; no significance claim or calibration curve is justified.

## Files and reproduction

- `capture.py`: public API snapshot capture, no credentials or order endpoints.
- `baseline.json`, `raw/`, `contracts/`: prices, raw responses and frozen terms.
- `compare.py`: integrity-checked comparison, future scoring and offline dashboard.
- `collect.py`: coordinator collection and independent calendar verification.
- `forecasts/KEY/outputs/`: sealed forecasts, evidence, research, calculations,
  review and reports. Fed's build script is at `forecasts/fed/build.py`.
- `forecasts/KEY/input_snapshot.zip`: exact starting package source and clean inputs.
- `forecasts/KEY/collection.json`: independent verification results.

The usual `.vorhersage` ignore rule excludes local SQLite files from source
control. Any physical database covered by a worker's seal is preserved unchanged;
a separate `validation_project` logical copy uses DELETE journal mode for portable
read-only checks. Generic copied source directories are ignored because their
exact contents are in the input archives. To preserve a complete portable snapshot
including sealed databases, use the accompanying [pilot archive](pilot_archive.zip).

Reproduction uses the preserved research snapshot and creates new artifact IDs;
it is not fresh research. Consult each build script's flags and keep regenerated
output separate from sealed originals.
