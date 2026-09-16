# One-question market workbench

Pick one unresolved market, record an initial estimate, investigate specific
uncertainties, and reveal the market probability after sealing the research.
The comparison is available immediately: no actual resolution is needed.

This workflow helps develop evidence collection and reasoning. The agent chooses
the research and probabilities; the package preserves the sequence and computes
agreement with a market target. It does not select or call a model automatically.

Open the [fictional demonstration](../examples/market_workbench/demo.html), or run
the complete offline CLI example into a **new** directory:

```bash
.venv/bin/python examples/market_workbench/walkthrough.py /tmp/my-workbench-demo
```

## 1. Browse without seeing prices

```bash
vorhersage workbench browse --venue kalshi --series KXRATECUT --limit 5
vorhersage workbench browse --venue polymarket --query election --pages 3 --limit 5
vorhersage workbench inspect --venue kalshi --market KXRATECUT-26DEC31
```

Kalshi accepts a series filter; Polymarket discovery starts with markets ordered
by recent volume. `--query` filters the fetched titles/rules locally. Discovery
is bounded (`--pages` defaults to 3), not an exhaustive exchange-wide search.
`more_available` records truncation. Both commands return allowlisted contract
fields without quote, volume, or numerical forecast fields. Contract text is
external content and can itself mention an outside forecast; report exposure.

These are public GET requests. API failures are surfaced without response bodies,
which could otherwise accidentally expose prices. Only binary Yes/No contracts
are supported. The Polymarket adapter maps the **Yes outcome token explicitly**;
the Kalshi adapter derives asks from complementary No bids. Midpoints are computed
from the order book rather than a potentially stale displayed last-trade price.

## 2. Register the question and save the hidden target

Use a fresh research project. The evaluator directory must be separate and cannot
be inside, or contain, the research project:

```bash
vorhersage init /tmp/case-research
vorhersage --project /tmp/case-research question add --from question.json
vorhersage --project /tmp/case-research workbench start \
  --from start.json --vault /tmp/case-evaluator
```

Use `vorhersage schema question` for the ordinary question specification. Check
the exchange's complete rules and source documents, then write the precise event
deadline yourself. Trading close, administrative settlement, and event deadline
can differ. In particular, Polymarket's `endDate` can be a midnight date marker
for an event that occurs later that day. It is not automatically a deadline.

Example `start.json` (replace identifiers with the selected question/contract):

```json
{
  "question": {"question_id": "my-question", "version": 1},
  "venue": "kalshi",
  "market_id": "KXRATECUT-26DEC31",
  "mode": "prospective",
  "method": "Targeted research on influential assumptions",
  "eligibility_rationale": "Checked the elapsed window; no qualifying event is known.",
  "contract_match_rationale": "Question matches the contract's event, window and exceptions.",
  "max_spread": 0.05,
  "min_contracts_each_side": 1
}
```

The optional selection limits default to a five-cent spread and one contract on
each best quote. They are deliberately lightweight and configurable. A fresh
snapshot must have an active market, positive two-sided depth, and an uncrossed
quote strictly between zero and one. The evaluator retains raw responses,
timestamps, terms and book statistics. These checks do not establish calibration
or a genuinely unknown outcome; the eligibility explanation remains necessary.
There is no insider-information assessment.

`start` prints a case ID, question, frozen contract terms, and commitment to the
hidden target. It does **not** print the price or store it in the research project.
The evaluator project initializes automatically if needed.

For an offline fixture only, set `mode: simulation`, use a simulation question,
and supply `--snapshot FILE`. Supplied snapshots are refused in prospective mode.
Historical quotes cannot be relabeled as fresh targets through this option.

## 3. Give the researcher a clean input

```bash
vorhersage --project /tmp/case-research workbench export CASE_ID --output researcher-input.json
vorhersage --project /tmp/case-research workbench show CASE_ID
```

Start a fresh model context with the exported input and access to the research
project only. Keep the evaluator directory and coordinator's conversation away
from that worker. The export includes relevant attached findings and models, and
instructions to avoid outside probabilities for the target event.

**This is storage separation, not a security sandbox.** These commands do not
restrict filesystem or internet access. An agent that can read the evaluator's
directory or retrieve market odds can see the target. A search snippet or article
can also reveal it. Record those incidents with `workbench_exposure`; do not call
the result independently blinded. Separate-context execution is managed by the
calling agent/tool environment, not automatically launched here.

## 4. Record an initial judgment, then plan and research

Every journal submission has the same envelope:

```json
{
  "kind": "initial",
  "expected_revision": 0,
  "idempotency_key": "initial-1",
  "payload": {
    "probability": 0.5,
    "rationale": "Initial judgment before researching this case.",
    "assumptions": ["The main prerequisite may still be incomplete."],
    "uncertainties": ["Current prerequisite status"],
    "research_status": "not_started",
    "evidence_refs": []
  }
}
```

```bash
vorhersage --project /tmp/case-research workbench submit CASE_ID --from initial.json
```

The 50% above is an example, not a required starting probability. If research has
already started, use `in_progress` or `completed`; the journal does not mislabel
that estimate as a pre-research prior. Existing evidence can be cited immediately.

Next submit `kind: plan` with the current revision and a new idempotency key:

```json
{
  "uncertainty": "How often do comparable projects miss this remaining window?",
  "why_it_matters": "The forecast depends heavily on the assumed delay rate.",
  "higher_if": "Comparable projects with these prerequisites usually finish in time.",
  "lower_if": "Comparable projects frequently require more time than remains.",
  "search_plan": "Define comparable cases before collecting outcomes; include successes and failures.",
  "stopping_rule": "Stop after checking the specified registry and documenting unavailable cases."
}
```

The JSON above is the **payload**, wrapped in the same submission envelope.
Only one research plan can be pending. Research happens outside the package using
the agent's tools; import findings with the existing evidence interface:

```bash
vorhersage --project /tmp/case-research research capture --from findings.json
vorhersage schema research_bundle
vorhersage schema workbench_checkpoint
```

Then submit `kind: checkpoint`, including:

- `probability` and `rationale`: the revised estimate and its justification;
- `findings`, `changed_assumptions`, and `remaining_uncertainties`;
- `sources_checked`, imported `evidence_refs`, and `limitations`;
- optional `model_artifact_ids` for saved calculations, and optional `usage`.

Unchanged probabilities and unsuccessful searches are legitimate checkpoints.
Describe what was checked and what remains unknown. Missing usage is **unmetered**,
not zero. Model links preserve calculations for inspection; they do not claim that
the checkpoint's subjective probability was mechanically derived from those models.
Evidence and model references are validated and pinned by hash.

Repeat plan → research → checkpoint as useful. `show` reports the revision and
next action. Retries with an identical idempotency key return the original result;
stale revisions and conflicting retries fail without changing history. Recorded
timestamps come from the package, not the agent's payload.

## 5. Finish, reveal, and compare

Submit `kind: finish` with this payload:

```json
{
  "stopping_reason": "The remaining uncertainties need unavailable information.",
  "outcome_status": "unresolved",
  "market_exposure": "none",
  "exposure_notes": "No outside probability for the event was sought or observed."
}
```

This seals the trajectory at its last checkpoint (or initial judgment). A clean
finish requires completing the pending research step. If an outcome becomes
known or uncertain, record that instead; the case remains inspectable but is
qualified in the comparison. Exposures can also be recorded as soon as they occur:

```json
{
  "kind": "market_probability",
  "description": "An unrequested search snippet contained the market odds.",
  "occurred_at": "2026-09-16T12:00:00Z"
}
```

That is the payload of a `kind: exposure` submission. Late disclosures of exposure
during research update the report's eligibility label without altering forecasts.

The coordinator then runs:

```bash
vorhersage --project /tmp/case-research workbench reveal CASE_ID --vault /tmp/case-evaluator
vorhersage --project /tmp/case-research workbench report CASE_ID --output comparison.html
vorhersage --project /tmp/case-research workbench report CASE_ID --output report.tex
```

These are full research reports, including the question, contract, journal, linked
models, prediction history, evidence, sources, and limitations. The extension
selects HTML, LaTeX (`.tex`), or JSON. See [full report exports](REPORTS.md) for
question-wide reports, supplemental calculation files, and PDF compilation.

Reveal fetches a later quote and publishes the **original opening target** into
the research project. A failed refresh is explicitly recorded; it does not prevent
revealing the saved target. `--skip-refresh` intentionally omits that secondary
check. Repeating reveal returns the existing reveal without fetching new prices.
For a simulation, provide a new `--snapshot` after finish or use `--skip-refresh`.

For each checkpoint, the report shows `(estimate - opening_midpoint)^2`, the gap
in percentage points, and improvement from the prior checkpoint. The JSON
comparison also records distance outside the spread. Positive improvement means
closer agreement. The report retains the
research plans, findings, source references, and reasons for each revision.

The later quote shows market movement separately, with its own timestamp. It
never silently replaces the target. Changed terms trigger a comparability warning;
movement is not calculated across different contracts. Neither snapshot is an
actual resolution, and ordinary outcome evaluations are unaffected.

Research can encounter information published after the opening target. Inspect
timestamps and movement before interpreting a step's agreement change. One case
does not establish causal benefit, accuracy, or general superiority of a method.
The bid–ask spread is not a confidence interval.

## 6. Learn from the disagreement on a fresh case

After reveal, submit `kind: reflection` with `what_helped`, `what_did_not`, and
`next_method_change`. The sealed trajectory cannot be rewritten. Post-reveal
reflections are labeled as such; a revealed case cannot be exported as a new blind
case. Further exploratory reasoning is useful, but test any method change on a
new live question whose target has not been revealed.

All payloads are discoverable with `vorhersage schema workbench_NAME`. The market
workbench stores its own checkpoints rather than manufacturing issued ordinary
forecasts or resolutions. Existing forecasting workflows can be used alongside it
and their artifacts linked to checkpoints.

### API references

- [Kalshi public market-data quickstart](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Kalshi order books](https://docs.kalshi.com/api-reference/market/get-market-orderbook)
- [Polymarket market data](https://docs.polymarket.com/market-data/overview)
- [Polymarket prices and order books](https://docs.polymarket.com/concepts/prices-orderbook)
