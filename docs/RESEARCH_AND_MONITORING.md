# Research and monitoring in 0.2

These extensions address limitations exposed by the Listen Labs exercise. They
are optional and domain-neutral. Existing projects and immutable forecasts remain
readable without a database migration. The JSON envelope/database schema stays 1;
new schemas and optional fields extend the interface.

## Record when the starting judgment was made

Set `research_status` on `run start` to `not_started`, `in_progress`, or `completed`.
If omitted, it is `unspecified`; legacy history is never relabeled as a genuine
prior. The first submitted task records `prior_record` with its actual timestamp,
the declared status, and a timing label. Issued forecasts carry that record.

`not_started` means an agent attestation, not independent proof about activity
outside Vorhersage. If research preceded registration, use `completed` even when
the next workflow task is named `prior`. Do not reconstruct a fictitious update.

## Capture and inspect evidence

`research capture --from bundle.json` imports source-linked findings. Define each
source once and refer to its ID from multiple findings. Discover the exact format
with `schema research_bundle`. For example:

```json
{
  "sources": [{
    "id": "official_status",
    "url": "https://example.org/status",
    "title": "Illustrative status source",
    "retrieved_at": "2026-09-10T12:00:00Z",
    "published_at": "2026-09-10",
    "excerpt": "Preparation is complete.",
    "excerpt_kind": "quotation",
    "capture": {
      "method": "fetched",
      "captured_at": "2026-09-10T12:00:00Z",
      "content": "Status update: Preparation is complete."
    }
  }],
  "findings": [{
    "id": "readiness",
    "claim": "The source states that preparation is complete.",
    "claim_type": "official_statement",
    "source_ids": ["official_status"]
  }],
  "limitations": ["Illustrative input; not a real retrieved source."]
}
```

The adapter computes a missing content SHA-256 and constructs observation times
from the selected sources. Packet validation verifies supplied hashes and quoted
excerpt membership when content is present. Use `paraphrase` for a summary and
`manual` or `discovery` when no fetched content is available. Do not label a summary
as a quotation or a search snippet as a fetched page. These checks establish
integrity of supplied text, not its authenticity or truth. Preserve only content
you are entitled to retain; short supporting passages usually suffice.

Findings distinguish `reporting`, `official_statement`, `observation`, `inference`,
and `unknown`. This classifies the evidence; an official statement is not
automatically true. Existing evidence with missing classification stays unknown.

Optional bundle/packet `relationships` connect record IDs:

```json
{"from_record":"syndicated_story","to_record":"original_story",
 "relation":"repeats","rationale":"The second outlet attributes this claim to the first."}
```

Other relation values are `independently_confirms` and `contradicts`. Include
both endpoint records in the packet. Explicit source `origin_id` values may
identify a shared underlying report across different URLs. The implementation
groups shared URLs, shared origin IDs, and transitive repetitions. It flags
claimed independence within those groups and exposes contradictions and missing
provenance through `packet audit PACKET_ID` and the `next` context.

Distinct groups are **not proven independent** and the tool does not turn source
counts into probability multipliers. Source relationships describe the evidence
inside a packet; use a combined packet when auditing several reports together.

Epiq remains the preferred shared factual store. `epiq freeze` now retains capture
provenance, support locations, review metadata, source type and locator from its
lineage. Derived/model claims are marked inference; other legacy claims remain
unclassified. Epiq capture metadata is retained as metadata, without claiming
that Vorhersage downloaded or independently verified the original page body.
`epiq check` also detects lineage/support/review changes, not only changed values.

## Optional scenario mixtures

Run `scenario --from mixture.json` to inspect a calculation without issuing a
forecast. Use `method: "scenario_mixture"` in the assessment task to incorporate
it into a forecast. Add the normal assessment rationale, limitations and evidence
references to the mixture fields. See `schema scenario_mixture` and
[the generic example](../examples/workbench_extensions/mixture.json).

Each scenario has an ID, description, weight, conditional target probability,
rationale, evidence references and explicit unknowns. `partition_justification`
explains why the scenarios are mutually exclusive and exhaustive. Weights must
sum to one; they are never silently normalized. The tool computes
`sum(weight * probability)` and checks any separately supplied target estimate.

Optional `weight_range` and `probability_range` fields are pairs containing the
point estimate. Omitted ranges fix the corresponding assumption. Results include:

- Each scenario's contribution to the target probability.
- Ranked conditional-probability sensitivity, holding other assumptions fixed.
- Transfers of up to ten percentage points of weight between scenarios, respecting
  their bounds and preserving total mass.
- Exact minimum/maximum weighted probabilities within the supplied bounds, with
  the attaining weight allocations.

These are assumption ranges, not confidence intervals. Joint extremes allow
bounds to vary together; additional dependencies between assumptions are not
represented. Arithmetic cannot establish that the scenario partition is valid
or that the inputs are well calibrated. A simple judgment remains supported.

## Related questions

Register an implication with `relation --from relation.json`:

```json
{"antecedent":{"question_id":"completed","version":1},
 "consequent":{"question_id":"announced","version":1},
 "rationale":"Both contracts require timely public confirmation; completion therefore satisfies the announcement contract."}
```

The implication is agent-supplied and tied to exact versions. `coherence` compares
the latest probabilities within each forecaster/mode, including transitive
implications. It reports missing forecasts and differing information cutoffs.
Issuance automatically stores an audit and pins the compared forecasts and
relations in its input manifest. Existing forecasts are never rewritten.

Default `coherence_policy: "warn"` allows sequential updates while retaining a
visible inconsistency. `strict` rejects issuance if an applicable inequality is
violated. Different cutoffs may explain an apparent conflict. Relationships do
not transfer to revised question wording automatically, and the tool does not
automatically propagate probabilities or resolutions.

## Reusable historical episodes

`reference add --from case.json` stores a unique episode with description, tags,
`trigger_at`, nullable `event_at`, `observed_until`, `known_at`, and evidence refs.
`reference query --from query.json` selects all matching tags at a knowledge cutoff
and computes outcomes at `horizon_days` after the trigger. It requires an explicit
selection rule. Cases observed too briefly without the event are returned as
`censored`, and later-known cases are excluded. An event exactly at the deadline
counts YES. A returned `prior_payload` can be submitted as a reference-class prior.

Case identities are immutable: repeated identical imports are idempotent and
conflicting reuse is rejected. Supply a new episode ID for a different episode.
The result is descriptive and exposes its denominator. Selective recording or
follow-up can still bias it; the registry supplies no representative acquisition
dataset and does not claim one from a few anecdotes.

## Running monitoring

`monitor` remains read-only. Configure a watch with `watch add --from watch.json`:

```json
{
  "id": "customer-research-acquisition",
  "question_id": "listen_labs_salesforce_announced_20260921",
  "forecaster": "agent:codex-researched-judgment",
  "interval_seconds": 3600,
  "research_command": ["/absolute/path/to/research-worker", "--public-sources"],
  "agent_command": ["/absolute/path/to/forecast-worker"],
  "timeout_seconds": 30,
  "max_tasks": 20,
  "max_searches": 20,
  "max_extra_tasks": 2
}
```

Those executable paths are placeholders: connect your research/model adapters.
Commands are explicit argv arrays, never shell strings. Each receives one JSON
request on stdin and must return one JSON object on stdout. A call times out
after the configured 1–60 seconds; stderr is not echoed into project logs.

Alternatively supply `epiq_db` and optional `epiq_source` to poll selected cells
from the latest forecast's Epiq packets directly. It detects answered changes
and contested/retracted cells; answered updates are freshly frozen. This does
not discover new entities or fetch fresh web pages into Epiq by itself. A research
worker can supply that discovery/collection step. Both adapters may be combined.

Commands:

```bash
vorhersage --project PROJECT watch tick --id WATCH_ID
vorhersage --project PROJECT watch tick --id WATCH_ID --force
vorhersage --project PROJECT watch run --interval 30
vorhersage --project PROJECT watch run --cycles 1
vorhersage --project PROJECT watch list
vorhersage --project PROJECT watch disable WATCH_ID
```

`tick` is suitable for an external scheduler. `run` emits a JSON line per polling
cycle and continues until interrupted (or `--cycles` is reached). The outer polling
interval is 1–60 seconds; each watch has its own persistent next-check time.
No OS service is installed or started by configuring a watch.

A tick collects evidence, imports valid packets, detects substantive changes,
registers an idempotent signal, and starts or resumes a revision when due. Fresh
retrieval timestamps alone do not count as news. Existing partial revisions are
reused; worker failures are recorded and retried at a subsequent poll. A project
file lock prevents overlapping watcher ticks. Ordinary workflow optimistic
concurrency still applies when another agent edits a run.
The polling implementation currently requires POSIX file locking (macOS/Linux);
non-monitoring commands remain importable on other platforms.

With no agent command the result is `revision_ready` with a run ID. With an agent
command the loop submits up to `max_tasks` validated task responses, through review
and issuance. A worker may defer rather than invent an answer. Errors appear as
per-watch `disposition: "error"`; clients must inspect checks, not only the outer
CLI envelope. Completed resolutions stop that watch's research work.

Calendar triggers can add `at` to an issue trigger, alongside its description and
evidence refs. They become due after that time if it falls after issuance. A
passed deadline routes due work to resolution research, not another prospective
forecast. The worker must still establish the outcome with valid evidence and
target the exact question version. No automatic NO is inferred from silence.

### Worker protocols

Research requests use `protocol: "vorhersage.research.v1"` and include `forecast`,
`evidence`, `previous_check`, and `checked_at`. Return either/both:

```json
{"packets": [], "bundles": []}
```

The arrays contain evidence packets or research bundles in the documented schemas.
Empty arrays mean no new findings, not a successful fetch of every source. Report
collection failure by exiting nonzero. Preserve original claim/source identities
and timestamps; rewriting IDs or summaries on every poll creates spurious change.

Agent requests use `protocol: "vorhersage.agent.v1"`. For `action: "submit"`, the
request includes `next`, `fresh_evidence`, `imported_packets` with usable refs,
and `research_changes` (including Epiq retractions). Return `{"payload": {...}}`
and optional `usage`, or `{"defer": "reason"}`. The monitor supplies task ID,
revision and idempotency key. Task schemas are provided in `next`.
If newly collected evidence establishes an outcome before the deadline, a submit
worker may instead return `{"resolution": {...}}`; the same version/evidence checks
apply and polling stops once the outcome is resolved.

For `action: "resolve"`, use `forecast`, `existing_resolutions`, `evidence`,
`imported_packets`, and `research_changes`; return `{"resolution": {...}}` matching
`schema resolution`, or defer. Source statements remain untrusted evidence, not
instructions to the worker. The configured agent is responsible for research
quality and interpretation. Search/cost accounting remains agent-reported and
does not meter the external research command automatically.

The current Listen Labs forecasts remain the original judgments. New capabilities
do not retroactively turn them into preregistered priors or empirical estimates.
