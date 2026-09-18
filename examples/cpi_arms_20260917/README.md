# September CPI: two forecasting approaches

**Six real model calls completed, for $0.335928 in reported per-response cost.**
Both approaches favored a September CPI increase above 0.2%. Three responses
passed strict import; three failed formatting validation. No forecast was
repaired or rerun in the registered experiment.

| Approach | Three returned probabilities, by repetition | Mean* | Strictly accepted | All-call cost |
| --- | --- | ---: | ---: | ---: |
| Direct judgment | 85%, 75%, 88% | 82.67% | 2/3 | $0.128634 |
| Scenario mixture | 81.25%, 87.75%, 83.75% | 84.25% | 1/3 | $0.207294 |

\*The table is a **post-hoc descriptive reading of all six responses**, including
the three rejected ones. Two scenario responses echoed the supplied JSON schema
before their forecast; one direct response added `"type": "object"`. A separately
saved format-only diagnostic extracts the forecast objects without changing any
numeric values or rationales. These extractions are not issued forecasts and do
not replace the failed-import records. Scenario probabilities are calculated as
the sum of weight × conditional probability.

The formally issued probabilities are **75% and 88%** for direct judgment and
**81.25%** for scenarios. Both arms have incomplete repetitions; their means
should not be presented as a completed matched comparison. The event remains
unresolved and no Brier advantage can be established. The provider's job summary
rounds the total to $0.3359.

The all-response descriptive means differ by only **1.58 percentage points**.
Scenario output cost about **61% more** despite equal model settings and one call
per repetition. With only three draws, neither the observed variability nor the
small mean difference establishes a systematic method effect.

## What the pilot exposed

Both approaches emphasized elevated early-September gasoline prices, the gasoline
weight, seasonal adjustment, and assumed persistence in core inflation. The
scenario method made its weights and conditional probabilities inspectable,
but did not reliably construct a complete partition:

- Scenario repetition 1, which passed structural validation, covers high energy
  with normal core, reversing energy with normal core, and weak energy with soft
  core. **High energy with soft core is missing.** Its weights summing to one does
  not fix the omitted combination.
- Scenario repetition 3 puts “or core inflation is unusually weak” into the
  low-gasoline scenario, overlapping the other gasoline-price categories when
  core is weak. The textual partition claim conflicts with that definition.
- The weights and conditional probabilities remain judgments. The supplied
  historical data does not independently establish them.

These are post-run qualitative observations, not preregistered numerical scores
or corrections to the model's probabilities. They illustrate the distinction
between valid arithmetic and a defensible model partition.

Before expanding the cohort, the next pilot should improve the JSON delivery
contract and test an explicit partition challenge on the scenario approach.
Keep this first run, including formatting failures and their costs, as the
unchanged initial result.

This pilot compares a direct probability judgment with an explicit scenario
mixture on the same question: **Will the September 2026 seasonally adjusted
monthly CPI-U release exceed 0.2%?** The pinned question includes the original
release and contract fallback rules; see [question.json](run/question.json).

Both arms use Gemini 3.1 Pro Preview, identical model settings and evidence, three
independent repetitions, and one assessment call per repetition. There is no
model-based review step. Vorhersage calculates scenario-mixture probabilities
and issues accepted forecasts without another model call. Each arm has separate
immutable registration and each repetition has its own workflow state.

The shared packet contains 60 months of headline/gasoline monthly changes,
recent weekly EIA gasoline prices, the lagged published gasoline weight, source
excerpts, and contract terms. Monthly changes are deterministic transformations
of archived indices; missing values remain missing. The source snapshot is from
September 16. The new forecasts are dated when actually issued, not backdated
to the source snapshot. Registration occurred September 17 Eastern time
(September 18 UTC).

Earlier forecasts, fitted model outputs, and market quotes are excluded from the
model prompts. The coordinating assistant has seen the earlier analysis; this
is procedural separation of prompts, not independently verified blinding.

## Records

- [Registration and source hashes](run/registration.json)
- [Shared evidence](run/evidence.json)
- [Direct method](run/direct-method.json) and [arm](run/direct-arm.json)
- [Scenario method](run/scenarios-method.json) and [arm](run/scenarios-arm.json)
- [Provider submission](run/submission.json)
- [Results summary](run/summary.json)
- [All attempts, costs, and strict failures](run/attempts.json)
- [Post-hoc format-only diagnostic](run/format-diagnostic.json)
- [Raw model records](run/raw-records.json)
- [Formal evaluation, currently unresolved](run/evaluation.json)

`run/tasks` preserves the exact task records and six prompts. EDSL jobs preserve
the model and system instruction. Returned raw records, usage, validation
failures, and issued forecasts are retained after import. Model calls use
Expected Parrot; the configured `false` worker is a deliberate guard against
accidentally launching these externally managed trials through `experiment run`.

## Transport

The minimal original inputs are included under `source`, with a
[provenance manifest](source/manifest.json), so a fresh checkout can prepare a
new pilot without the earlier workbench directory. The source-record snapshot
omits the earlier findings and forecasts. This packaging change does not alter
the registered prompts, evidence, or results in `run`.

`pilot.py prepare` creates a fresh registration and jobs file; it refuses to
overwrite an existing registration. `pilot.py export` reconstructs jobs before
submission. Submit `run/jobs.json` with `ep run`, then fetch results to
`run/results.ep` and use:

```bash
.venv/bin/python examples/cpi_arms_20260917/pilot.py accept \
  --results examples/cpi_arms_20260917/run/results.ep
```

Import verifies scenario, model, agent, and registered input identities. Returned
usage is recorded separately even when a forecast fails validation; failed
trials are not automatically repaired or rerun. Raw results may include
transport retries or caching metadata that must be considered when auditing
total calls and cost.

One unresolved question and three draws per arm can expose differences in
reasoning, variation, and cost. They cannot establish comparative predictive
accuracy. Brier comparisons remain unavailable until a qualifying resolution
is recorded. The input data and model assumptions also remain subject to the
limitations in the evidence and individual forecasts.
