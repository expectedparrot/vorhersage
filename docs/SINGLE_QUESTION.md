# Work on one forecast

Use these commands to make a forecast yourself or with an agent. They manage the
question and research run for you. You supply the evidence and judgments; the
package checks the records, performs declared calculations, and preserves the
forecast. No model or research service is called automatically.

## Start with a question

```bash
vorhersage start "Will our app launch before January 1, 2030?" --project launch
```

This saves your question and asks you to define the deadline, success criteria,
and outcome sources. It assigns no probability. Record those choices with:

```bash
vorhersage define --project launch \
  --deadline "2030-01-01T00:00:00Z" \
  --yes "Customers can sign up and use the public release before the deadline." \
  --source "Our public release log" \
  --forecaster Alice
```

If you already have that definition, supply the same options directly to `start`
in a fresh folder:

```bash
vorhersage start "Will our app launch before January 1, 2030?" \
  --project another-launch \
  --deadline "2030-01-01T00:00:00Z" \
  --yes "Customers can sign up and use the public release before the deadline." \
  --source "Our public release log" \
  --forecaster Alice
```

Both routes register the question and begin the research workflow. An invalid
complete definition leaves no partially initialized project. Existing ordinary
files are preserved; an existing forecast project is never replaced. Repeating
an identical `define` is safe; a different definition is rejected once work has
begun.

Dates without a time mean midnight UTC at the start of that date. Use a timestamp
with an explicit timezone for local deadlines. NO defaults to failure to meet
the YES criteria by the deadline; void covers defective criteria or resolution
evidence, not ordinary delay or cancellation. `define --help` lists the overrides.

The default forecaster is `user`. Set `--forecaster` to the person or agent making
the judgments and `--method` to your method's description. Declare
`--research-status in_progress` or `completed` if research has already begun.
These settings belong on the command supplying the complete definition.

## Inspect progress

```bash
vorhersage show --project launch
```

The readable view includes the event definition, current estimate, research
stage, evidence used with source links, recorded reasoning, uncertainties,
review objections, and the next task. An initial estimate is labeled as a
working estimate until review and issuance are complete. Research uncertainties
are attributed to the submissions that recorded them; they are not automatically
resolved by later findings. Issued forecasts display their review date and
update triggers.

## Do the next piece of work

Export the task and its answer template:

```bash
vorhersage next --project launch --output first-task.json
```

Open `first-task.json`. It contains:

- `task`: what to investigate or assess.
- `context`: the question, previous work, and evidence already used.
- `payload_schema`: the fields required in your answer.
- `submission`: an answer template with the task and retry bookkeeping filled in.

For the standard workflow, the first task asks for a starting estimate. For
example, replace **only `submission.payload`** with this illustrative judgment:

```json
{
  "method": "judgment",
  "probability": 0.6,
  "rationale": "My initial estimate, before checking the release blockers.",
  "limitations": ["A subjective starting point, without a comparable-release sample."],
  "evidence_refs": []
}
```

Then submit the whole task file:

```bash
vorhersage submit --project launch --from first-task.json
vorhersage next --project launch --output second-task.json
```

Use a new filename for each export: `next --output` refuses to overwrite an
existing answer. You can edit the files yourself or ask an agent to investigate
and fill them. Preserve `run_id`, `submission.task_id`, `expected_revision`, and
`idempotency_key`. An exact retry is accepted once; altered retries, stale tasks,
and task files from another forecast are rejected. A rejected answer does not
advance the workflow.

After the starting estimate, tasks cover mechanisms and paths to YES/NO, base
rates, current state, actors and process, contrary evidence, assessment, review,
and issuance. A research answer must cite saved evidence or explain an unknown.
Use [research capture](RESEARCH_AND_MONITORING.md) or
[packet import](AGENT_GUIDE.md#obtain-evidence-through-epiq) to save findings;
copy their returned evidence references into the answer. A citation is a traceable
input, not a guarantee of truth or relevance.

The assessment supports direct judgments, conditional paths, scenario mixtures,
odds ledgers, and timeline models. Review must challenge the estimate in both
directions and can request more research. The final task records a stopping
reason, review date, and observable triggers; submitting it issues the forecast.
There is no separate command that bypasses these steps to publish a number.

The default budget is 20 reported searches and two additional review tasks;
`--max-searches` and `--max-extra-tasks` can change these at definition. Report
usage in `submission.usage` when measured. Omitted usage is not evidence of
zero-cost research.

## Start from a timeline model

Use `--workflow timeline` on the command supplying the complete definition to
start with prerequisites and uncertain durations instead of a starting estimate.
The structure task links a registered model; parameter tasks then supply evidence
or assumptions for each scenario. `show` displays the model calculation separately
from the working or issued forecast.

Timeline runs use a **fixed information cutoff** at definition, and each model
has its own cutoff. Use previously captured evidence, or collect your evidence
before defining the timeline run and declare `--research-status completed`.
Later captures are not silently admitted to the fixed snapshot. Updating the
model's cutoff and remaining durations requires explicit new model/run records.
The [timeline guide](TIMELINE_MODELS.md#model-first-workflow) covers model authoring,
parameter submissions, and revisions. The standard prospective workflow instead
advances its evidence cutoff as you submit work.

## Share the report

```bash
vorhersage report --project launch
vorhersage report --project launch --output launch.tex
```

The first command writes `launch/report.html`. The second writes LaTeX to
`launch.tex`. Reports can be exported before issuance and describe the work
actually recorded; they do not manufacture a completed forecast. Re-exporting to
the same report path replaces the generated file. Use another path to keep an
older export.

## Resume, revise, or use the machine interface

Reopen the same folder with `show` or `next`; no IDs need to be remembered.
`--project` can appear before or after these single-question commands. Without
it, the current directory is used. Add `--json` for a machine-readable envelope;
`next --json` includes the same answer template as the exported task file.
`report --json` returns the question's forecast history on stdout without writing
an HTML file. To request a JSON export receipt instead, use `--output ... --json`.

A study stays bound to its original run; it never silently selects another run
in the database. To revise an issued forecast, use the existing
[revision workflow](AGENT_GUIDE.md#issue-monitor-and-revise) with an explicit
`previous_forecast_id`. Use its returned run ID for `next --run` and `submit --run`.
Question reports include the revision history.

Portfolio commands (`init`, `question add`, `run start`, `next --run`,
`submit --run`, and `report --question`) retain their JSON interface. The
single-question shortcuts intentionally require a project created with `start`;
they do not guess which question or run to select in an existing portfolio.
