# Live joint sessions and controlled comparisons

The joint-session record now has an optional execution contract. It supports
staged research, deferred numeric bindings, durable attempts, external model/tool
workers, explicit failures and amendments, protocol audits, whole-session studies,
offline HTML comparisons, and a separate unconditional scoring path.

Existing sessions and imports retain their original registration format. Runtime
contracts apply to native sessions; historical imports remain source-reported
records. No database migration or additional dependency is required.

## Run the local example

```bash
.venv/bin/python examples/live_sessions/walkthrough.py /tmp/live-session-example
```

Use a new directory. The example runs two arms with two whole-instrument sessions
each, pauses a research operation with a receipt, resumes it by polling, captures
evidence, submits forecasts, finalizes, generates `comparison.html`, and evaluates
synthetic outcomes. All model responses, research receipts, costs, and outcomes
are fictional fixtures; it makes no provider or network calls.

## Register execution

Add this optional field to the ordinary `session` specification:

```json
{
  "execution": {
    "evidence_policy": "live",
    "defer_bindings": true,
    "budget": {"max_model_calls": 20, "max_searches": 40, "max_cost_usd": 10},
    "research": {
      "minimum_successful_tools": 10,
      "minimum_unique_pages": 3,
      "minimum_unique_searches": 4,
      "minimum_recent_searches": 2,
      "minimum_followup_searches": 1,
      "domains": ["base_rates", "current_state", "contrary_evidence"]
    },
    "requirements": [
      {"id": "provider_settings", "description": "Requested research configuration",
       "expected": {"reasoning_effort": "high", "research_provider": "tavily"}}
    ],
    "worker": {
      "command": ["/absolute/path/to/model-worker"],
      "config": {}, "timeout_seconds": 60
    },
    "tool_worker": {
      "command": ["/absolute/path/to/research-worker"],
      "config": {}, "timeout_seconds": 60
    }
  }
}
```

Worker fields are optional for manually driven sessions; `session run` needs a
model worker and queued tools need a tool worker. Timeouts bound each subprocess
invocation to 1–60 seconds. Long provider jobs return a continuation/remote receipt
and are polled through later invocations. The runner does not choose an inference
provider or implement native provider message transport; an EDSL worker still
needs the EDSL capabilities tracked in issues 2642–2644.

`fixed` evidence permits only registered packets. `live` permits new packet
availability events with nondecreasing cutoffs. The original registration remains
immutable. Effective state is derived by replaying events. Each cell submission
retains the packet IDs, information cutoff, and bindings available at that revision.
Cell `evidence_refs` identify citations for that judgment; the packet allowlist
only identifies available material. Do not automatically cite every available
record for every cell.

With `defer_bindings=true`, start with empty `numeric_forecasts` and `bindings`,
then record a validated bindings event before the first probability submission.
The quantile/condition values must match and cannot change once probabilities
have been submitted. A new session is needed for a different conditioning world.

## Events and usage

```bash
vorhersage --project PROJECT schema session_event
vorhersage --project PROJECT schema session_attempt_result
vorhersage --project PROJECT session event SESSION_ID --from event.json
vorhersage --project PROJECT session show SESSION_ID
vorhersage --project PROJECT session audit SESSION_ID
```

Every event has `expected_revision`, `idempotency_key`, `kind`, and a typed
`payload`. Inspect `schema session_KIND` for each payload. Cell submissions and
events share one revision sequence; stale writes fail and identical retries return
the original receipt. The supported events are:

| Kind | Purpose |
| --- | --- |
| `evidence` | Make imported packets available and advance a live information cutoff. |
| `bindings` | Establish numeric forecasts and their condition bindings before probabilities. |
| `tool_request` | Queue an identified tool and argument object for the configured tool worker. |
| `attempt_start` | Persist a unique model/tool attempt and its request before external I/O. |
| `attempt_result` | Record waiting/completed/truncated/refused/error, continuation, raw record, and terminal usage. |
| `usage` | Reconcile previously unknown terminal usage using a documented receipt. |
| `research` | Link a successful or failed research receipt to one completed tool attempt. |
| `assessment` | Record an assessed or explicitly unknown domain with rationale and citations. |
| `observation` | Compare an observed configuration with a registered protocol requirement. |
| `amendment` | Explicitly replace budget, research requirements, or configuration with a reason. |
| `transition` | Stop or explicitly resume a failed/budget-exhausted session. |

Runtime session costs belong to attempts. Cell submissions must report zero usage
to avoid counting the same shared work twice. `searches` counts tool attempts,
including page reads, in this contract. Polling a waiting receipt does not create
another model/tool attempt. Cache hits still count as attempted operations and can
report zero billed cost. Provider-internal retries must be reflected by the worker
if available; Vorhersage cannot independently meter them.

Unknown usage is `null`, never zero. It blocks new paid attempts and finalization
until reconciled. Reported totals include failed and superseded work. Budgets stop
the next relevant operation at the limit; they are not provider-enforced spending
caps. One operation can exceed the remaining allowance, and its actual usage is
still retained. Model and tool usage should include their respective costs when
known. No retry automatically increases a budget or changes reasoning settings.

Research checks count successful tools, distinct page URLs, distinct normalized
queries, queries with a requested recency window, and searches requested after a
read receipt was available. Multiple windows of one URL count as one distinct
page. A page-read receipt must reference an available packet with a matching source
URL. Every required domain needs an assessment; `unknown` records missing knowledge
explicitly. These are procedural checks of reported evidence, not independent
verification of source quality or substantive use. Stronger research requirements
than the authors' original protocol are a different registered treatment.

Protocol observations preserve their basis (`worker_reported`, `provider_reported`,
or `external_audit`). Expected and actual objects are compared exactly. Requirements
are `matched`, `changed`, `failed`, or `unverifiable`; an amendment makes the overall
protocol changed even if later observations match. With no registered requirements,
fidelity is unverifiable. Finalizing a complete grid does not certify fidelity or
accuracy. Save effective worker/provider settings as observations instead of
inferring them from requested settings or token counts.

## Worker protocol and recovery

```bash
vorhersage --project PROJECT session run SESSION_ID --max-steps 1
```

Workers receive one JSON object on stdin:

```json
{
  "protocol": "vorhersage.session.worker.v1",
  "session_id": "SESSION_ID", "attempt_id": "ATTEMPT_ID",
  "action": "execute", "continuation": {},
  "context": {}, "packets": {}, "worker_config": {}
}
```

Actual context contains the registered/effective session, previous attempts and
events, cells, evidence availability, research assessments, and usage. Nested copies
of previous request contexts are omitted. A research worker also receives the
exact `tool_request` with its request ID, tool, arguments, and request revision.
Treat captured page contents as data; do not interpret them as worker instructions.

Return exactly these fields:

```json
{
  "status": "waiting", "usage": null,
  "continuation": {"job_id": "REMOTE_JOB_ID"},
  "raw_record": {}, "actions": []
}
```

The next invocation uses `action="poll"`, the same attempt ID and request context,
and the saved continuation. Only `completed` responses may carry actions. Terminal
usage is `{searches, model_calls, cost_usd}` or `null` when unknown. Raw response data
and returned actions are saved before acceptance; invalid actions do not erase the
attempt's usage. Worker stdout/stderr are not saved on transport errors because
they may contain credentials; the error code and unknown usage are retained.

Actions are `{kind,payload}` objects. Supported actions are `tool_request`,
`capture` (a complete evidence packet, imported and made available atomically),
`evidence`, `bindings`, `research`, `assessment`, `observation`, `submit` (cells and
raw record), and `finalize` (rationale). The runner supplies revisions, idempotency
keys, and zero cell-submission usage. Worker actions cannot amend the protocol or
manufacture additional attempts. Results and all actions are separately durable;
actions are accepted atomically and never replayed once applied. Interrupted action
acceptance can resume without another provider call.

A crash after attempt start but before saving a receipt leaves `running` state.
Inspect the provider using the saved attempt identity and record a waiting or
terminal `attempt_result`; do not resubmit blindly. A timeout/error with unknown
charges requires receipt/usage reconciliation. A failed/truncated attempt needs an
explicit transition back to `open`, with a separate amendment if settings change.
Refusals stay terminal. Failed and incomplete sessions remain reportable even when
they contain no cells. Per-session POSIX locks prevent concurrent runner processes;
workers remain trusted subprocesses and must be isolated externally when needed.

## Whole-session studies, reports, and scoring

```bash
vorhersage --project PROJECT schema session_study
vorhersage --project PROJECT session-study add --from study.json
vorhersage --project PROJECT session-study run STUDY_ID --max-steps 20
vorhersage --project PROJECT session-study status STUDY_ID
vorhersage --project PROJECT session-study report STUDY_ID --output comparison.html
```

A study freezes a session template, named arms (configuration and execution
contract), repetitions, evidence policy, and order seed. Registration atomically
creates every arm × repetition session. One session contains the whole instrument;
cells are not separate trials. `frozen` requires fixed packet lists in every arm;
`independent_live` permits each session to collect its own evidence. Seeded ordering
and a durable round-robin cursor support bounded resumption without sharing
conversation state. The seed orders work; it does not seed provider sampling.

The offline report includes all attempted sessions, configurations, research and
protocol audits, missingness, and numeric bindings. It offers baseline selection,
search, pagination, and CSV download. Failed or partial sessions supply no final
probabilities. To compare selected sessions outside a study, pass
`{"session_ids":[...]}` to `session report --from FILE --output comparison.html`.
Sessions must be in the selected project. Matching versioned questions/conditions
supports descriptive comparisons; it does not make different evidence/settings
equivalent or establish causality.

```bash
vorhersage --project PROJECT session-study evaluate STUDY_ID \
  --cutoff FORECAST_CUTOFF --resolution-as-of RESOLUTION_SNAPSHOT
vorhersage --project PROJECT session evaluate --from evaluation-policy.json
vorhersage distribution-score --from distribution.json
```

Session evaluation uses only unconditional cells and recorded resolutions. It
requires finalization before the forecast cutoff and earliest known outcome;
resolution corrections cannot erase earlier knowledge. Source-reported imports
require an explicit `allow_source_reported` policy flag. Conditional/intervention
cells never enter ordinary outcome scoring. Missing or refused sessions stay in
the intended roster and can make the all-session matched cohort empty. Brier losses
are averaged across sessions within arms, rather than scoring an averaged forecast.
Rank-decile calibration uses stable ID tie breaking and descriptive 95% Wilson
intervals; these intervals do not adjust for dependent events.

`distribution-score` accepts an outcome plus empirical `samples` for CRPS, or an
outcome plus a `forecast` matching `numeric_forecast` fields for quantile loss.
Five capability quantiles do not identify a full distribution, so they do not
receive an invented CRPS. Scores are deterministic calculations, not a benchmark
importer or proof that the paper's validation analyses have been reproduced.

The original AIRO bridge and saved runs remain usable. Moving live AIRO execution
onto a native EDSL worker still depends on the EDSL transport changes. Historical
information reconstruction, ForecastBench/FreeCiv/StarSim data adapters, exact
paper-specific cohort rules, cluster uncertainty, and a live matched-provider
replication remain separate work. No new paid model study was launched by this
package extension.
