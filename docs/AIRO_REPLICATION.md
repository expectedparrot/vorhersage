# Re-creating the AIRO analysis with Vorhersage

Vorhersage can supply the durable records, evidence provenance, logical checks,
and parts of evaluation for this project. Faithfully reproducing AIRO also needs
a joint elicitation runner and an analysis layer. Running the current binary
workflow separately for every probability would change the paper's procedure.

Implementation update: the [joint-session foundation](JOINT_SESSIONS.md) now
provides incremental session records, explicit conditions and numeric bindings,
atomic external imports, median panels, paired ratios, and scoped coherence.
The [executed principal-panel reproduction](../examples/airo/output/REPORT.md)
now imports the authors' original 11,760 probabilities and reproduces Figures 6–9,
with 376 matching published-value checks. The frozen inputs, adapter, and rerun
instructions are in [examples/airo](../examples/airo/README.md).
The [fresh EDSL pilot](../examples/airo/edsl_pilot_01/REPORT.md) also completes the
full grid with one new model through an external web-tool bridge. Its transport
amendments and research-instruction deviations are documented; it is not the
paper's complete four-model protocol or validation suite.

The assessment below records the original feasibility analysis and proposed work;
its support table describes the package before these additions. A clean repeat
of the complete panel protocol and the paper's separate validation experiments
remain outstanding.
It uses the supplied September 2026 working paper, *Automated Forecasts of
Catastrophic Risks*, especially §2, §3, §4, and Appendix A, and the local package
at commit `3f6e55804d82b9fd00a27852fe3b42ccd9b21fd2`. The supplied PDF's SHA-256 is
`e51675610dbfff0d9588cbca714a119f5bca0a0f1b5f70cb40a7a04b29098dcf`.
The package findings below come from source inspection; no model calls were made.

There are three distinct deliverables. First, reproduce the published tables and
figures from the authors' saved forecasts. Second, repeat their elicitation with
a new dated panel. Third, test whether Vorhersage's research and review procedure
improves forecasts. The first is an arithmetic/data replication, the second is a
new measurement, and the third needs an experiment with observable outcomes.
Agreement with the paper's catastrophe probabilities does not demonstrate accuracy.

**What the paper actually runs.** The principal instrument has 35 questions:
general catastrophe, AI catastrophe, human disempowerment, and four incident
categories with eight severity thresholds apiece. Six horizons give 210 cells.
Each cell gets 14 probabilities: unconditional, eight policy conditions, and
five capability conditions. That is 2,940 probabilities per model and 11,760 for
the four-model panel, plus five capability quantiles per model. These are four
joint forecasting sessions, potentially containing many model and tool calls;
they are not 11,760 independent interviews. Figure 10 uses additional conditional
elicitation beyond this principal grid and needs its own input records.

The paper selects four leading ECI models, skipping within-family duplicates.
An exact replication should pin the published roster, model settings, family
mapping, and dated ECI snapshot. A new panel should record its selection rule and
available model versions explicitly; substitution changes the experiment.
The supplied appendix dates its prompt September 10, 2026.

Each model receives the whole instrument, researches with common search/read
tools, and cannot submit until at least ten returned search or page-read calls.
It can replace previously submitted cells before finalizing the session.
Its final submission includes five ECI quantiles, a shared rationale, and sources
it actually read. Previous forecasting sessions are withheld (§2.2; Appendix A,
pp. 22–29).

| Paper requirement | Existing package support | Work needed |
| --- | --- | --- |
| Versioned event wording, horizons, resolution rules | `question`, immutable versions, `event_deadline`, `resolve_after` | Compile the instrument and retain question/horizon/condition metadata |
| Captured research and provenance | Research bundles, frozen packets, Epiq adapter, source audits | Search/read harness with actual tool receipts and the ten-call submission gate |
| One model answers the full related grid | Workflow currently advances one binary question at a time | Durable joint session with partial cell submission and finalization |
| Policy assumptions and model-specific capability conditions | Assumptions can appear in text; no typed condition registry | Versioned conditions and per-session numeric bindings |
| Median panel and paired conditional multipliers | Ordinary ensemble is a weighted arithmetic mean | Separate aggregation functions and immutable membership records |
| Horizon, severity, and cause coherence | Version-pinned implication graph with transitive checks | Compile valid relations and audit a complete session consistently |
| Repeated panel waves | Immutable forecasts, revisions, monitoring workers | Fresh joint sessions, rolling-window registration, panel roster history |
| ForecastBench Brier and calibration | Matched binary Brier; five equal-width calibration bins | ForecastBench importer, own-decile bins, Wilson intervals, original cohort rules |
| Simulation rare-event validation | Simulation mode, binary scoring | Simulator adapter, held-out base-rate oracle, skill and capability analysis |
| Intervention distributions | No numeric forecast/distribution schema or CRPS | External distributional scoring initially |
| Updating and passage experiments | Versioned methods, repetitions, fixed evidence | Paired exposures, joint calls, passage randomization, regressions |

Relevant implementations are [schemas](../src/vorhersage/schemas.py),
[workflow calculations](../src/vorhersage/workflow.py),
[relations](../src/vorhersage/relations.py), and
[evaluation](../src/vorhersage/evaluation.py). The
[experiment guide](EXPERIMENTS.md) documents the current runner's fixed evidence
and required prior → drivers → research → assessment → review → issue sequence.
It does not implement an arbitrary procedure or live research comparison.

**The smallest faithful architecture.** Start with an AIRO-specific example and
an immutable file manifest, then promote reusable pieces into the package once
the imported records establish the actual data contract. Suggested files below
are proposed work, not existing commands:

```text
examples/airo/
  instrument.json         complete question text, horizons, condition definitions
  panel.json              dated roster, ECI snapshot, model and harness settings
  compile_questions.py    ordinary question specs plus condition/session mappings
  import_records.py       lossless import of authors' sessions and raw outputs
  joint_worker.py         research, partial submissions, checkpoint/resume, finalize
  analyze.py              medians, paired ratios, coherence, tables and plots
  validation/             ForecastBench, simulator, and updating analyses
```

Use the natural experimental unit `(wave, model, protocol, repetition)` for a
session. Every probability row references that session, its exact question
version, horizon, condition, information cutoff, and evidence manifest. Store
the actual numeric ECI value for model-specific percentile conditions, the
target date, tolerance, and index vintage. Preserve raw responses, incremental
submissions, final accepted values, errors, timestamps, and actual usage once
per session. Do not count the same research cost thousands of times.

The present question schema rejects additional fields, so metadata belongs in
the sidecar manifest until a supported schema extension exists. Unconditional
question/horizon pairs fit ordinary binary questions directly. Conditional
cells need a distinct representation: a policy intervention is not the event
“policy occurs AND catastrophe occurs,” and the actual catastrophe outcome
cannot resolve all hypothetical policy worlds. Keep those cells out of ordinary
realized-outcome evaluation. Capability quantiles also need numeric storage,
rather than conversion to binary forecasts that loses the elicited distribution.

Keep authors' imported forecasts as timestamped external records with a separate
import timestamp. There is currently no faithful historical forecast-import API.
Do not generate fictional prior/research/review steps or backdate issuance to
make an import resemble a native workflow run. A reusable session artifact plus
validated external forecast import is the most useful eventual core extension.

The joint worker should maintain one model conversation across the complete
instrument, with fresh context each wave. Withhold submission tools until the
research gate is satisfied. Enforce finite probabilities in [0,1], exact IDs,
quantile ordering, and completeness before finalization. Retain every cell
replacement in the transcript. Missing cells remain missing; retries and their
costs remain visible. Cache provider requests by session and step identity.
The existing worker schema allows only 1–60-second invocations, so a long session
needs asynchronous jobs with short polling/defer steps or a new runner contract.

**Aggregation must match the estimand.** For cell `c`, model `m`, condition `k`,
and unconditional condition `u`, reproduce:

```text
unconditional_panel[c] = median_m(p[m,c,u])
conditional_panel[c,k] = median_m(p[m,c,k])
multiplier[c,k] = exp(median_m(log(p[m,c,k] / p[m,c,u])))
```

For four models, the probability median is the arithmetic midpoint of the two
middle probabilities. The multiplier is the geometric midpoint of the two
middle within-model ratios. The ratio of panel medians generally differs from
the median of within-model ratios. For example, the displayed 2030 probabilities
0.47% and 1.2% do not directly reproduce the paper's 2.21× high-capability
multiplier. Pair conditions with the same model's same-session unconditional
forecast, compute from unrounded values, and round only for display.

Register handling of zero probabilities before analysis: zero denominators and
zero numerators require explicit undefined/boundary handling. Never silently
clip them to an arbitrary epsilon. Preserve all four expected panel members;
flag incomplete panels rather than silently changing the ensemble. Additional
repetitions should describe session variability separately from the four-model
ensemble, under a declared within-model aggregation rule.

Vorhersage's `conditional_path` multiplies a nested event chain; it is not an
implementation of these conditional forecasts. Its `scenario_mixture` requires
an exhaustive mutually exclusive partition with weights. Policy alternatives
and five percentile point conditions do not meet that requirement, so neither
calculator should substitute for the paper's analysis.

**Definitions that would otherwise cause a false replication.** Incident ladders
and catastrophe questions have different clocks. Incident onset must fall between
elicitation and the horizon, but harms in the first three years after each onset
can count, including after the horizon. Use the onset deadline as `event_deadline`
and allow at least the additional three-year harm window in `resolve_after`,
with later adjudication if necessary. The separate catastrophe question requires
the mortality threshold within a linked catastrophe's window of at most five
years, beginning no earlier than December 31, 2025 and ending by the horizon.
It does not share the incident ladder's moving start date.

A new incident-ladder wave changes the target even for fixed-year horizons,
because it excludes incidents before the new elicitation. Register new question
identities or versions; the ordinary revision API requires the exact same
question version. Rolling six- and twelve-month horizons also move. Plot such
series as rolling targets, not repeated estimates of one unchanged event.

The incident categories overlap, and include death-equivalent morbidity or
economic damage. They cannot be summed or used as an exhaustive decomposition
of the deaths-only 10%-of-humanity catastrophe question. Only compile logically
justified implications: earlier horizons imply later horizons for a common
start; higher severity implies lower severity; domain incidents imply all AI
incidents under matching criteria; AI catastrophe implies general catastrophe.
Do not impose policy/capability monotonicity as logical truth.

The existing coherence audit selects latest forecasts by forecaster and mode,
so session-scoped checking is needed to avoid mixing waves or partial imports.
It also expands transitive implications. Obtain the authors' actual comparison
set before attempting to reproduce their 1,996-ordering denominator. Report raw
coherence first. Automatic probability repair or strict rejection would alter
the measurement unless included as a separately declared treatment.

Appendix A adds a consequential qualification to the policy analysis: every
policy condition also fixes capability to the model's median trajectory. The
unconditional forecast integrates over expected capability and policy responses.
Consequently, the published policy/unconditional multiplier changes both policy
and capability assumptions. Reproduce it as specified, and additionally report
policy/status-quo ratios within the common median-capability assumption as a
clearly labeled extension. The supplied prose does not establish a fully
specified structural causal model, especially for compute caps and later
capability trajectories. Capability conditions instead represent information
learned about the world, allowing associated variables and policies to change.

**Validation is a separate workstream.** The paper's long-run forecasts are
unresolved, so its validation evidence comes from other tasks:

| Analysis | Reproduction work |
| --- | --- |
| Figure 2: ForecastBench | Import original forecasts, outcomes, dates, and model/human cohorts. Calculate each forecaster's own deciles and 95% Wilson intervals. Preserve differing cohorts in the published reproduction; add a common-question/date comparison where possible. |
| Figure 3: rare events | Import FreeCiv and StarSim world reports, forecasts, outcomes, and ECI joins. Recreate the oracle excluding the evaluated simulation and compute `1 - Brier_model / Brier_oracle` on the authors' cohort. Recover exact pooling and exclusion rules; the text mentions 16 models while the plotted correlation has n=14. |
| Figure 4: intervention skill | Preserve forecast distributions and simulation distributions for baseline and 25/50/90% vaccination scenarios. Implement CRPS and recoverable skill `(CRPS_climatology - CRPS_model) / (CRPS_climatology - CRPS_simulator)`, verifying the authors' reference distribution and pooling order. Binary Brier is not equivalent. |
| Figure 5A: market updating | Pair initial and market-exposed forecasts. For each model fit the no-intercept slope `sum((market-prior)*(posterior-prior)) / sum((market-prior)^2)`. Reproduce the across-model ECI regression, HC3 errors, Spearman correlation, and matched 19-model/153-question slice separately. |
| Figure 5B: passages | Recover six exact passages, fixed common evidence, three baseline and three passage sessions per model, and randomized orders. Reproduce absolute shifts across the 35 unconditional 2100 questions and the last-author contrast. Obtain the exact repetition aggregation rule; repeated cells are dependent. |

ForecastBench publicly provides question sets, resolution histories, human
forecasts, and submitted model forecasts on its
[official data page](https://www.forecastbench.org/datasets/). These establish
an accessible starting point, but the paper's exact analysis cohort still needs
to be reconstructed and pinned. The
[ForecastBench-Sim paper](https://arxiv.org/abs/2606.18686) describes fixed world
reports and simulated continuations; this does not establish that AIRO's exact
FreeCiv/StarSim slices and intervention outputs have been obtained.

Use Vorhersage's matched Brier records for appropriate prospective or simulation
cohorts. Archived forecasts need a preserved historical-data scoring path;
today's retrospective runs are not automatically eligible for ordinary
evaluation against already-known outcomes. The existing Halawi replay importer
is not a ForecastBench importer. Keep simulation labels, rollout frequencies,
and oracle outputs outside model-visible packets and worker access. Use world
or event groups when estimating uncertainty, rather than treating horizons,
conditions, or repeated draws as independent observations.

**Recommended implementation order.**

1. Obtain and freeze the dashboard export. It should include the full instrument,
   eight complete policy definitions, model-specific conditions, raw sessions,
   evidence, and panel metadata. Appendix A is explicitly representative, not
   the full instrument. It also contains a leftover “X million” severity phrase;
   preserve the source and document any correction. Figure 10's additional
   prompts, the exact coherence edge set, and validation scripts/data are separate
   required inputs. The dashboard export was not located in this review.
2. Build the offline importer and analyzer. Reproduce Figures 6–9 and their
   numerical summaries from the original four sessions, with every plotted
   value traceable to raw cells. Add Figure 10 when its records are available.
   Verify arithmetic, percent conversion, same-session pairing, missingness,
   condition binding, dates, and coherence against explicit fixtures.
3. Implement the joint session runner. A small engineering pilot could use the
   three top-line questions, 2030/2050/2100 horizons, and all 14 conditions:
   126 probabilities per model, 504 across four models. This tests collection and
   analysis, but the smaller context changes elicitation; the full 35-question
   instrument remains necessary for protocol replication. Estimate cost from
   actual pilot tool/token receipts rather than multiplying cells by a call price.
4. Repeat the complete instrument as a new dated wave. Keep earlier sessions
   out of model context, preserve each model's independently gathered evidence,
   and record roster changes separately from within-model forecast changes.
   Fresh web research cannot reproduce the September 10 information environment.
5. Add the validation datasets and procedure comparison. First use identical
   frozen packets to compare joint direct elicitation with a joint structured
   research/review procedure on resolvable tasks. Keep model, question set,
   information, and budgets matched and repeat sessions. A comparison using
   today's per-question workflow also changes batching, so label it as a combined
   treatment or add a batching factor. Later compare live research strategies
   with actual collection metering and isolation.

The immediate useful deliverable is an offline reproduction of the original
panel's arithmetic plus a reusable joint-session record. That establishes whether
we can reproduce the reported analysis before spending on new elicitation. The
strongest subsequent use of Vorhersage is to test forecasting procedures on
near-term and simulated outcomes while retaining a transparent, evolving AIRO
panel for the long-run questions.
