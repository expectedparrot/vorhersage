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

The first task is **intake**, before any probability is assigned. Name the inputs
you need to estimate and link missing facts to them. For example, save this
payload as `intake.json`:

```json
{
  "rationale": "The release owner's current QA status could change the launch estimate.",
  "inputs": [{"id": "launch_chance", "target": "Probability of public access before the deadline."}],
  "unknowns": [{
    "id": "qa_status",
    "question": "Has QA passed, and what blockers remain?",
    "input_ids": ["launch_chance"],
    "route": "ask_user",
    "why_it_matters": "Unresolved QA blockers could delay public access.",
    "action": "Ask the release owner for the latest QA result and remaining blockers."
  }]
}
```

Submit the answer against the exported task. The package retains its identifiers:

```bash
vorhersage submit --project launch --task first-task.json --answer intake.json
vorhersage next --project launch --output second-task.json
```

The next task asks you to obtain that answer. Routes are `ask_user`, `search`,
`assumption`, and `unobservable`. Each unknown gets an inquiry task; submit
`status: "answered"` with the answer and evidence references, or `status:
"unresolved"` with the reason uncertainty remains. User answers and search
findings require captured evidence. An `unobservable` question remains unresolved.
An intake with no unknowns needs a rationale explaining why no further intake is
needed. Completing the form does not establish that the plan is adequate.

Use a new filename for each export: `next --output` refuses to overwrite an
existing answer. You can edit the files yourself or ask an agent to investigate
and fill them. Preserve `run_id`, `submission.task_id`, `expected_revision`, and
`idempotency_key` if editing a full task file and using `submit --from`.
With `--task`/`--answer`, write only the payload and leave the original task alone;
`--usage usage.json` supplies a separate usage record. An exact retry is accepted once; altered retries, stale tasks,
and task files from another forecast are rejected. A rejected answer does not
advance the workflow.

After intake and inquiries, the standard workflow asks for a starting estimate.
Its payload includes `research_status_at_estimate`: `not_started`, `in_progress`,
`completed`, or `unspecified`. Recorded searches, cited evidence, and answered
inquiries prevent it from being labeled before-research, even if the run began
before any research. This remains a declaration, not independent proof that the
agent has no outside knowledge.

Subsequent tasks cover mechanisms and paths to YES/NO, base
rates, current state, actors and process, contrary evidence, assessment, review,
and issuance. A research answer must cite saved evidence or explain an unknown.
Capture a finding without constructing a packet. For a fictional owner answer:

```bash
vorhersage evidence add "The release owner reports that QA passed." --project launch \
  --url "urn:interview:release-owner" --title "Release owner answer" \
  --excerpt "QA passed today; public signup is still being prepared." \
  --claim-type observation
```

This captures supplied text; it does not fetch or verify a URL. The tool records
capture and retrieval time and returns an `evidence_ref` with `packet_id` and
`record_id`. An optional `--observed-at` records when the underlying event was
observed, without changing the current capture time. Keep the owner's observation
separate from your inference about the launch probability. Do not backdate evidence
to fit a forecast's cutoff. Future-dated packet imports are rejected.

You can also use [research capture](RESEARCH_AND_MONITORING.md) or
[packet import](AGENT_GUIDE.md#obtain-evidence-through-epiq) to save findings;
copy their returned evidence references into the answer. A citation is a traceable
input, not a guarantee of truth or relevance.

### Offer a short survey for the user

When several influential unknowns are facts the user knows, an agent should
offer to turn them into a short survey if `ep` is available. This can help during
initial intake or when refining an existing forecast. For example:

> A few facts about your release could change this estimate: QA status, remaining
> blockers, and who controls the launch date. I can make a short survey for you,
> then use your answers to update the relevant assumptions. Would that be useful?

The respondent is the human user who knows the case facts. Link every question
to an intake unknown and its `input_ids`, and explain why the answer matters.
For a launch forecast, the mapping might be:

| Survey question | Model input it informs |
|---|---|
| Has QA passed? | Remaining QA duration or probability of readiness |
| What public-signup work remains? | Time from readiness to public access |
| Is a launch date committed, tentative, or undecided? | Timing assumptions and their uncertainty |

Keep it brief, ask neutral factual questions, and include “don't know” or “not
applicable” where appropriate. Elicit the facts before displaying the current
forecast to avoid anchoring the answers. A few questions can also be answered in
chat; a survey is optional. If `ep` is unavailable, collect the same facts in chat.

When the user chooses the survey, check the installed commands, author an EDSL
survey with stable question names, and save it as `intake-survey.json`. Keep the
question-name → unknown ID → input IDs mapping alongside it. Then create the
human survey:

```bash
ep humanize create --help
ep humanize create --survey intake-survey.json --name "Forecast follow-up"
```

Save the returned survey UUID and give the user its respondent link. After the
user completes it, retrieve the responses. Replace `SURVEY_UUID` with that UUID:

```bash
ep humanize responses SURVEY_UUID --output intake-responses.json
ep results columns --file intake-responses.json
ep results export intake-responses.json --format json --output intake-answers.json
```

Preserve the original responses and their timestamps. Capture each relevant
answer with `vorhersage evidence add --claim-type observation`, attributing the
claim to the user and citing the survey and question. For example, record “The
owner reports that QA passed,” then separately explain what that implies for
launch timing. A user answer may narrow uncertainty without establishing a
probability or a population base rate.

Use the returned evidence references to answer the corresponding inquiry tasks.
For an already issued forecast, start `vorhersage revise` with those references,
update the affected scenario assumptions and `parameter_support`, and complete
assessment, review, and issuance before regenerating the report. Explain which
answers changed which inputs, what remains uncertain, and whether the forecast
moved. An unchanged estimate is also a valid result. Creating a survey or
recording a signal alone does not revise the forecast.

### Connect evidence to each model input

The assessment supports direct judgments, conditional paths, scenario mixtures,
odds ledgers, and timeline models. New studies require `parameter_support` for
each supplied input. A judgment assessment might include this record:

```json
{
  "input_id": "launch_chance",
  "model_input": "probability",
  "value": 0.6,
  "target": "Probability of public signup before the deadline.",
  "evidence_measures": "The owner reports QA completion, not a launch frequency.",
  "transfer_assumptions": "Assume the remaining signup work is usually short; no comparable-release sample was found.",
  "basis": "assumed",
  "plausible_range": [0.35, 0.8],
  "evidence_refs": []
}
```

This is an illustrative assumption, not a researched estimate. `input_id` links
to intake; `model_input` identifies the actual number in the model. A scenario
mixture needs separate records for `scenarios/CASE/weight` and
`scenarios/CASE/probability`. `vorhersage guide` lists paths for other methods.
Values must match the model. A range has two endpoints containing its value.
`measured`, `calculated`, and `extrapolated` bases require evidence references;
unsupported values remain `assumed`. In each case, describe the target, what the
evidence measured, and the assumptions needed to transfer between them. A valid
record does not prove that the transfer is justified.

For mixtures, support ranges feed the existing bounded sensitivity calculation.
If a scenario also declares `weight_range` or `probability_range`, they must agree
with its support records. The resulting bounds vary declared assumptions, not
statistical sampling error. Reports and `show` expose them alongside the estimate.

Review must challenge the estimate in both directions and include
`sensitivity_review`: an `interpretation`, `influential_inputs` listing actual
model-input paths, and `next_evidence` explaining what obtainable evidence could
narrow uncertainty, or why further research is unlikely to help. The task supplies
the calculation in `context.sensitivity`. Methods without a joint bound still
require review of their declared input ranges. Review can request more research.
A direct review judgment changing the probability needs its own support record.
The final task records a stopping
reason, review date, and observable triggers; submitting it issues the forecast.
There is no separate command that bypasses these steps to publish a number.

The default budget is 20 reported searches and two additional review tasks;
`--max-searches` and `--max-extra-tasks` can change these at definition. Report
usage in `submission.usage` or `--usage` when measured. Count only newly performed
searches, not repeated citations to the same search. Do not reduce actual usage
to pass a budget check. Omitted usage is not evidence of zero-cost research.

## Start from a timeline model

Use `--workflow timeline` on the command supplying the complete definition to
start with prerequisites and uncertain durations instead of a starting estimate.
Intake and inquiries still come first. The structure task links a registered model; parameter tasks then supply evidence
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

A study selects its run through an explicit saved binding. When new evidence
arrives, capture it and start a revision (replace the reference with the one
returned by `evidence add`):

```bash
vorhersage revise --project launch --reason "The owner reported a new blocker" \
  --evidence PACKET:RECORD
vorhersage next --project launch --output revision-intake.json
```

`revise` preserves the old forecast, starts a linked run with a fresh cutoff, and
appends a new binding. It carries forward the earlier evidence and model records.
For a standard revision, intake and its inquiries lead to assessment, review, and
issuance; the earlier research coverage remains available. A timeline revision
also revisits structure and parameter research. It does not silently advance the
model's own cutoff or shorten remaining durations.

Use the same `next`/`submit`/`report` commands to finish. `show` and reports
distinguish the previous issued forecast, the pending revision, and its issued
replacement. Repeating an identical revision request while that revision is open
reuses it; a different request is rejected until the active work is completed.
`--expected-forecast ID` additionally guards against revising an unexpected
forecast. A signal records a reason to review and never changes a probability;
signals associated with the question are included in its report.

Portfolio commands (`init`, `question add`, `run start`, `next --run`,
`submit --run`, and `report --question`) retain their JSON interface. The
single-question shortcuts intentionally require a project created with `start`;
they do not guess which question or run to select in an existing portfolio.
Existing runs retain their original tasks. New portfolio runs can opt into the
same intake and parameter-support contract by setting
`"research_contract": "structured_v1"` in their run JSON.
