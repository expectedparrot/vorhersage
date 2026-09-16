"""Arithmetic for explicitly declared likelihood ratios; no evidence inference."""

import math

from .common import require
from .schemas import check


def logit(p):
    require(0 < p < 1, "Odds probabilities must be strictly between zero and one.")
    return math.log(p) - math.log1p(-p)


def logistic(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    e = math.exp(value)
    return e / (1 + e)


def calculate(spec):
    check(spec, "odds_ledger")
    anchor = spec["anchor"]
    start = logit(anchor["probability"])
    require(anchor["basis"] != "empirical" or anchor.get("prior_artifact_id"),
            "An empirical anchor needs a reference-class prior_artifact_id.")
    groups, findings = {}, set()
    for row in spec["entries"]:
        require(row["finding_id"] not in findings, "Duplicate ledger finding_id.")
        findings.add(row["finding_id"])
        require(len(row["evidence_refs"]) == 1 and row["evidence_refs"][0]["record_id"] == row["finding_id"],
                "Each ledger finding needs exactly its matching evidence reference.")
        groups.setdefault(row["dependence_group"], []).append(row)
    joints = {}
    for row in spec["joint_declarations"]:
        group = row["dependence_group"]
        require(group not in joints, "Duplicate joint declaration.")
        members = groups.get(group, [])
        require(len(members) >= 2 and len(set(row["finding_ids"])) == len(row["finding_ids"])
                and set(row["finding_ids"]) == {r["finding_id"] for r in members},
                "Joint declaration must cover exactly every finding in a repeated dependence group.")
        joints[group] = row
    for row in [*spec["entries"], *spec["joint_declarations"]]:
        lr = row["lr"]
        direction = "supports" if lr > 1 else "opposes" if lr < 1 else "neutral"
        require(row["direction"] == direction, "LR direction disagrees with its ratio.")
        bounds = row.get("lr_range", [lr, lr])
        require(len(bounds) == 2 and bounds[0] <= lr <= bounds[1],
                "LR range needs two ordered endpoints containing its estimate.")
    terms = []
    for group, rows in groups.items():
        require(len(rows) == 1 or group in joints,
                "Repeated dependence group requires an explicit joint declaration: " + group)
        row = joints[group] if len(rows) > 1 else rows[0]
        terms.append({"id": group, "finding_ids": [r["finding_id"] for r in rows],
                      "joint": len(rows) > 1, "lr": row["lr"],
                      "lr_range": row.get("lr_range", [row["lr"], row["lr"]]),
                      "rationale": row["rationale"]})
    logs = [math.log(t["lr"]) for t in terms]
    posterior_log_odds = math.fsum([start, *logs])
    target = spec.get("comparison_probability")
    target_log = logit(target) if target is not None else None
    sensitivity, waterfall = [], [{"id": "anchor", "probability": anchor["probability"], "log_odds": start}]
    for index, term in enumerate(terms):
        other = math.fsum([start, *logs[:index], *logs[index + 1:]])
        lo, hi = term["lr_range"]
        low, high = (logistic(other + math.log(v)) for v in (lo, hi))
        threshold_log = target_log - other if target_log is not None else None
        # Keep JSON finite even for extreme supplied ratios.
        threshold = math.exp(threshold_log) if threshold_log is not None and -745 < threshold_log < 709 else None
        sensitivity.append({"term_id": term["id"], "probability_range": [low, high], "swing": high - low,
                            "lr_to_match_comparison": threshold,
                            "log_lr_to_match_comparison": threshold_log,
                            "crosses_comparison": low < target < high if target is not None else None})
        subtotal = math.fsum([start, *logs[:index + 1]])
        waterfall.append({"id": term["id"], "probability": logistic(subtotal), "log_odds": subtotal})
    return {"probability": logistic(posterior_log_odds), "log_odds": posterior_log_odds,
            "terms": terms, "waterfall": waterfall,
            "sensitivity": sorted(sensitivity, key=lambda r: r["swing"], reverse=True),
            "limitations": ["Likelihood ratios and independence across groups are agent declarations, not inferred from findings.",
                            "A joint ratio replaces all individual ratios in its group.",
                            "Sensitivity varies one declared ratio at a time; ranges are not confidence intervals."]}
