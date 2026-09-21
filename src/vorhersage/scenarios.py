"""Optional, domain-neutral mixtures and bounded assumption sensitivity."""

import math

from .common import require
from .schemas import check


def calculate(spec):
    check(spec, "scenario_mixture")
    rows = spec["scenarios"]
    require(len({r["id"] for r in rows}) == len(rows), "Scenario IDs must be unique.")
    require(math.isclose(math.fsum(r["weight"] for r in rows), 1, abs_tol=1e-9, rel_tol=0),
            "Scenario weights must sum to one; include remaining possibilities explicitly.")
    bounds = {}
    gaps = []
    for r in rows:
        semantics = r.get("semantics")
        if not semantics:
            gaps.append(r["id"])
        elif semantics["target_relation"] in ("entails_yes", "entails_no"):
            fixed = 1 if semantics["target_relation"] == "entails_yes" else 0
            require(r["probability"] == fixed and r.get("probability_range", [fixed, fixed]) == [fixed, fixed],
                    "A scenario that entails YES/NO must have a definitionally fixed conditional probability and range.")
        else:
            require(semantics.get("residual_event") and semantics.get("non_overlap_rationale"),
                    "Unresolved scenarios need residual_event and non_overlap_rationale.")
        for field in ("weight", "probability"):
            interval = r.get(field + "_range", [r[field], r[field]])
            require(len(interval) == 2 and interval[0] <= r[field] <= interval[1],
                    "Each range needs ordered endpoints containing its point estimate.")
            bounds[r["id"], field] = interval

    def extreme(maximize):
        weights = {r["id"]: bounds[r["id"], "weight"][0] for r in rows}
        remaining = 1 - math.fsum(weights.values())
        ordered = sorted(rows, key=lambda r: bounds[r["id"], "probability"][int(maximize)], reverse=maximize)
        for r in ordered:
            extra = min(max(0, remaining), bounds[r["id"], "weight"][1] - weights[r["id"]])
            weights[r["id"]] += extra
            remaining -= extra
        require(abs(remaining) <= 1e-9, "Scenario weight bounds cannot allocate total probability one.")
        return {"probability": math.fsum(weights[r["id"]] * bounds[r["id"], "probability"][int(maximize)] for r in rows),
                "weights": weights}

    p = math.fsum(r["weight"] * r["probability"] for r in rows)
    sensitivity = []
    for r in rows:
        lo, hi = bounds[r["id"], "probability"]
        sensitivity.append({"scenario_id": r["id"], "assumption": "conditional_probability",
                            "target_range": [p + r["weight"] * (lo - r["probability"]),
                                             p + r["weight"] * (hi - r["probability"])],
                            "swing": r["weight"] * (hi - lo)})
    transfers = []
    for a in rows:
        for b in rows:
            if a["id"] == b["id"]:
                continue
            amount = min(0.1, a["weight"] - bounds[a["id"], "weight"][0],
                         bounds[b["id"], "weight"][1] - b["weight"])
            if amount > 0:
                transfers.append({"from": a["id"], "to": b["id"], "weight_transferred": amount,
                                  "probability_change": amount * (b["probability"] - a["probability"])})
    return {"semantic_review_gaps": gaps, "probability": p, "contributions": {r["id"]: r["weight"] * r["probability"] for r in rows},
            "bounded_range": [extreme(False)["probability"], extreme(True)["probability"]],
            "extreme_allocations": {"minimum": extreme(False), "maximum": extreme(True)},
            "conditional_sensitivity": sorted(sensitivity, key=lambda r: r["swing"], reverse=True),
            "weight_transfers": sorted(transfers, key=lambda r: abs(r["probability_change"]), reverse=True),
            "limitations": ["Weights and conditional probabilities are supplied judgments unless supported by data.",
                            "The partition is agent-attested; arithmetic cannot prove scenarios are exclusive or exhaustive.",
                            "Bounds vary supplied assumptions, not statistical confidence. Omitted ranges fix that assumption.",
                            "Joint extremes assume supplied bounds can vary together; dependencies beyond total weight are not modeled."]}
