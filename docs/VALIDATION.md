# Version 0.1 validation

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
