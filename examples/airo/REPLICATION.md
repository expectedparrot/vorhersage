# Replicating the AIRO elicitation

The original saved outputs reproduce exactly (376 numerical checks). Producing
new forecasts is a separate replication question. The expanded EDSL study runs
three available original models plus Gemini, using independent model-selected
research on the original September 10 instrument. This does not recreate the
original September 10 information set or identify a causal effect of EDSL.

## What the authors actually ran

Source commit: `646da9a2cd61f7043f46b2ccd4ac53e525925018`.

- [Research tools](https://github.com/forecastingresearch/airo/blob/646da9a2cd61f7043f46b2ccd4ac53e525925018/redlines/tools.py):
  Tavily advanced search, normally five results, up to ten; result passages
  capped at 1,500 characters. Recency searches use the news index with exact
  start and end dates. General searches have no date bound.
- Page reads use Tavily basic extraction and 7,000-character windows, with
  `offset`, `total_chars`, and `next_offset`. The authors could read beyond the
  first window; this was missing from our first pilot's action schema.
- [Model runner](https://github.com/forecastingresearch/airo/blob/646da9a2cd61f7043f46b2ccd4ac53e525925018/redlines/llm.py):
  native tool messages, accumulated conversation, Anthropic signed thinking
  blocks, and an 8,000-character limit on each tool reply. Reasoning starts at
  `xhigh` for OpenAI and adaptive `max` for Anthropic, with recorded fallback
  for rejected parameters. It does not silently disable reasoning.
- [Joint run](https://github.com/forecastingresearch/airo/blob/646da9a2cd61f7043f46b2ccd4ac53e525925018/code/run_unified.py):
  64,000 output tokens, a 40-turn termination guard, and a ten-returned-tool-call
  submission floor. The prompt requests research in rounds and recency checks
  by cause, but does not set a six-page requirement. The guard is not disclosed
  as a research budget. Observed sessions recorded 6–16 page-read calls;
  these can include multiple windows of the same page.

**Firecrawl is not required.** Tavily search and extraction provide the closest
provider match. Firecrawl could be a separately labeled provider experiment;
changing it would not by itself recover the authors' prompts, model settings,
research decisions, or original information set.

## Expanded live EDSL study

`edsl_study_02/study.json` freezes the roster and design. Its original
registration settings remain unchanged when an audited amendment is applied.

| Session | Requested reasoning | Relationship to original panel |
| --- | --- | --- |
| GPT-6 Astra | xhigh | Original model name; EDSL uses Chat Completions, authors used Responses |
| Claude Opus 5 | adaptive / max | Original model name |
| Claude Fable 5.1 | adaptive / max | Original model name |
| Gemini 3.1 Pro Preview | Provider default; temperature 0.2 | Repeat of our pilot model under expanded research |

GPT-5.5 Pro was absent from EDSL's working-model catalog at preparation. Regular
GPT-5.5 is not silently substituted. Requested settings are saved with every
job; returned reasoning usage must be inspected separately.

**Astra reasoning discrepancy discovered during execution:** the local EDSL
adapter recognizes GPT-5.6 but omits GPT-6 from its reasoning-model list. Its
request builder drops `reasoning_effort="xhigh"` for Astra, despite retaining
that value in the saved model specification. Early returned Astra usage also
reports zero reasoning tokens. This run therefore does **not** establish a
match to the authors' reasoning settings. `edsl_reasoning_audit.py` reproduces
the omission, regression-checks a one-line fix, and writes
`edsl_study_02/astra-reasoning.patch`. The patch is not applied to the installed
package or deployed to remote workers. The exact remote request body is not
available to this audit. Both Chat Completions and Responses adapters share
the affected model list; the Responses catalog did not list Astra or GPT-5.5 Pro.

The audit also produces `anthropic-streaming.patch`, exercising the patched
adapter against a fake SDK at 20,000 and 64,000 tokens. Large requests use
`messages.stream()` and return the complete final message, retaining adaptive/max
settings. This patch is also not deployed. The live Opus session exhausted the
20,000-token cap entirely on thinking, then continued after an explicit max-to-high
effort amendment. Fable returned a provider refusal after research and was ended,
with the refusal cost included. Neither outcome is hidden or treated as an exact
reproduction of the authors' model configuration.

The expanded gate requires 16 successful calls, eight distinct successful search
queries, six distinct successfully read URLs, four distinct recency-filtered
searches, and a search requested in a later model turn after receiving a successful
page read. It allows up to 60 research calls and 32 model continuations. These
are our explicit additions, not a claim that the authors used those thresholds.
Topic coverage and whether the model substantively uses a source still require
an audit; a numeric tool gate alone cannot establish research quality.

Each response can submit at most seven question rows total. Forecasts are never
repaired or replaced by a different model. The initial Anthropic requests were
rejected before inference because EDSL's non-streaming adapter would not accept
64,000 tokens. Saved zero-cost failures and amendments lower the allowance to
20,000, retaining adaptive/max reasoning. New preparations use that limit.

The first expanded wave uses `web.run`, because no Tavily key was available in
the execution environment. This is a material provider difference: web.run's
recency filter is not the authors' exact-date Tavily news filter, and it does
not expose a result-count parameter. Raw service returns are retained; search
excerpts are limited to approximately the authors' tool envelope, and extracted
page representations are cached and windowed. A page can be incomplete at the
provider level even after every available window is read.

## Run and resume

The completed wave has three final grids (Astra, Opus, Gemini), one retained
Fable refusal, and $19.310065 in reported model costs. Each imported grid has
zero violations in 72,324 coherence comparisons. The independent raw-output
replay checks all 8,820 probabilities and reconciles every attempt's model cost.
See [results and comparisons](edsl_study_02/REPORT.md).

```bash
.venv/bin/python examples/airo/edsl_study.py prepare --out /tmp/airo-expanded --provider tavily
.venv/bin/python examples/airo/edsl_study.py status --out /tmp/airo-expanded
```

Set `TAVILY_API_KEY` in the execution environment for the Tavily executor. Do
not put credentials in a registration, transcript, or command-line argument.
Use the existing EDSL prepare/run/accept/next sequence in [EDSL.md](EDSL.md).
For each pending Tavily action, execute and record it with:

```bash
.venv/bin/python examples/airo/research_bridge.py tavily --out /tmp/airo-expanded/astra --index 0
```

For web.run, the external executor saves the exact requested action, actual
completion timestamp, actual status, full response text and provider in
`capture-N.json`; `research_bridge.py ingest` creates the paginated receipt.
Failed requests stay failures. No provider fallback is performed silently.

Rebuild the completed study's comparison and verify its data without new calls:

```bash
.venv/bin/python examples/airo/study_report.py
.venv/bin/python examples/airo/verify_study.py
.venv/bin/python examples/airo/edsl_reasoning_audit.py
```

## What would isolate the remaining differences

1. Compare each new original-model session to that same original model, alongside
   the panel comparison. Do not treat a three-model panel as the original four.
2. Repeat Gemini with expanded research and compare it to the first pilot. A
   single repeat changes both research and sampling; it cannot identify which
   change caused any probability difference.
3. Run repeated paired experiments using frozen evidence, identical model and
   reasoning settings, and common prompts through the authors' native tool
   transport and EDSL. This tests transport while holding visible information
   fixed. A forced replay of an original evidence trail is an experiment, not
   independent live research, and should be labeled that way.
4. Run the original Tavily/native workflow separately to assess fidelity to the
   published live procedure. Exact historical probabilities are not expected
   from new stochastic calls or a changed information date.
