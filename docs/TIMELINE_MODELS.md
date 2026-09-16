# Deadline models: structure before probability

A `timeline_model` declares what must finish, what can overlap, and which inputs
remain unknown. Vorhersage computes the resulting schedules and creates research
tasks for the declared parameters. There is no initial probability task.

This supports a concrete disagreement such as “preparation can happen before
authorization” versus “preparation must wait.” The dependency changes the computed
launch date even when both models use identical dates and durations.

## Try the Waymo example

From an installed checkout:

```bash
python examples/waymo_boston_2029/timeline/build.py
```

Open [the standalone comparison](../examples/waymo_boston_2029/timeline/comparison.html).
Select `late` to see preparation in parallel produce November 1, 2028, while
sequential preparation produces March 3, 2029. These are **invented stress-test
inputs**, not newly researched Waymo estimates. Neither model has weights or
a forecast probability. The example uses a separate project and issues no forecast.

The script also exports complete JSON inputs, an unresolved draft, a gap report,
and a run specification. Read [the example notes](../examples/waymo_boston_2029/timeline/README.md).

## What a model contains

| Field | Meaning |
| --- | --- |
| `question` | Exact question ID and version |
| `information_as_of` | Cutoff for the model's observations and evidence |
| `deadline`, `deadline_rule` | Question's event deadline; strict `before` or inclusive `on_or_before` |
| `nodes`, `target` | Acyclic milestone graph and the node satisfying the event definition |
| `parameters` | Named calendar dates or durations in elapsed days |
| `scenarios` | Explicit joint assignments of parameter values, with optional weights |
| `limitations` | Remaining substantive qualifications |

Inspect the full schema and examples:

```bash
vorhersage schema timeline_model
vorhersage schema timeline_structure
vorhersage schema timeline_research
```

### Milestones and scheduling

Each node has a `completion_condition`, `parents`, `state`, dependency `rationale`,
and `evidence_refs`. Every node must contribute to the target.

| Kind | Computation |
| --- | --- |
| `event` | Calendar date from its parameter; no parents |
| `task` | Wait for all prerequisites, then add its duration |
| `all` | Latest completion among its prerequisites |
| `any` | Earliest completion among alternative prerequisites |

A pending task starts no earlier than the information cutoff, its parents, or its
optional `not_before` date. A task marked `in_progress` requires an evidenced
`started_at`; its duration parameter means **remaining days at the cutoff**.
A `completed` milestone requires an evidenced `completed_at` and has no parameter.
Observed starts/completions must be compatible with prerequisites in every scenario.

For partial overlap, split preparation into distinct tasks: work possible before
authorization and work that requires it. The engine does not decide which tasks
legally or operationally require permission.

All timestamps require timezone offsets. Computation uses UTC, and a duration day
is exactly 86,400 seconds. Months, business days, resource queues and staffing
constraints are not implicit. Zero durations are permitted.

### Inputs can stay unknown

Each scenario assessment identifies a parameter, a `basis`, a `rationale`, and
evidence references:

```json
{
  "parameter_id": "authorization_date",
  "basis": "unresolved",
  "rationale": "Effective authorization routes have not yet been established.",
  "evidence_refs": []
}
```

- `unresolved`: omit `value`. An omitted assessment is also unresolved.
- `assumed`: supply a value; the gap report retains it as an assumption.
- `estimated`: supply a value and evidence references. The package does not fit it.
- `observed`: supply a value and evidence references. Observed dates cannot lie
  after the cutoff; observed parameter values must agree across all scenarios.

Resolved date values are timestamps; duration values are numbers. Either type
can instead have `value: "never"`, an explicitly assumed or estimated failure to
complete. Unknown and never are different states. For an `any` join with an unknown
alternative, this first engine conservatively leaves the exact result unresolved,
even when a known alternative might suffice to establish the deadline outcome.

Registration checks that evidence records exist and satisfy existing observation
and retrieval cutoff rules. It pins the question and hashes referenced artifacts.
That checks provenance and arithmetic, not the truth or relevance of a claim.

### Probability requires declared weights

Each scenario is a **joint** assignment: correlated delays belong in the same
case. The engine neither independently samples parameters nor weights cases equally.
Unweighted successful-case counts have no probabilistic interpretation.

For a point probability, give every scenario a `weight` and `weight_rationale`,
plus a model-level `partition_justification` explaining why cases represent a
mutually exclusive, exhaustive partition. Weights must sum to one. The package
adds the weights of scenarios that meet the deadline. It does not verify the
partition's substantive adequacy or calibrate weights.

Unresolved outcomes produce no point estimate. Weighted unresolved cases yield
bounds by allocating their mass to failure or success; these are not confidence
intervals. Unweighted models remain valid research artifacts and reports.

## CLI and offline reports

```bash
vorhersage --project PROJECT timeline add --from model.json
vorhersage --project PROJECT timeline list
vorhersage --project PROJECT timeline show MODEL_ID
vorhersage --project PROJECT timeline gaps MODEL_ID
vorhersage --project PROJECT timeline analyze MODEL_ID --sensitivity
vorhersage --project PROJECT timeline compare LEFT_ID RIGHT_ID
vorhersage --project PROJECT timeline report LEFT_ID --compare RIGHT_ID --output comparison.html
```

Use the returned artifact ID, not the model's human-readable name. Comparisons
require a common question version, cutoff and deadline rule. They match scenario
IDs and disclose changed fields; matching labels alone do not establish equal inputs.

Sensitivity substitutes one parameter using values already declared in the model,
and identifies changes that flip the outcome. Such substitutions can break a joint
scenario's dependence assumptions. They are stress tests, never probability samples
or estimates of the value of additional research.

HTML reports are self-contained and interactive: choose a scenario to inspect
its schedule, controlling prerequisites, unknowns, assumptions and exact records.
No model or network calls occur. `export-widget FORECAST_ID --output audit.html`
also supports issued timeline assessments. A later direct review judgment is
displayed separately from the model's computed probability.

## Model-first workflow

Add `"workflow": "timeline"` to an ordinary run specification, then use the normal
`start`, `next` and `submit` commands:

1. **Structure:** register a model, then submit its `timeline_model_id` and rationale.
   Unresolved inputs and absent weights are valid. This creates a separate revision
   family for this run, linked to the original model.
2. **Parameter research:** `next` creates one task per parameter, supplying the
   current model and analysis. Submit `{scenario_id, assessment}` for every scenario
   exactly once. Each accepted task creates an immutable model revision atomically.
3. **Assessment:** submit `method: "timeline_model"`, the final `timeline_model_id`,
   rationale, limitations and evidence references. To add weights, retrieve the
   current model, increment `version`, set `previous_model_id` to its artifact ID,
   add weights and rationales, and register it. Assessment checks that researched
   inputs and dependencies have not silently changed.
4. **Review and issue:** existing review, stopping rules, manifests and forecast
   history apply. Review can request a parameter ID as its research `domain`, or
   `structure` for a fresh structure pass, subject to the run's extra-task budget.

An incomplete or unweighted assessment is rejected without advancing the run.
It can still be analyzed and exported. If an unresolved research pass needs new
inputs before any assessment can succeed, register an updated draft and start a
new run. There is no obligation to manufacture a probability to complete a run.

Timeline runs default to a fixed cutoff. Advancing the run cutoff does not advance
the model cutoff or automatically shorten a duration: revised observations and
remaining-work estimates require an explicit model revision. This release does
not automatically condition on non-occurrence or decay probabilities over time.

Revision runs referencing an issued timeline forecast inherit the timeline workflow
unless another workflow is explicitly selected. Their first structure task includes
the previous model for inspection; its dates and probability are not auto-updated.

Register experimental methods with `prior_method: "none"` and
`assessment_method: "timeline_model"`. Their sequence starts at structure; research
tasks come from parameters rather than `research_domains` (the method schema still
requires a nonempty domain list). Workers must support the two new task schemas.
Frozen evidence allowlists, usage budgets, and repeated trials still apply.

## Scope of this first version

This release computes finite declared scenarios. It does not infer dependencies,
learn duration distributions from censored historical episodes, simulate a fitted
hazard model, or establish improved forecast accuracy. Its testable contribution
is making the structure and consequential unknowns inspectable before selecting
a probability. Accuracy comparisons need registered cohorts and resolved outcomes.
