# Optional generic scenario calculation

```bash
.venv/bin/vorhersage scenario --from examples/workbench_extensions/mixture.json
```

The fictional readiness mixture yields 52%. Varying the declared assumption
bounds yields a 14–76% range; this is a sensitivity calculation, not a confidence
interval or evidence that a forecaster is accurate. No domain-specific states or
transition rules are built into the calculator.

The [extension guide](../../docs/RESEARCH_AND_MONITORING.md) documents capture,
source relationships, prior timing, implications, reference cases, and monitoring.
The subprocess acceptance test in `tests/test_extensions.py` demonstrates a
configured agent completing a monitored revision through issuance. All fixtures
are explicitly synthetic; no model or web service is invoked by the tests.
