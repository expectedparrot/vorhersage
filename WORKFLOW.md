# A forecasting workflow an agent can operate

**Implementation update, September 9, 2026:** the general binary workflow now
exists in `src/vorhersage/`. The [agent guide](docs/AGENT_GUIDE.md) describes the
implemented schemas, CLI, live/fixed cutoffs and lifecycle. The proposal below
remains a design record, including interfaces that differ from version 0.1.

Proposal, September 9, 2026. This specifies behavior for Vorhersage; the CLI and
schemas below are not implemented. It extends [DESIGN.md](DESIGN.md) and the
[superforecasting notes](SUPERFORECASTING.md).

The [Patriots 2027 simulation](examples/patriots_2027/README.md) now exercises a
bounded version of the contract with recorded agent responses and real source
observations. It is a standalone prototype, not the proposed package CLI.

## Operating contract

The agent repeatedly asks for the next task, reads its exact inputs, produces a
typed result, and submits it. Vorhersage validates and stores the result, performs
the applicable calculations, and determines what is actionable next.

Each task must name its purpose, required inputs, output schema, completion
conditions, remaining budget, and an allowed inconclusive outcome. A task can
ask the agent to investigate an uncertain fact; it cannot require the agent to
invent an answer to advance the workflow.

Research needs a coverage policy tied to the question. For a team championship
forecast, require prior performance, quarterback play, coaching, roster changes,
schedule, and current health before synthesis. Each domain must link findings
and an interpretation, or record an explicit unknown and its reason. This gate
checks that the agent addressed the topic; it cannot establish that the research
is sufficient or the judgment accurate. A run restricted to market prices must
declare that narrower purpose. Counting completed searches alone is inadequate.

The package should distinguish four run dispositions: `actionable`, `waiting`,
`blocked`, and `complete`. A published forecast normally enters `waiting` with
a review time or trigger. Issuing a forecast completes a forecasting run;
monitoring and resolution create subsequent runs in the question's lifecycle.

## Records and operations by step

| Step | Required records | Package operations | Agent contribution |
| --- | --- | --- | --- |
| Specify | Question version, deadline, criteria, resolution source | Validate fields, date ordering, target type, version identity | Interpret the intended event and identify ambiguity |
| Establish a prior | Reference-class definition, case outcomes, exclusions, initial belief | Select cases using explicit rules; calculate counts and frequencies; compare classes | Judge comparability and justify departures from observed frequencies |
| Identify drivers | Drivers, prerequisites, alternate paths, open uncertainties | Find missing inputs; traverse declared prerequisites; calculate supplied probability expressions | Identify plausible mechanisms, actors, constraints, and dependencies |
| Research | Research tasks, source captures, findings, entity links, source-origin links | Retrieve candidates; filter dates; deduplicate exact captures; track budget | Search externally, assess relevance, attribute claims, and reconcile conflicts |
| Update | Belief revisions, exact finding uses, assumption changes | Preserve history; calculate probability differences; evaluate explicit formulas | Assess how evidence changes the estimate and justify the revision |
| Challenge | Review, objections, responses, before/after beliefs | Create review tasks; check each objection is addressed or left explicitly unresolved | Find substantive failure paths and decide whether a revision is warranted |
| Check | Declared logical constraints and check results | Validate probability bounds, sums, ordering, and explicit joint calculations | Confirm that the mathematical relationship applies to these questions |
| Issue and monitor | Forecast, immutable input manifest, stopping reason, triggers | Freeze inputs; register timers; find forecasts depending on changed findings | Make a final estimate and specify useful update conditions |
| Resolve and learn | Resolution revisions, evaluation policy, cohort, scores | Select eligible submissions; score; summarize calibration and matched differences | Interpret resolution evidence, adjudicate ambiguity, and propose testable lessons |

Every step needs structured state. Several need straightforward algorithms;
others primarily need task scheduling and validated inputs for judgment.

## Minimal data model

Use explicit tables for core records and typed relationship tables. Natural
language remains useful inside findings, rationales, and questions, with enough
structure around it to recover identity, time, provenance, and dependencies.

- `QuestionVersion`: stable question ID, version ID, wording, target definition,
  criteria, information cutoff if applicable, deadline, and event-cluster ID.
- `SourceCapture`: source ID, capture ID, content hash, publication/availability
  claims and their basis, retrieval time, storage reference, and upstream origin
  when known. Unknown dates stay unknown.
- `Finding`: immutable ID, attributed claim, entity references, time scope,
  producer/run identity, and recording time. Evidence links identify captures,
  locators, and whether they support or challenge the claim.
- `FindingRelation`: typed links such as `corrects`, `updates`, `contradicts`,
  or `derived_from`, with author, time, and justification. New information does
  not silently overwrite an old finding.
- `BeliefRevision`: question version, probability/distribution, previous revision,
  exact findings used, changed assumptions, rationale, and producer/run identity.
- `ResearchTask`: uncertainty or objection being investigated, expected relevance,
  input IDs, budget, search attempts, result disposition, and findings produced.
- `Forecast`: issued belief revision, exact input manifest, issue time, method,
  model/run identifiers, update triggers, and stopping reason.
- `ResolutionRevision`: question version, resolved/void/disputed disposition,
  outcome, evidence, effective and recording times, and previous resolution ID.
- `Evaluation`: frozen forecast and resolution IDs, eligibility policy, exclusions,
  scores, grouping, and comparison method.

An issued forecast must pin its findings and source captures by immutable ID.
Current-status views can incorporate later corrections; historical views must
reconstruct the inputs actually used. An availability claim alone is not proof
that an agent lacked access to later information.

## Workflow state and task results

Add three orchestration records:

| Record | Fields |
| --- | --- |
| Run | Question version, purpose, workflow-policy version, state revision, resource budget, reserved finalization budget, disposition |
| Task | ID, kind, input IDs, prerequisite task IDs, result schema version, status, priority basis, attempt count |
| TaskResult | Task ID, input state revision, idempotency key, disposition, artifact IDs, unresolved items, resource use, validation result |

Task dependencies form an acyclic graph within a run. A review that generates
new research appends new tasks and new belief revisions; it does not create a
cycle in the already executed task graph. The graph of real-world relationships
can contain cycles and is a separate structure.

Submissions are atomic. Validate referenced IDs, input versions, schema, and
domain constraints before accepting the result and changing run state. An
idempotency key makes a retry return the original accepted result. A stale
submission receives an explicit conflict rather than attaching to changed inputs.
For an externally driven agent, resource use is reported by the agent; hard
enforcement requires execution through package-controlled adapters.

An illustrative research task response:

```json
{
  "schema_version": "1",
  "run_id": "run_factory_1",
  "state_revision": 7,
  "disposition": "actionable",
  "task": {
    "id": "task_power_dependency",
    "kind": "research",
    "purpose": "Determine whether commercial production requires the delayed substation.",
    "input_ids": ["question_factory_v1", "finding_utility_schedule"],
    "result_schema": "research_result.v1",
    "allowed_dispositions": ["completed", "inconclusive"],
    "budget": {"max_additional_searches": 3},
    "completion_conditions": [
      "Record sources checked and findings with capture references.",
      "Explain what remains unknown and whether it affects the forecast."
    ]
  }
}
```

The eventual interface should support this proposed interaction:

```text
vorhersage next --run RUN_ID
vorhersage schema research_result.v1
vorhersage task submit --run RUN_ID --task TASK_ID --from result.json
```

The driving agent owns that loop and performs the research or judgment requested.
The package supplies concrete instructions and exact input records on every turn,
so the agent can resume without reconstructing the workflow from conversation.

## How next chooses work

Start with a deterministic policy whose decisions can be inspected:

1. Return unresolved input or validation errors that prevent meaningful work.
2. Reconcile accepted task results and derive the current run state.
3. Select eligible tasks whose prerequisites have been satisfied. An inconclusive
   investigation satisfies an attempt requirement, not a requirement for verified
   evidence. Downstream tasks receive its unresolved uncertainty explicitly.
4. Prioritize question-definition issues, contradictions affecting the estimate,
   and required finalization work. Within eligible research, use the agent's
   declared relevance and effort estimates, with stable tie-breaking by task ID.
5. Stop optional research at the budget or stopping condition. Reserve enough
   budget for final assessment and issuance. Do not add review/search tasks
   indefinitely because an uncertainty remains unresolved.
6. Return the selected task with its rationale, context, and result schema.
7. If none is actionable, return `waiting` with a trigger/time, `blocked` with
   the specific missing prerequisite, or `complete` with the final artifacts.

`next` should be read-only: repeated calls against the same state return the
same task. Mutation happens through explicit submissions and run creation.
The single-agent version needs no task leasing; concurrent workers would require
an additional claim/lease operation before execution.

A later research scheduler could rank tasks by estimated probability impact,
chance of obtaining useful evidence, and cost. Those are elicited estimates, not
computed truth or a formal expected-value-of-information calculation. Record
them and test whether the policy beats a simpler fixed budget.

## Completion gates and valid uncertainty

**Hard gates** should cover structural defects: missing event definition,
invalid probability, unknown referenced artifacts, incompatible question versions,
or evidence violating an explicitly enforced historical cutoff. Mathematical
violations can block issuance when the relevant constraint has been confirmed.

**Uncertainty** should remain representable: no adequate reference class,
conflicting reports, inaccessible sources, an unanswered objection, or limited
research budget. The agent can issue with these limitations recorded, provided
the question is defined and it supplies a valid forecast. A judgmental prior is
an accepted alternative to an empirical base rate.

A failed fetch is not evidence that an event did not occur. A review may conclude
that no probability change is justified. A corrected report does not erase its
original contribution to an earlier forecast. These are routine outcomes that
the result schemas must support.

## Algorithms to implement first

1. **State derivation and next-task selection.** Deterministic dependency traversal,
   budget checks, and explicit waiting/blocked/completed results.
2. **Validation and immutable history.** Typed input checks, transactions,
   idempotent submissions, version conflicts, and exact input manifests.
3. **Evidence retrieval and dependency lookup.** Entity/date/text filtering,
   exact-content deduplication, and reverse lookup from a changed finding to
   affected forecasts. Semantic duplicates and common origins require review;
   text similarity alone cannot establish evidential independence.
4. **Small numerical functions.** Reference-class counts, supplied conditional
   calculations, probability constraints, simple ensemble means, and Brier loss.
5. **Monitoring and evaluation.** Due-task selection, event-trigger matching,
   latest-eligible forecast selection, resolution corrections, and matched
   score differences. Related events remain grouped in evaluation splits.

Belief updates can use Bayesian odds when likelihood ratios are explicitly
provided and their assumptions are recorded. The package must not invent
likelihood ratios or automatically multiply evidence from dependent sources.
Similarly, a dependency graph schedules review; it is not automatically a
Bayesian network that propagates probabilities.

## First implementation slice and acceptance examples

Implement one binary question with `next`, typed task submission, immutable
artifacts, a capped research/review loop, issuance, resolution, and scoring.
Use the hypothetical factory example as a walkthrough. Learned calibration,
semantic clustering, complex ensemble selection, and automatic probability
propagation can follow as separately evaluated extensions.

The workflow should handle these cases before being considered operational:

- Resume after interruption and receive the same unfinished task.
- Retry an accepted submission without duplicating findings or forecast revisions.
- Reject a result against an outdated question or run state.
- Finish research inconclusively and continue with that uncertainty visible.
- Exhaust optional research budget and advance to finalization.
- Issue a forecast without an empirical reference class or a resolved objection.
- Receive new evidence, find affected forecasts, and initiate review while
  preserving their issued probabilities until a new revision is accepted.
- Resolve or void the question; score only eligible resolved submissions under
  a declared policy, retaining the effects of subsequent resolution corrections.
