"""Post-hoc output review; never changes accepted forecasts or primary scores."""
import json
import re
from pathlib import Path
from statistics import mean

from batch import CONDITIONS, MODELS, OUT, transport_module, verify_seals, write
from vorhersage.common import digest, load, now, require
from vorhersage.schemas import check
from vorhersage.workflow import Workflow, verify_refs


def main():
    reg, seals = verify_seals()
    comparison = load(OUT / "comparison.json")
    lookup, reviews = {}, []
    w = Workflow(OUT / "researcher")
    trials = {t["trial_id"]: t for t in reg["trials"]}
    for key in MODELS:
        attempts = {a["trial_id"]: a for a in seals[key]["attempts"]}
        for row in load(OUT / key / "raw-records.json"):
            tid = row["scenario"]["trial_id"]
            trial = trials[tid]
            condition = reg["arm_info"][trial["arm_id"]]["condition"]
            payload = json.loads(row["answer"]["forecast"])
            check(payload, "assessment")
            require(payload["method"] == "judgment", "Unexpected method.")
            with w.store.connect() as c:
                verify_refs(c, payload["evidence_refs"], reg["specification"]["information_as_of"])
            lookup[key, trial["question_id"], condition] = payload["probability"]
            if not attempts[tid]["accepted"]:
                text = payload["rationale"] + " " + " ".join(payload["limitations"])
                category = "definition_naming_convention" if key == "fable" and trial["question_id"] == "candidate-20" else "explicit_denial_of_using_odds"
                require(attempts[tid]["error"].startswith("Excluded-content mention"), "Unexpected failure; manual review needed.")
                reviews.append({"trial_id": tid, "model": key, "question_id": trial["question_id"], "condition": condition,
                                "primary_status": "excluded", "review_category": category, "probability": payload["probability"],
                                "matching_contexts": [text[max(0, m.start()-100):m.end()+180] for m in transport_module.MARKET_TEXT.finditer(text)],
                                "judgment": "No numerical market odds are reported. Denials and home-team inference from contract naming do not themselves establish price exposure. This is a coordinator content review, not independent certification."})
    pairs = []
    for p in comparison["pairs"]:
        require(all((key, p["id"], c) in lookup for key in MODELS for c in CONDITIONS), "Incomplete raw response cohort.")
        pairs.append({**p, "forecasts": {key: {c: lookup[key, p["id"], c] for c in CONDITIONS} for key in MODELS}})
    def stats(cohort, key, condition):
        return transport_module.metrics([{**p, "p": p["forecasts"][key][condition]} for p in cohort], "p")
    result = {"created_at": now(), "comparison_sha256": digest(comparison),
              "status": "Post-hoc sensitivity; does not issue forecasts, alter primary exclusions, or replace the registered cohort.",
              "reviews": reviews, "pairs": pairs,
              "metrics": {k: {c: stats(pairs, k, c) for c in CONDITIONS} for k in MODELS},
              "non_nfl_metrics": {k: {c: stats([p for p in pairs if p["series"] != "KXNFLGAME"], k, c) for c in CONDITIONS} for k in MODELS},
              "equal_weight_research": transport_module.metrics([{**p, "p": mean(p["forecasts"][k]["outside_research"] for k in MODELS)} for p in pairs], "p"),
              "limitation": "Review performed after target reveal; all 90 original JSON objects used without edits, extra calls, or selective numerical changes."}
    write(OUT / "output-review-sensitivity.json", result)
    print(json.dumps({"reviewed_exclusions": len(reviews), "metrics": result["metrics"], "ensemble": result["equal_weight_research"]}, indent=2))


if __name__ == "__main__":
    main()
