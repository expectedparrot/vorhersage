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
    check(spec, "reference_query")
    require(time(spec["known_as_of"]) <= time(now()), "Reference query cutoff cannot be in the future.")
    with store.connect() as c:
        rows = [Store.artifact(c, r[0]) for r in c.execute("SELECT id FROM artifacts WHERE kind='reference_case'")]
    cases, censored, excluded = [], [], []
    for row in rows:
        if not set(spec["tags"]) <= set(row["tags"]):
            continue
        if time(row["known_at"]) > time(spec["known_as_of"]):
            excluded.append(row["id"])
            continue
        deadline = time(row["trigger_at"]) + timedelta(days=spec["horizon_days"])
        event = time(row["event_at"]) if row["event_at"] else None
        if event is not None and event <= deadline:
            outcome = 1
        elif time(row["observed_until"]) >= deadline:
            outcome = 0
        else:
            censored.append(row["id"])
            continue
        cases.append({"id": row["id"], "outcome": outcome, "evidence_refs": row["evidence_refs"]})
    limitations = ["Descriptive frequency among the selected, sufficiently observed episodes; not an automatically representative base rate.",
                   "Censored episodes are reported separately. Selective follow-up and selection after seeing outcomes can bias the rate.",
                   "known_at is declared historical availability; recorded_at separately preserves actual import time."]
    result = {"cases": cases, "censored": censored, "excluded_after_cutoff": excluded,
              "sample_size": len(cases), "probability": sum(c["outcome"] for c in cases) / len(cases) if cases else None,
              "selection": spec, "limitations": limitations}
    result["prior_payload"] = {"method": "reference_class", "cases": cases,
                               "selection_rule": spec["selection_rule"], "rationale": "Selected recorded episodes at the specified horizon.",
                               "limitations": limitations, "evidence_refs": [], "probability": result["probability"]} if cases else None
    return result
