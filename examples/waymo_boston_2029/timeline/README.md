# Waymo Boston: inspect the dependency assumption

Open [comparison.html](comparison.html) and select `late`.

Both models use hypothetical July 1, 2028 authorization, preparation no earlier
than March 1, 2028 lasting 184 elapsed days, and 61 days of public rollout.

| Structure | Computed qualifying launch | Before 2029? |
| --- | --- | --- |
| Preparation can precede authorization | November 1, 2028 | Yes |
| Preparation waits for authorization | March 3, 2029 | No |

These inputs are invented to expose a structural disagreement. They are not
evidence that either date, duration, or dependency is right. Authorization is
compressed into one effective date; research could require several milestones
and alternative routes. Preparation may need to be split into work that can
overlap authorization and work that cannot.

No weights are assigned, so neither model produces a probability. This does not
update the earlier odds-ledger forecast or reproduce FutureSearch's forecast.

## Rebuild and explore

```bash
python examples/waymo_boston_2029/timeline/build.py
```

The script creates its own `timeline/project/.vorhersage` store, registers the
original question definition, and emits these files:

- `parallel.json`, `sequential.json`: complete unweighted assumptions.
- `draft.json`: the same initial graph with missing parameter assignments.
- `gaps.json`: parameter-specific research targets for the draft.
- `comparison.json`, `comparison.html`: computed schedules and the offline report.
- `models.json`: artifact IDs in this example's separate store.
- `run.json`: optional model-first run input with no initial probability.

To start the draft workflow, run:

```bash
vorhersage --project examples/waymo_boston_2029/timeline/project start --from examples/waymo_boston_2029/timeline/run.json
```

Use `next RUN_ID`, then submit the draft artifact ID from `models.json` to the
structure task. Subsequent tasks name the parameters to research. The fixed
September 2026 cutoff is for reproducing this snapshot; a fresh forecasting task
needs a new explicit information cutoff and newly eligible evidence.

See [the timeline guide](../../../docs/TIMELINE_MODELS.md) for schemas, commands,
weighting, review and immutable revisions. Rebuilding creates no forecast and
makes no external calls. Generated artifact IDs are local to the example store.
