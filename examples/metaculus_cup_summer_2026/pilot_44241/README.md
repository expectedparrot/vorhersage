Read [the forecast](forecast.md): **64% YES**, using the fixed information cutoff
`2026-07-07T17:00:00Z`. The outcome has not been retrieved or scored.

This is a title-based pilot, because the API and historical question fetch did
not supply the original resolution criteria. Reconcile the working definition
in [question.json](question.json) with the actual contract before scoring.
The existing conversation and model knowledge were not independently isolated.

- [registration.json](registration.json) preserves the initial choice, cutoff,
  budget, and exposure declaration. Its initial status fields remain unchanged.
- [completion.json](completion.json) records completion, validation, and artifact
  hashes. [forecast.json](forecast.json) preserves the issued probability.
- [retrievals](retrievals) contains saved Exa responses; [findings.json](findings.json)
  and [evidence.json](evidence.json) link claims to archived passages.
- [submissions](submissions) contains Vorhersage task answers and receipts,
  including the reference-class exception and model challenge.
- [report-context.json](report-context.json) and its companion full records file
  preserve reporting material. [report-check.json](report-check.json) records the
  successful check against [report-claims.json](report-claims.json).

`snapshot.py` enforces the fixed cutoff and research budget and loads the Exa
key from the repository `.env` without saving it. `record.py` submitted task
answers to the local Vorhersage project. These are audit helpers for this run;
do not rerun the completed study or revise its probability after seeing the result.
The local project database is ignored by Git; portable JSON records are retained.
