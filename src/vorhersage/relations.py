"""Version-pinned logical implications and descriptive coherence checks."""

from .common import digest, now, require, time
from .schemas import check
from .store import Store


def key(ref):
    return (ref["question_id"], ref["version"])


def add(store, spec):
    check(spec, "relation")
    require(key(spec["antecedent"]) != key(spec["consequent"]), "A question cannot imply itself.")
    with store.connect(True) as c:
        questions = [Store.question(c, r["question_id"], r["version"])["specification"]
                     for r in (spec["antecedent"], spec["consequent"])]
        require(questions[0]["kind"] == questions[1]["kind"], "Cannot relate simulation and real questions.")
        id = "relation_" + digest(spec)[:24]
        existing = c.execute("SELECT id FROM artifacts WHERE id=?", (id,)).fetchone()
        if not existing:
            Store.put(c, "relation", {**spec, "recorded_at": now()}, id=id)
        return {"relation_id": id}


def audit(c, candidate=None):
    relations = Store.all(c, "relation")
    graph = {}
    for r in relations:
        graph.setdefault(key(r["antecedent"]), []).append((key(r["consequent"]), r["id"]))
    paths = {}
    for start in graph:
        queue = [(start, [])]
        visited = {start}
        while queue:
            node, path = queue.pop(0)
            for target, rid in graph.get(node, []):
                if target not in visited:
                    visited.add(target)
                    paths[start, target] = path + [rid]
                    queue.append((target, path + [rid]))
    latest = {}
    for f in Store.all(c, "forecast"):
        k = (f["question_id"], f["question_version"], f["forecaster"], f["mode"])
        if k not in latest or time(f["issued_at"]) >= time(latest[k]["issued_at"]):
            latest[k] = f
    if candidate:
        latest[(candidate["question_id"], candidate["question_version"], candidate["forecaster"], candidate["mode"])] = candidate
    groups = {(k[2], k[3]) for k in latest}
    comparisons, missing = [], []
    for (a, b), path in paths.items():
        for who, mode in sorted(groups):
            fa, fb = latest.get((*a, who, mode)), latest.get((*b, who, mode))
            if candidate and not ((fa and fa.get("id") == "pending") or (fb and fb.get("id") == "pending")):
                continue
            if not fa or not fb:
                missing.append({"antecedent": list(a), "consequent": list(b), "forecaster": who, "mode": mode})
                continue
            comparisons.append({"antecedent_forecast": fa["id"], "consequent_forecast": fb["id"],
                                "antecedent_probability": fa["probability"], "consequent_probability": fb["probability"],
                                "relation_ids": path, "forecaster": who, "mode": mode,
                                "violation": fa["probability"] > fb["probability"] + 1e-12,
                                "same_information_cutoff": time(fa["information_as_of"]) == time(fb["information_as_of"])})
    return {"comparisons": comparisons, "violations": [r for r in comparisons if r["violation"]],
            "missing_forecasts": missing,
            "limitations": ["Implications are supplied by the agent and pinned to exact question versions.",
                            "Different information cutoffs can explain apparent incoherence; review before revising."]}
