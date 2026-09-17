# What we have learned about agent forecasting

**Implementation update:** the first general binary package is now built. See
the [README](README.md) and [agent guide](docs/AGENT_GUIDE.md) for its current
capabilities; references below to an unimplemented package describe earlier
stages of the discussion.

Working synthesis, September 9, 2026. This consolidates the literature review,
package discussion, and Patriots exercise. Proposed designs and subjective
forecast judgments are identified below; neither the prototype nor this review
establishes superforecaster-level accuracy.

## 1. The central lesson

**An agent can complete every procedural step and still omit the substance of
the forecasting problem.**

Our first Patriots run defined the event, recorded a prior, gathered odds,
checked injuries, reconciled conflicting sources, calculated a probability,
reviewed it, and issued a reproducible artifact. But it did not investigate last
season, the quarterback, coaching, roster turnover, or schedule. Its 4.27% was
a market baseline. Calling that our best estimate overstated the analysis.

The user's objection exposed a product requirement: the workflow must specify
what needs investigation for the question, as well as how to record the results.
A generic instruction to research the question is insufficient. Equally, adding
more required headings is not proof of better forecasting. Coverage should be
auditable, and its effect on accuracy must eventually be measured.

Three kinds of success therefore need separate tracking:

| Kind | What would establish it? |
| --- | --- |
| Operational correctness | Valid records, repeatable calculations, preserved history, reliable resumption |
| Substantive adequacy | Relevant uncertainties investigated, sources assessed, alternatives and omissions addressed |
| Predictive skill | Better scores on new resolved questions against comparable baselines |

The prototype demonstrates parts of the first and helps inspect the second.
It has not established the third.

## 2. What the literature supports—and leaves open

The [literature collection](literature/README.md) contains 39 annotated sources,
with reading depth and limitations recorded. It is a substantial initial review,
not an exhaustive systematic review, and we have not reproduced its studies.

The strongest general lesson is to measure the whole forecasting system:
question selection, information access, research, probability formation,
aggregation, updating, and resolution. A model name alone does not describe the
system being evaluated. Event probabilities also need to be distinguished from
numerical time-series prediction, weather forecasting, and other specialist tasks.

The reviewed work makes evidence retrieval, simple ensembles, explicit belief
states, and calibration reasonable candidates to test. Their usefulness depends
on the questions, information available, models and resource budgets. More
agents, more text, or more reasoning steps do not imply better predictions.
See the review's [methods and evidence](literature/REVIEW.md).

The supplied Liptay et al. paper, *Evaluating Strategic Reasoning in Forecasting
Agents*, motivates review of incentives, institutional processes, alternative
perspectives, and failure paths. Its case studies suggest concrete questions:
is a public threat a commitment or bargaining tactic, and has a new incentive
changed the relevance of historical delay? Its rationale analysis does not show
that adding those fields causes better forecasts. Benchmark overfitting and the
way rationales are formatted remain concerns.

Claims about matching humans or beating markets require careful comparison:
matched questions, common forecast horizons, actual outcomes, dependence between
questions, and uncertainty around score differences. Agreement with a market
price on an unresolved event is not outcome accuracy. Historical evidence
snapshots also cannot establish that a model lacks later training knowledge.
These issues are detailed in the [evaluation review](literature/REVIEW.md#10-evaluation-failures-and-resolution-quality).

## 3. What to take from FutureSearch

FutureSearch presents a forecasting service with multiple output types, agent
access, research tooling, and public evaluation and trading pages. That suggests
a useful product shape: agents should be able to request a forecast as a tool
and inspect its supporting work. These are observations of its public offering,
not verification of its performance claims or internal architecture.
[Public site, checked September 9, 2026](https://futuresearch.ai/)

The reusable-findings database and maintained world model discussed here are
design ideas for Vorhersage. We should not describe our proposed schema as
FutureSearch's implementation. The transferable question is whether research
can improve multiple forecasts rather than being discarded after one answer.

The supplied paper concerns BTF-2. A current product or evaluation page may
describe later systems; those versions must remain distinct in our notes and
comparisons.

## 4. The right division of labor

**The agent researches and judges; the package maintains state, computes,
validates, and guides the next action.**

The package can count reference-class outcomes, multiply explicitly supplied
conditional probabilities, normalize a price board, find affected forecasts,
and calculate scores. It cannot infer valid causal effects merely because a
finding mentions a new coach or player. A graph of dependencies is not
automatically a probabilistic model.

Local packages suggest useful patterns: Flyvbjerg for auditable reference classes,
Epiq for evidence history and agent interfaces, Premortem for targeted challenge,
Kahn for scenarios, and Raiffa for downstream decisions. Use small artifact
contracts before requiring all of them as dependencies. The inspected patterns
and proposed interfaces are recorded in [DESIGN.md](DESIGN.md).

## 5. Three kinds of durable memory

One undifferentiated collection of prose would mix claims with predictions and
lessons. Keep these logically separate, even if they share one SQLite database:

| Memory | Example | Appropriate use |
| --- | --- | --- |
| World findings | A coordinator already called the defense before being promoted | Reuse as sourced context for related forecasts |
| Forecast history | A dated 6.048% judgment with exact evidence and assumptions | Reconstruct, revise, resolve and score the forecast |
| Method lessons | A hypothesis that net roster analysis improves forecasts | Design a future experiment; do not treat it as established advice |

A finding records an attributed claim. It is not automatically true, independent
of other findings, or a numerical probability adjustment. Several articles may
repeat the same announcement. Conflicting claims should coexist with links
explaining the conflict; a correction should not erase the original record.

A method lesson should preserve its origin, affected cases, proposed mechanism,
exceptions, and validation status. One surprising outcome does not establish a
forecasting mistake. A sound 20% prediction will sometimes resolve YES.

## 6. A practical data structure

Use relational core records with typed links and JSON for bounded structured
payloads. Keep large source captures in content-addressed files. A separate graph
database is not a prerequisite: edge tables can express dependencies and
contradictions. Start with entity, time, and text retrieval; evaluate semantic
search later.

| Record | Essential information |
| --- | --- |
| QuestionVersion | Exact event, criteria, horizon, cutoff, resolution source, related-event group |
| SourceCapture | URL, actual captured content or observation, hash, locator, publication and capture times, capture limitations |
| Finding | Attributed claim, entities, time scope, evidence links, qualifications, recording time |
| FindingRelation | Supports, contradicts, corrects, derives from, or shares a source origin |
| ReferenceClass | Selection rule, included cases, exclusions, outcomes, denominator, comparability limitations |
| Driver / Assumption | Mechanism or prerequisite, supplied value if any, rationale, finding references, estimation method |
| ResearchCoverage | Required domain, assessed/unknown status, findings, interpretation, remaining gap |
| BeliefRevision | Probability, previous belief, changed findings or assumptions, calculation and rationale |
| Forecast | Issued belief, immutable input manifest, method/run identity, issue time, review triggers |
| ResolutionRevision | Resolved/void/disputed status, outcome evidence, effective and recording times, corrections |
| Evaluation | Eligible forecast and resolution IDs, scoring policy, cohort, exclusions, results |
| MethodLesson | Proposed lesson, supporting cases, counterexamples, test status and evaluation references |

`Run`, `Task`, and `TaskResult` provide orchestration around these records. The
[workflow proposal](WORKFLOW.md) specifies their fields and submission behavior.

An illustrative reusable finding—not an implemented general schema:

```json
{
  "id": "finding_coaching_continuity_v1",
  "claim": "The promoted coordinator already called the defense last season.",
  "entity_ids": ["team_ne", "coach_kuhr"],
  "time_scope": {"season": 2026, "comparison_season": 2025},
  "evidence_ids": ["capture_coach_biography"],
  "qualifications": ["Does not quantify the effect on team performance."],
  "supersedes": null
}
```

Keep the forecast-specific interpretation elsewhere: “This is evidence of
continuity, so do not treat the promotion as a wholesale scheme change.” Another
question can use the same finding differently.

Separate when something happened, when a source published it, when we captured
it, and when we issued a forecast. Unknown dates remain unknown. A content hash
proves identity of saved content, not historical public availability.

## 7. How findings get reused

Suppose a question asks whether New England will win its division, after we have
researched its Super Bowl prospects. The agent can retrieve findings about the
team's quarterback, staff, roster and schedule under the new question's cutoff.
It then checks freshness and relevance, researches division-specific competitors,
and forms a new forecast. Reuse saves research; it does not transfer the previous
title probability to a different event.

If a later report changes an important injury assessment, append a new finding
and link it to the earlier one. Reverse dependency lookup identifies forecasts
that used it and creates review tasks. The original forecasts remain fixed until
new revisions are accepted. A source change does not itself determine the size
or direction of a probability update.

Retrieval should show disagreements, qualifications and common source origins,
not just the most semantically similar sentences. Historical replay must exclude
later findings and preserve the exact evidence actually supplied.

## 8. How large the findings database might become

Storage depends more on retained source material and versions than on the number
of concise claims. These are planning calculations, not measurements of the
prototype or anyone else's database:

| Findings | At 2–10 KB per structured finding |
| ---: | ---: |
| 10,000 | 20–100 MB |
| 100,000 | 0.2–1 GB |
| 1,000,000 | 2–10 GB |

These decimal-size estimates exclude indexes, edges, source archives, embeddings,
backups and database overhead. One million 1,536-dimensional float32 vectors
would add 6.144 GB before indexing. At an assumed 100 KB per archived document,
100,000 unique documents add 10 GB. Documents and findings have a many-to-many
relationship, so deduplicating captures matters.

Annual new findings can be planned as:

```text
questions/year × findings/question × fraction genuinely new
```

For example, 10,000 questions × 30 findings × 50% new produces 150,000 new
findings, before corrections and later updates. The harder early problems are
relevance, freshness, provenance and evaluation—not storing the text. Measure
actual record sizes and retrieval behavior before committing to larger systems.

## 9. Procedures the agent should follow

The desired operating loop is `next → perform task → submit → next`. Each task
must include its purpose, exact inputs, expected result structure, completion
conditions and remaining budget. The agent should resume from saved state
without reconstructing the conversation.

1. Define the event precisely, including season versus calendar year and voids.
2. Identify an outside view and record whether it is empirical or assumed.
3. Map important drivers, prerequisites and paths to both YES and NO.
4. Create required research domains appropriate to the question.
5. Gather and interpret evidence, including contrary findings and net changes.
6. Form explicit judgments or use a suitable specialist model; label the method.
7. Challenge the estimate with concrete objections in both directions.
8. Check numerical consistency and source/version references.
9. Issue with limitations, a stopping reason and update triggers.
10. Monitor, revise, resolve and evaluate under an explicit policy.

A research domain is complete when assessed with evidence and interpretation,
or explicitly unknown with a reason. An inconclusive search is legitimate. It
should neither force an invented answer nor satisfy a requirement for verified
evidence. Where unknowns remain, downstream judgment must see them.

Use budgets and reserve time for synthesis. Prioritize questions whose answers
could change the forecast. Any numerical estimate of research value is itself
an assumption until tested. Review can legitimately leave the probability
unchanged. Completing a checklist never earns an automatic probability bonus.

## 10. Where algorithms actually help

| Operation | Initial algorithm or mechanism | Judgment still required |
| --- | --- | --- |
| Choose next work | Stable prerequisite traversal, priority rules, budget checks | Which uncertainties matter |
| Accept results | Typed validation, transaction, state revision, idempotency key | Whether the research is persuasive |
| Retrieve findings | Entity/time/text filters, exact deduplication | Relevance and shared source origins |
| Establish base rates | Select declared cases, count outcomes, compare windows | Comparability and selection rules |
| Calculate a forecast | Evaluate explicit conditionals or supplied model outputs | Parameters and applicability |
| Check coherence | Probability bounds, sums, nested-event inequalities | Whether the declared relationship holds |
| Monitor | Time triggers and reverse dependency lookup | Whether evidence warrants revision |
| Evaluate | Select eligible forecasts, calculate losses and matched differences | Resolution interpretation and lesson validity |

Do not turn a dependency graph into automatic Bayesian updating. Likelihood
ratios require defensible estimates, and dependent evidence cannot be multiplied
as though independent. The same caution applies to ensembles: repeated runs or
different personas do not establish independent errors.

## 11. Lessons from the Patriots simulation

The question is winning Super Bowl LXI, the championship concluding the 2026
season. Both runs preserve an unresolved outcome. Full sources and football
details are in the [researched assessment](examples/patriots_2027/RESEARCHED_ASSESSMENT.md).

The first run's normalized market estimates were 3.97% and 4.57%, averaged to
4.27%. The corresponding raw prices, +2000 and +1700, imply 4.76% and 5.56%.
Bookmaker margin explains why these are different comparisons. Proportional
normalization is an assumption, not uniquely correct de-vigging. Captures also
contained disagreements between page elements, and exact quote times were
unknown. Preserve those disagreements rather than silently picking a convenient
number. [Original calculation](examples/patriots_2027/README.md#where-the-estimate-comes-from)

The second pass added previous performance, quarterback, staff continuity,
net roster turnover, protection problems and schedule. Specific lessons were:

- A previous strong season must enter the analysis; team symmetry is a weak
  substitute for an available empirical record.
- A hiring announcement can describe continuity rather than a new regime.
- A star arrival must be assessed alongside the player and role being replaced.
- A vulnerability exposed in the playoffs deserves investigation without
  treating one game as a complete estimate of underlying strength.
- Schedule rankings based on prior-year records are not realized schedule
  strength or a forecast of opponents' future strength.
- An opening-game absence does not establish a season-long impairment.

The researched run used:

```text
P(title) = P(playoffs) × P(AFC champion | playoffs) × P(title | AFC champion)
         = 0.70 × 0.18 × 0.48
         = 0.06048
```

This is a valid conditional identity, not an independence assumption. But all
three input probabilities were subjective and unfitted. Linked facts make the
judgments inspectable; they do not uniquely imply those numbers. The 2.88% and
11% sensitivity scenarios are illustrative alternatives, not confidence bounds.

A historical runner-up reference class yielded one next-season champion in
25 cases, or 4%; the last ten eligible cases yielded 10%. That instability is a
useful warning about small, selected reference classes. Neither rate settles
the Patriots question, and the conditional product does not mechanically use
the reference-class frequency.

The second estimate was made after seeing the market. It cannot be called blind,
and its disagreement with the baseline does not establish an edge. Better
research does not require changing the number. An unchanged estimate supported
by better investigation would also be a valid result.

## 12. Market comparisons need an explicit purpose

Separate three modes:

| Mode | What it establishes |
| --- | --- |
| Market baseline | What captured prices imply under a stated margin adjustment |
| Market-assisted forecast | A judgment using prices along with other evidence |
| Blind forecast, then comparison | A recorded estimate formed before market exposure |

The initial run fits the first mode. The researched run is not blind; prior
exposure must remain on the record even though its formula does not use odds.
Future controlled comparisons should save the blind estimate before revealing
prices, then save any assisted revision separately.

Public coaching, roster and performance information may already be in prices.
Adding a news bonus to a market baseline can double-count it. To claim value
over a bookmaker, compare forecasts and contemporaneous prices on matched
resolved events. Betting returns also involve execution, costs and selection;
one disagreement between point estimates establishes little.

## 13. Evaluation is how the system becomes better

Begin with binary Brier loss, `(p - y)^2`, while keeping the eligible submission
policy explicit. Select at most one forecast per forecaster and question under
a common cutoff or horizon for the comparison. Revisions should not buy extra
weight. Preserve missing submissions, voids, disputes and resolution corrections.

Compare a simple single-agent forecast, a defensible base rate, available market
or specialist baselines, and a simple ensemble where appropriate. Group related
events when splitting data and estimating uncertainty. Fit calibration or
ensemble weights only on training data, and retain unadjusted comparators.

The first useful experiments are whether research coverage, explicit belief
states, targeted review, and reused findings improve scores at comparable cost.
Hold evidence fixed to study judgment; vary research separately to study
information gathering. Include future live questions because historical replay
cannot by itself remove contamination concerns.

Measure research failures, cost, latency, coverage and auditability alongside
predictive accuracy, but do not substitute them for it. Treat proposed lessons
as hypotheses until they transfer to new cases.

## 14. What exists, and what to build next

Implemented: a standalone Python replay harness, two Patriots cases with recorded
agent responses and structured source observations, saved tasks and artifacts,
arithmetic and validation, a research coverage gate for the second case, dependency
lookup, and hypothetical scoring. Thirteen behavioral tests passed at the end
of that implementation. Source captures are transcriptions, not raw page archives.

Not implemented: the general Vorhersage package CLI, SQLite findings store, live
research execution, general scheduling, automatic monitoring and resolution,
fitted football models, or a validated forecasting improvement. The hypothetical
scores are examples; the actual championship outcome remains unresolved.

Proposed order:

1. Generalize the smallest binary-question workflow with durable typed records,
   read-only `next`, atomic submission, revisions, resolution and scoring.
2. Make research coverage configurable by domain, with explicit unknowns and
   an explicitly narrower policy for market-only runs.
3. Establish a prospective evaluation cohort and simple baselines before tuning
   elaborate reasoning procedures.
4. Add reusable findings, retrieval, provenance, freshness review and dependency
   triggers; measure whether reuse improves quality or cost.
5. Add provider interfaces for specialist models and test incremental value.
   For football, candidate work includes opponent-adjusted ratings, roster
   assumptions, and season/playoff simulation rather than untested point bonuses.
6. Add calibration, more elaborate ensembles and adaptive research allocation
   only as independently evaluated extensions.

The unresolved product question is which domain supplies useful questions,
accessible evidence and timely resolutions for the first prospective cohort.
The unresolved scientific question is which of these interventions improves
accuracy enough to justify its cost.

## Related records

### Agent workflow follow-up: substance and valid recovery paths

A live agent exercise completed research, review and issuance while assigning
precise conditional probabilities from indirect evidence. Important case facts
were collected only after the user proposed an interview. After new information
arrived, the agent wrote a proposed probability into a signal instead of issuing
a revision, and changed evidence timestamps after a cutoff error. The error
itself named a run cutoff in a context that actually checked the current time.

New single-question runs now begin with linked intake/inquiry tasks. Assessment
records separate the forecast target, what evidence measured, transfer
assumptions, and plausible input ranges. Review addresses the sensitivity
calculation and obtainable next evidence. The revision command appends an
explicit study binding and retains the old issued forecast until review is
complete. Tool-recorded evidence capture times and errors with actual cutoff
values provide a valid route through the work without changing chronology.

These checks improve inspectability, not demonstrated forecasting accuracy.
Agents can still supply weak assumptions or unsupported prose. Manually imported
historical timestamps remain declarations, and sensitivity bounds are consequences
of declared ranges, not calibrated confidence intervals. Regression tests use
fictional cases rather than storing the user's personal transcript.

### Implementation follow-up: Epiq

The [Epiq integration](examples/patriots_2027/EPIQ_INTEGRATION.md) now exercises
the proposed storage boundary. Sixteen captures and fifteen findings are stored
through Epiq's CLI, then selected from a consistent snapshot into a portable
packet. Vorhersage reconstructs its evidence from those records, retains their
claim/evidence IDs, and reproduces the 6.048% researched judgment. The original
research cutoff and actual Epiq import times remain separate.

The suite now has 21 passing tests. Withdrawing a required Epiq claim blocks a
new freeze while the earlier packet remains replayable. This supports using
Epiq for shared research memory and retaining forecasting-specific state in
Vorhersage. It does not establish automatic research, probability updating,
general retrieval or better accuracy; the agent judgments are still fixtures.

### Earlier notes and examples

- [Package design](DESIGN.md)
- [Superforecasting capabilities and experiments](SUPERFORECASTING.md)
- [Executable workflow proposal](WORKFLOW.md)
- [Literature review and bibliography](literature/README.md)
- [Patriots simulation and commands](examples/patriots_2027/README.md)
- [Researched Patriots assessment](examples/patriots_2027/RESEARCHED_ASSESSMENT.md)

## Evidence transfer needs a model challenge

A later field trial completed intake, evidence capture, parameter support, and
sensitivity review, but justified a scenario's price-trajectory weight with
evidence about political opposition conditional on prices. The proposed model
had changed from political pathways to price trajectories without rebuilding the
research mapping. Complete fields made this inspectable; they did not make it
sound.

New studies therefore version the research-to-model map, distinguish quantity
types, and challenge transfers and scenario boundaries before review. Named
concerns become linked investigations, explicit deferred evidence, or retained
assumptions. No schema claims to prove semantic relevance. New assessments must
be challenged again, including models repaired without further searches.

The same trial treated still-active proposals as failed historical episodes and
attached multiple claims to a source excerpt supporting only part of the finding.
Empirical priors now use registered, dated reference queries with eligibility,
censoring, and declared shared episodes; claim support links passages to individual
findings and distinguishes inference. Existing records remain readable.

Research also needs reuse within a run: an inquiry can substantively address a
profile domain. Explicit coverage reuses that answer instead of requiring another
research task to restate it. The saved task and source trail remain available.
