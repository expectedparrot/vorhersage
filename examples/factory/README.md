# Fictional portfolio acceptance walkthrough

This example drives the actual CLI in separate processes. It creates two
fictional binary questions, forecasts each with an agent and a 50% baseline,
registers new evidence, revises the first agent forecast, records outcomes,
and produces a matched evaluation. Every task response and authored input is saved.

From the repository root:

```bash
.venv/bin/python examples/factory/walkthrough.py /tmp/fresh-factory-portfolio
```

Use a new directory. The driver refuses to overwrite its input folder or an
existing Vorhersage project. Alternatively, inspect the already generated
[summary](output/summary.json), [evaluation](output/evaluation.json), and
[first question's report](output/factory_east_report.json).

The fixture agent has mean Brier loss 0.07625 versus 0.25 for its fixed 50%
baseline, on two matched questions. These deliberately authored outcomes and
probabilities verify arithmetic and selection behavior; they establish no
real forecasting skill. Outcome evidence is added after the forecasts issue.
