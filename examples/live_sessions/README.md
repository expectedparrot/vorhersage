# Live session fixture

[Open the generated comparison](comparison.html) · [Execution summary](summary.json)

Run `python examples/live_sessions/walkthrough.py /tmp/new-live-study` from the
repository root. It uses the generic session/study APIs and a JSON subprocess
worker to exercise two arms × two repetitions, staged evidence, waiting/polling,
finalization, HTML comparison, and unconditional Brier evaluation.

Every observation, forecast, usage amount, and outcome is synthetic. There are no
provider calls. Expected arm Brier scores after the fictional yes outcome are
0.5625 and 0.0625; total reported fixture cost is $0.10 across eight model attempts
and four tool attempts. Polls do not add attempts.

See [the worker contract](../../docs/LIVE_SESSIONS.md) to supply your own model
and research workers. The original AIRO records are not altered by this example.
