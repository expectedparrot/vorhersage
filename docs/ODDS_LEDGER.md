# Declared odds ledgers and interactive audits

`odds_ledger` is an assessment method. The agent supplies the anchor, likelihood
ratios, dependence groups, and rationale; Vorhersage checks the declarations and
calculates the result. The existing immutable task result is the belief-revision
record. Issuance freezes it in the forecast input manifest.

```sh
vorhersage schema odds_ledger
vorhersage odds-ledger --from ledger.json
vorhersage --project ./study export-widget FORECAST_ID --output audit.html
```

The standalone calculator takes the ledger directly. A workflow assessment takes
`method: "odds_ledger"`, an `odds_ledger` field containing that declaration, and the
usual `rationale`, `limitations`, and `evidence_refs`. Registered experiment methods
can select `assessment_method: "odds_ledger"`.

## Declaration

```json
{
  "anchor": {
    "probability": 0.2,
    "basis": "assumed",
    "rationale": "Illustrative assumed base rate."
  },
  "entries": [{
    "finding_id": "factory_status",
    "evidence_refs": [{"packet_id": "REPLACE_WITH_PACKET_ID", "record_id": "factory_status"}],
    "lr": 2,
    "lr_range": [0.5, 5],
    "direction": "supports",
    "dependence_group": "readiness",
    "rationale": "Subjective likelihood ratio for the observed readiness finding."
  }],
  "joint_declarations": [],
  "independence_rationale": "Only one evidence group is used.",
  "comparison_probability": 0.5
}
```

The likelihood ratio convention is `P(finding | YES) / P(finding | NO)`.
`supports` requires LR > 1, `opposes` LR < 1, and `neutral` LR = 1. The package
uses `logit(anchor) + sum(log(LR))`, then converts back to probability. This avoids
overflow from multiplying large ratios.

Anchors and optional comparison probabilities must be strictly between 0 and 1.
Ratios must be positive and finite. Optional ranges must contain their estimate;
omitting a range fixes that ratio in the sensitivity analysis and widget.

An `empirical` anchor requires `prior_artifact_id`, pointing to this run's
reference-class prior task result. Workflow submission verifies the type and
computed rate. That record contains the selection rule, cases, denominator,
evidence, and limitations. An assumed anchor may link a judgment prior in the
same way. Standalone arithmetic cannot resolve store references; workflow
submission performs that verification.

Each entry has one exact evidence reference matching its `finding_id`. Finding
IDs must be unique within the ledger. Evidence dependencies flow through normal
cutoff validation, issuance manifests, and monitoring.

## Dependence and sensitivity

Two or more entries in one group require a joint declaration:

```json
{
  "dependence_group": "board",
  "finding_ids": ["board_refresh", "strategic_review"],
  "lr": 1.6,
  "lr_range": [0.8, 3],
  "direction": "supports",
  "rationale": "Overlapping board signals; judge their combined likelihood."
}
```

The joint declaration must cover exactly all members of that group. Its ratio
**replaces** their individual ratios. Independence across groups remains an
explicit agent assumption; the package does not establish it from source text.

Sensitivity changes one effective ratio at a time over its supplied range. It
reports the resulting probability interval, the ratio that would match the
comparison probability, and whether that interval strictly crosses the comparison.
These are assumption ranges, not statistical confidence intervals. Extreme
thresholds also have a log-ratio representation so exports remain finite JSON.

## Widget behavior

The HTML is self-contained and works offline. Anchor and ratio controls update the
posterior, cumulative odds waterfall, and single-ratio sensitivity. Checkboxes
exclude effective terms. A dependence group with a joint declaration has one
control, with its constituent findings listed; separate member multiplication is
unavailable. Ratios stay within declared bounds. Reset restores the recorded ledger.

The issued forecast stays visible. If the review supplied a final judgment, the
page identifies the ledger as the earlier assessment and shows both values. A
forecast whose latest assessment used another method cannot export a stale ledger.
The export verifies manifest hashes and includes the frozen ledger and findings.
Untrusted record text is displayed as text, with escaped JSON embedding.

Slider changes are local exploration. Reviewer attribution, importing adjusted
ledgers as new revisions, and deadline-hazard terms are follow-up work.

## Working example

```sh
python examples/odds_ledger/demo.py
```

Open [the generated example](../examples/odds_ledger/demo.html). It uses a fictional
acquisition question, an assumed 12% anchor, overlapping board signals combined
at ×1.6, and a filing-search observation at ×0.7. The resulting probability is
13.25%. These are demonstration assumptions; no Upwork figures or real-company
observations were supplied for this implementation. The script builds a temporary
simulation project and exports its immutable forecast before removing the project.
