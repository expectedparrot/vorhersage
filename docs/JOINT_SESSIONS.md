# Joint forecasting sessions

Joint sessions record one elicitation producing probabilities for several related
binary questions under explicit conditions. They support incremental submissions,
immutable finalization, external imports, median panels, paired conditional ratios,
and session-scoped coherence checks. They share the existing project database,
questions, evidence packets, and relation records; no migration or dependency is
required. An optional [execution contract](LIVE_SESSIONS.md) adds staged evidence,
worker execution, attempts, research checks, protocol audits, and session studies.

The existing single-question workflow remains available. Joint records are separate
artifact kinds, so **none of their cells enter ordinary `evaluate` or experiment
scoring**, including unconditional cells. The separate `session evaluate` command
now scores eligible unconditional cells under an explicit timing policy, without
treating hypothetical worlds as observations.
No priors, reviews, or other workflow steps are synthesized when importing records.

Run the complete example in a new directory:

```bash
.venv/bin/python examples/joint_sessions/walkthrough.py /tmp/joint-session-example
```

It creates two related fictional questions, three conditions, and four forecasters.
One session is submitted incrementally with a replacement and retry; three are
imported. It saves all inputs, raw records, session histories, coherence reports,
a four-model panel, and a deliberately incomplete panel. The six cells per model
are software fixtures, not AIRO forecasts. The example makes no model calls and
incurs no research charges.

The unconditional median is 0.11, the intervention median is 0.06, and the median
conditional multiplier is approximately 0.70710678. Dividing the two medians
instead would give approximately 0.54545, a different quantity.

**Register conditions and inputs.** Register ordinary question versions and evidence
packets first. Register each condition with `condition add --from FILE`; the result's
`condition_id` is an immutable artifact ID. `condition show ID` and `condition list`
inspect the registered definitions. Names and versions are frozen: changing a
definition requires a new version. A condition has these fields:

```json
{
  "id": "restriction",
  "version": 1,
  "kind": "intervention",
  "description": "Assume an exogenous shipping restriction is imposed."
}
```

Kinds are `unconditional`, `intervention`, and `information`. The description must
state the substantive assumptions; the package does not infer a causal model from
the kind. A session requires exactly one unconditional condition. The others are
alternative worlds for the same question; they are not conjunctions with an event
that the policy will be adopted. All questions receive all registered conditions.

A condition may have a `binding` naming a model-specific numeric quantile:

```json
{
  "variable": "frontier_capability",
  "unit": "index points",
  "target_at": "2027-03-10T00:00:00Z",
  "vintage": "index-2026-09-10",
  "quantile": 0.9,
  "tolerance": 2
}
```

This object is part of the versioned condition definition. The session supplies
`numeric_forecasts`, with the same variable, unit, target timestamp, and vintage,
and `quantiles` such as `[{"level": 0.1, "value": 170}, {"level": 0.9, "value": 188}]`.
It also supplies `bindings: [{"condition_id": "CONDITION_ID", "value": 188}]`.
Levels must be unique and increasing; values must be nondecreasing and finite.
Every binding must exactly equal the referenced quantile. Tolerance describes
the assumed world around that value; it does not permit an incorrect binding.
Numeric forecast identifiers, including the target timestamp string, must match
the condition definition exactly. Unconditional conditions cannot have bindings.

Different models can bind the same condition to different numeric values. The
panel preserves these values beside each model's probability and baseline. A
new index vintage or target date requires a new condition version. This first
default implementation freezes quantiles and bindings at session registration;
collect those values first or include them in an import. Execution contracts can
defer them until a bindings event before the first probability submission.

**Start, submit, and finalize.** Inspect `schema session` for the full strict schema,
or use the example's saved inputs. Required fields include a unique session `id`,
`wave`, `forecaster`, `protocol`, `repetition`, `mode`, `information_as_of`, exact
`questions` references, `condition_ids`, `packet_ids`, `relation_ids`,
`numeric_forecasts`, `bindings`, `provenance`, and `configuration`. Use empty arrays
or an empty configuration object when appropriate. Native provenance is
`{"kind": "native", "source": "Description of the elicitation"}`. Configuration
can record model settings and code revisions; do not store credentials.

```bash
vorhersage --project PROJECT session start --from session.json
vorhersage --project PROJECT session show SESSION_ID
vorhersage --project PROJECT session submit SESSION_ID --from partial.json
vorhersage --project PROJECT session finalize SESSION_ID --from final.json
vorhersage --project PROJECT session list
```

A submission contains `expected_revision`, `idempotency_key`, nonempty `cells`,
`usage`, and `raw_record`. Every cell contains `question_id`, `version`,
`condition_id`, a finite `probability` in [0,1], and `evidence_refs`. References
must use the session's pinned packets and respect its fixed information cutoff.
The session pins the exact question specifications as well as packet, condition,
and relation hashes. The default fixed evidence policy prohibits adding packets.
An execution contract with live evidence records new packet availability and
nondecreasing information cutoffs as immutable events.

The starting revision is zero. Each accepted submission advances it once. A later
submission can replace a cell; the complete earlier record remains accessible.
Duplicate cell keys within one submission are rejected as ambiguous. Identical
idempotent retries return the original receipt even after finalization. Changed
content under an existing key and stale revisions are rejected. Submissions and
receipts are committed atomically.

`usage` contains **incremental** `searches`, `model_calls`, and `cost_usd` for that
submission. Session totals include superseded submissions and exclude duplicate
retries. Record costs once for shared work, not once per cell. `raw_record` is a
JSON object for source responses or tool receipts; wrap original verbatim text in
a string field when exact text formatting matters. It is retained without repair.
Empty raw objects and zero usage are allowed but do not certify research quality.
Without an execution contract this API does not enforce research gates. Runtime
sessions instead record usage on attempts, require zero usage on cell submissions,
and enforce their registered research gates. All usage remains worker-reported.

Finalization takes `expected_revision`, `idempotency_key`, and `rationale`. Every
question × condition cell must exist. It stores the final grid, accumulated usage,
input hashes, and coherence audit. Native finalization uses the local current time;
prospective finalization must precede each deadline and cannot occur after a
question has a recorded resolution. Partial records remain inspectable if a
deadline passes. Finalized sessions cannot be edited; use a new session for another
wave or repetition. A repeated `start` with the same identity and specification
returns its current state; different content under that identity is rejected.

**Import external forecasts.** `session import --from FILE` accepts a `session`
with external provenance, a nonempty `submissions` array, `finalized_at`, and
`rationale`. Each source submission supplies `submitted_at`, `cells`, `usage`, and
`raw_record`. Inspect `schema session_import` for the exact shape. Source timestamps
must follow the information cutoff, be nondecreasing, and precede finalization;
none can be in the future. A prospective source finalization must precede the
question deadlines.

The entire import either succeeds or rolls back, including session registration.
It preserves the complete supplied bundle, all replacements, original submission
and finalization timestamps, and separate local recording timestamps. Imported
times are explicitly `source_reported`; validation does not authenticate the
source's timing or prove that its models lacked hindsight. Identical reimports
are idempotent; conflicting reuse of a source session ID is rejected. The native
submission API cannot modify external sessions.

**Aggregate an explicit panel.**

```json
{
  "session_ids": ["SESSION_A", "SESSION_B", "SESSION_C", "SESSION_D"],
  "expected_forecasters": ["model-a", "model-b", "model-c", "model-d"]
}
```

```bash
vorhersage --project PROJECT session aggregate --from panel.json
vorhersage --project PROJECT session_aggregation show AGGREGATION_ID
vorhersage --project PROJECT session_aggregation list
```

All supplied sessions must be finalized, with one per forecaster, and share wave,
protocol, repetition, mode, question versions, and condition versions. Packet
choices, model-specific numeric bindings, and information cutoffs may differ;
each session's cutoff is reported and `same_information_cutoff` makes variation
visible. Select repeated sessions separately rather than counting one model
several times. Missing expected forecasters yield an incomplete-panel report with
null panel medians and multipliers, while retaining available member values.
Unlisted forecasters, duplicate identities, and mixed session designs are rejected.

For a complete panel, probability summaries use the unweighted median. Ratios
pair each model's condition with the baseline in its **same session**, then take
the median on the log scale and exponentiate. With four positive ratios this is
the geometric midpoint of the two middle ratios. `baseline_condition_id` optionally
selects another registered condition, for example status quo; otherwise the
unconditional condition is used.

A zero denominator, including 0/0, is explicitly undefined and makes that panel
multiplier null. A zero numerator over a positive denominator is a valid zero
ratio; the log-median calculation uses the limiting value at zero. Values outside
representable floating-point ratio ranges are reported as null with an explicit
status. No epsilon clipping or probability imputation is performed. Reports include
both cell and baseline submission IDs, definition/binding metadata, once-per-session
usage, and the hashes of the finalized inputs. They are descriptive summaries,
not estimates of accuracy, statistical independence, or causal effects.

**Check coherence.** Register implications with the existing `relation` command
before starting a session and include their artifact IDs in `relation_ids`.
Their endpoints must be question versions in the session. Run
`session coherence SESSION_ID` to check those relations and their transitive
implications separately within each condition. Open sessions report missing
comparisons. Finalization records violations without rejecting or repairing
probabilities. Later waves, new relations, and other forecasters never replace
the cells in a saved audit.

Only genuine logical implications should be registered. Policy effects or
capability-risk relationships are not automatically monotonic. Rolling windows
that change the event definition require new question versions or identities.
The generic `coherence` command continues to inspect ordinary workflow forecasts;
use `session coherence` for joint records. `doctor` checks all joint artifact hashes
and the pinned input/question manifests.

The [AIRO replication plan](AIRO_REPLICATION.md) describes the motivating analysis.
The [executed AIRO example](../examples/airo/README.md) uses these capabilities to
import the authors' frozen dataset and reproduce its principal panel. The
[EDSL pilot](../examples/airo/EDSL.md) adds a live model loop with an external
web-tool executor and recorded development amendments. The live-session guide
describes reusable research gates, protocol observations, and empirical CRPS.
Automatic panel selection, independent verification of research quality, native
EDSL transport integration, and paper-specific benchmark validation remain future work.
