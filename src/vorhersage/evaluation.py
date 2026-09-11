"""Frozen, matched binary evaluations with explicit exclusions and cohorts."""

import math

from .common import digest, now, require, time
from .schemas import check
from .store import Store


def average(values):
    return math.fsum(values) / len(values) if values else None


def evaluate(store, policy, *, forecast_ids=None, input_ids=()):
    check(policy, "evaluation")
    require(len(set(policy["forecasters"])) == len(policy["forecasters"]), "Duplicate forecasters.")
    keys = [(q["question_id"], q["version"]) for q in policy["question_versions"]]
    require(len(set(keys)) == len(keys), "Duplicate questions in evaluation cohort.")
    require(time(policy["cutoff"]) <= time(now()) and time(policy["resolution_as_of"]) <= time(now()), "Evaluation cutoffs cannot be in the future.")
    with store.connect(True) as c:
        forecasts = Store.all(c, "forecast")
        if forecast_ids is not None:
            allowed = set(forecast_ids)
            forecasts = [f for f in forecasts if f["id"] in allowed]
        resolutions = Store.all(c, "resolution")
        selected, exclusions, cohort = [], [], []
        for question_id, version in keys:
            q = Store.question(c, question_id, version)["specification"]
            cohort.append({"question_id": question_id, "version": version, "event_group": q["event_group"]})
            history = [r for r in resolutions if r["question_id"] == question_id and r["question_version"] == version
                       and time(r["recorded_at"]) <= time(policy["resolution_as_of"])]
            resolution = history[-1] if history else None
            if not resolution or resolution["outcome"] in ("void", "disputed"):
                exclusions.append({"question_id": question_id, "version": version,
                                   "reason": resolution["outcome"] if resolution else "unresolved",
                                   "resolution_id": resolution["id"] if resolution else None})
                continue
            # Corrections cannot move eligibility past the earliest recorded knowledge claim.
            known = min(time(r["known_at"]) for r in history)
            y = int(resolution["outcome"] == "yes")
            for forecaster in policy["forecasters"]:
                eligible = [f for f in forecasts if f["question_id"] == question_id and f["question_version"] == version
                            and f["forecaster"] == forecaster and f["mode"] == policy["mode"]
                            and time(f["issued_at"]) <= time(policy["cutoff"]) and time(f["issued_at"]) < known]
                if not eligible:
                    exclusions.append({"question_id": question_id, "version": version, "forecaster": forecaster,
                                       "reason": "no_eligible_forecast_before_cutoff_and_resolution_knowledge"})
                    continue
                forecast = max(eligible, key=lambda f: (time(f["issued_at"]), f["id"]))
                selected.append({"question_id": question_id, "question_version": version, "event_group": q["event_group"],
                                 "forecaster": forecaster, "forecast_id": forecast["id"], "resolution_id": resolution["id"],
                                 "probability": forecast["probability"], "outcome": y,
                                 "brier": (forecast["probability"] - y) ** 2,
                                 "cost_usd": forecast["cost_usd"], "method": forecast["method"]})
        membership = {}
        for row in selected:
            membership.setdefault((row["question_id"], row["question_version"]), set()).add(row["forecaster"])
        common = {key for key, members in membership.items() if members == set(policy["forecasters"])}
        matched = [r for r in selected if (r["question_id"], r["question_version"]) in common]
        summaries = {}
        for forecaster in policy["forecasters"]:
            own = [r for r in selected if r["forecaster"] == forecaster]
            comparable = [r for r in matched if r["forecaster"] == forecaster]
            calibration = []
            for bin_index in range(5):
                rows = [r for r in own if min(int(r["probability"] * 5), 4) == bin_index]
                calibration.append({"lower": bin_index / 5, "upper": (bin_index + 1) / 5, "count": len(rows),
                                    "mean_probability": average([r["probability"] for r in rows]),
                                    "outcome_frequency": average([r["outcome"] for r in rows])})
            summaries[forecaster] = {"available_n": len(own), "available_brier": average([r["brier"] for r in own]),
                                    "matched_n": len(comparable), "matched_brier": average([r["brier"] for r in comparable]),
                                    "selected_run_cost_usd": math.fsum(r["cost_usd"] for r in own), "calibration": calibration}
        comparisons = []
        for index, left in enumerate(policy["forecasters"]):
            for right in policy["forecasters"][index + 1:]:
                differences = []
                for key in sorted(common):
                    pair = {r["forecaster"]: r for r in matched if (r["question_id"], r["question_version"]) == key}
                    differences.append({"question_id": key[0], "version": key[1], "event_group": pair[left]["event_group"],
                                        "brier_difference": pair[left]["brier"] - pair[right]["brier"]})
                comparisons.append({"left": left, "right": right, "n": len(differences),
                                    "event_groups": len({r["event_group"] for r in differences}),
                                    "mean_brier_difference": average([r["brier_difference"] for r in differences]),
                                    "by_question": differences, "interpretation": "Negative favors left; no significance claim."})
        inputs = sorted({r[k] for r in selected for k in ("forecast_id", "resolution_id")}
                        | {r["resolution_id"] for r in exclusions if r.get("resolution_id")} | set(input_ids))
        manifest = {id: digest(Store.artifact(c, id)) for id in inputs}
        body = {"policy": policy, "cohort": cohort, "selected": selected, "exclusions": exclusions,
                "summaries": summaries, "comparisons": comparisons, "created_at": now(), "input_manifest": manifest,
                "limitations": ["Calibration bins are descriptive; inspect counts.",
                                "Related events are labeled but no cluster uncertainty interval is estimated.",
                                "Recorded mode and timestamps do not certify freedom from hindsight or training contamination.",
                                "Reported costs cover selected runs, not all prior revisions or shared research."]}
        if forecast_ids is not None:
            body["eligible_forecast_ids"] = sorted(set(forecast_ids))
        id = Store.put(c, "evaluation", body)
        return {"evaluation_id": id, **body}
