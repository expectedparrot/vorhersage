# Vorhersage: a forecasting workbench for agents

**Implementation update, September 9, 2026:** version 0.1 now implements the
binary workflow, Epiq packets, review/revisions, monitoring, resolution and
evaluation. See the [agent guide](docs/AGENT_GUIDE.md) for actual commands and
limits. The proposal below is preserved as design history.

Proposal, September 8, 2026. The commands below describe a proposed package
interface. A [standalone Patriots simulation](examples/patriots_2027/README.md)
now exercises part of the workflow; the package itself is not implemented.

See [what we have learned](LEARNINGS.md) for the consolidated lessons and
corrections from the literature and forecasting exercise.

See [Superforecasting notes](SUPERFORECASTING.md) for the proposed capabilities,
experiments, and priorities for improving agent forecasting accuracy.
The [AI forecasting literature review](literature/README.md) adds a research
synthesis, annotated sources, and an evidence-based evaluation agenda.
See [the executable workflow proposal](WORKFLOW.md) for task schemas, state
transitions, algorithms, and the agent's repeated `next`/submit interaction.

Vorhersage helps an agent turn a question and researched evidence into a
probability, preserve revisions, and learn from resolved outcomes. The agent
researches and exercises judgment. The package maintains the record, checks
consistency, performs calculations, and supplies the next useful task.

## Patterns worth borrowing

| Local package | Observed pattern | Application here |
| --- | --- | --- |
| [Flyvbjerg](../flyvbjerg/README.md) | Registered captures, explicit evidence decisions, frozen reference-class analyses; agent owns research | Cite a base rate and its actual cases; preserve the evidence used for a forecast |
| [Epiq](../epiq/epiq/README.md) | SQLite history, source-backed claims, versioned JSON responses, schemas, exact argument arrays for next actions | Durable forecast revisions and an interface an agent can discover and resume |
| [Premortem](../premortem/README.md) | Guided failure analysis, structured research agenda, report context, portable EDSL Jobs | Ask how a forecast could fail and turn unresolved objections into research tasks |
| [Kahn](../kahn/README.md) | Explicit uncertainties, scenario narratives, state-dependent next actions | Describe alternate paths to an outcome and indicators that distinguish them |
| [Raiffa](../raiffa/README.md) | Decision trees consume conditional probabilities and support sensitivity analysis | Export forecasts with their conditions and provenance for downstream decisions |

Epiq's [forecasting-tournament example](../epiq/epiq/examples/cli/forecasting-tournament/README.md)
explicitly identifies gaps: selecting the latest submission per forecaster,
dynamic ensemble membership, resolution events, Brier scores, and calibration.
These provide a concrete starting point for a dedicated package.

Implementation references inspected include Flyvbjerg's `cli.py`, `workspace.py`,
and `edsl_bridge.py`; Epiq's `agent_interface.py`; and Premortem's `cli.py` and
`workflow.py`.

## The forecasting workflow

1. **Specify the question.** Record the event, observation window, timezone,
   deadline, exact YES/NO criteria, exclusions, and resolution sources. Assign
   a version so later wording changes cannot silently alter an earlier forecast.
2. **Establish an initial estimate.** Record a probability, rationale, and any
   reference class. A judgmental prior is valid if labeled as such; a claimed
   empirical base rate needs its denominator, selection rules, and evidence.
3. **Research the uncertainties that matter.** Register source captures and
   evidence for and against the event. Keep quotations, factual claims, and
   the agent's interpretation distinguishable. Record what remains unknown.
4. **Challenge the initial estimate.** Examine actors' incentives, institutional
   steps and delays, changes to the historical base rate, alternative paths,
   and reasons the forecast could be wrong in either direction.
5. **Issue a forecast.** Save the probability, evidence snapshot, initial estimate,
   review, forecaster identity, and explanation of the change. An unchanged
   probability is an acceptable result of review.
6. **Monitor and revise.** Specify update triggers and a next review date. New
   forecasts append to the history and explain what changed.
7. **Resolve and evaluate.** Record the outcome with evidence under the original
   criteria, then score an explicitly selected set of submissions.

The package should make this easy for one question and repeatable across a
portfolio. An initial forecast should remain possible with sparse evidence;
the record should expose that limitation.

## First-class records

| Record | Essential content |
| --- | --- |
| Question version | Text, criteria, window, deadline, timezone, domain, related-event cluster |
| Evidence | Source identity, excerpt/locator, capture hash, publication and retrieval times, claimed availability time, relevance and limitations |
| Snapshot | Exact question version, evidence IDs/hashes, information cutoff, creation time |
| Analysis | Initial probability, reference-class basis, actors and incentives, prerequisites, contrary evidence, alternate paths, unknowns |
| Review | Target analysis or forecast, concrete objection, relevant evidence, agent response, resulting change or reason for no change |
| Forecast | Question version, snapshot, probability in [0,1], forecaster/run identity, issue time, prior forecast ID, rationale, update triggers |
| Resolution | Question version, YES/NO/void/disputed status, outcome evidence, effective time, recording time, superseded resolution if corrected |
| Evaluation | Frozen forecast and resolution IDs, selection policy, exclusions, scores, comparison cohort |

Use server-generated recording times separately from user-supplied historical
times. A probability update and a correction to a malformed record are different
operations; both preserve the original record.

An actor analysis should capture who can act or veto, their stated position,
incentives, constraints, and evidence that distinguishes rhetoric from commitment.
A process analysis should capture required steps, current status, remaining time,
and catalysts that could accelerate or block progress.

## Agent interface

Borrow the local conventions: `guide`, `schema`, `status`, `next`, `validate`,
and `report context`; accept structured input files and return one versioned JSON
envelope with data, warnings, errors, artifacts, and next actions. Errors should
use nonzero exit codes. Keep diagnostics off the JSON output stream.

All commands should support explicit project selection. Next actions should carry
argument arrays, project context, input requirements, and mutation/network
metadata. Tasks that require the agent to research or exercise judgment should
say so and provide the expected result schema. Never present a placeholder
command as an immediately executable action.

Illustrative command sequence, assuming the agent has authored the input files:

```bash
vorhersage init ./forecast-study
vorhersage --project ./forecast-study question add --from question.json
vorhersage --project ./forecast-study evidence add --from evidence.json
vorhersage --project ./forecast-study snapshot create --from snapshot.json
vorhersage --project ./forecast-study analysis add --from analysis.json
vorhersage --project ./forecast-study review add --from review.json
vorhersage --project ./forecast-study forecast issue --from forecast.json
vorhersage --project ./forecast-study next
vorhersage --project ./forecast-study report context --question q_bill
```

Later, as new evidence arrives or the question resolves:

```bash
vorhersage --project ./forecast-study forecast revise f_initial --from revision.json
vorhersage --project ./forecast-study resolution add --from resolution.json
vorhersage --project ./forecast-study evaluate --from evaluation-policy.json
```

`next` should distinguish actionable work from waiting: an issued forecast with
no due trigger is ready for monitoring, not an invitation to research indefinitely.
Prioritize concrete gaps such as an unverified resolution criterion, an unanswered
objection, or a forecast whose registered evidence has changed. Let the agent
record a research budget and a reason to stop with an unresolved uncertainty.

## Numerical behavior

Start with binary questions and Brier score, `(p - y)^2`. Require an evaluation
policy selecting a common forecast cutoff or lead time and at most one eligible
submission per forecaster per question. Report missing forecasts and excluded
questions explicitly. Historical evaluation must distinguish issue time,
information availability, and when the result became known.

Repeated revisions must not give one forecaster extra weight. For ensembles,
select one submission per member under the same question version and cutoff,
save the exact membership and weights, and append a new ensemble when membership
changes. Repeated runs from one model should retain their shared model identity.

Calibration reports need bin counts and sample-size context. Comparisons should
use matched questions; questions concerning the same underlying event should
remain grouped when estimating uncertainty. Fitting calibration or ensemble
weights belongs on a declared training split, with evaluation on held-out data.

Analysis fields are aids to judgment. Checking an incentives box does not earn
an automatic probability adjustment. Multiplying component probabilities is valid
only with the necessary conditional probabilities or explicit independence
assumptions; unrelated marginal estimates cannot silently become a joint forecast.

## What the paper suggests testing

The supplied *Evaluating Strategic Reasoning in Forecasting Agents* paper makes
pre-mortems, other perspectives, incentives, and institutional processes useful
candidates for structured review. Its rationale comparisons do not establish
that adding those fields will improve accuracy.

A later experiment interface should compare a baseline with a reviewed forecast,
retain both, and record model, prompt, evidence snapshot, research budget, cost,
and run identity. Use fixed evidence to study judgment; separately vary research
to study information gathering. Randomize treatment or use independent matched
runs so extra inference and research are not confused with a review effect.
Preserve evaluation splits before tuning.

A frozen snapshot can make supplied evidence reproducible. It cannot establish
that a model lacks later training knowledge or that an externally driven agent
did not browse elsewhere. Record cutoff provenance and any isolation controls;
do not describe an ordinary snapshot export as a contamination-free benchmark.

## Package shape and delivery order

Use a small Python package with a Typer CLI, validated record schemas, a SQLite
store under `.vorhersage/`, and content-addressed local captures. Keep forecasting
calculations and validation callable independently of the CLI. Use transactions,
idempotency keys, and append-only issued records, with JSON exports for inspection
and portability. Hashes detect changed content; local storage is not external
proof that a forecast was submitted at a claimed historical time.

The first working slice should cover one binary question end to end: criteria,
evidence snapshot, initial analysis, challenge, issued forecast, revision,
resolution, Brier score, and report context. Include a fictional example and
tests for changed criteria, retrospective evidence, duplicate ingestion, invalid
probabilities, preserved revisions, and exact score calculations.

Next add portfolio monitoring, ensembles, calibration, and matched comparisons.
Then add optional EDSL Jobs export and Results import for repeated forecasts and
reviews. The driving agent owns model execution; imports should validate run and
question identities and distinguish failures from substantive answers.

Use portable artifacts to compose with Flyvbjerg, Epiq, Premortem, and Raiffa.
The [Patriots Epiq adapter](examples/patriots_2027/EPIQ_INTEGRATION.md) now tests
this boundary: shared research lives in Epiq, and a frozen packet supplies exact
inputs to Vorhersage's forecast state. It uses the CLI without direct SQL writes.
Start with simple file contracts rather than making all four packages mandatory
dependencies. Rich benchmark execution, numeric distributions, and automatic
recalibration can follow after the basic forecasting record is useful.
