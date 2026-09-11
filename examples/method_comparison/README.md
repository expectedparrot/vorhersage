# Offline method comparison

```bash
python examples/method_comparison/walkthrough.py /tmp/vorhersage-method-comparison
```

Use a new output directory. This makes no model calls and requires no API keys.
It exercises two registered methods (direct judgment and conditional
decomposition), two fictional questions and two repetitions through separate CLI
processes. It deliberately pauses and resumes worker execution before resolving
the questions and saving an evaluation.

Expected result: eight forecasts, a clean `doctor` report, and mean Brier scores
of 0.25 for direct judgment and 0.26 for decomposition. These are deterministic
software checks, not estimates of forecasting skill.

Inspect `inputs/`, `started.json`, `partial.json`, `completed.json`,
`evaluation.json`, and `summary.json` in the chosen output directory. The methods
use the included `worker.py`; replace it with an agent worker to run an actual
forecasting comparison. See the [experiment guide](../../docs/EXPERIMENTS.md)
for registration schemas, worker contracts, scoring rules and limitations.
