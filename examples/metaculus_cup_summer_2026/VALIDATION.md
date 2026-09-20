# Setup validation, September 20, 2026

At initial setup, no tournament forecasts or forecasting scores had been produced.

Live Exa Snapshot search: two returned sources, July 1 cutoff, no warnings.
See `smoke/summary.json` and the compressed full retrieval. Reported request
cost was unavailable. This verifies API acceptance and retained provenance,
not independent historical verification of every returned page.

Focused offline checks: **66 passed** across two test commands.

```bash
.venv/bin/python -m pytest -q \
  tests/test_metaculus_snapshot.py tests/test_web_research.py \
  tests/test_backtesting.py tests/test_workflow.py
.venv/bin/python -m pytest -q tests/test_cli.py tests/test_extensions.py
```

These cover request payloads, real capture timestamps, historical packet
acceptance, later-cutoff rejection, content integrity, mixed live/historical
evidence rejection, no live fallback, question-field allowlisting, review gates,
case-specific request budgets including failures, and fixed retrospective runs.
Importer and runner tests use synthetic questions, not real tournament data.
Authenticated tournament acquisition subsequently succeeded: 62 feed posts,
unique IDs, tournament membership verified for each, and an empty terminal page.
The account has `has_data_access: false`; no question criteria or resolutions
were returned. Two detail checks confirm the missing fields. This is a metadata
inventory, not a complete benchmark dataset. See `acquisition.json`.

The downloader now accepts the configured `METACULUS_API_KEY` alias and uses
documented tournament-slug, sort, and pagination parameters. The focused
`tests/test_metaculus_snapshot.py` suite covers the alias and saved feed pages.

A broader check also found seven existing failures: six in
`tests/test_research_v2.py` and
`tests/test_study.py::StudyTests::test_full_research_review_issue_and_reports`.
All fail because their fixture payload helper lacks `reference_class_design`.
The same seven failures reproduced using unchanged `HEAD` source exported to
a temporary directory and imported through `PYTHONPATH`. They were not repaired
as part of this experiment setup. `git diff --check` passed.

## Subsequent pilot and workflow changes

The [pilot forecast](pilot_44241/forecast.md) was subsequently issued at 64% YES
using the July 7 Snapshot cutoff. Its original records remain frozen; the user
later reported a NO resolution. The original contract criteria have not been
reconciled, so no exact-contract score is claimed here.

The broader reference-research implementation now supports widening searches,
partial analogies, follow-up rounds, incomplete-cohort bounds, and audited budget
extensions. The fixture incompatibilities above were corrected in that work.
The full suite passed **389 tests**, followed by **44 relevant tests** after a
final refinement preserving both original and revised candidate assessments.
These validate software behavior, not an improvement in forecasting accuracy.
