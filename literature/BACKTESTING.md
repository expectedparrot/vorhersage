# Backtesting opportunities for Vorhersage

Checked September 9, 2026. This is an access inventory and proposed experiment,
not a completed replication or a claim of forecasting accuracy.

## Reusable sources

| Source | What we can reuse | Suitable experiment | Access checked |
| --- | --- | --- | --- |
| Halawi et al., bibliography [8] | Formatted binary questions, resolution criteria, dates, outcomes, and community forecast histories | First importer; compare judgment methods and historical crowd baselines | Authors' [repository](https://github.com/dannyallover/llm_forecasting) links cleaned and raw datasets; inspected the [cleaned dataset viewer](https://huggingface.co/datasets/YuehHanChen/forecasting). Exact paper replication also needs its splits, forecast dates, and research inputs. |
| Autocast, [5] | Tournament questions, answers, crowd histories; a dated news corpus is documented | Temporal retrieval and updating experiments | [Repository](https://github.com/andyzoujm/autocast) documents fields and a download link. This session's web tool could not retrieve that linked file; no successful corpus download claimed. README specifies research-only hosting permission for Metaculus data; the code's MIT license should not be substituted for data terms. |
| ForecastBench, [11] | Historical question sets, resolution values, and submitted human/model forecasts | Reproduce historical scores; later replay resolved questions and join new prospective rounds | Official [data page](https://www.forecastbench.org/datasets/) lists these assets; [dataset repository](https://github.com/forecastingresearch/forecastbench-datasets) specifies CC BY-SA 4.0. Pin a commit because resolutions change. These downloads alone do not supply an archived web research environment. |
| BTF / BTF-2, [17, 21] | Resolved questions paired with frozen research environments | Closest match to evaluating the full research-and-judgment workflow | [BTF-2](https://arxiv.org/html/2604.26106v1) reports 1,417 questions. The original [BTF paper](https://arxiv.org/abs/2506.21558) directs researchers to contact FutureSearch for access. Public downloadable access to the complete BTF-2 corpus remains unconfirmed. |

The Halawi dataset viewer includes cases about affordable autonomous cars by
2018, a VIX reading above 50 during 2016, and a hyperloop demonstration by
mid-2017. These are paraphrases for identifying candidate exercises; preserve
the full criteria and source IDs on import. They illustrate useful variety,
but are already exposed to us and belong in the demonstration set, not a held-out
test. [Dataset viewer](https://huggingface.co/datasets/YuehHanChen/forecasting)

## Proposed first experiment

Start with 20 binary questions for debugging, then a separate, prespecified
100–200-question development comparison. These are practical initial sizes,
not statistical power guarantees. Keep related questions and repeated dates in
the same split. Audit overlap across datasets before treating one as held out.

Compare these conditions on the same questions and forecast dates:

1. The historical crowd forecast available at the cutoff, where available.
2. A simple model prompt with a fixed evidence packet.
3. Vorhersage's structured workflow with exactly that packet.
4. The structured workflow plus review, retaining the pre-review forecast.

Hold model version and compute budget constant where possible, otherwise report
their differences. This first comparison isolates judgment and review. A later
experiment can let agents search the same frozen corpus with equal budgets to
test research. Ensembling should also have an equal-cost baseline.

Use matched binary Brier scores, paired differences, coverage/failure counts,
and total cost. Repeated dates must not accidentally give one event extra weight.
Keep development and final test results separate. For uncertainty estimates,
resample related event groups, not individual forecast rows. ForecastBench's
leaderboard methodology must be reproduced separately if claiming its scores:
a simple resolved-only Brier mean is a different evaluation.

## Replay records and leakage controls

The importer should create two separate artifacts:

- **Agent input:** benchmark/revision, source question ID, question version and
  criteria, simulated forecast time, event group, evidence snapshot ID/hash,
  and a historical baseline only for conditions explicitly allowed to see it.
- **Evaluator input:** outcomes, resolution provenance and knowledge dates,
  withheld historical forecasts, cohort and scoring policy.

Use an allowlist to build agent inputs. Removing only an `answer` field is
insufficient: question updates, resolved status, comments, source URLs, later
crowd values, and retrospective summaries can reveal the outcome. Date-only
records need an explicit conservative timestamp convention. Store current
execution time separately from the simulated historical cutoff.

Frozen evidence prevents later retrieval; it does not erase outcomes from a
model's training. Prompting a model to pretend it is an earlier year does not
solve this. Record model identity, documented training cutoff where available,
and an explicit contamination assessment. Even relative workflow improvements
on historical cases can depend on memorized outcomes. Validate promising
changes prospectively before treating them as evidence of live forecasting skill.

Historical scoring of forecasts actually made before resolution is another
useful exercise: it can validate our evaluator without eliciting new predictions
about known outcomes. Authenticate original timestamps and preserve import time.

## Implementation status after the first replay exercise

The current [evaluator](../src/vorhersage/evaluation.py) requires actual
`issued_at` to precede the earliest recorded outcome `known_at`, including in
retrospective mode. Consequently, newly generated historical replays do not
become score-eligible merely by selecting that mode.

The dedicated `benchmark evaluate` path now supplies an explicit simulated
forecast timestamp, preserves actual issuance time, checks evidence cutoffs,
and labels results as historical replay. The ordinary evaluator's guard remains
unchanged. Imported crowd baselines retain their source-date convention and
are not represented as newly issued forecasts.

The Halawi importer, evaluator-only label files, replay scoring, and
[20-case software walkthrough](../examples/backtesting/README.md) are implemented.
All 20 constant-50% workflow controls issued successfully; 18 cases had eligible
crowd baselines. A [model pilot](../examples/backtesting/model_pilot_01/RESULTS.md)
then completed 80 question-only responses: 64 passed strict validation, and
five more were usable under a separate parsing diagnostic. Gemini 3.1 Pro's
structured prompt scored better on its complete 20-case pair, but reported
outcome recognition in 19/20 responses (plain: 18/20), preventing a clean skill
interpretation. Remaining work: audit historical wording and missing criteria;
assemble archived evidence; fix output formatting before scaling; validate
promising changes prospectively. File
separation is implemented, but an isolated agent execution environment is not.
