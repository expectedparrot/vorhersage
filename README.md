# Vorhersage

[Documentation](https://expectedparrot.github.io/vorhersage/) ·
[Source](https://github.com/expectedparrot/vorhersage) ·
[Expected Parrot tools](https://expectedparrot.github.io/directory/)

<p align="center">
  <img src="docs/assets/vorhersage-artwork.png" width="800" alt="Vorhersage artwork: a green parrot connected to sensors in a glass tank, framed by expectation brackets">
</p>

A forecasting workbench for agents. **Version 0.3 is implemented:** a Python CLI
for binary questions, durable research workflows, Epiq evidence packets,
probability calculations, revisions, resolution and matched evaluation.

Agents do the research and judgment. Vorhersage supplies the next task, enforces
research coverage, performs declared calculations and preserves the record.

## Start here

The command is installed in this checkout's virtual environment:

```bash
.venv/bin/vorhersage guide
.venv/bin/vorhersage schema
.venv/bin/vorhersage --project examples/live_portfolio/project status
```

The [agent guide](docs/AGENT_GUIDE.md) explains the complete interface. On another
machine, install with Python 3.11+ using `python -m pip install .` in your chosen
environment. The package has no runtime dependencies. Without installation,
`PYTHONPATH=src python3 -m vorhersage guide` works from this repository.

The operating loop is:

```text
question add → run start → next → submit → next → … → issue
                              ↑                       ↓
                    new revision ← monitor ← waiting
                                              ↓
                                         resolve → evaluate
```

`issue` is a task submitted through `submit`. All ordinary commands return JSON;
errors return JSON on stderr and a nonzero exit code. Question/profile versions,
evidence and issued forecasts retain their history. Prospective runs can gather
new research while active; each accepted step records its information cutoff.

## What works

- Configurable research profiles with explicit assessed or unknown outcomes.
- Durable resumption, atomic submissions, idempotent retries and stale-state checks.
- Epiq search, consistent evidence freezing, portable packet import and change checks.
- Judgmental and empirical priors, conditional paths, and explicit ensembles.
- Review in both directions, bounded follow-up research, immutable forecast revisions.
- Scheduled review detection, evidence signals, resolution corrections and Brier scoring.
- Matched comparisons, descriptive calibration bins, missingness and event-group labels.
- Separate prospective, retrospective and simulation evaluation modes.
- Versioned forecasting methods and frozen-packet experiments, with repeated trials, resumable workers, and matched method scores.
- One-question market workbench: hidden Kalshi/Polymarket targets, planned research steps, immutable checkpoints, and immediate market-agreement reports.
- [Full HTML and LaTeX reports](docs/REPORTS.md): question definitions, research, models, sources, and prediction histories, exported offline through the CLI.
- Joint elicitation sessions with explicit conditions, atomic external imports,
  partial submissions, median panels, paired conditional ratios, and session coherence.
- Live session events, staged evidence and bindings, resumable model/tool workers,
  attempt costs, protocol audits, whole-session studies, and offline comparisons.
- Explicit unconditional session evaluation, empirical CRPS, and quantile loss.
- Halawi benchmark import, fixed historical replay, and separate replay scoring.
- Research bundles, captured-text integrity checks, source dependence and contradiction audits.
- Explicit starting-judgment timing; legacy or after-research judgments are not labeled original priors.
- Optional generic scenario mixtures, probability-mass checks and bounded sensitivity analysis.
- Declared odds ledgers with joint ratios for dependent findings, sensitivity, and offline interactive HTML audits.
- Deadline models with explicit milestone dependencies, unresolved parameters, generated research tasks, joint scenarios, and offline schedule comparisons.
- Version-pinned question implications, transitive coherence checks and optional strict issuance.
- Reusable historical episodes with horizon-specific outcomes and censored-case reporting.
- Persistent monitoring with Epiq or configured research workers, resumable agent execution and resolution routing.

The [research and monitoring guide](docs/RESEARCH_AND_MONITORING.md) documents these
extensions, runnable commands, worker protocols, and their limitations.
The [odds-ledger guide](docs/ODDS_LEDGER.md) includes `export-widget` and a
[working fictional demo](examples/odds_ledger/demo.html).
The [timeline guide](docs/TIMELINE_MODELS.md) explains modeling before choosing a
probability, with an [unweighted Waymo dependency comparison](examples/waymo_boston_2029/timeline/comparison.html).
The [improvement plan](docs/IMPROVEMENT_PLAN.md) maps the remaining evaluation and research proposals.
The [method comparison guide](docs/EXPERIMENTS.md) explains versioned procedures,
experiment registration, repeated trials, and controlled evidence inputs.
The [market workbench guide](docs/MARKET_WORKBENCH.md) walks through one live question
at a time, with a [fictional research-and-reveal demo](examples/market_workbench/demo.html).
The [joint-session guide](docs/JOINT_SESSIONS.md) explains shared elicitation
records, model-specific conditions, source timestamps, and panel aggregation.
The [live-session guide](docs/LIVE_SESSIONS.md) documents execution contracts,
worker recovery, research checks, study registration, reporting, and scoring.

Shared factual research stays in Epiq. Vorhersage stores its own workflow state
and frozen evidence copies in each project's `.vorhersage/state.sqlite`.

## Executed examples

- [NYC temperature forecast — full report](https://expectedparrot.github.io/vorhersage/examples/nyc-2026-09-16/):
  a live research case with a methodology flowchart, model assumptions, and a
  sealed 28.6% prediction compared with Kalshi. [Source and calculation](examples/market_workbench/nyc_20260916/README.md).

- [Joint sessions](examples/joint_sessions/README.md): four fictional model sessions,
  partial submission and import, explicit conditions, coherence, and median ratios.
- [Live sessions](examples/live_sessions/README.md): two arms × two repetitions,
  research receipt polling, staged evidence, finalization, HTML reports, and scoring
  through deterministic workers with no provider calls.

- [Method comparison](examples/method_comparison/README.md): two methods, two fictional
  questions, two repetitions; pauses and resumes workers, then scores all eight trials.

- [Historical benchmark walkthrough](examples/backtesting/README.md): 20 Halawi
  validation questions pass through the task loop with a constant-50% control;
  18 have historical crowd baselines.
- [Model pilot](examples/backtesting/model_pilot_01/RESULTS.md): 80 completions
  compare plain and structured prompts. Format failures and widespread outcome
  recognition limit the accuracy comparison.
- [Fictional factory portfolio](examples/factory/README.md): separate CLI processes
  create questions, research, issue, revise, resolve and compare with a baseline.
- [Patriots package regression](examples/patriots_2027/package_output/package_report.json):
  the general package reads 31 Epiq capture/finding records and reproduces the
  recorded 6.048% judgment. It is labeled retrospective, with the outcome unresolved.
- [Initial live research queue](examples/live_portfolio/README.md): three related
  NFL questions are registered and ready for research, with no probabilities issued.
- [Listen Labs / Salesforce](examples/listen_labs_salesforce_2026/README.md): original
  prospective announcement and completion forecasts, with research and provenance.
- [Generic scenario input](examples/workbench_extensions/mixture.json): fictional
  readiness assumptions for the optional mixture calculator.
- [AIRO principal-panel reproduction](examples/airo/README.md): imports the authors'
  11,760 probabilities, reproduces Figures 6–9, and checks 376 published values.
- [Fresh AIRO EDSL pilot](examples/airo/edsl_pilot_01/REPORT.md): one model completes
  2,940 probabilities through a recorded research loop, with transport amendments
  and research limitations documented.

Run the acceptance walkthrough in a new directory:

```bash
.venv/bin/python examples/factory/walkthrough.py /tmp/new-factory-portfolio
```

Run checks:

```bash
.venv/bin/python -m pytest -q
python3 -m unittest discover -s examples/patriots_2027 -p 'test_*.py'
```

There are **206 package/integration tests and 21 earlier prototype tests**. Local Epiq tests
explicitly skip if their optional checkout/database fixtures are unavailable.
The CLI has also been installed and a distributable wheel built locally.
See the [validation record](docs/VALIDATION.md) for checks and their limits.

The package does not select a web service or model, learn calibration, or establish
predictive superiority. Configured research/agent workers perform collection and
judgment. `watch run` keeps polling while running; `watch tick` can be invoked by an
external scheduler. No OS service is installed automatically. Resource use is agent-reported.
The implementation is intended for small portfolios; scale testing and database
migrations remain future work.

An optional [EDSL model-run example](examples/backtesting/model_pilot_01/README.md)
prepares label-free jobs and imports validated model outputs. Its first 80-call
comparison is completed, with raw outputs, costs, forecasts and evaluations saved.

## Research and design record

- [What we have learned](LEARNINGS.md): consolidated lessons and corrections.
- [Original design](DESIGN.md) and [workflow proposal](WORKFLOW.md): design history;
  the agent guide documents the implemented command syntax.
- [Superforecasting](SUPERFORECASTING.md): capabilities and experiments to test.
- [Literature](literature/README.md): review and 39 annotated sources.
- [Original Patriots exercises](examples/patriots_2027/README.md) and
  [first Epiq adapter](examples/patriots_2027/EPIQ_INTEGRATION.md).
