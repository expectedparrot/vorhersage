# Vorhersage

**A forecasting workbench for AI agents, from research question to probability and report.**

[Documentation](https://expectedparrot.github.io/vorhersage/) ·
[Example report](https://expectedparrot.github.io/vorhersage/examples/nyc-2026-09-16/) ·
[Expected Parrot tools](https://expectedparrot.github.io/directory/)

Give an agent a question such as **“Will Waymo launch public driverless rides in
Boston by the start of 2029?”** Vorhersage helps it define what counts as a Yes,
collect and cite evidence, build a probability model, investigate the assumptions
that matter, and record its forecast. It produces a durable research record and
HTML or LaTeX reports explaining how the estimate was reached.

The agent supplies the research and judgment. The package supplies the workflow,
validates each step, computes declared models, and preserves sources, assumptions,
and revisions. Another agent can resume the same project without reconstructing
the work from a conversation.

## Copy and paste into an agent

Copy this block into your coding agent along with a forecasting question:

```text
Use Vorhersage to research my forecasting question and produce a sourced HTML
report. If I haven't supplied a question, ask for one.

Install uv if needed: https://docs.astral.sh/uv/getting-started/installation/
Then install Vorhersage and EDSL's ep command together:

uv tool install --python 3.11 --with-executables-from \
  "edsl @ git+https://github.com/expectedparrot/edsl.git@main" \
  "vorhersage @ git+https://github.com/expectedparrot/vorhersage.git@main"
export PATH="$(uv tool dir --bin):$PATH"

Reuse an existing Expected Parrot login; otherwise run this and let me
complete the browser login:

ep auth login

Read the installed guide, then create or resume a project:

vorhersage guide

Follow the guide and CLI schemas to register the question, research it,
record the model and issue a forecast. Use `next` and `submit` to advance
the run. Preserve sources, assumptions and uncertainty. Finish with
`vorhersage report --question QUESTION_ID --output report.html` and show
me the forecast, its main drivers, and the report.
```

This installs from GitHub and requires Git; uv supplies Python 3.11 if needed.
EDSL provides `ep` for Expected Parrot authentication and model execution.
Vorhersage's core workflow, calculations and exports also work locally without
an account. Model and research services are chosen by the agent or configured
workers. For a persistent shell setup, run `uv tool update-shell`.

## Worked example: will an app launch next week?

Suppose a small team plans to release an app within seven days. We want a
probability, an explanation, and a record we can update when the QA results arrive.

This example is **fictional and runs offline**. Its briefing and probabilities are
authored teaching inputs. It makes no model calls and needs no login. From a
checkout of this repository, after installing Vorhersage:

```bash
python3 examples/quickstart.py ./launch-demo
```

Choose a new output directory. The [helper](examples/quickstart.py) writes the
example inputs, calls the installed `vorhersage` CLI for every step, and saves
the responses. It ends with:

```text
Issued forecast: 72.0% (0.90 × 0.80)
Report: .../launch-demo/report.html
```

Here is the forecast it worked through.

### 1. Define the event

**Question:** Will the app launch publicly within seven days?

- **Yes:** QA has passed and at least one external user can access the public
  release by the deadline.
- **No:** Those requirements are not met by the deadline.
- **Void:** The teaching fixture is withdrawn.

The helper writes an exact UTC deadline, registers the question with
`question add`, and starts a simulation run with `run start`. Its small research
profile requires two checks: QA readiness and the release process. The saved
question is in `launch-demo/inputs/question.json`.

### 2. Record the starting estimate and evidence

We record **50% as an assumed starting baseline**. The fictional briefing is
already available, so the record does not label this an independent pre-research
prior. The briefing supplies two judgments:

| Finding | Assumed probability | What it means |
|---|---:|---|
| The remaining QA checks pass by the deadline | 90% | A judgment from the fictional engineering lead. |
| Approval and public deployment finish by the deadline, given QA passes | 80% | A conditional judgment that must include the time left after QA. |

`research capture` stores the briefing and returns evidence references. The
research submissions cite those references and record what remains unknown:
defect severity, approval delays, and deployment failures. These numbers are
subjective inputs, not measured success rates.

### 3. Have the package calculate the prediction

Public launch requires QA, so we declare a `conditional_path` assessment:

```text
P(launch by deadline)
  = P(QA passes by deadline)
    × P(launch by deadline | QA passes by deadline)
  = 0.90 × 0.80
  = 0.72
```

Vorhersage computes **72%** from the submitted components. The second probability
is conditional on the first event; the multiplication does not assume the stages
are independent. The complete input, including rationales and evidence links, is
saved in `launch-demo/inputs/assessment.json`. The script does not supply a final
72% value in that assessment—the package calculates it.

### 4. Challenge the estimate and issue it

The review considers both directions. **Too high?** QA could finish too late to
leave time for approval. **Too low?** Preparing approval during QA could make the
last step easier. The example retains the stated assumptions and their limits,
then submits the issuance task with a review scheduled for the next day and a
trigger for new QA results or a changed release schedule.

The issued forecast is **72%**, with the sources, calculation and review attached.
A real agent would investigate these objections and justify or revise the inputs;
completing the workflow alone does not establish that 72% is well calibrated.

### 5. Inspect the project and open the report

```bash
vorhersage --project ./launch-demo status
vorhersage --project ./launch-demo run list
vorhersage --project ./launch-demo report --question app-launch --output ./launch-demo/report.html
```

Open `launch-demo/report.html` in your browser. It contains the question, prediction,
research, calculation, review and sources. The helper also saves:

| File or directory | Contents |
|---|---|
| `summary.json` | The run ID, forecast ID and final probability. |
| `inputs/` | Question, briefing, model and every authored submission. |
| `tasks/` | Each `next` response, including the requested input schema. |
| `receipts/` | The CLI's responses to every command. |
| `report.json` | The exported question and forecast records. |
| `.vorhersage/state.sqlite` | The project state used to resume or revise the work. |

The core loop is **`next` → do the requested work → `submit` → `next`**.
The helper supplies fixed answers for this example; an agent supplies research
and judgment in a real run. `next` returns the current task and its input schema.
Issuance is one of those tasks. Each accepted submission preserves the history.

Use `vorhersage guide` for the workflow and `vorhersage schema NAME` for exact
input fields. Ordinary commands return JSON; errors return JSON on stderr and a
nonzero exit code. Sources can be captured directly or imported from an
[Epiq evidence library](docs/RESEARCH_AND_MONITORING.md).

## What you can do

- **Research a forecast.** Define the event, deadline and resolution source;
  save an initial judgment; collect evidence; review competing explanations;
  then issue a probability with its rationale.
- **Make the model inspectable.** Declare a reference-class estimate, conditional
  scenarios, an odds ledger, or a timeline of necessary milestones. The package
  performs the arithmetic and sensitivity checks; the agent justifies the inputs.
- **Improve a research process against a live market.** Freeze a Kalshi or
  Polymarket quote, keep it hidden during research, record checkpoints, then
  reveal it and compare. This gives an immediate development target while the
  event is unresolved. Market agreement is separate from forecast accuracy.
- **Compare forecasting methods.** Register methods, hold evidence fixed or
  vary research, repeat trials, and compare matched predictions. Joint sessions
  can answer related questions and check their logical consistency.
- **Maintain and evaluate forecasts.** Resume unfinished work, schedule reviews,
  record new revisions, and score predictions once outcomes are known.
- **Share the work.** Export a full HTML or LaTeX report with the question,
  evidence, methodology, model, prediction history and limitations. Declared
  odds ledgers can also become interactive HTML widgets.

<p align="center">
  <img src="docs/assets/vorhersage-artwork.png" width="760" alt="An Expected Parrot connected to sensors in a glass tank, framed by expectation brackets">
</p>

## Choose a workflow

| Your task | Start here |
|---|---|
| Research and maintain one forecast | [Agent guide](docs/AGENT_GUIDE.md) |
| Pick a live market, research, then compare with its hidden price | [Market workbench](docs/MARKET_WORKBENCH.md) |
| Model a deadline through milestones and dependencies | [Timeline models](docs/TIMELINE_MODELS.md) |
| Declare and audit likelihood-ratio updates | [Odds ledgers and widgets](docs/ODDS_LEDGER.md) |
| Compare methods on the same questions | [Method experiments](docs/EXPERIMENTS.md) |
| Run model/tool workers across related questions | [Live sessions](docs/LIVE_SESSIONS.md) and [joint sessions](docs/JOINT_SESSIONS.md) |
| Produce a readable report and methodology flowchart | [Report exports](docs/REPORTS.md) |

## Worked examples

- **[Read a complete forecast report](https://expectedparrot.github.io/vorhersage/examples/nyc-2026-09-16/).**
  The NYC case shows the research, methodology flowchart, assumptions and
  probability calculation, followed by a Kalshi comparison.
  [Sources and reproduction](examples/market_workbench/nyc_20260916/README.md).
- **[Run an offline walkthrough](https://expectedparrot.github.io/vorhersage/).**
  A fictional study demonstrates research, pause/resume, model comparisons and
  scoring without API keys. The page includes a downloadable example.
- **[Inspect a deadline model](examples/waymo_boston_2029/timeline/README.md).**
  The Waymo example makes regulatory and operational dependencies explicit and
  compares alternative timeline structures.
- **[Reproduce a published study](examples/airo/README.md).** The AIRO example
  imports the authors' 11,760 probabilities, reconstructs figures, and checks
  376 published values. Reproducing an analysis does not validate its predictions.

## Development and design

For a source checkout:

```bash
git clone https://github.com/expectedparrot/vorhersage.git
cd vorhersage
uv venv --python 3.11
uv pip install -e . pytest
.venv/bin/vorhersage guide
.venv/bin/python -m pytest -q
```

The core package requires Python 3.11+ and has no runtime dependencies.
EDSL and Epiq are optional integrations. The current implementation targets small
portfolios; database migrations and large-scale operation remain future work.

[Learnings](LEARNINGS.md) records what the forecasting exercises taught us,
including contamination in historical replay and the limits of procedural
compliance. See also the [validation record](docs/VALIDATION.md),
[improvement plan](docs/IMPROVEMENT_PLAN.md), [literature review](literature/README.md),
and original [design](DESIGN.md) and [workflow proposal](WORKFLOW.md).
