# CPI follow-up: output format and partition review

**All 11 model responses passed strict JSON/schema validation; all six forecasts
were issued.** The shorter output contract worked on these draws. Partition
review detected real defects, but the reviewers also raised probabilities
without repairing the underlying mixtures. This is evidence of useful diagnosis,
not evidence that review improved forecasting accuracy.

The follow-up cost **$0.545458** in reported per-response costs: $0.439982 for
the six forecasts and their three reviews, plus $0.105476 for two separate
diagnostic cases. All attempts are included. There were no provider exceptions,
output repairs, or repeated calls to replace rejected responses.

## Forecast results

The question is the same as the [first pilot](../cpi_arms_20260917/README.md):
will the published September 2026 seasonally adjusted monthly CPI-U increase
exceed 0.2%, subject to the pinned contract terms? It remains unresolved.

| Arm | Initial probabilities, repetitions 1–3 | Issued probabilities | Initial mean | Issued mean | Cost |
| --- | --- | --- | ---: | ---: | ---: |
| Direct judgment | 82%, 75%, 85% | 82%, 75%, 85% | 80.67% | 80.67% | $0.123858 |
| Scenario mixture, then partition review | 80.5%, 79.5%, 73.5% | 92%, 88%, 85% | 77.83% | 88.33% | $0.316124 |

Both arms use the exact same frozen evidence packet and Gemini 3.1 Pro Preview
configuration as the first pilot: temperature 0.5, topK 40, topP 1,
maxOutputTokens 8192, and thinking_budget 2048. Each call has an independent
context. Reviewers see their assigned initial assessment; they are not blind
independent forecasters. The scenario arm gets an additional call per repetition.
Source information remains frozen at the earlier snapshot; issuance uses the
actual current time. No new research, earlier forecasts, or market quotes are
supplied to the fresh forecasters.

The review revisions are stored as **review judgments**, with the original
scenario assessments preserved. The 92%, 88%, and 85% estimates are not outputs
of corrected scenario mixtures. The review raised the mean by 10.5 percentage
points; that change has no established relationship to predictive accuracy.

## Output contract

The new prompts list the required response keys and their types in plain text,
instead of embedding a full JSON Schema that a model might echo. They ask for
one object and no fences or additional fields. Import uses the unchanged package
schemas and workflow checks, plus a JSON parser that does not remove fences or
extract objects from commentary.

Six of six fresh assessments passed, versus three of six in the first pilot.
All three new reviews and both diagnostic reviews also passed. This is a small
descriptive before/after comparison: the old and new contracts were not randomly
assigned concurrently. The result does not establish a general reliability rate.

## What partition review found—and missed

The optional existing `review` stage asks for logical conditions, combinations
across dimensions, intermediate cases, exact boundaries, and concrete cases
matching zero or multiple scenario IDs. No new mandatory workflow stage or
semantic truth validator was added.

In the fresh scenario assessments:

- **Repetition 1:** the reviewer identified ambiguous coverage of a moderate
  gasoline decline: it might neither maintain the early gains nor qualify as a
  plunge. This is a useful ambiguity finding, not a numerically specified proof
  of an uncovered interval.
- **Repetition 2:** elevated gasoline with 0.0% core inflation is a clear missing
  combination. The reviewer also claimed that the shared 0.2% core boundary
  creates an overlap. That claim is insufficient: the gasoline conditions must
  also overlap, and the reviewer supplied no simultaneous witness.
- **Repetition 3:** high energy with core at or below 0.1%, and core above 0.3%,
  have no matching scenario under the stated conditions. The reviewer caught
  both omissions.

All three then raised the probabilities. Their justifications often treated
partial-month gasoline observations as if they nearly fixed the monthly energy
contribution. In repetition 3, the reviewer used the approximately 6% change
from August 31 to September 14 as a proxy for the monthly CPI gasoline change.
That point-to-point comparison does not by itself establish the relevant
monthly-average, seasonally adjusted change. Detecting a partition defect does
not justify that substitution or establish the direction of a probability update.

The witness/ID instructions were not consistently followed, although all outputs
satisfied the structural review schema. Schema acceptance must remain separate
from substantive review quality.

## Saved-case diagnostic checks

Two flawed partitions from the first pilot were registered before these review
calls, with a specific success criterion for each. The criteria were withheld
from the reviewers. The second fixture uses the previously documented format-only
extraction of a rejected response; it was never imported as a new forecast.

| Saved case | Expected defect | Returned diagnosis | Assessment |
| --- | --- | --- | --- |
| First pilot, scenario repetition 1 | High energy with soft core is missing | “energy rises and core drops (0 matches, gap)” | Defect noticed; weak explanation, no scenario IDs or numeric witness, and an unsupported “guarantees” claim about energy contribution. |
| First pilot, scenario repetition 3 | Weak core overlaps high/moderate gasoline categories | Gasoline at $4.40 and weak core matches Scenario 1 and Scenario 3 | Correct, concrete overlap witness; scenarios identified by their array positions rather than the requested IDs. |

Both reviewers noticed the targeted logical problem. Neither fully followed the
literal request for scenario IDs, so **this is not a claim of two fully compliant
rubric passes**. The judgments here are a post-run coordinator assessment, not
independent evaluation. Two selected known-flaw cases provide no estimate of
sensitivity or false-positive rate. Both fixture reviewers proposed 88%; those
numbers are diagnostic outputs only and were not issued.

## Records and reproduction

- [Registration, stage contracts, and withheld fixture criteria](run/registration.json)
- [Evidence packet](run/evidence.json) and [question](run/question.json)
- [Summary, costs, and integrity check](run/summary.json)
- [Formal evaluation, still unresolved](run/evaluation.json)
- [Fresh assessment attempts](run/assessment/attempts.json)
- [Fresh review attempts](run/review/attempts.json)
- [Saved-case attempts](run/fixtures/attempts.json)
- [Manual diagnostic assessment](run/diagnostic-assessment.json)

Each stage directory also preserves exact prompts, registered transport hashes,
serialized EDSL jobs, provider receipts, raw results, costs, and accepted
submissions. The local SQLite project is ignored by git; the exported artifacts
and results remain available for inspection. The first pilot's records are
unchanged.

`pilot.py prepare` registers a fresh experiment and exports six assessment jobs.
It refuses to overwrite an existing registration. To run another experiment,
use a new output directory (change `OUT`) and review its registration before
submission. Calls use Expected Parrot's `ep run --jobs ... --background --fresh`;
download completed results with `ep jobs results JOB_ID --output PATH`.

```bash
.venv/bin/python examples/cpi_partition_20260918/pilot.py accept \
  --stage assessment --results examples/cpi_partition_20260918/run/assessment/results.ep
.venv/bin/python examples/cpi_partition_20260918/pilot.py export --stage review
.venv/bin/python examples/cpi_partition_20260918/pilot.py export --stage fixtures
# Submit/download the two new jobs, then accept each with its corresponding stage.
.venv/bin/python examples/cpi_partition_20260918/pilot.py report
```

An existing imported stage cannot be imported again; inspect its saved attempts
instead. Submission is guarded by matching the registered job, scenario, model,
agent, and task hashes. Cost limits are post-call accounting limits, not provider
spending caps. The configured `false` worker prevents accidentally executing
these externally transported trials through `experiment run`.

The live exercise passed the project's integrity check. The package test suite
also passed: **285 tests**, with two existing dependency deprecation warnings.
The next useful comparison would hold the starting assessments fixed and
compare generic review with partition review, including valid partitions to
measure false alarms. Automatic probability revision should not be justified
by defect detection alone.
