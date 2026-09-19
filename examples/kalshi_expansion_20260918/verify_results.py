"""Offline verification of published targets, chronology, and reported scores."""
import json
from math import isclose, sqrt
from statistics import mean

from batch import CONDITIONS, MODELS, OUT, verify_seals
from vorhersage.common import digest, load, time


def main():
    reg, seals = verify_seals()
    comparison = load(OUT / "comparison.json")
    assert comparison["registration_sha256"] == digest(reg)
    cases = {c["id"]: c for c in reg["cases"]}
    assert len(comparison["pairs"]) == len(cases) == 15
    for pair in comparison["pairs"]:
        cid = pair["id"]
        target = load(OUT / "revealed-targets" / (cid + ".json"))
        reveal = load(OUT / "reveals" / (cid + ".json"))
        assert digest(target) == cases[cid]["start"]["target_sha256"]
        assert target["baseline"]["quote"]["midpoint"] == pair["target"]
        assert target["baseline"]["quote"]["bid"] == pair["bid"]
        assert target["baseline"]["quote"]["ask"] == pair["ask"]
        assert time(load(OUT / "protocol.json")["registered_at"]) < time(pair["target_captured_at"])
        for r in load(OUT / "packets" / (cid + ".json"))["records"]:
            for source in r["sources"]:
                assert time(pair["target_captured_at"]) < time(source["retrieved_at"]) < time(reg["registered_at"])
        for key, seal in seals.items():
            assert time(reg["registered_at"]) < time(seal["sealed_at"]) < time(reveal["revealed_at"])
            for condition in CONDITIONS:
                entries = [f for f in seal["forecasts"] if f["question_id"] == cid and f["condition"] == condition]
                assert pair["forecasts"][key][condition] == (entries[0]["probability"] if entries else None)

    def check(rows, ps, reported):
        assert len(rows) == len(ps) == reported["contracts"]
        errors = [abs(p - row["target"]) for row, p in zip(rows, ps)]
        outside = [max(row["bid"] - p, p - row["ask"], 0) for row, p in zip(rows, ps)]
        for field, value in (("mae_pp", 100 * mean(errors)),
                             ("rmse_pp", 100 * sqrt(mean(e * e for e in errors))),
                             ("mean_outside_spread_pp", 100 * mean(outside))):
            assert isclose(value, reported[field], abs_tol=1e-10), field

    pairs = comparison["pairs"]
    common = [p for p in pairs if all(p["forecasts"][k][c] is not None for k in MODELS for c in CONDITIONS)]
    research = [p for p in pairs if all(p["forecasts"][k]["outside_research"] is not None for k in MODELS)]
    assert [p["id"] for p in common] == comparison["common_question_ids"]
    assert [p["id"] for p in research] == comparison["research_common_question_ids"]
    for key in MODELS:
        for condition in CONDITIONS:
            check(common, [p["forecasts"][key][condition] for p in common], comparison["common_metrics"][key][condition])
            available = [p for p in pairs if p["forecasts"][key][condition] is not None]
            check(available, [p["forecasts"][key][condition] for p in available], comparison["available_metrics"][key][condition])
        check(research, [p["forecasts"][key]["outside_research"] for p in research], comparison["research_common_metrics"][key])
        non_nfl = [p for p in research if p["series"] != "KXNFLGAME"]
        check(non_nfl, [p["forecasts"][key]["outside_research"] for p in non_nfl], comparison["non_nfl_research_metrics"][key])
    check(research, [mean(p["forecasts"][k]["outside_research"] for k in MODELS) for p in research], comparison["equal_weight_research_metrics"])
    check(research, [.5] * len(research), comparison["constant_50_research_cohort"])
    diagnostic = load(OUT / "output-review-sensitivity.json")
    assert diagnostic["comparison_sha256"] == digest(comparison)
    for key in MODELS:
        for condition in CONDITIONS:
            rows = diagnostic["pairs"]
            check(rows, [p["forecasts"][key][condition] for p in rows], diagnostic["metrics"][key][condition])
    print(json.dumps({"verified": True, "target_commitments": len(pairs), "terminal_calls": 90,
                      "accepted_forecasts": sum(len(s["forecasts"]) for s in seals.values()),
                      "fully_matched_contracts": len(common), "research_matched_contracts": len(research),
                      "max_midpoint_drift_pp": max(100 * abs(p["target"] - p["followup_quote"]["midpoint"]) for p in pairs),
                      "comparison_sha256": digest(comparison)}, indent=2))


if __name__ == "__main__":
    main()
