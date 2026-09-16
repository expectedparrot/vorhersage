# Full question reports

Generate a self-contained HTML document or a LaTeX document from the question,
research history, models, evidence, and predictions already recorded in a project.
Export is offline: it does not research, call a model, change forecasts, reveal
market targets, or compile executable content from research text.

Reports carry Expected Parrot branding, matching Bewley's wordmark, green palette,
and serif headings. HTML includes the `E[🦜]` mark and a linked brand header and
footer; LaTeX uses a text wordmark so compilation does not require an emoji font.
Branding is built into the export and needs no remote assets or fonts.

## A complete question

```bash
vorhersage --project PROJECT report --question QUESTION_ID \
  --format html --output report.html
vorhersage --project PROJECT report --question QUESTION_ID \
  --format latex --output report.tex
```

This includes ordinary forecasting runs and workbench cases for the question.
Question versions and issued forecasts remain identifiable; a workbench checkpoint
is not presented as an issued forecast. Referenced evidence and forecast inputs
are loaded with integrity checks. Existing `report --question ID` JSON output
and `--format markdown` stdout output retain their previous behavior.

## One workbench case

```bash
vorhersage --project PROJECT workbench report CASE_ID --output report.html
vorhersage --project PROJECT workbench report CASE_ID --output report.tex
vorhersage --project PROJECT workbench report CASE_ID --output report.json
```

The extension selects the format, or use `--format html|latex|json` explicitly.
An unknown extension requires an explicit format. A `.json` output contains JSON,
not an HTML document with a different filename.

Reports cover:

- The precise question, deadline, resolution source, Yes/No/void rules, and version.
- Frozen market terms, selection rationale, research state, and sealed time.
- Initial estimate and subsequent predictions, with timestamps and reasons.
- Research plans, searches, findings, changed assumptions, remaining uncertainties,
  stopping reasons, exposure declarations, and post-reveal reflections.
- Linked model artifacts, parameters, calculations, scenarios, and sensitivity
  results as actually recorded. Missing model records are explicitly identified.
- Source-linked findings and numbered source records, including assertion and
  retrieval dates when available, quotations/paraphrases, and provenance.
- Opening and later market snapshots, spreads, depth, comparison qualifications,
  and market-agreement arithmetic after reveal. Before reveal, the target stays hidden.
- Limitations and recorded usage; missing usage is unmetered, not zero.

The main report leads with the assessment, a short prediction table, research
findings, assumptions, and market comparison. IDs, hashes, timestamps, nested model
records, and full source records live in a collapsed technical appendix. Browser
printing includes the reading view. LaTeX puts the technical appendix after the
main report. JSON retains all data.

The HTML has responsive tables and print styling. It needs no JavaScript,
external fonts, or network connection. LaTeX contains the same substantive sections.
Text from records is escaped in both formats; it is never interpreted as HTML or
LaTeX commands. Export preserves descriptions; it does not invent a narrative or
claim that a subjective estimate was mechanically derived from a model.

## Write an explanatory report

Stored research prose is used by default. For a polished explanation, the agent
or author should write a narrative that explains the mechanism, influential
numbers, revisions, and limitations in language a reader can follow:

```bash
vorhersage --project PROJECT workbench report CASE_ID --output report.html \
  --narrative narrative.json --attachment calculation.json
```

Both question and workbench reports accept `--narrative`. Its JSON structure is:

```json
{
  "record_sha256": "COPY_RECORD_SHA256_FROM_THE_REPORT_EXPORT_RECEIPT",
  "title": "An explanatory title",
  "summary": "The forecast, its main reason, and its most important uncertainty.",
  "sections": [
    {
      "heading": "How the model works",
      "paragraphs": ["Explain the mechanism before presenting its arithmetic."],
      "finding_refs": [],
      "table": {
        "headers": ["Assumption", "Basis"],
        "rows": [["An illustrative assumption", "Clearly labeled judgment"]]
      }
    }
  ]
}
```

The table and `finding_refs` are optional. Finding references use the
`packet_id:record_id` keys from the JSON report; their source links appear beside
the relevant explanation. Unknown references and narratives for a different
record snapshot are rejected. This validates record identity and citation
existence, not the truth of authored prose: the author remains responsible for
accurate claims and for avoiding price exposure in a hidden-target report.

Narrative prose is labeled as written at report generation. It cannot edit the
research journal or replace its probabilities. All original records remain in
the appendix and JSON. The NYC example's [narrative](../examples/market_workbench/nyc_20260916/narrative.json)
shows a complete explanation of the question, research, model, and comparison.

### Explaining the methodology

Give readers enough detail to reconstruct how the evidence became a probability:

- Describe case selection, research timing, and what was hidden. Distinguish
  choices declared before research from choices made after examining the data.
- Define the reference class: population, date window, issuance time or lead time,
  data fields, join rules, missing-data exclusions, and weighting. Explain any
  mismatch with the actual settlement rule.
- Define quantities such as forecast error and show a worked example. Explain
  how each fitted parameter is estimated and why it should apply to this question.
- Show the calculation from parameters to the final probability, including units,
  interval boundaries, and any independence, rounding, or distribution assumptions.
- Separate empirically estimated inputs from subjective allowances. Explain what
  sensitivity checks and alternative estimators change, and identify validation
  that was not performed.
- Define the comparison statistic and its limits. A market probability is a
  development target, not a resolved outcome.
- Point to the saved inputs and executable calculation. Label methodology prose
  written after the forecast; do not imply retrospective explanation was preregistration.

Keep this explanation in the reading view. Hashes, full data rows, and internal
identifiers can remain in the appendix. Equations should follow their plain-language
meaning rather than replace it.

### Methodology flowcharts

A narrative section can include a `flowchart` alongside its paragraphs:

```json
{
  "heading": "Methodology at a glance",
  "paragraphs": ["Read the steps from top to bottom."],
  "flowchart": {
    "caption": "Evidence and assumptions feed the estimate before the market is revealed.",
    "steps": [
      {"title": "Collect comparable cases", "text": "Apply the declared inclusion rules.", "kind": "data"},
      {
        "title": "Calculate and seal the estimate",
        "text": "Record the result before revealing market odds.",
        "kind": "result",
        "inputs": [{"title": "Error distribution", "text": "Declare its form and limitations.", "kind": "judgment"}]
      }
    ]
  }
}
```

Charts support 2–12 steps and up to three additional inputs per step. Node kinds
are `process`, `data`, `judgment`, and `result`. Use short titles and descriptions;
the prose can explain each step in detail. The HTML chart uses accessible text,
colored cards, and arrows without JavaScript or external assets. LaTeX uses TikZ
(the `tikz` package and its `positioning` library) only when a chart is present.
Charts share the narrative's record-snapshot binding and do not change forecasts.

## Include a saved calculation

For a calculation or research dataset saved outside the artifact store:

```bash
vorhersage --project PROJECT workbench report CASE_ID --output report.html \
  --attachment calculation.json
```

`--attachment` accepts JSON and can be repeated. Both question and workbench
reports support it. Attachments are rendered as structured fields and tables,
with their filename and SHA-256 hash. They are explicitly labeled as supplied at
report generation. They do not retroactively become sealed evidence, and scripts
are not executed. A hash can be checked against a commitment made during research.

For new forecasts, attach model artifacts through the existing research workflow
or workbench `model_artifact_ids` before sealing so their provenance is part of
the forecast itself.

## Compile LaTeX

Use **XeLaTeX or LuaLaTeX**, with the standard `fontspec`, `geometry`, `longtable`,
`array`, `xcolor`, and `hyperref` packages. Export itself has no LaTeX or Python dependencies
beyond those of vorhersage. Run twice to settle document references:

```bash
xelatex -no-shell-escape -halt-on-error report.tex
xelatex -no-shell-escape -halt-on-error report.tex
```

PDF compilation is a separate action, not part of the CLI export. Browser printing
is another option for the HTML report.

## Live example

The NYC temperature case has a [published HTML report](https://expectedparrot.github.io/vorhersage/examples/nyc-2026-09-16/),
a [PDF download](https://expectedparrot.github.io/vorhersage/examples/nyc-2026-09-16/full-report.pdf),
[LaTeX source](../examples/market_workbench/nyc_20260916/full-report.tex), and
[JSON report input](../examples/market_workbench/nyc_20260916/full-report.json).
The [compiled PDF](../examples/market_workbench/nyc_20260916/full-report.pdf) is also included.
Its calculation attachment includes all 31 forecast/observation pairs, sensitivity
scenarios, assumptions, and raw-file hashes. The original sealed forecast is unchanged.
