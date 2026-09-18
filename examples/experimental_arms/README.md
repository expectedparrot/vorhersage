# Experimental arms, offline

Run from an installed checkout, using a new output directory:

```bash
python examples/experimental_arms/walkthrough.py /tmp/vorhersage-arms-demo
```

This registers eight arms: two procedures (direct and reviewed), two synthetic
model configurations, and two data sets (question only and a fictional report).
Each arm runs twice on the same fictional question, producing 16 forecasts.
Execution pauses after three tasks, resumes, records a synthetic outcome, and
compares all arms. It makes no model or network calls.

The worker deliberately uses preset probabilities and a fixed review adjustment
to exercise configuration, data access, and before/after scoring. Its results
measure software behavior, not forecasting performance. Zero usage is accurate
for this fixture, not a template for reporting actual model usage.

The output directory contains method, arm, and experiment specifications,
`partial.json`, `execution.json`, the complete `evaluation.json`, and a compact
`summary.json`. Compare arms through:

```bash
vorhersage arm list --project /tmp/vorhersage-arms-demo
vorhersage experiment status EXPERIMENT_ID --project /tmp/vorhersage-arms-demo
```

Use the returned experiment ID. For real experiments, register actual question
versions and evidence packets, replace the worker with one that honors
`worker_config.provider`, `model`, and `model_parameters`, and supply accurate
usage. See [the experiment guide](../../docs/EXPERIMENTS.md).
