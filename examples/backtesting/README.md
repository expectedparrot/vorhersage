# Historical replay: first executable benchmark example

This example imports real historical questions and runs a constant-50% control
through the full Vorhersage workflow. **It makes no model forecasts.** It checks
the importer, task loop, immutable issuance, and separate replay evaluator.

The [first model comparison](model_pilot_01/RESULTS.md) is complete:
80 interviews, 64 strictly valid forecasts, and a separate parsing diagnostic.
Outcome recognition is common, limiting conclusions about forecasting skill.

The [saved summary](smoke_output/summary.json) contains:

| Forecaster/control | Available cases | Common cases | Common Brier |
| --- | ---: | ---: | ---: |
| Workflow constant 50% | 20 | 18 | 0.250000 |
| Evaluator constant 50% | 20 | 18 | 0.250000 |
| Historical crowd | 18 | 18 | 0.189758 |

The crowd-minus-control difference is about -0.0602 on this small development
cohort. It is descriptive, not evidence about Vorhersage's predictive skill.
Two cases have no eligible historical crowd observations. No missing forecast
is silently replaced with 50%.

## Source and selection

Source: the authors' [Halawi et al. dataset](https://huggingface.co/datasets/YuehHanChen/forecasting),
revision `c88acc8705f03c8a6526b0b057200c1f0b1b8505`, `validation.json`.
The repository declares Apache-2.0 in its dataset metadata. Citation: Danny
Halawi, Fred Zhang, Yueh-Han Chen, and Jacob Steinhardt, *Approaching Human-Level
Forecasting with Language Models*, NeurIPS 2024.

The downloaded file has 840 rows, including multiple-choice records. We retain
resolved binary rows in the selected categories whose platform close and
resolution dates follow the simulated cutoff. Rank eligible questions by a hash
of the seed and source URL, then take 20. No winner/loser balancing is applied.
The original test split was not downloaded.

For this run, the allowed categories were Science & Tech, Sports, Environment &
Energy, and Arts & Recreation. There were 146 eligible rows; the selected cohort
contains 12 sports, 6 science/technology, and 2 environment/energy questions.
The [manifest](halawi_validation_20/manifest.json) records source hashing,
selection counts and every excluded row's reason.

Cutoff: 00:00 UTC seven days after the question's opening date. Date-only crowd
observations become available at the end of their recorded day. The baseline
averages all observations from the latest eligible day because their intraday
order is not certified. This is our comparison convention, not a replication
of the paper's full evaluation protocol.

Five selected questions lack separate criteria. The adapter flags them and
inserts an explicit review requirement. Question wording and criteria may have
later edits. Platform close dates are metadata, not verified event deadlines.
Background text and extracted URLs are withheld; no archived research evidence
has been imported. Audit these issues before a substantive experiment.

## Reproduce in fresh directories

Run from the repository root:

```bash
curl -L --fail --silent --show-error \
  https://huggingface.co/datasets/YuehHanChen/forecasting/resolve/c88acc8705f03c8a6526b0b057200c1f0b1b8505/validation.json \
  -o /tmp/halawi-validation.json

.venv/bin/vorhersage benchmark import-halawi \
  --from /tmp/halawi-validation.json --out /tmp/halawi-replay-bundle \
  --revision c88acc8705f03c8a6526b0b057200c1f0b1b8505 --split validation \
  --limit 20 --seed vorhersage-1 --days-after-open 7 \
  --category 'Science & Tech' --category Sports \
  --category 'Environment & Energy' --category 'Arts & Recreation'

.venv/bin/python examples/backtesting/smoke.py \
  /tmp/halawi-replay-bundle /tmp/halawi-replay-project
```

The input file SHA-256 for this saved run is
`589a966ea2051d950d3704f30bf4a3686ac09a72dbd10b42fe4a96ca39549de6`.
The importer refuses to overwrite an existing output directory. The walkthrough
also requires a fresh project directory.

## Run an actual forecaster

Give the forecasting process only `agent/cases.json` and any separately audited
historical evidence packets. Keep `evaluator/`, the raw source file, saved scores,
and previous experiment traces out of its accessible environment. Directory
separation here is not an enforced security boundary.

Initialize a fresh project, then start each case:

```bash
.venv/bin/vorhersage --project /tmp/my-replay init
.venv/bin/vorhersage --project /tmp/my-replay benchmark start \
  --cases /tmp/halawi-replay-bundle/agent/cases.json \
  --case CASE_ID --forecaster agent:fixed_evidence --method fixed-evidence-v1
```

This creates a real question and fixed retrospective run with zero searches and
zero extra research tasks. Use normal `next` and `submit` commands for research
and judgment. Imported packets must satisfy the historical cutoff. Missing
evidence must be represented as unknown. The current replay starter is for
fixed-evidence comparisons; it supplies neither a search archive nor model calls.

After issuing all forecasts, prepare a `replay_evaluation` policy with explicit
`forecast_ids`, `forecasters`, `experiment`, and `contamination_assessment`.
Forecasters may include `baseline:half` and `baseline:crowd`; these reserved
baselines are calculated by the evaluator and are not stored as issued forecasts.
The [saved policy](smoke_output/evaluation_policy.json) is a concrete example.

```bash
.venv/bin/vorhersage --project /tmp/my-replay benchmark evaluate \
  --cases /tmp/halawi-replay-bundle/agent/cases.json \
  --labels /tmp/halawi-replay-bundle/evaluator/labels.json \
  --manifest /tmp/halawi-replay-bundle/manifest.json \
  --from /tmp/my-replay-policy.json
```

The evaluator rejects duplicate case/forecaster revisions, wrong question
versions, wrong cutoffs, and changed bundle hashes. It freezes the chosen
forecasts and complete evaluation inputs in a `replay_evaluation` artifact.
Inspect with `replay_evaluation show ID` or `doctor`.

Actual `issued_at` timestamps remain current. `simulated_forecast_at` is an
explicit replay field. Ordinary `evaluate` still excludes new forecasts issued
after known outcomes. Historical results never become prospective results.

The saved [evaluation](smoke_output/evaluation.json) and
[CLI transcript](smoke_output/transcript.json) expose outcomes and belong to the
evaluation side of future experiments. This cohort is now a demonstration set.
