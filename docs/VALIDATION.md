# Validation history

## Reusable live sessions and session studies

`python -m pytest -q`: **140 passed** (119 package/integration tests and 21 earlier
prototype tests), with two existing EDSL/Pydantic deprecation warnings. Sixteen
new tests cover staged evidence, deferred bindings, research coverage and follow-up
queries, immutable event retries, refusal retention, unknown usage reconciliation,
explicit retry amendments, interrupted attempts, atomic rejected actions,
waiting/polling, budgets, study isolation, unconditional scoring eligibility,
resolution corrections, report escaping, and known distribution-score values.

The executed [live-session fixture](../examples/live_sessions/README.md) runs
two arms × two repetitions through real local subprocess workers, pauses and resumes
tool receipts, and finalizes all four sessions. It records eight synthetic model
attempts and four synthetic tool attempts, $0.10 in fictional reported cost, and
passes 109 artifact integrity checks. Expected synthetic Brier scores are 0.5625
and 0.0625. These checks establish software behavior, not predictive performance.

The standalone HTML was exercised in Chromium at 1440, 768, and 390 pixels,
including baseline selection, search, CSV download, zero JavaScript errors, and
zero external requests. The generic report also loaded the saved original AIRO
project and generated a four-model comparison of all 2,940 matched cells without
changing the original project. The new `session-study report` CLI returned a
successful JSON envelope and wrote the requested standalone file.

The [implementation guide](LIVE_SESSIONS.md) states the remaining limits: workers
are trusted external executables, provider costs are reported rather than metered,
research observations are not independently certified, and native EDSL transport
and the paper's benchmark/simulator imports remain separate work. No new paid
model calls were made for this extension.

## Expanded AIRO research and model study

`python -m pytest -q`: **124 passed** (103 package/integration tests and 21 earlier
prototype tests). New checks cover distinct-source requirements, later-turn
follow-up searches, pagination, exact Tavily news dates, whole-response batch
limits, terminal provider refusals, invalid-output resubmission without probability
repair, and recorded changes to reasoning effort. The local EDSL parameter audit
also regression-checks proposed Astra reasoning and Anthropic streaming patches
without changing the installed package or remote workers.

See the [expanded study](../examples/airo/edsl_study_02/REPORT.md) and
[replication audit](../examples/airo/REPLICATION.md) for execution outcomes,
costs, and remaining differences from the authors' procedure. Tavily request
construction and pagination are tested offline; no live Tavily call was made
without credentials.

The completed expanded wave imports **8,820 probabilities** across Astra,
Opus, and Gemini. Each project passes 513 artifact/integrity checks and has
zero violations in 72,324 logical comparisons. Independent replay of accepted
raw model outputs matches every imported probability and reconciles costs for
all four attempts, including Fable's refusal. The offline HTML comparison was
checked in Chromium at desktop, tablet and phone widths, including baseline
selection, filters, pagination, CSV export, and zero external page-load requests.

## EDSL joint-elicitation bridge

`python -m unittest discover -s tests`: **95 tests passed**. Eight new tests cover
the research gate, atomic response validation, complete grids, frozen ECI
quantiles, source-read requirements, invalid probabilities, disallowed tools,
unambiguous JSON parsing, and explicit continuations after two provider failure
types. Failed calls retain their costs and raw records; no truncated probability
JSON is repaired. See the [EDSL guide](../examples/airo/EDSL.md).

The [completed live pilot](../examples/airo/edsl_pilot_01/REPORT.md) imports all
2,940 probabilities from Gemini 3.1 Pro Preview. Its project passes integrity
checks on 513 artifacts and records zero violations in 72,324 comparisons.
Six EDSL continuations cost $2.27623 including the two failures. The output cap
and text-delivery instructions were amended during development. One successful
page read, missing recency filters and no post-read search round limit fidelity
to the authors' research procedure; successful execution is not evidence of
forecasting accuracy.

## AIRO principal-panel reproduction

`python -m unittest discover -s tests`: **87 tests passed**. Six new tests check
the frozen authors' dataset, complete session membership, once-per-call usage,
headline medians and paired ratios, the original coherence denominator, distinct
incident and catastrophe deadlines, own-median policy bindings, shared-field
placeholders, and rejection of corrupted source files.

The [executed reproduction](../examples/airo/output/REPORT.md) imports four complete
sessions with 11,760 probabilities, renders Figures 6–9, and passes **376 checks**
against the authors' saved summaries. Project integrity checks pass. The frozen
source was also regenerated from the pinned archive and compared byte for byte.
The authors' unconditional coherence diagnostic has zero violations in 1,996
comparisons; the package's separate conditional audit finds four violations.
No new model calls are made. This verifies data handling and arithmetic, not
forecast accuracy or the paper's separate validation experiments.

## Joint-session foundation

Added 16 joint-session tests covering incremental replacement, stale revisions,
idempotent retries, atomic import rollback, preserved source timestamps and raw
records, frozen question/condition versions, numeric quantile bindings, transitive
coherence within a session, complete and incomplete panels, paired geometric
ratios, zero/overflow handling, prospective timing, and exclusion from ordinary
outcome scoring. The CLI acceptance example completes four fictional sessions
through separate processes and checks project integrity. No AIRO data or model
calls are used. See [the joint-session guide](JOINT_SESSIONS.md).

## Version 0.2

`python -m unittest discover -s tests`: **56 tests passed**. The added acceptance
coverage checks scenario partitions and bounded extrema; capture hashes and quote
membership; transitive repetitions and conflicting independence assertions;
prior timing declarations; version-pinned transitive implication checks;
reference-case horizons and censoring; timer triggers; worker failure recovery;
partial-run resumption; early outcome resolution; and deadline routing. A real subprocess fixture completes
a monitored revision through issuance. CLI capture, audit, scenario, reference,
and finite polling commands are exercised in separate processes.

The existing optional Epiq roundtrip test passed with the local checkout. These
tests establish software behavior, not forecast accuracy or source authenticity.
They do not measure web-service reliability, empirical calibration, large-scale
performance, or the quality of a particular external research/model worker.

Built `vorhersage-0.2.0-py3-none-any.whl` without dependencies/build isolation and
verified its CLI version with site packages disabled. Wheel SHA-256:
`69b5d9fe21fbc1a867fbf8f03205026ea401caf535417690bf026a8712bfe308`.

## Version 0.1

Completed September 9, 2026.

| Check | Result |
| --- | --- |
| General package/integration suite | All 38 tests passed, including explicit strict versus post-hoc parsing checks |
| Completed model pilot | 80 interviews, no remote execution exceptions; 64 strict valid outputs; 69 with post-hoc single-JSON-block extraction; about $1.13 |
| Model pilot integrity | Strict project: 641 artifacts verified; diagnostic project: 691; JSON, report links, and 80-response accounting checked |
| Historical replay through separate CLI processes | 20 Halawi validation cases; 18 matched crowd baselines; constant control only, zero model calls; 201 artifacts verified |
| Earlier Patriots/Epiq prototype suite | 21 tests passed |
| Fictional portfolio through separate CLI processes | Two questions, baseline, revision, resolutions and matched evaluation completed |
| General package reading Patriots evidence from Epiq | 31 records imported; recorded probability reproduced at 0.06048 |
| Live portfolio setup | Three related questions registered, zero forecasts issued |
| Editable install and console command | Passed in the checkout's `.venv` |
| Wheel install outside checkout | Passed in a fresh isolated environment, with no runtime dependency downloads |
| Project integrity and forecast input manifests | Passed for all three saved package projects |
| Documentation links and example JSON | Verified |

Tests cover resumption, read-only next-task selection, atomic rejection,
idempotency, research budgets and unknowns, reference-class arithmetic, conditional
chains, ensemble eligibility, review follow-ups, concurrent revision conflicts,
question versions, immutable artifacts, source cutoffs, live cutoff advancement,
prospective blocking, resolution corrections, matched cohorts and mode exclusions.
Epiq integration tests cover scalar and multi-valued claims and unchanged-source
checks. Earlier prototype tests additionally exercise source retraction and
contested inputs against disposable Epiq databases.

The previously built wheel predates benchmark replay support. Its original
installation check and hash remain recorded here; use the editable checkout
for the new commands. File: `dist/vorhersage-0.1.0-py3-none-any.whl`, SHA-256:

```text
d404bedf1e845e8de645830aac731f45d27d939dfa59fac5a0a10498b96a5132
```

The fictional portfolio scores validate calculation and selection behavior.
Replay tests additionally cover input allowlisting, daily crowd cutoffs,
reproducible selection, bundle hashes, missing matched forecasts, actual versus
simulated timestamps, unchanged ordinary evaluation guards, and frozen results
after label corrections. The historical walkthrough compares a mechanical
constant control with supplied crowd observations; it is not an agent skill test.
The Patriots regression preserves recorded judgments. Neither establishes
predictive skill, calibrated uncertainty or an advantage over a market.

Some portfolio operations load artifacts into memory. Large-portfolio performance,
schema migrations, background scheduling and adversarial tamper resistance are
not established by these checks. The Epiq CLI integration tests explicitly skip
when the optional local Epiq fixtures are unavailable.
