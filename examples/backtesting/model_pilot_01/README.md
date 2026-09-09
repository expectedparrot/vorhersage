# Model pilot 01: completed

All 80 interviews completed on September 9, 2026, for about $1.13. The strict
importer accepted 64 forecasts; a separately labeled JSON-block diagnostic
accepted 69. See [results and interpretation](RESULTS.md) and the
[machine-readable summary](summary.json). Most parsed responses report
recognizing the historical outcome; this is not a clean forecasting skill test.

Remote job: `ce56feeb-f4bc-4275-a771-d32303453150`. The [submission](submission.json),
[completion receipt](completion.json), [original responses](results.ep),
[strict evaluation](evaluation.json), and [post-hoc evaluation](posthoc_evaluation.json)
are retained. No model calls were rerun to repair answers.

The [registration](registration.json) freezes 80 planned interviews:
20 questions × 2 prompt conditions × 2 models. Models are Gemini 2.5 Flash and
Gemini 3.1 Pro Preview through Expected Parrot's Google service. Both were
present in its working-model catalog when prepared. Each uses temperature 0.2,
an 8,192-token output cap, and the other parameters recorded in the registration.
No model fallback or experiment-level retries are configured.

- **Plain:** probability, short rationale, and outcome-recognition self-report.
- **Structured:** prior, drivers, outcome paths, unknowns, assessment, and
  review in both directions, plus the same recognition self-report.

Each condition is one independent completion. The structured condition records
the model's fields through Vorhersage's task loop after inference. It is not a
multi-step research agent, and this experiment cannot measure retrieval quality.
Both conditions have the same output cap, not necessarily equal actual cost.

Only the question, YES/NO criteria, cutoff, and missing-criteria flag are embedded
in prompts. No source URLs, outcomes, crowd values, files, or tools are sent to
the models. The [requests](requests.json) are reviewable, and the
[jobs](jobs.json) passed `ep validate --type job`. Historical knowledge in model
training remains uncontrolled; self-reports of recognition cannot certify its
absence. This is the already exposed development cohort, not a held-out test.

## Reproduction

Use valid Expected Parrot credentials and fresh output paths for a new run.
The saved project directories below already exist and are protected against
accidental overwrite. The commands describe how this pilot was executed.

From the repository root:

```bash
ep jobs cost examples/backtesting/model_pilot_01/jobs.json

ep run --jobs examples/backtesting/model_pilot_01/jobs.json --background \
  --remote_inference_results_visibility private \
  --remote_inference_description 'Vorhersage pilot 01: question-only historical replay'
```

Save the returned job UUID and receipt. Fetch the completed results with:

```bash
ep jobs wait JOB_UUID
ep jobs results JOB_UUID --output examples/backtesting/model_pilot_01/results.ep
ep results cost examples/backtesting/model_pilot_01/results.ep

.venv/bin/python examples/backtesting/model_runs.py import \
  --prepared examples/backtesting/model_pilot_01 \
  --results examples/backtesting/model_pilot_01/results.ep \
  --project examples/backtesting/model_pilot_01/project

.venv/bin/vorhersage --project examples/backtesting/model_pilot_01/project benchmark evaluate \
  --cases examples/backtesting/model_pilot_01/cases.json \
  --labels examples/backtesting/halawi_validation_20/evaluator/labels.json \
  --manifest examples/backtesting/halawi_validation_20/manifest.json \
  --from examples/backtesting/model_pilot_01/project/evaluation_policy.json
```

The importer rejects changes to registered prompts or model parameters, and
rejects duplicate/unexpected interviews. Malformed answers are reported as
failures; they are not repaired or replaced with 50%. It retains raw model
records and hashes in forecast method provenance. Actual workflow issuance is
the import time; model invocation timing remains in the saved EDSL records.

Known EDSL `forecast_cost` values enter the workflow once per interview.
Unavailable costs have explicit flags in the import report and zero placeholders
in workflow state. Do not interpret those placeholders as free inference.

The separate diagnostic import used `--allow-surrounding-prose` and a fresh
`posthoc_project` directory. It extracts exactly one fenced JSON object, rejects
ambiguous/malformed answers, and labels its forecasts and evaluation as post-hoc.
The original strict project and evaluation remain unchanged.

Regenerate the report without making model calls:

```bash
.venv/bin/python examples/backtesting/analyze_model_pilot.py examples/backtesting/model_pilot_01
```

Report matched comparisons, all missing/invalid responses, recognized-outcome
counts, and the five cases lacking separate criteria. Avoid attributing a score
difference to live forecasting skill or equal compute. Keep label files and
evaluation reports out of later model prompts.
