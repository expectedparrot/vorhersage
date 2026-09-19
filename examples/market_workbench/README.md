# One-question research demonstration

Open [demo.html](demo.html) for a complete fictional research trajectory:
50% initial → 72% after a readiness check → 65% after reference-class research,
then reveal a 70% opening target. A later 74% quote is labeled separately.

All evidence and probabilities are fictional. This exercises the CLI without
network access or a model, and demonstrates that a research step can move the
estimate away from the target without proving the research was unhelpful.

Run into a new directory:

```bash
.venv/bin/python examples/market_workbench/walkthrough.py /tmp/my-workbench-demo
```

The directory contains separate researcher and evaluator projects, all input
JSON, a report before reveal, a comparison after reveal, and an integrity check.
See the [workbench guide](../../docs/MARKET_WORKBENCH.md) for live markets.

## Live cases

- [September CPI](cpi_202609/README.md): 66.9% forecast versus 98.5% opening midpoint; current gasoline data and a substantial uncertainty-model mismatch.

- [NYC, September 16](nyc_20260916/README.md): 28.6% forecast versus 28% opening midpoint.
- [Chicago Midway, September 17](chicago_20260917/README.md): 24.4% versus 36.5%; predeclared residual estimator and a substantial dispersion disagreement.

These compare sealed estimates with market snapshots; they do not establish accuracy.
