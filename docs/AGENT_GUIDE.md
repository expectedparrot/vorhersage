# Operating Vorhersage 0.2

For research capture, provenance audits, optional scenario mixtures, reference-case
queries, related-question checks, and executable monitoring, see
[Research and monitoring](RESEARCH_AND_MONITORING.md). Existing 0.1 projects remain
readable; the original commands below continue to work.

Vorhersage is a deterministic Python CLI for binary-event forecasting. The
driving agent searches, interprets evidence and supplies probability judgments.
The package stores state, validates tasks, performs declared calculations,
preserves forecasts, tracks review work, and evaluates resolved predictions.

## Start and resume

From this checkout, the installed command is `.venv/bin/vorhersage`. The examples
below use `vorhersage`, assuming it is on your PATH. Global `--project` goes before
the command and selects a directory containing `.vorhersage/state.sqlite`.

```bash
vorhersage version
vorhersage guide
vorhersage init /tmp/my-forecast-study --name "My forecast study"
vorhersage --project /tmp/my-forecast-study schema question
vorhersage --project /tmp/my-forecast-study question add --from question.json
vorhersage --project /tmp/my-forecast-study schema run
vorhersage --project /tmp/my-forecast-study run start --from run.json
```

Author the JSON files using the returned schemas. `--from -` accepts stdin. Run
creation returns `data.run_id` and an exact, read-only next action. Continue:

```bash
vorhersage --project /tmp/my-forecast-study next --run RUN_ID
vorhersage --project /tmp/my-forecast-study submit --run RUN_ID --from result.json
```

`next` returns the current task, its payload schema, submission schema, remaining
budget, frozen question/profile, previous analyses and referenced evidence. It
does not change the database. A replacement agent can use `status` or `run list`
to find the run and continue with `next`.

An authored submission has this shape; replace identifiers and values from the
actual `next` response:

```json
{
  "task_id": "task_FROM_NEXT",
  "expected_revision": 0,
  "idempotency_key": "unique_submission_key",
  "payload": {
    "method": "judgment",
    "probability": 0.3,
    "rationale": "An explicitly subjective starting estimate.",
    "limitations": ["No adequate empirical reference class yet."],
    "evidence_refs": []
  },
  "usage": {"searches": 0, "cost_usd": 0, "model_calls": 1}
}
```

Retrying the identical submission returns the accepted result without duplication.
Reusing its key with changed content, or submitting against an old revision,
fails without partial writes. Read `next` again after a state conflict.

Normal responses are one JSON envelope on stdout with `schema_version`, `status`,
`data`, `warnings`, `errors`, and `next_actions`. Errors use a JSON envelope on
stderr and exit nonzero. Explicit `--help` is human-readable. `report --format
markdown` is also an explicit non-JSON output mode.

## Define the event before estimating it

Questions require YES, NO and void rules, an event deadline, a time to check
resolution, a resolution source, domain, event group, and research profile.
`kind` distinguishes real events from simulation fixtures. All timestamps need
a timezone. `resolve_after` must be at or after the event deadline; an earlier
conclusive official outcome can still be recorded.

`question revise --expected-version N --from question.json` appends a version.
Existing runs retain their original version and criteria. New runs use the latest
version. A forecast revision must stay on the same event version; changed wording
requires a new run rather than silently attaching to an old forecast.

The three run modes are explicitly selected:

- `prospective`: real questions, issued before the event deadline and before
  any resolution has been registered for that version.
- `retrospective`: replay or hindsight work, evaluated separately.
- `simulation`: fictional questions and outcomes, evaluated separately.

These labels and local timestamps do not certify the absence of hindsight,
outside information, or model training contamination. Evaluation additionally
excludes forecasts issued at or after the earliest recorded resolution-knowledge
time. Agents must record that time honestly and promptly.

## Research coverage and bounded review

Built-in profiles are `general`, `team_championship`, and `market_baseline`.
`profile list` shows their domains. Add another immutable policy with `profile
add --from profile.json`; a changed policy should get a new ID.

The workflow is:

```text
prior → drivers → required research domains → assessment → review → issue
                                                            │
                              optional research ←────────────┘
                                      └→ assessment → review
```

Every required research domain needs an interpretation and either referenced
evidence (`assessed`) or an explicit reason for uncertainty (`unknown`). Record
source conflicts, including unresolved ones and their treatment. Unknowns can
advance the workflow; missing coverage cannot. A schema validates coverage,
not the substantive quality of the research.

The prior may be a judgment or a reference class. An empirical prior requires
unique case IDs, outcomes, evidence, a selection rule and comparability caveats.
The package computes its frequency. Drivers describe mechanisms and paths to
both YES and NO.

Declare `research_status` when starting a run: `not_started`, `in_progress`,
`completed`, or `unspecified`. The prior task preserves this declaration and its
actual submission time in `prior_record`. Research completed before registration
must not be presented as an original pre-research prior.

Research usage is reported by the agent. `max_searches` limits submitted search
counts; it does not control external browsing. Existing evidence can still be
used when this budget is exhausted. `max_extra_tasks` limits additional research
requested by reviews, reserving a path to finalization. Every review must address
objections that the probability is too high and too low. An unchanged estimate
is legitimate.

## Obtain evidence through Epiq

Epiq owns shared factual research. Use its existing interface to add evidence,
claims and corrections. Vorhersage reads Epiq through its CLI and never writes
Epiq's SQLite tables directly.

```bash
vorhersage --project /tmp/my-forecast-study epiq search \
  --db /path/to/research.sqlite --kind Company --text factory
vorhersage --project /tmp/my-forecast-study schema epiq_selection
vorhersage --project /tmp/my-forecast-study epiq freeze \
  --db /path/to/research.sqlite --from selection.json
```

For a source checkout rather than an installed Epiq CLI, add `--epiq-source
/path/to/epiq/src`. For this workspace, that directory is `../epiq/epiq/src`.

A selection names exact cells:

```json
{
  "information_as_of": "2026-09-09T10:27:04Z",
  "cells": [
    {"kind": "ResearchFinding", "subject": "f_season", "question": "finding_record"}
  ]
}
```

An optional `known_at` controls Epiq's historical projection. It is distinct from
the original research cutoff. Freezing uses a consistent SQLite export, selects
answered cells, and preserves values, claim/evidence IDs, source content and
assertion recording events. Both scalar and multi-valued cells are supported.
Contested, missing and withdrawn selected cells need reconciliation first.

The result supplies references of the form:

```json
{"packet_id": "pkt_FROM_FREEZE", "record_id": "cell_FROM_FREEZE"}
```

Put these in task `evidence_refs`. `packet show ID` returns the portable packet;
`packet import --from packet.json` lets another project use it without Epiq.
Manual packets use `schema packet` and must identify their source content and
times. An optional supplied hash is verified; otherwise the package computes it.

All selected observations and source retrieval times must precede the packet's
information cutoff, which must precede or equal the run cutoff. Prospective
runs default to `cutoff_policy: live`: their cutoff advances to the actual time
of each accepted submission so research gathered during the run is admissible.
Every task records its cutoff, and the issued forecast retains both the initial
and final cutoffs. Specify `cutoff_policy: fixed` for a prospective run with an
enforced fixed information boundary. Retrospective and simulation runs always
use fixed cutoffs. Day-only Epiq
retrieval dates are conservatively treated as available at day's end. An import
today does not establish that Epiq knew the claim on an earlier research date.
Hashes establish content identity, not historical availability or truth.

## Probability calculations

Assessment supports three methods:

| Method | Required judgment and calculation |
| --- | --- |
| `judgment` | A supplied probability with rationale, limitations and evidence |
| `conditional_path` | A nested chain of conditional probabilities, multiplied by the package |
| `ensemble` | Explicit member forecast IDs and optional weights; equal weights by default |

For a conditional path, the first component's `conditional_on` is null. Each
subsequent component names the preceding component, and the final component is
named `target`. Explain why the events are nested. These are conditional inputs,
not independent marginal probabilities. If an optional total probability is
supplied, it must match the computed result.

Ensembles require one latest eligible forecast per forecaster at the run cutoff,
with identical question version and mode. Weights must be nonnegative and sum
to one. Repeated runs do not automatically represent independent information.

A review can retain the estimate, revise it as a new judgment, or request more
research and reassessment. A direct review revision is labeled `review_judgment`
on the issued forecast; it is not presented as the output of unchanged earlier
conditional parameters. Earlier calculations remain in the history.

## Issue, monitor and revise

The issue task records a stopping reason, review time and observable triggers.
It freezes the question, profile, probability, method, coverage, evidence
references, costs, and exact input hashes. Issuance ends that run's task sequence
and puts it in `waiting`; it does not resolve the event.

```bash
vorhersage --project /tmp/my-forecast-study monitor
vorhersage --project /tmp/my-forecast-study epiq check \
  --db /path/to/research.sqlite --packet PACKET_ID
vorhersage --project /tmp/my-forecast-study signal --from signal.json
```

`monitor` and `epiq check` are read-only. The latter compares selected cells with
a fresh consistent snapshot, reporting changed claim IDs, values or cell states.
When something changes, it returns a suggested signal payload. Submit that
payload explicitly to register the review request. A question-level signal can
also report newly relevant evidence outside the old selection.

Start a new run with `previous_forecast_id` to revise. It repeats the research
and review process under a new cutoff, reusing existing evidence where suitable.
The previous forecast remains unchanged. A competing revision that already
issued prevents another run from overwriting that successor. Signals target
existing forecasts, so a completed successor is not perpetually marked due by
the old signal.

`watch run` provides a persistent polling loop; `watch tick` integrates with an
external scheduler. Configured research and agent workers can collect changes,
start/resume a revision and submit validated tasks through issuance. No OS service
is installed and no probability propagation is inferred automatically. See the
worker protocol in the extension guide. A fixed-cutoff run needs a new run when later information
is required; an active prospective live run admits it at the next submission.

## Resolve and compare

```bash
vorhersage schema resolution
vorhersage --project /tmp/my-forecast-study resolve --from resolution.json
vorhersage schema evaluation
vorhersage --project /tmp/my-forecast-study evaluate --from evaluation-policy.json
```

Resolutions require evidence, exact question version, known time, outcome and
reason. Valid outcomes are `yes`, `no`, `void` and `disputed`. The first resolution
uses `previous_resolution_id: null`; corrections must name the latest resolution.
Earlier resolution records and evaluations remain unchanged.

Evaluation requires an explicit question-version cohort, forecaster list,
forecast cutoff, resolution-history cutoff, and mode. It selects one latest
eligible forecast per forecaster/question, excludes predictions issued after
resolution knowledge, and records missing submissions and void/disputed cases.

Reports show available-case Brier means and a separate common matched cohort.
Paired differences use the common cohort. Calibration bins include counts;
related events retain their group IDs. No significance or cluster uncertainty
interval is estimated in this version. Costs cover selected runs and are
agent-reported. Learn calibration or weights only in future held-out experiments.

Use `forecast show`, `evaluation show`, `report --question ID`, and `doctor` to
inspect records and verify integrity. `report --format markdown` provides a
compact human-readable history; the JSON report retains full manifests.

## Storage and limits

For historical benchmark questions, use `benchmark import-halawi`,
`benchmark start`, and `benchmark evaluate`. The [executable replay guide](../examples/backtesting/README.md)
documents bundle separation, cutoff conventions, policy fields, and the first
20-case software control. `schema replay_evaluation` describes its policy;
`replay_evaluation show ID` retrieves a frozen replay score. Replay evaluation
preserves actual issuance timestamps and scores at an explicit simulated cutoff;
it does not relax the ordinary evaluator's pre-resolution eligibility rule.

This first replay path supports fixed-evidence judgment runs. It does not
supply an archived search service or change the ordinary ensemble member
eligibility rules. Training contamination and historical question edits remain
unverified; directory separation alone does not prevent an agent reading labels.

Each project stores SQLite workflow state in `.vorhersage/state.sqlite`. Question
versions, profiles, artifacts, receipts and events are append-only through the
CLI and guarded against SQL updates/deletions. Run state advances transactionally
with revision checks. This protects routine operation, not an adversary who can
rewrite the database file. Schema version 1 has no migration path yet.

Evidence packets embed source content for portability. This first version reads
project artifacts into memory for some portfolio operations, and Epiq freezing
takes a database snapshot. It is intended for small portfolios; large-scale
indexing and incremental exports remain future work. New domains, numeric
distributions, fitted models, learned calibration, background agents and live
benchmark results are outside this release.
