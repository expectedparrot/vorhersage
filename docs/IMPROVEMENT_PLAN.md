# Assessment of the proposed improvements

This maps the supplied proposals to the current code. External performance claims
in the proposal have not been independently verified or reproduced here.

## Implemented first: declared odds ledger and widget

See [the odds-ledger guide](ODDS_LEDGER.md). The implementation extends existing
assessment task results and manifests rather than introducing a parallel history
store. It supports experiment method registration, explicit joint ratios,
single-ratio sensitivity, and offline HTML export. Reviewer round-tripping and
hazard calculations remain separate follow-ups.

## Next priorities

Deadline structure is now implemented through [timeline models](TIMELINE_MODELS.md):
milestones, parallel and alternative routes, explicit remaining work, unresolved
inputs, parameter research, weighted joint scenarios, and offline comparisons.
The [Waymo example](../examples/waymo_boston_2029/timeline/README.md) is unweighted
and illustrates a dependency disagreement. Duration fitting and automatic hazard
updates remain future work; no accuracy gain is established by this implementation.

| Proposal | Existing support | Remaining work and design decision |
| --- | --- | --- |
| Cheap evaluation loop | Historical replay, contamination assessments, matched per-question Brier differences, versioned methods | Add deterministic paired bootstrap intervals, resampling related-event groups together. For method comparisons, average repetitions within each question first. Preserve seed, cohort, resampling unit, and exclusions; tiny cohorts may not support useful uncertainty estimates. |
| Closed-book ignorance probes | Versioned questions and replay metadata | Store model/version, exact prompts, responses, grader criteria, timestamps, and probe decisions in an immutable cohort-admission artifact. A failed recall probe is evidence about that probe; it cannot verify absence of latent outcome knowledge. Retain rejected questions and selection rules to expose selection effects. |
| Micro-horizon prospective cohort | Prospective deadlines, monitoring, resolution and evaluation | Start with one explicitly chosen feed and deterministic resolution rules. Deduplicate related questions, register cutoffs before outcomes, and preserve ambiguous or missing releases. Feed access and cohort quality need an operational pilot. |
| Deadline hazards | Scheduled review tasks and reference episodes with censoring | Define conditional hazards per interval and compute `1 - product(1 - h_t)` over remaining intervals. Conditioning on survival needs confirmation that the event has not occurred; missing precursor observations alone do not justify decay. Keep a proposed revision subject to agent confirmation. |
| Research/judgment variance | Frozen-packet method experiments; session studies allow frozen or independent live evidence | Register a crossed design: multiple research packets per question, multiple judgment draws per packet, comparable budgets. Estimate within-packet judgment variance and between-packet research variance with uncertainty. Prospective scoring remains a separate accuracy endpoint. |
| Empty checks and double dating | Evidence observations and source retrieval/capture times; optional Epiq assertion events | Add a typed search observation with query, scope, source, attempted time, success status, and zero-result semantics. Add an explicit assertion timestamp and cutoff policy; unknown timestamps should stay unknown. Observation time is not automatically assertion time. Existing historical adapters need an explicit migration policy. |
| Incentive audit experiment | Versioned task instructions, required research domains, matched method comparisons | Define control and treatment methods with equal budgets and structured cheap-talk/costly-signal fields. Freeze cohort and analysis policy before running. An instruction or coverage gate alone does not establish that statements were classified correctly. |
| Coherence distance | Version-pinned implication closure and violation reporting; joint-session coherence | Declare a distance metric and constrained projection over a pinned relation set. Group results by method version and common information cutoff. Sum of edge violations is not minimum reconciliation distance and can double-count transitive constraints. Validate any relationship with accuracy on later resolutions. |

Evaluation intervals and a small prospective cohort should precede an expensive
variance study. The ledger can already be an experimental arm; its auditability
does not establish improved predictive accuracy. A registered incentive experiment
is mostly a specification-and-data task after choosing the cohort and workers.

No external model jobs, feed polling, or experiments were launched as part of the
ledger implementation.
