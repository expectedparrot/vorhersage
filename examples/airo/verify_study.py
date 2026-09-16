"""Independently replay accepted raw output and check the imported final grids."""
import argparse
import gzip
import json
import math
from pathlib import Path
import edsl_pilot as pilot


def verify(out):
    result = {"verified_at": pilot.now(), "models": {}, "probabilities_checked": 0}
    for name in pilot.load(out / "study.json")["roster"]:
        directory = out / name
        reg, state = pilot.checked(directory)
        assert state["pending"] is None
        assert state["final"] or state.get("terminal_failure")
        replay, costs = {}, []
        for event in state["events"]:
            if event["kind"] != "model":
                continue
            accepted = pilot.load(directory / event["path"])
            record = pilot.load((directory / event["path"]).parent / "record.json")
            cost = record["raw_model_response"].get("action_cost")
            if cost is None:
                status = pilot.load((directory / event["path"]).parent / "status.json")
                assert status["data"]["latest_job_run_details"]["cost_usd"] == 0
                cost = 0
            costs.append(cost)
            assert cost == accepted["reported_cost_usd"]
            if accepted.get("transport_failure") or accepted.get("terminal_failure"):
                continue
            action = pilot.parse_action(record["answer"]["action"])
            assert action == accepted["transcript"]["content"]
            for a in action["actions"]:
                if a["tool"] == "submit_cells":
                    for row in a["rows"]:
                        replay[row["question_id"]] = row["probabilities"]
        assert replay == state["cells"]
        assert math.isclose(sum(costs), state["reported_cost_usd"], abs_tol=1e-9)
        count = 0
        if state["final"]:
            panel = json.loads(gzip.decompress((directory / "panel.json.gz").read_bytes()))
            mapping = pilot.load(directory / "question-map.json")
            conditions = {v: k for k, v in pilot.load(directory / "condition-map.json").items()}
            assert len(panel["rows"]) == 2940
            for row in panel["rows"]:
                q = mapping[row["question_id"]]
                p = replay[q["source_question_id"]][conditions[row["condition_id"]]][pilot.airo.HORIZONS.index(q["horizon"])]
                assert row["median_probability"] == p
                assert len(row["members"]) == 1 and row["members"][0]["probability"] == p
                count += 1
            assert pilot.load(directory / "summary.json")["doctor"]["ok"]
        else:
            assert state["terminal_failure"]["kind"] == "provider_refusal"
        result["models"][name] = {"probabilities_checked": count, "raw_outputs_replayed": True,
                                  "cost_reconciled_usd": sum(costs), "terminal": True}
        result["probabilities_checked"] += count
    assert result["probabilities_checked"] == 8820
    result["ok"] = True
    pilot.write(out / "verification.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "edsl_study_02")
    args = parser.parse_args()
    print(json.dumps(verify(args.out), indent=2))
