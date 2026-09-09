# Initial prospective research queue

Three real questions are registered in the local `project/` directory:

1. New England qualifies for the 2026-season playoffs.
2. New England wins the AFC for the 2026 season.
3. New England wins Super Bowl LXI.

They share event group `nfl_2026`. They are useful related test cases, not three
independent observations of forecasting skill. All use the team-championship
research profile. The March 31 resolution deadline is a backstop; official
results should be recorded promptly when known.

No probabilities have been issued. The [saved queue](project/research_queue.json)
contains each question and run ID. Begin from the repository root:

```bash
.venv/bin/vorhersage --project examples/live_portfolio/project status
.venv/bin/vorhersage --project examples/live_portfolio/project next --run run_48418f18ff3848d497a5
```

That run begins with the playoff question's prior. The subsequent tasks require
drivers, previous performance, quarterback, coaching, roster changes, schedule,
health, assessment and review. Prospective cutoffs advance on accepted submissions
so the agent can research while the run is active. The initial cutoff is retained.

To register a fresh copy elsewhere:

```bash
.venv/bin/python examples/live_portfolio/seed.py /tmp/new-live-portfolio
```

Use an unused project path. The script registers questions and starts tasks; it
does not fetch facts, supply probabilities or create outcome labels. If these
questions have already resolved when rerunning this example, use a new cohort
for prospective work or explicitly use retrospective mode for historical study.
