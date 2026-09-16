# Offline joint forecasting sessions

```bash
.venv/bin/python examples/joint_sessions/walkthrough.py /tmp/new-joint-session-project
```

Use a fresh output directory. The example exercises the CLI in separate processes:
two related fictional questions, three conditions (unconditional, intervention,
and a model-specific numeric condition), and four forecasters. It submits one
session incrementally, replaces a cell, retries safely, imports three sessions,
and computes complete and incomplete panel reports.

Inspect `inputs/`, `partial.json`, `retry.json`, `import-retry.json`, `sessions/`,
`coherence/`, `aggregation.json`, `incomplete-panel.json`, and `summary.json`.

Expected probability medians are 0.11 unconditionally and 0.06 under the intervention.
The paired geometric-median multiplier is approximately 0.70710678, which differs
from the ratio of those medians. Each session contains six final cells; imported
raw records and the native session's superseded cell remain inspectable.

No model calls, research, API keys, or paid services are used. These are software
fixtures, not AIRO data or evidence of forecasting ability. See the
[joint-session guide](../../docs/JOINT_SESSIONS.md) for schemas, timestamp semantics,
boundary handling, and limits.
