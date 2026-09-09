# Patriots research stored in Epiq

Implemented September 9, 2026. This is a narrow CLI adapter for the recorded
Patriots case, not a general Vorhersage backend or an autonomous researcher.

The integrated run reconstructs its evidence from Epiq and produces **6.048%**,
matching the researched second run. That is expected: storage and provenance
changed, while the recorded probability judgments stayed the same. It is an
integration check, not new evidence for forecasting accuracy.

## Saved results

- [Research database](epiq_integration/patriots.sqlite): the dedicated local Epiq project.
- [Research table](epiq_integration/research.html): an inspectable HTML export.
- [Frozen evidence packet](epiq_integration/frozen/evidence_packet.json): portable
  source content, claims, identifiers, lineage, import history and replay template.
- [Reconstructed case](epiq_integration/frozen/case.json): inputs materialized from
  the packet rather than the original case's source observations.
- [Issued forecast](epiq_integration/output/forecast.json): probability, Epiq project
  identity, packet hash and immutable input manifest.
- [Run transcript](epiq_integration/output/TRANSCRIPT.md).
- [Comparison](epiq_integration/comparison.json): all three runs and their distinct purposes.

The database contains 33 entities, 16 evidence records and 76 claims. These
represent two domain entities, 16 captures and 15 findings. The claim count also
includes readable finding text and typed links to the domain entities; it does
not mean 76 independent pieces of evidence. The packet selects 31 capture/finding
records with their supporting lineage.

## What each component does

Epiq stores source observations as `ResearchCapture` rows and findings as
`ResearchFinding` rows. `finding_text` makes the claims readable, and `about`
links them to the Patriots and the championship. Full capture/finding records
use Epiq's `Json` type for lossless transport. Numerical football fields have not
yet been normalized into separate typed questions; that would make broader
cross-team analysis easier later.

Vorhersage owns the resolution contract, required research coverage, driver map,
conditional judgments, review, issuance and scoring examples. The adapter uses
Epiq's CLI for every database operation, with an explicit database path. It does
not change Epiq's code, select a global project, or write SQL directly.

The import writes through Epiq's atomic `batch-write` operation after schema
creation. The entire schema-plus-batch sequence is not one transaction. A seed
manifest identifies the case and project, allowing an identical import to be
retried without duplicating claims. Existing databases without that manifest and
different seed cases are rejected.

Freezing first asks Epiq for a transactionally consistent SQLite export. All
packet reads then use that snapshot, so concurrent changes to the live database
cannot produce a mixture of different versions. Every selected cell must be
`Answered`; contested or withdrawn required inputs need review before a new
packet can be issued. This does not resolve all possible contradictions in the
underlying research. Disagreements already represented inside the recorded
findings still proceed to the existing reconciliation task.

The packet preserves exact claim and evidence IDs, source URLs, excerpts,
locators, temporal metadata and Epiq assertion events. It verifies that selected
values match those assertions and that each finding references the evidence of
its selected captures. Vorhersage includes the packet as a forecast input and
links source artifacts to it. Hashes detect changed content; they are not
signatures or third-party timestamps.

## Research time versus import time

The original research cutoff is **2026-09-09 10:27:04 UTC**. This Epiq project was
created later that day. Original observation dates are retained as the imported
claims' observation times; Epiq's actual recording times remain in its history.
The packet explicitly carries both the research cutoff and Epiq recorded cutoff.

Importing an old observation today does not mean Epiq knew it at the original
research date. It also does not independently prove that the source content was
available then. We are replaying previously recorded research, not manufacturing
a historical live submission.

Evidence excerpts are explicitly labeled **structured analyst transcriptions**.
They contain the saved source observations, not freshly fetched pages or verbatim
article text. Epiq's imported `medium` confidence is an import label, not a fitted
confidence measure or the probability of winning the championship. Epiq evidence
assessment status remains visible in the packet.

## Run or inspect it

Python 3.11+ is needed for Epiq. With the sibling checkout, these commands require
no installation or network access. Run them from the Vorhersage repository root.

Retry the import into the existing dedicated database:

```bash
python3 examples/patriots_2027/epiq_bridge.py seed --epiq-source ../epiq/epiq/src
```

Create another freeze and replay in fresh output directories:

```bash
python3 examples/patriots_2027/epiq_bridge.py freeze --epiq-source ../epiq/epiq/src --out /tmp/patriots-epiq-frozen
python3 examples/patriots_2027/epiq_bridge.py replay --packet /tmp/patriots-epiq-frozen/evidence_packet.json --out /tmp/patriots-epiq-replay
```

Choose unused output paths. Freeze and bridge replay refuse to overwrite their
output directories. A failed freeze can leave a diagnostic SQLite snapshot in
its directory, but produces no accepted packet or forecast.

If `epiq` is installed, omit `--epiq-source`. To seed another database, supply
`--db PATH` to both seed and freeze. Replay only requires the packet and Python;
it does not read the Epiq database, source checkout, or original case file.

Inspect reusable finding text and entity relationships directly in Epiq:

```bash
env PYTHONPATH=../epiq/epiq/src python3 -m epiq --db examples/patriots_2027/epiq_integration/patriots.sqlite matrix --kind ResearchFinding --questions finding_text,about
env PYTHONPATH=../epiq/epiq/src python3 -m epiq --db examples/patriots_2027/epiq_integration/patriots.sqlite related "New England Patriots"
```

## Validation and remaining work

All **21 tests** pass, including real CLI round trips through disposable Epiq
databases. Tests cover import idempotency, unrelated-project protection,
retrieving values from Epiq rather than the original case, typed entity links,
contested inputs, cutoff enforcement, packet tampering and forecast provenance.
A retracted finding blocks a new freeze; the previously frozen packet still
replays to its original probability.

```bash
python3 -m unittest discover -s examples/patriots_2027 -p 'test_*.py'
```

The four CLI integration tests use the sibling checkout, `EPIQ_SOURCE`, or an
installed `epiq`; they explicitly skip when none is available. Packet tests and
the original workflow tests run without Epiq.

Selection currently uses an explicit list of capture/finding IDs, and the small
dedicated database's event history is included in full. General retrieval by
entity, domain and time; selective event export; automatic monitoring of new
claims; forecast writeback; and rerunning agent judgments after substantive
evidence changes remain future work. Frozen judgments must not be mistaken for
an automatically updated forecast.
