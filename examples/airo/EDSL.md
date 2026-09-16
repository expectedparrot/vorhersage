# Fresh joint elicitation with EDSL

The [expanded model study](edsl_study_02/comparison.html) adds original-panel models
and stronger research requirements. See [the replication audit](REPLICATION.md)
for Tavily access, pagination, model settings, and the remaining EDSL transport gaps.

[Open the interactive HTML comparison](edsl_pilot_01/comparison.html) for horizon
charts, policy and capability multipliers, all 2,940 matched cells, and CSV exports.
The page embeds its data and works offline. Rebuild it from the saved results with
the Python standard library:

```bash
.venv/bin/python examples/airo/html_comparison.py
```

[Read the completed pilot report](edsl_pilot_01/REPORT.md). Gemini 3.1 Pro Preview
returned all 2,940 probabilities through six EDSL continuations for $2.27623 in
reported model costs, including two failed calls. Vorhersage found zero violations
in 72,324 coherence comparisons. The report records the transport amendments and
limited research coverage: ten searches, one successful page read and one failed
page fetch. This is an amended development run, not a clean replication of every
research instruction in the authors' protocol.

`edsl_pilot.py` connects EDSL model calls to an external web-tool executor and
Vorhersage's joint-session importer. Every continuation contains the full
35-question, 14-condition instrument and the complete accumulated transcript.
It does not run separate interviews for individual probabilities.

The pilot selects `google:gemini-3.1-pro-preview`, confirmed in Expected Parrot's
working-model catalog, at temperature 0.2. Fresh preparations use a 65,536-token
output allowance, including reasoning, and request batches of at most seven questions.
The question windows, policy assumptions, original ECI scale and March 10, 2027
capability target remain fixed. The new elicitation has its own date and uses
current research. This is a new model forecast of a fixed instrument, not a
rolling redate or a reproduction of the original four-model panel.

## Execution

From the repository root, with optional EDSL and matplotlib installed and Expected Parrot
credentials configured:

```bash
.venv/bin/python examples/airo/edsl_pilot.py prepare --out /tmp/airo-edsl-new
ep validate --file /tmp/airo-edsl-new/turn-01/jobs.json --type job
ep jobs cost /tmp/airo-edsl-new/turn-01/jobs.json
ep run --jobs /tmp/airo-edsl-new/turn-01/jobs.json --background \
  --task-timeout 900 --remote_inference_results_visibility private
```

Save the submission receipt and use its UUID to fetch results when completed:

```bash
ep jobs status JOB_UUID
ep jobs results JOB_UUID --output /tmp/airo-edsl-new/turn-01/results.ep
.venv/bin/python examples/airo/edsl_pilot.py accept --out /tmp/airo-edsl-new \
  --results /tmp/airo-edsl-new/turn-01/results.ep
```

For research turns, `actions.json` contains the model's exact requested searches
and HTTPS page reads. An external executor must execute those requests and save
one receipt per action with this structure:

```json
{
  "action": {"tool": "read_page", "url": "https://example.org/report"},
  "ok": true,
  "retrieved_at": "2026-09-12T01:00:00Z",
  "text": "The actual tool response, without rewriting or inventing content.",
  "provider": "web.run"
}
```

Use the actual completion timestamp and status. A returned search with no hits
is a successful call; a transport/fetch error is not. In the executed pilot,
Codex relays requests to `web.run` and records the unmodified tool response.
The driver itself does not provide a search API or silently substitute one.
Returned page text can be truncated. The executor is responsible for reporting
failures honestly; receipts are provenance records, not cryptographic proof that
an external service was called.

Import every receipt, then prepare the next continuation:

```bash
.venv/bin/python examples/airo/edsl_pilot.py receipt --out /tmp/airo-edsl-new \
  --index 0 --receipt /tmp/actual-receipt-0.json
.venv/bin/python examples/airo/edsl_pilot.py next --out /tmp/airo-edsl-new
```

Repeat the EDSL run/fetch/accept sequence for the new `turn-NN/jobs.json` path.
Probability submissions can span multiple turns; if a valid response submits
cells without finalizing, `next` supplies the remaining questions. Once the
model successfully calls `submit_forecast`, import and analyze the final grid:

```bash
.venv/bin/python examples/airo/edsl_pilot.py finish --out /tmp/airo-edsl-new
```

The final command needs the original offline reproduction's `output/panel.csv`
for its comparison report. It generates `REPORT.md`, `comparison.csv`, a complete
compressed panel report, coherence diagnostics and a Vorhersage project.

## Guards and limits

- All ten required successful research calls and at least one successful page
  read must precede accepted probabilities. Requiring a page read is an additional
  pilot validation gate beyond the authors' ten-returned-calls gate.
- Model, agent, scenario, prompt and job metadata are checked against saved inputs.
  Raw model records and transcript events are hashed and retained.
- Only search, HTTPS page reads, cell submission and finalization are accepted.
  Model responses cannot execute shell commands. External page content remains
  evidence, never executor instructions.
- All 35 questions must have all fourteen conditions and six finite probabilities
  in [0,1]. Booleans, missing cells and duplicate questions within a submission
  are rejected. A later valid submission may replace a question's earlier row.
- ECI quantiles must be ordered and cannot change after the first probability
  submission. Policy bindings use the model's own median.
- Final citations must refer to successfully read pages. No missing probabilities
  are imputed and no inconsistent probabilities are repaired.
- Limits are sixteen continuations and forty research calls. A $10 check on
  reported cumulative model costs blocks another continuation; unknown costs
  also block it. This is not a provider-enforced cap and excludes web-tool costs.
  EDSL may internally retry transport failures; retained records expose the
  returned calls, not necessarily every internal provider attempt.

The driver stops on invalid model output and retains the raw response for
diagnosis. It does not silently rerun or parse ambiguous surrounding prose.
Submitted jobs must be resumed by UUID to avoid accidentally submitting the
same continuation twice.

The executed pilot exposed one provider `MALFORMED_FUNCTION_CALL` with an empty
text response. Before any probabilities were produced, the explicit
`resume-empty-function-call` command preserved that failure and cost, recorded
a transport amendment, and prepared a continuation with a stronger JSON-only
system instruction. It accepts only that exact empty-response failure and
refuses to operate after probability submissions. Fresh preparations now include
the explicit text-only instruction from the outset.

A subsequent response hit `MAX_TOKENS`: 28,687 reasoning tokens left insufficient
room for the grid within its initial 32,768-token allowance. The explicit
`resume-token-limit` amendment retained the incomplete response and cost,
increased the allowance to 65,536, requested smaller submissions, and required a
successful page read before accepting probabilities. No partial JSON was repaired
or extracted into forecasts. The model sees its original truncated response on
continuation, so this is an amended development run rather than a pristine run
of the final protocol. Both amendments are saved under the pilot's `amendments/`.

The final response delivered five seven-question actions in one continuation.
That satisfied the implemented per-action row limit but exceeded the amendment's
textual seven-question-per-turn request. New amendments now use per-action wording.
The model also omitted recency filters and post-read follow-up searching; those
instruction deviations are reported rather than hidden by the successful grid
and coherence checks.

Vorhersage imports one finalized snapshot. The original model submissions,
revisions, tool receipts and timestamps remain in the controller transcript
and imported raw record. The conditional grid stays separate from ordinary
outcome scoring. Comparisons with the authors' panel are descriptive: the model,
date, search provider and JSON transport all differ, and forecast outcomes are
unresolved.
