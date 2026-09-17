# Deadline models: structure before probability

A `timeline_model` declares what must finish, what can overlap, and which inputs
remain unknown. Vorhersage computes the resulting schedules and creates research
tasks for the declared parameters. There is no initial probability task.

This supports a concrete disagreement such as “preparation can happen before
authorization” versus “preparation must wait.” The dependency changes the computed
launch date even when both models use identical dates and durations.

## Try the Waymo example

The [README walkthrough](../README.md#2-turn-the-question-into-something-we-can-research)
builds the initial plan step by step, then uses the saved research to reproduce
the 39% estimate and a 22% sensitivity alternative. The next section explains
how to author a working plan for your own question.

### Build a plan with small commands

After registering a question, create an editable TOML file:

```bash
vorhersage timeline new launch.toml --project PROJECT
vorhersage timeline step launch.toml permission "Effective legal permission" --date
vorhersage timeline step launch.toml preparation "Fleet and technical preparation"
vorhersage timeline step launch.toml launch "Paid public service" \
  --after permission preparation --target \
  --rationale "Public service requires both permission and operational readiness."
vorhersage timeline show launch.toml
vorhersage timeline gaps launch.toml
vorhersage timeline save launch.toml --project PROJECT
```

`new` selects the project's only question and pins its current version and
deadline. Supply `--question ID` if the project has several questions. The plan's
information cutoff defaults to now; `--as-of TIME` sets an explicit cutoff.
`--deadline-rule on_or_before` makes the deadline inclusive; the default is
strictly before. The model name defaults to the filename without `.toml`.

A step normally needs an unknown duration in elapsed days. `--date` instead
declares an unknown calendar milestone, with no prerequisites. `--after` lists
the steps that must all finish first; omit it for work that can begin at the
information cutoff. `--target` identifies the step satisfying the event definition.
Add prerequisites before dependent steps. `--rationale` records the reason for
the dependency; otherwise it is explicitly labeled provisional and needing research.

The file is ordinary text and can also be edited directly. For example:

```toml
[[steps]]
id = "launch"
description = "Paid public service"
kind = "duration"
after = ["permission", "preparation"]
rationale = "Public service requires both permission and operational readiness."
```

Use the complete file created by `new`; this excerpt is one step within it.
`show` displays partial plans, including their unknown dates and durations.
`gaps` and `analyze` require a complete dependency graph and target. They keep
unknown inputs unknown. **The plan has one unweighted, unresolved scenario; it
does not imply that launch has any particular probability.**

`save` applies the full timeline validator, including cycle and disconnected-work
checks, then registers an immutable version 1. Retrying an unchanged save reuses
that model. Editing the working file never edits the saved record; a changed file
cannot overwrite the same saved name/version. Use a new `name` for a separate
draft, or the full model schema below for explicit versioned revisions.

`new` refuses to overwrite a file. `step` refuses conflicting duplicate names,
unknown prerequisites, and invalid combinations before replacing the working
file. Repeating the same step is safe. Commands serialize their writes using
a temporary `.lock` file beside the plan; direct editor changes should be made
between commands.

### Revise dependencies after researching them

The forecaster decides what the evidence implies for the model. Importing
findings never edits the graph. To split one broad permission milestone into
state permission and local commercial arrangements, for example:

```bash
vorhersage timeline edit launch.toml permission --rename state \
  --description "Effective state permission" \
  --rationale "State permission and local commercial arrangements are separate steps."
vorhersage timeline step launch.toml local "Local commercial arrangements" --after state
vorhersage timeline edit launch.toml launch --after local preparation \
  --rationale "Public service needs both local arrangements and operational readiness."
```

`edit` changes the working TOML file and requires an explanation. `--rename`
updates every prerequisite and target reference to that step. `--after` replaces
the complete prerequisite list; `--after` alone clears it. `--description`,
`--kind date|duration`, and `--target` change those parts of the definition.
Unknown names, duplicate names, invalid date prerequisites, and cycles are
rejected without altering the file. Intermediate disconnected steps are allowed
while building; a complete model must connect every step to the target.

Saved models remain immutable. Use another model name or an explicit versioned
revision when registering changed work. The working plan retains the latest
rationale; save model snapshots when you need a history of structural alternatives.

### Generate the dependency diagram

```bash
vorhersage timeline diagram launch.toml --output launch.svg
```

Open the SVG in a browser; it requires no network, JavaScript, or extra packages.
It draws the validated prerequisites and highlights the target. A diagram shows
the declared structure, not whether its assumptions are true. Dates and
probabilities remain in the scenario analysis and full report.

The same command accepts a saved model, such as `timeline diagram launch@1
--project PROJECT --output launch.svg`. Omit `--output` to print Mermaid source,
use `.mmd` to save that source, or use `.md` for a fenced Mermaid diagram ready
for Markdown documentation. SVG labels are escaped; Mermaid uses generated node
identifiers and escaped labels. Re-exporting replaces the generated output file.
Diagrams require a complete, valid graph and a target; use `show` for partial plans.

These commands author the initial research structure. Scenario weights,
source-linked estimates, observations of work already started or completed,
and richer joins use the full model schema and research workflow below. TOML
plans intentionally reject extra fields instead of silently ignoring inputs.
Use `timeline show MODEL@VERSION --format text` to inspect a saved model's full
milestones, scenario inputs, rationales, and limitations.

Working-file commands show readable text by default; add `--format json` for
the machine-readable result. Existing saved-model commands still default to
JSON; `diagram` defaults to Mermaid source or an export confirmation.
`--project` works before the command or after any timeline subcommand.

### Compare two hypothetical structures

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

Each timeline command accepts either the returned artifact ID or the model's
declared name with an explicit version, such as `waymo@1`. An unversioned name is
rejected; adding version 2 cannot silently change what a saved command selects.
References resolve to immutable artifact IDs before analysis or export.

For readable terminal output, add `--format text`. JSON remains the default,
including machine-readable errors. For example:

```bash
vorhersage timeline analyze waymo@1 --format text
vorhersage timeline gaps waymo@1 --format text
```

Comparisons
require a common question version, cutoff and deadline rule. They match scenario
IDs and disclose changed fields; matching labels alone do not establish equal inputs.

### Change a duration assumption

Create an alternative without copying and editing the full model file:

```bash
vorhersage timeline shift waymo@1 --parameter public_access --days 180 \
  --name slower-access --rationale "Public access takes six months longer" --format text
vorhersage timeline compare waymo@1 slower-access@1 --format text
```

`shift` adds elapsed days to that duration in every scenario. Negative days
shorten it; resulting durations must remain within the model's valid range.
It preserves `never` assignments, rejects unresolved or observed durations,
and requires at least one finite duration to change. It also requires a new
model name and an explicit rationale. Calendar dates use a different kind of
parameter and cannot be shifted through this command.

The alternative starts at version 1, links to the exact source artifact through
`derived_from_model_id`, and preserves its evidence, scenario weights, cutoff,
and other parameters. Changed values are labeled assumed, with the original
value and rationale retained in their explanations. Registration is atomic;
invalid changes leave no partial model. Repeating the same command reuses the
same model, while reusing its name with different inputs fails.

The source and issued forecasts stay unchanged. A sensitivity alternative is a
model to examine; issuing a revised forecast still requires the review workflow.

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
