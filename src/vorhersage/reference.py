"""Reusable event episodes, with deadline-specific outcomes and censoring."""

from datetime import timedelta

from .common import digest, now, require, time
from .schemas import check
from .store import Store
from .workflow import verify_refs


def add(store, spec):
    check(spec, "reference_case")
    require(time(spec["trigger_at"]) <= time(spec["observed_until"]) <= time(spec["known_at"]) <= time(now()),
            "Reference case times must order trigger, observation, knowledge, and present.")
    if spec["event_at"] is not None:
        require(time(spec["trigger_at"]) <= time(spec["event_at"]) <= time(spec["observed_until"]),
                "Reference event must fall within the observed episode.")
    id = "reference_" + digest(spec["id"])[:24]
    with store.connect(True) as c:
        verify_refs(c, spec["evidence_refs"], spec["known_at"])
        existing = c.execute("SELECT id FROM artifacts WHERE id=?", (id,)).fetchone()
        if existing:
            old = Store.artifact(c, id)
            require(all(old[k] == v for k, v in spec.items()), "Reference case ID already has different content; use a new episode ID.")
        else:
            Store.put(c, "reference_case", {**spec, "recorded_at": now()}, id=id)
    return {"reference_case_id": id}


def query(store, spec):
    with store.connect() as c:
        return query_cases(c, spec)


def query_cases(c, spec):
    """Select within the caller's snapshot, including forecast submission."""
    check(spec, "reference_query")
    require(time(spec["known_as_of"]) <= time(now()), "Reference query cutoff cannot be in the future.")
    rows = [Store.artifact(c, r[0]) for r in c.execute("SELECT id FROM artifacts WHERE kind='reference_case' ORDER BY id")]
    cases, resolved, censored, excluded, immature, unascertained = [], [], [], [], [], []
    episodes, selected = {}, []
    for row in rows:
        if not set(spec["tags"]) <= set(row["tags"]):
            continue
        if time(row["known_at"]) > time(spec["known_as_of"]):
            excluded.append(row["id"])
            continue
        selected.append({**{k: row.get(k) for k in ("id", "episode_id", "eligibility", "trigger_at", "observed_until", "known_at", "event_at", "evidence_refs")},
                         "artifact_id": "reference_" + digest(row["id"])[:24]})
        episodes.setdefault(row.get("episode_id", row["id"]), []).append(row["id"])
        deadline = time(row["trigger_at"]) + timedelta(days=spec["horizon_days"])
        event = time(row["event_at"]) if row["event_at"] else None
        mature = deadline <= time(spec["known_as_of"])
        if not mature:
            immature.append(row["id"])
        if event is not None and event <= deadline:
            outcome = 1
        elif time(row["observed_until"]) >= deadline:
            outcome = 0
        else:
            censored.append(row["id"])
            if mature:
                unascertained.append(row["id"])
            continue
        case = {"id": row["id"], "outcome": outcome, "evidence_refs": row["evidence_refs"]}
        resolved.append(case)
        if mature:
            cases.append(case)
    limitations = ["The prior estimates event frequency by the requested horizon in the selected mature cohort, not an automatically representative population rate.",
                   "Maturity is determined from trigger plus horizon at known_as_of, independently of outcome. Mature episodes need an observed event or follow-up through the horizon.",
                   "Resolved-case frequency includes immature early successes and is descriptive only; it is not an empirical prior.",
                   "Selection, incomplete ascertainment, and differences between historical and current cohorts can bias inference.",
                   "known_at is declared historical availability; recorded_at separately preserves actual import time."]
    dependent = {episode: sorted(ids) for episode, ids in episodes.items() if len(ids) > 1}
    if dependent:
        limitations.append("Multiple cases share a declared episode; choose one representative per episode before using a rate.")
    reasons = []
    if not cases:
        reasons.append("no_mature_observed_cases")
    if unascertained:
        reasons.append("incomplete_mature_outcomes")
    if dependent:
        reasons.append("dependent_episodes")
    if any(not row["episode_id"] or not row["eligibility"] for row in selected):
        reasons.append("missing_episode_metadata")
    result = {"cases": cases, "censored": censored, "excluded_after_cutoff": excluded,
              "immature": immature, "unascertained_mature": unascertained,
              "estimator": "mature_cohort_frequency.v1", "censoring_policy": "require_complete_mature_cohort",
              "estimand": "Event by trigger_at + horizon_days among selected episodes whose horizon has elapsed at known_as_of.",
              "prior_eligible": not reasons, "prior_ineligibility_reasons": reasons,
              "mature_cohort_size": len(cases) + len(unascertained),
              "resolved_case_frequency": {"sample_size": len(resolved), "cases": resolved,
                                          "probability": sum(c["outcome"] for c in resolved) / len(resolved) if resolved and not dependent else None},
              "selected_episodes": selected, "dependent_episodes": dependent,
              "sample_size": len(cases), "probability": sum(c["outcome"] for c in cases) / len(cases) if not reasons else None,
              "selection": spec, "limitations": limitations}
    result["prior_payload"] = {"method": "reference_class", "cases": cases,
                               "selection_rule": spec["selection_rule"], "rationale": "Complete outcome ascertainment in the selected mature cohort at the specified horizon.",
                               "reference_query": spec,
                               "limitations": limitations, "evidence_refs": [], "probability": result["probability"]} if not reasons else None
    return result
