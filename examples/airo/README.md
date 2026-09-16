# AIRO: reproduce the authors' principal panel

For fresh model calls, see the separate [EDSL joint-elicitation pilot](EDSL.md).
The [interactive comparison page](edsl_pilot_01/comparison.html) compares its
forecasts with this panel and works offline.
The [expanded study](edsl_study_02/comparison.html) adds other models and more
research; [the replication audit](REPLICATION.md) documents the remaining gaps.

[Read the executed report](output/REPORT.md), with reconstructed Figures 6–9,
or inspect [all 2,940 panel cells](output/panel.csv). This example imports the
authors' four original sessions (11,760 probabilities) into Vorhersage and
recomputes unweighted probability medians and geometric medians of paired
within-model conditional ratios. All 376 checks against the saved published
summaries pass. It makes no model calls.

The source is [Forecasting Research Institute's AIRO repository](https://github.com/forecastingresearch/airo/tree/646da9a2cd61f7043f46b2ccd4ac53e525925018),
commit `646da9a2cd61f7043f46b2ccd4ac53e525925018`, run `2026-09-10T2141Z`,
protocol `unified-joint-combined-v5`. The 2.2 MB frozen source directory includes
the complete selected original rows, instrument, definitions, ECI snapshot,
reference summaries, licenses, and a SHA-256 manifest. Data and documentation
are attributed to AIRO, Forecasting Research Institute, under CC BY 4.0, subject
to the original [third-party carve-outs](source/LICENSE-DATA).

## Run offline

From the repository root, with Vorhersage installed in the environment:

```bash
.venv/bin/python examples/airo/reproduce.py --out /tmp/airo-reproduction
.venv/bin/python examples/airo/report.py --out /tmp/airo-reproduction
```

Use a new output directory. The importer refuses to overwrite an existing run.
Rendering requires the optional `matplotlib` dependency; importing and numerical
verification use the package and Python standard library. No network is needed.
The generated project database occupies approximately 240 MB, including frozen
raw records and detailed coherence comparisons, and is ignored by Git. It can
be regenerated from the included source. The portable report, CSV, JSON summaries,
compressed panel/member records, and PNG/PDF figures are saved alongside it.

To regenerate the frozen source from the pinned upstream archive:

```bash
gh api repos/forecastingresearch/airo/tarball/646da9a2cd61f7043f46b2ccd4ac53e525925018 > /tmp/airo-source.tar.gz
.venv/bin/python examples/airo/prepare_source.py --archive /tmp/airo-source.tar.gz --out /tmp/airo-source
.venv/bin/python examples/airo/reproduce.py --source /tmp/airo-source --out /tmp/airo-from-archive
.venv/bin/python examples/airo/report.py --source /tmp/airo-source --out /tmp/airo-from-archive
```

The source preparation records archive and file hashes, original log line numbers,
and exact selected line hashes. No probability-based filtering is applied.

## What is preserved and checked

- All 35 question definitions, six horizons, and 14 conditions; incident deadlines
  and subsequent three-year harm windows remain distinct from catastrophe windows.
- Four complete joint sessions with original finalization timestamps, raw rows,
  prompts, shared rationale, recorded research, and once-per-session usage.
- Each model's five numeric ECI quantiles. Every policy condition fixes capability
  at that model's own median; capability conditions use its corresponding quantile.
- All 210 unconditional panel medians, 156 saved conditional endpoint probability
  and ratio summaries, and ten unconditional coherence counts match the authors'
  references at their saved precision: **376 checks**.
- The authors' unconditional diagnostic reproduces **0 violations in 1,996
  comparisons**. Its 24 BRACKET comparisons span different counting windows and
  are retained as a diagnostic rather than registered as logical implications.
- Vorhersage separately audits valid implications and their transitive consequences
  under every condition. It finds four conditional inconsistencies in Opus 5;
  the report lists the unchanged source probabilities. These are outside the
  paper's unconditional coherence claim.

Source tool outputs are preserved as records, without independently verifying
their claims. The expanded final export lacks original partial-submission
chronology and per-tool timestamps. Evidence captures explicitly use completion
time as an upper bound; the importer does not invent those missing timestamps.

The report also shows an additional policy-versus-status-quo comparison, labeled
separately from the authors' policy-versus-unconditional ratios. Model-elicited
policy comparisons do not establish causal effects. Incident categories overlap
and must not be summed.

This reproduces the principal panel and Figures 6–9. ForecastBench calibration,
simulation validation, anchoring experiments, and the additional Figure 10
instrument are separate tasks. It does not rerun model elicitation or establish
the accuracy of the catastrophe forecasts.

## Generic package comparison

The saved principal-panel project can also be rendered by the reusable
`session report` command. [Open the generated comparison](output/generic-session-comparison.html)
for all four original sessions and 2,940 matched cells. This report is generated
from package records and complements the AIRO-specific figure reproduction.
