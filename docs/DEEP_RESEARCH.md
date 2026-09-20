# Deep research mode

The single-question interface defaults to `research_effort: "deep"`, with
60 searches and eight follow-up tasks available. New ordinary deep runs use
`reference_policy: "widening_v1"`. Research should seek informative imperfect
evidence rather than abandon the outside view when exact matches are absent.
The driving agent performs searches and interprets sources; the package
organizes tasks, validates records, and preserves the work.

## Plan, search, widen

The sequence is intake → reference-class design → class searches and ordinary
inquiries → reference-class analysis → estimation. Timeline studies also receive
reference research before timeline construction. Existing runs retain their
original task queues and policy; reopening a project does not silently migrate it.

The design includes at least a `close` class and a `nearby` or `mechanism` class.
Each class records an ID, population, selection rule, target intake input IDs,
transfer rationale, and search plan. A close class might cover previous repairs
at the same site; a nearby class might cover coating repairs at other public
pools; a mechanism class might cover waterproofing remediation more generally.
Do not choose classes based on whether their outcomes favor the target forecast.

`search_allocation` divides the planned search allowance into `discovery`,
`verification`, and `followup`. These are advisory allocations within the run's
ceiling, not extra caps or mandatory minimums. Reserve capacity to check actual
outcomes and investigate consequential uncertainties.

Each class generates a `reference_class_search` task. Its answer records:

- `class_id`, status (`searched`, `unavailable`, or `budget_exhausted`), limitations,
  and the next useful action.
- Queries, findings, and links to saved `retrieval_ids` or captured search
  `evidence_refs`. Empty search results still need a saved receipt or capture.
- Candidate ID, independent episode ID, description, outcome status (`verified`,
  `partial`, or `unknown`), intended use, similarities, differences, target inputs,
  rationale, and evidence references.

Saved retrieval queries must match the declared query. Snapshot or retrieval
times must respect the run cutoff, and captured evidence must pass the usual
evidence checks. External tools can supply captured search evidence instead of
a native retrieval. Searches are still reported in submission usage; records
do not independently certify the exhaustiveness of external browsing.

## Use imperfect cases

Candidate uses are `base_rate`, `input_analogy`, `context_only`, and `excluded`.
An outcome must be verified to mark a candidate for a base rate, but verification
alone does not establish comparability or an empirical denominator. Input
analogies may have partial or unknown outcomes. For example, a cleaning episode
can inform drainage time without estimating total coating-repair completion.
Explain which quantity the evidence informs and how scale or mechanism differs.
Use `extrapolated` or `assumed` parameter support with ranges where appropriate.

Multiple reports of one episode retain the same episode ID. Do not pool broader
classes automatically, count duplicate reporting as independent evidence, or
translate an unobserved outcome into failure. Current modeled sensitivity and
assumed/extrapolated inputs are exposed in `context.research_priorities` to guide
follow-up; these are research leads, not measured values of information.

`reference query` retains its strict eligibility rules for an empirical prior.
It now also returns `partial_identification`: mature cases, observed successes
and failures, unknown outcomes, and probability bounds obtained by assigning all
unknown outcomes first to failure and then to success. For example, two successes,
one failure, and two missing outcomes give bounds of 0.4–0.8. These describe the
selected cohort, not the target event or a confidence interval. No bounds are
reported for an empty mature cohort, missing episode metadata, or dependent cases.
Partial cohorts can inform judgment through explicit missingness and transfer
assumptions without being presented as an empirical prior.

## Analyze and continue

Analysis records `class_results` for every planned class and
`remaining_assumptions`, in addition to the usual analysis fields. Distinguish:

| Status | Meaning |
|---|---|
| `complete` | An exported empirical analysis is available |
| `partial` | Useful evidence or analogies exist, but the full estimate remains judgmental |
| `search_incomplete` | Discovery or verification is unfinished |
| `budget_exhausted` | The search ceiling has actually been reached |
| `outcomes_unavailable` | Candidates exist but needed outcome information is unavailable |
| `no_usable_cases_found` | All planned classes were searched and no useful candidates were recorded |
| `continue_research` | Another search/verification round is warranted |

For `continue_research`, supply `followups: [{class_id, action}]`,
`additional_classes` using the original class schema, or both. The workflow
queues the requested searches and returns to analysis. New classes are recorded
as amendments in analysis history; they do not rewrite the initial design.
Each requested search task consumes a follow-up slot. Analysis history and all
candidate observations remain available in the forecast and report context.

A completed empirical analysis still identifies a Flyvbjerg `analysis.json`
export; its ID, frozen subjects, metric, and dependence metadata are validated.
The empirical prior is separately checked against registered dated episodes.
An incomplete or partial analysis can proceed to a judgmental forecast with an
explicit `reference_class_exception`; lack of perfect data does not block a
forecast. The structured disposition remains visible instead of being replaced
by a claim that no reference class exists. Legacy runs still accept `blocked`.

## More research within explicit budgets

Prefer another targeted search when it could improve a consequential assumption.
Wide sensitivity ranges disclose uncertainty but do not substitute for evidence.
An unfinished ordinary run can increase its total ceilings:

```bash
vorhersage budget --project PROJECT --max-searches 90 --max-extra-tasks 12 \
  --reason "Verify missing outcomes and search nearby repair classes"
```

Portfolio callers add `--run RUN_ID`. The amendment preserves the original
budget, usage, and reason. Fetch `next` again because old task files become stale.
This command does not itself make research requests, change the cutoff, extend
the event deadline, or override limits in an external runner. Frozen experiment
budgets remain fixed. A useful stopping point need not spend the entire budget.

## Compare methods before claiming improvement

Use untouched questions, the same historical content policy, and separate
forecaster/run IDs for each arm. First compare the legacy and widening policies
at equal budgets; then compare widening at larger budgets. Record model/version,
case selection, budgets and stopping rules before running. Keep evaluation labels
outside forecasting contexts and group dependent questions when assessing results.
Compare Brier score, calibration across enough questions, actual search/cost
usage, verified independent cases, and input analogies recovered. Exclude the
Reflecting Pool pilot from an untouched evaluation because its outcome informed
development. No accuracy improvement is established by passing software tests.

Low-level run specifications can choose `research_effort: "deep"` with
`reference_policy: "legacy"` or `"widening_v1"` for paired research runs.
The existing frozen-packet experiment runner allows no live searches; it can
compare reasoning on supplied evidence but is not a live-research comparison.
`--research-effort standard` on `start`/`define` retains the smaller task sequence.
