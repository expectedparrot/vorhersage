# Comparing forecasting methods

Vorhersage supports versioned `MethodSpec` and `ExperimentSpec` records through
the `method` and `experiment` JSON schemas. A method specifies how an agent should
complete the workflow; an experiment freezes a comparison across methods,
questions, and repetitions. Registering and starting an experiment make no model
calls. `experiment run` invokes the explicitly configured workers.

The initial runner uses **shared frozen packets**. It is suitable for testing
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

The standard sequence remains prior → drivers → research → assessment → review → issue.
Timeline methods require `prior_method: "none"` and start with structure → parameter
research → assessment → review → issue. Each trial gets a separate model revision
family, so repeated trials can reuse a starting model without sharing mutable research
state. Workers must support `timeline_structure` and `timeline_research`; method
research domains are replaced by the model's parameters. See
[the timeline guide](TIMELINE_MODELS.md).
Review can revise the computed assessment probability, and can request bounded
additional packet review. This is not yet an arbitrary task-graph or no-review
ablation system. Existing ensemble calculations remain available in ordinary
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
