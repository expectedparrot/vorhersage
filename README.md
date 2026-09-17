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

## How the CLI works

A project stores its records in `.vorhersage/state.sqlite`. Each command reads
or advances that saved state. Sources can be captured directly or imported from
an [Epiq evidence library](docs/RESEARCH_AND_MONITORING.md).

The ordinary forecasting loop is:

```text
Define question → Start run → Get next task → Research / model / review
                                   ↑                    ↓
                                   └──── Submit work ───┘
                                                        ↓
                                              Issue forecast → Report
                                                        ↓
                                            Monitor → Revise or resolve
                                                        ↓
                                                     Evaluate
```

`next` returns the task and its required input schema. The agent authors a JSON
submission and calls `submit`; issuance is one of these tasks. Records retain
question versions, evidence references and forecast history. Use `status` and
`run list` to resume an existing project.

```bash
vorhersage --project ./forecast-study status
vorhersage --project ./forecast-study run list
vorhersage --project ./forecast-study next --run RUN_ID
vorhersage --project ./forecast-study submit --run RUN_ID --from result.json
vorhersage --project ./forecast-study report --question QUESTION_ID --output report.html
```

Replace IDs with those returned by the CLI. Ordinary responses are JSON; errors
return JSON on stderr and a nonzero exit code. `--help` explains command syntax,
and `schema NAME` supplies the exact input shape.

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
