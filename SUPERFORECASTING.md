# Notes on making Vorhersage support superforecasting

September 8, 2026. Working notes from the package-design discussion; these are
proposed capabilities and experiments, not implemented features or demonstrated
accuracy gains. See [DESIGN.md](DESIGN.md) for the underlying records and CLI.

## Objective

Help agents gather better evidence, form better probabilities, and learn from
resolved forecasts. Build a repeatable cycle:

**Forecast → resolve → evaluate → diagnose → change the method → test again.**

Success means sustained performance against strong baselines on new questions,
with comparable information, deadlines, and explicit resource budgets. An
auditable rationale is useful, but its completeness does not establish accuracy.

## Capabilities to develop

### 1. A forecasting practice ground

- Precisely defined questions, dated evidence snapshots, and separately stored
  outcomes.
- Development questions for experimentation, an untouched test set, and a live
  forecasting track.
- Reproducible records of question versions, evidence, models, prompts, methods,
  costs, and forecast times.
- Baselines including a defensible base rate, a simple single-agent forecast,
  and an equal-weight ensemble when available.

Test whether improvements survive new questions and later time periods. Frozen
evidence alone cannot remove knowledge acquired during model training. Group
questions about the same underlying event when splitting data and estimating
uncertainty.

### 2. An outside-view engine

- Use Flyvbjerg artifacts to find comparable cases and estimate base rates.
- Preserve inclusion rules, denominators, missingness, and dependence between
  cases.
- Ask why the cases are comparable and what makes the present case different.
- Compare plausible reference classes and show sensitivity to their selection.
- Label judgmental priors explicitly when an empirical reference class is absent.

Test whether an explicit outside view improves forecasts and whether adjustments
away from it help. Avoid treating a historical frequency as decisive after the
process generating that frequency has changed.

### 3. Research driven by competing explanations

- Identify plausible paths to YES and NO before searching.
- Ask which observable evidence would distinguish those paths.
- Track unanswered questions, contrary evidence, source quality, and shared
  underlying sources.
- Preserve publication time, retrieval time, and the basis for claimed historical
  availability.
- Record a research budget, stopping reason, and unresolved uncertainties.

For a threatened strike, research progress on concessions and the union's decision
process alongside its public threats. Multiple articles repeating one press
release are one underlying signal. Measure the incremental benefit of research
at comparable budgets.

### 4. Models of actors, processes, and time

- Actors: objectives, incentives, constraints, veto power, stated positions, and
  evidence about whether statements are commitments or bargaining positions.
- Processes: prerequisites, current stage, remaining steps, plausible delays, and
  the time available before the question's deadline.
- Catalysts: changes that could accelerate, block, or otherwise alter the process.
- Distinguish sourced facts from the agent's interpretation of motives.

The supplied paper motivates this capability with two cases: a strike threat
treated as a commitment, and legislative inertia weighted heavily despite a new
political incentive associated with hosting COP30. These are useful diagnostic
examples, not a sufficient test set for the feature.

### 5. Independent estimates and targeted challenge

- Collect initial estimates before exposing forecasters to one another's answers.
- Preserve model, run, prompt, and evidence identities so shared dependencies are
  visible.
- Classify disagreements: facts, question interpretation, reference class,
  assumptions, or probability judgment.
- Ask what could make the estimate too high and too low; tie objections to
  concrete mechanisms or evidence.
- Retain pre-review and post-review probabilities, including justified decisions
  to leave an estimate unchanged.
- Compare individual forecasts, simple averaging, and any more elaborate
  aggregation on held-out questions.

Test whether review improves predictions beyond the benefit of extra inference
or research. Repeated runs and different persona prompts do not establish
independent sources of information.

### 6. Disciplined updating and probability checks

- Explain what new evidence or changed assumption caused each revision.
- Register update triggers, review dates, and relevant expected milestones.
- Check logical relationships between probabilities. For the same event under
  otherwise identical criteria, probability by June cannot exceed probability
  by December.
- Keep conditional and unconditional probabilities distinct. Require explicit
  assumptions for joint calculations.
- Monitor missed milestones when the forecast's process model makes their
  absence informative.

Evaluate whether revisions improve scores under a fixed selection policy. Count
at most one eligible forecast per forecaster and question for that comparison;
frequent updating should not automatically increase a forecaster's weight.

### 7. A memory of forecasting performance

- Track accuracy and calibration by domain, horizon, model, and method, with
  sample counts and uncertainty.
- Retrieve relevant past cases with their original evidence and forecasts.
- Diagnose recurring errors across multiple questions: excessive confidence,
  anchoring, stale base rates, missed incentives, or weak interpretation of
  resolution criteria.
- Separate outcome surprise from an error detectable using information available
  at forecast time. A sound 20% forecast will sometimes resolve YES.
- Test any learned calibration adjustment on later or held-out data, retaining
  the unadjusted forecast as a comparator.

Review selected successes as well as failures to catch correct answers reached
for weak reasons. Treat suggested lessons as hypotheses until they generalize.

### 8. Experiments on the forecasting process

- Compare baseline forecasting with reference-class support, incentive analysis,
  pre-mortems, additional research, and ensembles.
- Hold evidence fixed when studying judgment; vary research separately when
  studying information gathering.
- Use randomized treatment or independent matched runs where appropriate.
- Account for differences in inference budget, research budget, model, and prompt.
- Freeze evaluation policies and test sets before tuning methods or weights.
- Preserve failures, missing submissions, exclusions, and exact comparison cohorts.

The central product question is: which intervention improves forecasts enough to
justify its cost? Rationale length, checklist completion, and agreement between
agents are not substitutes for that measurement.

## Build priorities

1. **Complete one forecasting cycle.** Question, evidence snapshot, initial
   analysis, review, issued forecast, revision, resolution, Brier score, and
   report context. Use a fictional fixture to verify behavior.
2. **Make evaluation repeatable.** Frozen cohorts, explicit submission cutoffs,
   baselines, held-out questions, and a live track. Establish this before tuning
   elaborate forecasting workflows.
3. **Add the first improvement methods.** Reference-class support, independent
   forecasts, and structured challenges. Preserve intermediate forecasts so their
   incremental effects can be studied.
4. **Add ongoing learning.** Monitoring, calibrated aggregation, case retrieval,
   and method comparisons as enough resolved questions accumulate.

The agent owns research and judgment. Vorhersage owns state, validation,
calculations, task guidance, and evaluation. Optional EDSL Jobs can support
repeated runs while the driving agent handles model execution.

## Evidence informing these notes

- Liptay et al., *Evaluating Strategic Reasoning in Forecasting Agents* (2026),
  supplied as `/Users/johnhorton/Downloads/forcasting.pdf`. The paper reports an
  advantage for its combined forecasting system and differences in reasoning
  emphasis. Its limitations include potential benchmark overfitting and rationale
  structure affecting the comparison. It motivates experiments with pre-mortems,
  perspectives, incentives, and institutional processes; it does not establish
  that adding those fields causes improved agent accuracy.
- [Mellers et al., *Psychological Strategies for Winning a Geopolitical
  Forecasting Tournament* (2014)](https://www.psychologicalscience.org/journals/psychological-science/0956797614524255/)
  reports benefits from probability training, team collaboration, and tracking
  human forecasters' performance. Those findings motivate analogous agent
  experiments, with transfer to agents remaining an empirical question.
- [Chang et al., *Developing expert political judgment* (2016)](https://sjdm.org/~baron/journal/16/16511/jdm16511.html)
  reports 6–11% improvements in Brier scores from brief forecasting training in
  human tournaments. This supports testing structured forecasting guidance, not
  assuming the same effect size for LLMs.

## Open design questions

- Which initial question domains and horizons provide useful outcomes soon enough
  to support learning?
- What is the smallest useful evidence packet for an independent forecaster?
- Which reference-class and forecast artifact contracts should connect Vorhersage
  to Flyvbjerg and Raiffa?
- How should the workflow prioritize the next research task under a fixed budget?
- When does the available track record justify domain-specific calibration or
  ensemble weights?
- What evidence would establish that a learned lesson transfers beyond the cases
  that suggested it?
