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
