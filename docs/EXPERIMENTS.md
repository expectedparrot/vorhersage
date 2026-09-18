# Comparing experimental arms

An **arm** is an immutable, versioned combination of a method, a model
configuration, and a named set of frozen evidence packets for each question.
Use arms to change one factor at a time or register all combinations in a
factorial comparison. Arm identity, not method identity, determines trial and
score grouping. Two arms using the same method remain separate.

See [the arm walkthrough](../examples/experimental_arms/README.md) for a runnable
offline comparison of two procedures, two model configurations, and two data sets.
The [CPI pilot](../examples/cpi_arms_20260917/README.md) records real model calls,
including rejected outputs and their costs. Its
[partition-review follow-up](../examples/cpi_partition_20260918/README.md) uses
optional review stages and separately registered diagnostic cases.

## Register arms

After registering a method and importing evidence packets, create `arm.json`:

```json
{
  "id": "direct-model-a-official-data",
  "version": 1,
  "description": "Direct judgment using model A and official-source evidence.",
  "method_id": "METHOD_ID",
  "model": {
    "provider": "PROVIDER",
    "name": "MODEL_NAME",
    "parameters": {"temperature": 0}
  },
  "data": {
    "label": "official sources",
    "questions": [{"question_id": "QUESTION_ID", "version": 1, "packet_ids": ["PACKET_ID"]}]
  }
}
```

```bash
vorhersage arm add --from arm.json --project PROJECT
vorhersage arm list --project PROJECT
vorhersage arm show ARM_ID --project PROJECT
```

Use returned artifact IDs for `method_id` and `arm_ids`. Arm registration freezes
the configuration, packet/method hashes, and question-version hashes. A changed
configuration requires a new arm version. Empty packet lists are valid for a
question-only control. Every arm must cover exactly the experiment's question
versions, but its packets may differ. Labels describe data; the actual pinned
packet IDs determine data identity. An arm has no live data-fetching step.

Register an experiment with `arm_ids`:

```json
{
  "id": "arms-pilot",
  "version": 1,
  "description": "Compare registered method, model, and data combinations.",
  "questions": [{"question_id": "QUESTION_ID", "version": 1}],
  "arm_ids": ["ARM_A_ID", "ARM_B_ID"],
  "repetitions": 3,
  "mode": "prospective",
  "information_as_of": "2026-09-17T12:00:00Z",
  "forecast_cutoff": "2026-09-18T12:00:00Z",
  "evidence_policy": "frozen_packets",
  "order_seed": "arms-pilot-1"
}
```

Replace illustrative IDs and dates. Omit question-level `packet_ids` when using
arms; each arm supplies them. Supply exactly one of `arm_ids` or legacy
`method_ids`. Existing method-only specifications and `method_scores` output
remain supported. Both forms use `experiment add/start/run/status/evaluate`.
All packets must satisfy the experiment information cutoff, and prospective
deadlines must precede outcome knowledge.

Workers receive the arm's model in `next.context.run.model_spec`, plus
`worker_config.provider`, `worker_config.model` (the name), and
`worker_config.model_parameters`. These override identically named method worker
configuration fields. Workers must honor these values; registration alone does
not attest which model an external executable actually calls. Other worker
configuration fields remain those of the method. Keep model-specific settings in
the arm's `model.parameters`, not in competing method config fields.

Only the arm's allowed packet bodies are supplied as initial evidence for its
trial. Accepted citations are restricted to those packets. Workers remain
trusted executables; use process isolation if preventing outside access matters.
Each repetition has separate workflow state and forecaster identity.

## Minimal baselines and omitted stages

Methods may specify an ordered `stages` subset of
`prior, drivers, research, assessment, review, issue`. `assessment` and `issue`
are always required; issue preserves the forecast record and update policy.
For a direct baseline, set:

```json
{
  "stages": ["assessment", "issue"],
  "prior_method": "none",
  "assessment_method": "judgment",
  "research_domains": []
}
```

These fields belong inside the complete method specification below. A baseline
receives its frozen evidence and goes directly to assessment; it does not execute
placeholder prior/research/review tasks. To test review alone, add `review`
between assessment and issue. Omitted prior requires `prior_method: "none"`;
omitted research requires empty `research_domains`.

Without `stages`, methods keep their existing sequence. A method can also set
`research_contract: "structured_v2"` to run intake, research-to-model mapping,
model challenge, and concern disposition. Structured contracts and timeline
methods retain their required stages and cannot combine with custom `stages`.
This supplies a direct-versus-full comparison without weakening the structured
contract's validation rules. Arbitrary task graphs and dependencies between arms
are not implemented.

## Compare results

`experiment evaluate` returns `arm_scores` and paired `comparisons`. Scores use
only questions complete across every arm and repetition: average Brier losses
within each question, then average equally across questions. Repetitions are not
silently converted into ensemble forecasts. Missing submissions remain visible
in status/exclusions, and matched scores are null if no complete cohort exists.

Each comparison identifies `changed_dimensions` among method, model, and data.
Negative `mean_brier_difference` favors the left arm. Changing multiple factors
compares their combined configuration, not an isolated causal effect. Reports
include event groups but do not yet compute uncertainty intervals.

Forecasts preserve `assessment_probability`, the last assessment before issuance,
alongside final `probability`; arm scores include `matched_assessment_brier`.
All task results preserve earlier assessments and reviews. Since review can
commission additional assessments, this before/after record is descriptive;
use separately randomized arms to estimate review's effect.

Usage summaries include accepted reported usage from unfinished trials. Rejected,
interrupted, or unreported worker calls can still incur unrecorded costs; this
runner does not independently meter providers. Prospective performance and cost
advantages must be measured, not inferred from the registered configuration.

## Existing method-only experiments

Vorhersage supports versioned `MethodSpec` and `ExperimentSpec` records through
the `method` and `experiment` JSON schemas. A method specifies how an agent should
complete the workflow; an experiment freezes a comparison across methods,
questions, and repetitions. Registering and starting an experiment make no model
calls. `experiment run` invokes the explicitly configured workers.

The method-only runner uses **shared frozen packets**. It is suitable for testing
different forecasting procedures against the same supplied information. It does
not yet implement controlled comparisons of live research strategies.

## Try the complete offline example

From an installed checkout, choose a new output directory:

```bash
python examples/method_comparison/walkthrough.py /tmp/vorhersage-method-comparison
```

The example registers direct-judgment and conditional-decomposition methods,
two fictional questions, and two repetitions: eight trials. It stops after three
worker tasks, resumes, records fictional outcomes, and evaluates all trials.
Every CLI input and the resulting summaries are saved in the output directory.
The deterministic scores (0.25 and 0.26) check software behavior; they say nothing
about which procedure produces better real forecasts.

## Register a method

```json
{
  "id": "outside_view",
  "version": 1,
  "description": "Start with empirical analogues, then assess case-specific evidence.",
  "instructions": "Use only supplied packets. Distinguish observations from assumptions. Explain uncertainty.",
  "task_instructions": {
    "prior": "Select comparable cases from the packets. State inclusion rules before counting outcomes.",
    "assessment": "Explain each departure from the empirical prior.",
    "review": "Look for omitted analogues and double-counted evidence. Challenge both directions."
  },
  "prior_method": "reference_class",
  "assessment_method": "judgment",
  "research_domains": ["base_rates", "case_specific_evidence", "contrary_evidence"],
  "worker": {
    "command": ["/absolute/path/to/forecast-worker"],
    "config": {"model": "YOUR_MODEL", "temperature": 0.2},
    "timeout_seconds": 60
  },
  "budget": {
    "max_searches": 0,
    "max_extra_tasks": 1,
    "max_model_calls": 20,
    "max_cost_usd": 2.0
  }
}
```

```bash
vorhersage --project PROJECT method add --from outside-view.json
vorhersage --project PROJECT method list
vorhersage --project PROJECT method show METHOD_ID
```

The returned `method_id` identifies an immutable artifact. Registering identical
content under the same name and version returns the same artifact. Changing that
content requires a new version. Method names alone are not executable identifiers.

Global and task-specific instructions are appended to the workflow task returned
by `next`. Method research domains replace the question's default research profile
for that run, allowing methods to use different domains on the exact same question
version. Prior types are `judgment`, `reference_class`, and `none` (timeline only).
Assessment types include `judgment`, `conditional_path`, `scenario_mixture`,
`odds_ledger`, and `timeline_model`. Submission
validation enforces these types, the packet allowlist, and reported usage limits.
Reference-class methods require suitable cases in the supplied evidence.

Without custom `stages`, the standard sequence is prior → drivers → research → assessment → review → issue.
Timeline methods require `prior_method: "none"` and start with structure → parameter
research → assessment → review → issue. Each trial gets a separate model revision
family, so repeated trials can reuse a starting model without sharing mutable research
state. Workers must support `timeline_structure` and `timeline_research`; method
research domains are replaced by the model's parameters. See
[the timeline guide](TIMELINE_MODELS.md).
Review can revise the computed assessment probability, and can request bounded
additional packet review. Custom standard stages permit no-review ablations;
arbitrary task graphs are not supported. Existing ensemble calculations remain available in ordinary
workflows; experiment arms do not yet declare dependencies on other arms.

## Freeze an experiment

```json
{
  "id": "procedure_comparison",
  "version": 1,
  "description": "Compare direct judgment and an outside-view procedure under equal budgets.",
  "questions": [
    {"question_id": "YOUR_QUESTION", "version": 1, "packet_ids": ["PACKET_ID"]}
  ],
  "method_ids": ["DIRECT_METHOD_ID", "OUTSIDE_VIEW_METHOD_ID"],
  "repetitions": 3,
  "mode": "prospective",
  "information_as_of": "2026-09-11T12:00:00Z",
  "forecast_cutoff": "2026-09-18T12:00:00Z",
  "evidence_policy": "frozen_packets",
  "order_seed": "procedure-comparison-1"
}
```

Replace the illustrative identifiers and timestamps. The information cutoff must
not be in the future; the forecast cutoff must be in the future when registering
and no later than any prospective question's event deadline. Each packet must have
an information cutoff at or before the experiment's. All methods receive the same
registered packets for each question. An empty packet list is allowed for an
explicit question-only experiment; research tasks must then report unknowns.

```bash
vorhersage --project PROJECT experiment add --from experiment.json
vorhersage --project PROJECT experiment show EXPERIMENT_ID
vorhersage --project PROJECT experiment start EXPERIMENT_ID
vorhersage --project PROJECT experiment run EXPERIMENT_ID --max-tasks 20
vorhersage --project PROJECT experiment status EXPERIMENT_ID
```

`start` atomically creates the full question × method × repetition matrix; repeating
it returns the same runs. Question versions, packets, method configurations, and
cutoffs are pinned. Subsequent question revisions do not change the cohort. Each
method/repetition has a distinct forecaster identity shared across its questions.

`run` starts missing trials and makes at most `--max-tasks` worker invocations.
Trials advance in rounds using a seeded order and a saved cursor on resumption,
so repeated failures cannot monopolize small task limits. Accepted submissions
persist immediately. Worker errors and deferrals
allow other trials to continue, and are recorded in an execution artifact visible
through `status`. Repeat `run` to resume. Execution uses a project-level POSIX lock
(macOS/Linux); it installs no service. It is also possible to drive a trial with
ordinary `next` and `submit`; the same method restrictions apply.

## Worker protocol

Each configured executable receives one JSON object on stdin:

```json
{
  "protocol": "vorhersage.experiment.agent.v1",
  "action": "submit",
  "next": {"disposition": "actionable", "task": {}, "context": {}, "budget": {}},
  "worker_config": {"model": "YOUR_MODEL", "temperature": 0.2}
}
```

The actual `next` includes the complete task, payload schema, accumulated task
results, current probability, frozen method, and run configuration. Registered
packets are available in `next.context.artifacts`, keyed by the packet IDs listed
in `next.context.run.packet_ids`. Return exactly:

```json
{
  "payload": {"...": "fields required by the current payload schema"},
  "usage": {"searches": 0, "model_calls": 1, "cost_usd": 0.03}
}
```

Alternatively, return `{"defer": "Why this task cannot proceed yet."}`. The runner
supplies task IDs, revisions, and idempotency keys. It does not choose a provider or
interpret the worker's model configuration. See the
[offline worker](../examples/method_comparison/worker.py) for an executable example.

Use absolute executable/script paths and pin the worker's code and environment
outside Vorhersage. Registration freezes argv, configuration and instructions, but
does not copy executable files, model weights or credentials. Put credentials in
the worker environment, not in the stored JSON configuration. Provider-side seeds,
when supported by your worker, belong in its configuration; `order_seed` controls
trial order only. Workers can use the supplied repetition number for their own
documented sampling policy.

## Evaluate after outcomes arrive

Resolve questions through the ordinary `resolve` command, with outcome evidence.
Then specify an explicit resolution-knowledge snapshot:

```bash
vorhersage --project PROJECT experiment evaluate EXPERIMENT_ID \
  --resolution-as-of 2026-09-21T12:00:00Z
```

The report links to a frozen ordinary evaluation, scoped to the experiment's own
trial forecasts. An unrelated later forecast using the same forecaster identity
cannot replace a trial result. Forecasts must have been issued before the effective
forecast cutoff and before recorded outcome knowledge. Interim reports use the
current time as the effective cutoff; final reports use the registered deadline.
Both timestamps are preserved. Resolution snapshots cannot be in the future.

Method scores use the question cohort complete across **every method and
repetition**. Each method's Brier losses are averaged over repetitions within each
question, then equally over matched questions. Probabilities are not averaged into
an ensemble before scoring. Missing trials can reduce the common cohort; inspect
exclusions and the per-forecaster scores in the underlying evaluation. Method
summaries also include reported costs and model calls from all their trials,
including unfinished ones, as observed when scoring starts.

Retrospective mode does not relax outcome-knowledge eligibility. This runner does
not yet attach benchmark label bundles for replay scoring. Use the existing
`benchmark evaluate` workflow for that purpose, and preserve its contamination
assessment. Simulations and prospective forecasts have their own modes.

## What a comparison does and does not establish

- Choose equal method budgets when testing procedure alone. Unequal budgets are
  permitted and visible in the frozen specifications and method summaries.
- Registered evidence is available from the first task. Initial judgments are
  marked with unspecified prior timing, never certified as blind pre-research
  priors. This runner does not yet offer delayed evidence release.
- Workers are trusted subprocesses that inherit the caller's working directory
  and environment. Packet allowlists constrain submitted evidence references;
  they do not prevent a worker from accessing files, the network, or outside
  knowledge. Freeze evidence and isolate workers externally for stronger controls.
- Search, model-call and monetary limits validate reported usage. Calls that fail,
  time out, or return rejected submissions may already have incurred unrecorded
  charges. A crash after a provider call can cause that call to repeat. Use provider
  limits and task-ID-based caching in workers when those guarantees matter.
- Versioned specifications make inputs auditable. They do not guarantee stochastic
  reproducibility, freedom from hindsight, empirical calibration, or superiority
  of a method. Scores and calibration are descriptive; repeated draws and related
  questions do not become independent observations for significance testing.
