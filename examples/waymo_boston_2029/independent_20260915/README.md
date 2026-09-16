# Waymo Boston: independent-context timeline forecast

**39%** probability of paid, general-public driverless Waymo service with pickup
and dropoff inside Boston before January 1, 2029, Eastern time.

- [Interactive forecast report](outputs/forecast.html)
- [Full forecast explanation and sources](outputs/forecast_summary.md)
- [Model](outputs/model.json) and [sensitivity calculations](outputs/sensitivity.json)
- [Context-isolation protocol](PROTOCOL.md), [launch record](launch.json), and
  [sealed result](outputs/sealed_result.json)
- [Coordinator's independent validation](validation.json)

The worker started with zero forwarded conversation messages, the exact question,
and generic package code in a clean directory. No prior estimates, research,
source lists or demonstration parameters were supplied. It saved an unresolved
structure before browsing and sealed its result before reporting the number.
It reports no exposure to another event probability or prediction-market price.
This excludes supplied history; it does not remove training knowledge or create
an operating-system security boundary. The coordinator had seen earlier work.

Research cutoff: **September 15, 2026, 8:34:03 p.m. Eastern**
(`2026-09-16T00:34:03+00:00`). Forecast ID:
`forecast_36336b5d641a4a009f32`.

## Where 39% comes from

| Successful scenario | Assigned probability mass |
| --- | ---: |
| Early state permission, ordinary rollout | 22% |
| Permission in the first half of 2028, ordinary rollout | 12% |
| Permission in the third quarter of 2028, accelerated rollout | 5% |
| **Total qualifying probability** | **39%** |

The remaining 61% covers state delay, local delay, ordinary late rollout,
technical/operational delay, and corporate or national disruption. All eight
weights are subjective. The engine computes dates and sums their declared mass.

The main bottleneck is legal permission; the two principal enabling proposals
reached study orders in 2026. Preparation can overlap political deliberation, and
the model separates final local authorization, driverless validation, and general
public access. The source-linked explanation distinguishes proposed restrictions
from enacted law and selected-rider openings from qualifying public service.

Transferring 15 percentage points between early success and state delay yields
**24%–54%**. Adding 180 days to the final public-access task yields **22%**.
These are assumption stresses, not confidence intervals. The coarse state-delay
class also absorbs possible rapid launches after late-2028 permission, a documented
potential downward bias. Displayed dates are representative scenario points.

## Validation and reproduction

The coordinator independently recomputed all eight scenario calendars and the
weighted probability, verified all 11 sealed-output hashes and 24 starting-file
hashes, and confirmed the single issued forecast and all 21 database artifacts.
The resulting arithmetic agrees with the worker's own checks.

From this directory, restore the exact source snapshot if necessary:

```bash
python3 -m zipfile -e input_snapshot.zip .
python3 outputs/build.py --verify-existing
python3 validate_result.py .
```

The SQLite project is local and excluded by the repository's usual `.vorhersage`
ignore rule. To reconstruct a project from the preserved research snapshot in a
new directory:

```bash
python3 outputs/build.py --destination /private/tmp/waymo-independent-rebuild
```

This replays preserved inputs without new web research. Rebuilt artifact IDs and
issuance times can differ; the scenario calculation should remain 39%. This is
one forecaster's judgment with unmetered research/model costs, not an accuracy
evaluation or a controlled frozen-evidence comparison with an earlier method.

### Database portability note

The worker's SQLite database used WAL mode. An initial coordinator read failed
when empty WAL/SHM sidecars were absent; reopening the database restored them.
Both the main file's immutable read and normal integrity checks confirmed all
21 artifacts. The repository copy is a logical SQLite backup in DELETE journal
mode, allowing read-only verification without sidecars. Sealed outputs, forecast
probability, and logical records were preserved. The local copied project passes
both the worker's verifier and the coordinator's independent validator.
