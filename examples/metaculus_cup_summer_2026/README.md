# Summer 2026 Metaculus Cup: historical research experiment

Use Vorhersage on the [Summer 2026 Cup](https://www.metaculus.com/tournament/metaculus-cup-summer-2026/?page=3),
with Exa Snapshot supplying evidence as of each simulated forecast date.
The provisional scope is the whole tournament, with a cutoff seven days after
each question opened. These defaults are recorded in [protocol.json](protocol.json).
A first [title-based pilot forecast](pilot_44241/forecast.md) has been issued for
the Lincoln Memorial Reflecting Pool question using a July 7 Snapshot cutoff.
It records 64% YES, with no outcome retrieved or scored. Original contract
criteria remain unavailable, and the pilot used the existing conversation;
it is not the isolated cohort evaluation described below.

## Current state

- Exa Snapshot search was successfully exercised against the live API. Its
  request/response and source hashes are in [smoke/search.json.gz](smoke/search.json.gz).
  This Python documentation query is an integration check, not tournament evidence.
- The authenticated inventory is saved: [browse the entries](cohort/entries.md)
  or use [entries.csv](cohort/entries.csv). The API returned 60 question posts
  containing 61 individual questions, plus two notebooks. All belong to tournament
  33021, and the next feed page was empty. Tournament metadata still reports 58;
  all returned entries are retained pending reconciliation.
- The account's data-access endpoint returns `has_data_access: false`. Titles,
  types, and dates are available, but **none of the 61 question criteria or
  resolutions were returned**. Single-question and grouped detail checks also
  lack those fields. Raw responses and explicit missing labels are under
  [cohort/evaluator](cohort/evaluator). Null resolutions never mean NO.
  See [acquisition.json](acquisition.json) for the acquisition receipt.
- `experiment.py` can download an inventory when API access works, or import a
  saved Metaculus post export. It retains all question types and keeps raw exports
  on the evaluator side. Historical wording/deadline review precedes forecasting.
- The first scoring adapter supports binary questions. Numeric, date, multiple
  choice, conditional, and grouped questions are retained for a later adapter;
  they are not silently converted into arbitrary binary thresholds.

## Acquire and review the questions

Run from the repository root, using a fresh output directory. Set the required
`METACULUS_API_TOKEN` (or `METACULUS_API_KEY`) environment variable using the token at
[account settings > API Access](https://www.metaculus.com/accounts/settings/account/#api-access).
It is sent only to Metaculus and is never saved. The script does not automatically
load `.env`; export the variable before running it.

Authentication succeeded on September 20 after loading the configured key.
[Metaculus's API documentation source](https://github.com/Metaculus/metaculus/blob/main/docs/openapi.yml)
also distinguishes authenticated access to open questions from closed-question
text and resolutions (normally questions the account predicted on). For wider
historical access, use its linked Data Needs Form and specify this tournament.
The same documentation requires written permission for AI/ML evaluation; include
the retrospective forecasting evaluation purpose in the request.

```bash
.venv/bin/python examples/metaculus_cup_summer_2026/experiment.py acquire \
  --feed-only --out examples/metaculus_cup_summer_2026/cohort-new

# Alternatively, import a complete array of Metaculus post detail objects:
.venv/bin/python examples/metaculus_cup_summer_2026/experiment.py import \
  --from /path/to/posts.json --out examples/metaculus_cup_summer_2026/cohort-new
```

Importing a file does not certify tournament membership or completeness. Review
the inventory against the tournament before selecting cases. `inventory.json`
and `review.json` contain current wording and are curator inputs, not certified
historical evidence. Keep them out of the forecasting environment.

For each included binary question, fill its review entry with historical
`text`, `yes`, `no`, `void`, `event_deadline`, `resolve_after`, `domain`, and
`event_group`. Record the source and explanation in `audit_note`, and set
`approved` to true only after verifying the wording existed at the cutoff and
the event was not already knowable then. Use archived criteria, not current
resolution comments. Related questions should share an event group.
Record reasons for exclusions in `audit_note`. A missing archive is a missing
case; never move its cutoff later just to find evidence.

```bash
.venv/bin/python examples/metaculus_cup_summer_2026/experiment.py prepare \
  --cohort examples/metaculus_cup_summer_2026/cohort \
  --out examples/metaculus_cup_summer_2026/frozen
```

This creates hashed `agent/cases.json`, `evaluator/labels.json`, and a manifest
compatible with Vorhersage's replay evaluator. Only reviewed, resolved binary
cases are eligible. Current crowd values, comments, background, resolutions,
and raw post bodies never enter `agent/cases.json`. Free text still needs review.

## Research and forecast

Use a fresh forecasting process with only `frozen/agent/cases.json`, the runner,
and its empty project available. The current setup conversation has already
seen present-day tournament information and must not be a forecasting context.
Directory separation is a convention; restrict filesystem and network tools in
the actual worker. Its only external research route should be this runner's
`search` and `fetch`, which pin the case cutoff and exclude Metaculus pages.

Set `EXA_API_KEY` in the worker environment. The library does not load `.env`.
Choose and record the model, model version, training cutoff if known, and budget
before running the cohort. Start one shared project per cohort repetition:

```bash
.venv/bin/python examples/metaculus_cup_summer_2026/experiment.py start \
  --cases examples/metaculus_cup_summer_2026/frozen/agent/cases.json \
  --case CASE_ID --project examples/metaculus_cup_summer_2026/runs/cup
.venv/bin/python examples/metaculus_cup_summer_2026/experiment.py search \
  --cases examples/metaculus_cup_summer_2026/frozen/agent/cases.json \
  --case CASE_ID --project examples/metaculus_cup_summer_2026/runs/cup \
  --query 'a question-specific research query'
.venv/bin/python examples/metaculus_cup_summer_2026/experiment.py fetch \
  --cases examples/metaculus_cup_summer_2026/frozen/agent/cases.json \
  --case CASE_ID --project examples/metaculus_cup_summer_2026/runs/cup \
  --url https://example.com/source
```

Continue through `vorhersage next`, `research capture --retrieval ID --from
findings.json`, and `submit`. Cite passages present in saved snapshot text and
report search usage in submissions. The run uses the deep research workflow,
including reference-class construction or a documented exception. The runner
limits each project's research requests and records the protocol and case hash.
An empty result stays empty; it does not trigger a live-web retry.

After all forecasts are frozen, a separate evaluator can use `benchmark evaluate`
with the frozen cases, labels, manifest, and an evaluation policy listing the
issued forecast IDs and forecasters (see [the replay guide](../backtesting/README.md)).
Start each case once in the shared project. Use fresh projects for repetitions.
Do not report setup smoke results as forecasting performance.

## What the cutoff does and does not establish

[Exa Snapshot](https://exa.ai/docs/search/snapshot) supplies a stored version at
or before the requested time. Search ranking uses current signals. Model weights
may contain outcomes; prefer a model predating the target outcomes and record
recognition of any result. Self-reported nonrecognition is not proof of absence.
Question revisions, outcome-aware case selection, prompts, reference-class data,
and unbounded tool access can also leak information.

This is a retrospective experiment with bounded retrieved content, not a
certification of zero leakage. Keep actual retrieval and forecast issuance times.
On September 20, 2026, Exa documents a rolling five-month pay-as-you-go window
and 100 preview requests before contacting sales. Even five searches across
58 questions would exceed that allowance. Start with a small, prespecified pilot
and archive responses while the May cutoffs remain accessible.
