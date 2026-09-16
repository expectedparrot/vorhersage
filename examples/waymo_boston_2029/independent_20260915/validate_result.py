"""Independent calendar arithmetic and database audit of the completed forecast.

Usage: python validate_result.py /path/to/worker/workspace
Writes validation.json and portable history into this directory; does not mutate
the worker's model, probability, evidence, report, or database.
"""

import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def independent_schedule(spec, scenario):
    """Recompute the schedule without importing the package's calculation engine."""
    values = {a["parameter_id"]: a for a in scenario["assessments"]}
    dates = {}
    pending = {n["id"]: n for n in spec["nodes"]}
    cutoff = dt(spec["information_as_of"])
    while pending:
        ready = [n for n in pending.values() if all(p in dates for p in n["parents"])]
        assert ready, "Cycle or missing dependency"
        for n in ready:
            parents = [dates[p] for p in n["parents"]]
            if n["state"] == "completed":
                finish = dt(n["completed_at"])
            elif n["kind"] == "any":
                if "unknown" in parents:
                    finish = "unknown"
                else:
                    finite = [p for p in parents if p is not None]
                    finish = min(finite) if finite else None
            elif None in parents:
                finish = None
            elif "unknown" in parents:
                finish = "unknown"
            elif n["kind"] == "all":
                finish = max(parents)
            else:
                a = values.get(n["parameter_id"], {"basis": "unresolved"})
                if a["basis"] == "unresolved":
                    finish = "unknown"
                elif a["value"] == "never":
                    finish = None
                elif n["kind"] == "event":
                    finish = dt(a["value"])
                else:
                    start = cutoff if n["state"] == "in_progress" else max(
                        [cutoff, dt(n.get("not_before", spec["information_as_of"]))] + parents)
                    finish = start + timedelta(seconds=86400 * a["value"])
            dates[n["id"]] = finish
            del pending[n["id"]]
    target = dates[spec["target"]]
    assert target != "unknown", "Issued forecast has an unresolved target"
    outcome = False if target is None else (
        target < dt(spec["deadline"]) if spec["deadline_rule"] == "before" else target <= dt(spec["deadline"]))
    return {"scenario_id": scenario["id"], "weight": scenario["weight"],
            "launch_at": target.isoformat() if target else None, "meets_deadline": outcome}


def main(workspace):
    workspace = Path(workspace).resolve()
    destination = Path(__file__).resolve().parent
    sys.path.insert(0, str(workspace / "src"))
    from vorhersage.store import Store
    from vorhersage.workflow import Workflow
    from vorhersage import timeline

    assert (workspace / "outputs/sealed_result.json").is_file(), "Worker has not sealed its result"
    seal = json.loads((workspace / "outputs/sealed_result.json").read_text())
    for relative, expected in seal["files"].items():
        assert hashlib.sha256((workspace / "outputs" / relative).read_bytes()).hexdigest() == expected, relative
    manifest = json.loads((workspace / "input_manifest.json").read_text())
    for relative, expected in manifest["inputs"].items():
        assert hashlib.sha256((workspace / relative).read_bytes()).hexdigest() == expected, relative
    w = Workflow(workspace / "project")
    doctor = w.doctor()
    assert doctor["ok"], doctor
    with w.store.connect() as c:
        forecasts = Store.all(c, "forecast")
        assert len(forecasts) == 1, "Expected one independent forecast"
        forecast = forecasts[0]
        model = timeline.read(c, forecast["timeline_model_id"])["specification"]
        analysis = timeline.analyze(model)
        rows = [independent_schedule(model, s) for s in model["scenarios"]]
        assert math.isclose(math.fsum(r["weight"] for r in rows), 1, abs_tol=1e-12)
        probability = math.fsum(r["weight"] for r in rows if r["meets_deadline"])
        assert math.isclose(probability, analysis["probability"], abs_tol=1e-12)
        for row, calculated in zip(rows, analysis["scenarios"]):
            assert row["scenario_id"] == calculated["scenario_id"]
            assert row["launch_at"] == calculated["launch_at"]
            assert row["meets_deadline"] == calculated["meets_deadline"]
        assert math.isclose(probability, forecast["probability"], abs_tol=1e-12), "Review changed the issued probability; inspect explicitly"
        for table in ("artifacts", "runs", "events"):
            history = [dict(r) for r in c.execute("SELECT * FROM " + table)]
            for row in history:
                for field in ("body", "state"):
                    if field in row:
                        row[field] = json.loads(row[field])
            (destination / (table + ".json")).write_text(json.dumps(history, indent=2) + "\n")
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "doctor": doctor,
              "sealed_output_hashes_verified": len(seal["files"]),
              "input_snapshot_hashes_verified": len(manifest["inputs"]),
              "forecast_id": forecast["id"], "timeline_model_id": forecast["timeline_model_id"],
              "information_as_of": forecast["information_as_of"],
              "issued_probability": forecast["probability"], "independently_computed_probability": probability,
              "scenarios": rows, "limitation": "Calendar, arithmetic and integrity checks do not validate subjective probabilities or substantive model assumptions."}
    (destination / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"forecast_id": forecast["id"], "probability": probability, "scenario_count": len(rows), "doctor_ok": doctor["ok"]}))


if __name__ == "__main__":
    main(sys.argv[1])
