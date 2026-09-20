"""Explicit historical replay, separate from prospective outcome evaluation."""

import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from .common import Error, digest, load, now, probability, require, time
from .evaluation import average
from .schemas import check
from .store import Store
from .workflow import Workflow, verify_refs

FORMAT = "vorhersage.replay.v1"
BASELINES = ("baseline:half", "baseline:crowd")
LIMITATIONS = [
    "Historical replay; not prospective forecasting performance.",
    "Question text and criteria may contain later edits; historical wording is not certified.",
    "No archived research corpus is supplied; model training may contain outcomes.",
    "Dataset resolution dates do not establish the earliest time the outcome was knowable.",
    "Date-only crowd values are averaged within the latest available day, not treated as ordered intraday quotes.",
    "Event groups initially identify source questions only; related-event clustering needs review.",
]


def day(value, end=False):
    """This adapter accepts the release's date-only format; never guess timezone."""
    require(isinstance(value, str) and len(value) == 10, "Expected date-only dataset field.")
    date.fromisoformat(value)
    return value + ("T23:59:59.999999Z" if end else "T00:00:00Z")


def crowd_at(raw, cutoff):
    values = json.loads(raw) if isinstance(raw, str) else raw
    require(isinstance(values, list), "Crowd history must be a list.")
    eligible = []
    for item in values:
        require(isinstance(item, list) and len(item) == 2, "Malformed crowd history entry.")
        available = day(item[0], end=True)
        p = probability(item[1])
        if time(available) <= time(cutoff):
            eligible.append((available, p))
    if not eligible:
        return None
    latest = max(t for t, _ in eligible)
    ps = [p for t, p in eligible if t == latest]
    return {"probability": average(ps), "available_at": latest, "observations": len(ps),
            "method": "mean of all supplied values on latest complete day at cutoff"}


def prepare_halawi(source, output, *, revision, split, limit=20, seed="vorhersage-1",
                   days_after_open=7, categories=()):
    require(limit > 0 and days_after_open > 0, "Limit and days-after-open must be positive.")
    require(bool(revision.strip()), "Source revision is required.")
    raw = Path(source).read_bytes()
    rows = load(source)
    require(isinstance(rows, list), "Expected a Halawi JSON array.")
    source_hash = hashlib.sha256(raw).hexdigest()
    source_info = {"dataset": "YuehHanChen/forecasting", "revision": revision,
                   "split": split, "file_sha256": source_hash,
                   "url": f"https://huggingface.co/datasets/YuehHanChen/forecasting/blob/{revision}/{split}.json"}
    candidates, exclusions, seen = [], [], set()
    for index, row in enumerate(rows):
        try:
            require(isinstance(row, dict), "not_an_object")
            require(str(row.get("question_type", "")).lower() == "binary", "not_binary")
            require(row.get("is_resolved") is True, "not_resolved")
            require(type(row.get("resolution")) in (int, float) and row["resolution"] in (0, 1), "not_binary_resolution")
            category = row.get("gpt_3p5_category", "Other")
            require(not categories or category in categories, "category_filter")
            url = row["url"]
            require(isinstance(url, str) and url.startswith("https://"), "missing_source_url")
            require(url not in seen, "duplicate_source_question")
            seen.add(url)
            opened = time(day(row["date_begin"]))
            closed = time(day(row["date_close"]))
            resolved = time(day(row["date_resolve_at"]))
            cutoff = (opened + timedelta(days=days_after_open)).isoformat()
            require(time(cutoff) < min(closed, resolved), "insufficient_open_window")
            require(time(day(row["date_resolve_at"], end=True)) < time(now()), "resolution_not_in_past")
            require(isinstance(row.get("question"), str) and row["question"].strip(), "missing_question")
            criteria = row.get("resolution_criteria") or ""
            require(isinstance(criteria, str), "invalid_criteria")
            criteria_present = criteria.strip() not in ("", "Not applicable/available for this question.")
            # No outcome, status, crowd, background, or extracted comment URLs in agent inputs.
            # Free-text question/criteria still require historical-version review.
            case_id = "halawi_" + digest({"source": source_info, "url": url, "cutoff": cutoff})[:20]
            q = {"id": case_id, "text": row["question"],
                 "yes": criteria if criteria_present else "Source question resolves YES; separate criteria unavailable; manual review required.",
                 "no": "Source question resolves NO under its original criteria.",
                 "void": "Ambiguous criteria or invalid source resolution; exclude from substantive evaluation.",
                 "event_deadline": day(row["date_close"], end=True),
                 "resolve_after": day(row["date_close"], end=True),
                 "resolution_source": url, "event_group": "source_" + digest(url)[:20],
                 "domain": category, "profile": "general", "kind": "real"}
            check(q, "question")
            case = {"id": case_id, "question": q, "information_as_of": cutoff,
                    "criteria_available": criteria_present,
                    "historical_wording_audit": "unverified",
                    "evidence_status": "no_archived_research_supplied"}
            label = {"case_id": case_id, "outcome": int(row["resolution"]),
                     "resolution_date": row["date_resolve_at"],
                     "source_url": url, "source_row": index,
                     "crowd": crowd_at(row.get("community_predictions", []), cutoff)}
            candidates.append((digest({"seed": seed, "url": url}), case, label))
        except (Error, ValueError, KeyError, TypeError) as exc:
            exclusions.append({"source_row": index, "reason": str(exc)})
    candidates.sort(key=lambda item: (item[0], item[1]["id"]))
    require(len(candidates) >= limit, f"Only {len(candidates)} eligible cases; requested {limit}.")
    chosen = candidates[:limit]
    cases = {"schema_version": FORMAT, "source": source_info,
             "selection": {"seed": seed, "limit": limit, "days_after_open": days_after_open,
                           "categories": sorted(set(categories)), "ranking": "sha256 of seed and source URL",
                           "purpose": "development_smoke_test"},
             "limitations": LIMITATIONS, "cases": [c for _, c, _ in chosen]}
    labels = {"schema_version": FORMAT, "cases_sha256": digest(cases),
              "labels": [label for _, _, label in chosen]}
    manifest = {"schema_version": FORMAT, "created_at": now(), "source": source_info,
                "cases_sha256": digest(cases), "labels_sha256": digest(labels),
                "source_rows": len(rows), "eligible_rows": len(candidates), "selected_rows": limit,
                "exclusion_counts": dict(Counter(r["reason"] for r in exclusions)), "exclusions": exclusions}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("agent", "evaluator"):
        (output / folder).mkdir()
    for path, body in (("agent/cases.json", cases), ("evaluator/labels.json", labels), ("manifest.json", manifest)):
        (output / path).write_text(json.dumps(body, indent=2, allow_nan=False) + "\n")
    return {"output": str(output.resolve()), "selected_rows": limit, "eligible_rows": len(candidates),
            "cases_sha256": digest(cases), "labels_sha256": digest(labels), "limitations": LIMITATIONS}


def validate_cases(bundle):
    require(bundle.get("schema_version") == FORMAT, "Unsupported replay bundle.")
    cases = bundle.get("cases")
    require(isinstance(cases, list) and cases, "Replay cohort is empty.")
    ids = set()
    for case in cases:
        require(case["id"] not in ids, "Duplicate replay case.")
        ids.add(case["id"])
        check(case["question"], "question")
        require(case["id"] == case["question"]["id"], "Case/question ID mismatch.")
        require(case["question"]["kind"] == "real", "Replay cases must be real questions.")
        require(time(case["information_as_of"]) < time(case["question"]["event_deadline"]), "Replay cutoff must precede close.")
        require(time(case["information_as_of"]) < time(now()), "Replay cutoff must be historical.")
    return {case["id"]: case for case in cases}


def start_case(project, bundle, case_id, forecaster, method):
    cases = validate_cases(bundle)
    require(case_id in cases, "Unknown replay case.")
    require(forecaster not in BASELINES, "Reserved baseline forecaster name.")
    case = cases[case_id]
    w = Workflow(project)
    with w.store.connect() as c:
        exists = c.execute("SELECT 1 FROM questions WHERE id=?", (case_id,)).fetchone()
        if exists:
            q = Store.question(c, case_id)
            require(q["version"] == 1 and q["specification"] == case["question"], "Replay question changed.")
    if not exists:
        w.question(case["question"])
    result = w.start({"question_id": case_id, "forecaster": forecaster, "method": method,
                      "mode": "retrospective", "information_as_of": case["information_as_of"],
                      "cutoff_policy": "fixed", "max_searches": 0, "max_extra_tasks": 0})
    return {**result, "case_id": case_id, "cases_sha256": digest(bundle), "limitations": bundle.get("limitations", LIMITATIONS)}


def evaluate_replay(store, bundle, labels, manifest, policy):
    """Score named immutable forecasts at exact simulated cutoffs; never backdate."""
    check(policy, "replay_evaluation")
    cases = validate_cases(bundle)
    require(digest(bundle) == manifest["cases_sha256"] == labels["cases_sha256"], "Case bundle hash mismatch.")
    require(digest(labels) == manifest["labels_sha256"], "Label bundle hash mismatch.")
    require(labels.get("schema_version") == FORMAT, "Unsupported replay labels.")
    answers = {row["case_id"]: row for row in labels["labels"]}
    require(len(answers) == len(labels["labels"]) and set(answers) == set(cases), "Label/cohort membership mismatch.")
    forecasters = policy["forecasters"]
    require(len(set(forecasters)) == len(forecasters), "Duplicate forecasters.")
    require(len(set(policy["forecast_ids"])) == len(policy["forecast_ids"]), "Duplicate forecast ID.")
    with store.connect(True) as c:
        chosen, inputs = {}, {}
        for fid in policy["forecast_ids"]:
            f = Store.artifact(c, fid, "forecast")
            key = (f["question_id"], f["forecaster"])
            require(key[0] in cases and key[1] in forecasters and key[1] not in BASELINES, "Forecast outside declared cohort/forecasters.")
            require(key not in chosen, "Multiple forecasts for a case/forecaster; select exactly one revision.")
            case = cases[key[0]]
            require(f["mode"] == "retrospective" and f.get("cutoff_policy") == "fixed", "Replay requires fixed retrospective forecasts.")
            require(f["question_version"] == 1 and f["question"] == case["question"], "Forecast question differs from frozen case.")
            require(time(f["information_as_of"]) == time(case["information_as_of"]), "Forecast has the wrong simulated cutoff.")
            require(time(case["information_as_of"]) <= time(f["issued_at"]) <= time(now()), "Invalid actual issuance time.")
            require(digest(f["input_manifest"]) == f["manifest_sha256"], "Forecast manifest hash mismatch.")
            for aid, expected in f["input_manifest"].items():
                require(digest(Store.artifact(c, aid)) == expected, "Forecast input hash mismatch.")
            verify_refs(c, f["evidence_refs"], case["information_as_of"])
            inputs[fid] = digest(f)
            chosen[key] = {"forecast_id": fid, "probability": probability(f["probability"]),
                           "issued_at": f["issued_at"], "selected_run_cost_usd": f["cost_usd"]}
        rows, exclusions = [], []
        for cid, case in cases.items():
            label = answers[cid]
            require(type(label["outcome"]) is int and label["outcome"] in (0, 1), "Invalid binary replay label.")
            require(time(case["information_as_of"]) < time(day(label["resolution_date"])), "Cutoff is on/after resolution day.")
            require(time(day(label["resolution_date"], end=True)) < time(now()), "Resolution is not historical.")
            for forecaster in forecasters:
                row = chosen.get((cid, forecaster))
                if forecaster == "baseline:half":
                    row = {"probability": 0.5, "issued_at": None, "selected_run_cost_usd": 0,
                           "method": "constant probability; computed at evaluation time"}
                elif forecaster == "baseline:crowd" and label["crowd"] is not None:
                    crowd = label["crowd"]
                    require(time(crowd["available_at"]) <= time(case["information_as_of"]), "Crowd baseline leaks past cutoff.")
                    row = {**crowd, "probability": probability(crowd["probability"]), "issued_at": None,
                           "selected_run_cost_usd": 0}
                if row is None:
                    exclusions.append({"case_id": cid, "forecaster": forecaster, "reason": "missing_forecast"})
                else:
                    rows.append({**row, "case_id": cid, "forecaster": forecaster, "outcome": label["outcome"],
                                 "simulated_forecast_at": case["information_as_of"],
                                 "brier": (row["probability"] - label["outcome"]) ** 2})
        common = {cid for cid in cases if sum(r["case_id"] == cid for r in rows) == len(forecasters)}
        summaries = {}
        for name in forecasters:
            own = [r for r in rows if r["forecaster"] == name]
            matched = [r for r in own if r["case_id"] in common]
            summaries[name] = {"available_n": len(own), "available_brier": average([r["brier"] for r in own]),
                               "matched_n": len(matched), "matched_brier": average([r["brier"] for r in matched]),
                               "selected_run_cost_usd": sum(r["selected_run_cost_usd"] for r in own)}
        paired = []
        by_key = {(r["case_id"], r["forecaster"]): r for r in rows}
        for i, left in enumerate(forecasters):
            for right in forecasters[i + 1:]:
                diffs = [{"case_id": cid, "event_group": cases[cid]["question"]["event_group"],
                          "difference": by_key[cid, left]["brier"] - by_key[cid, right]["brier"]} for cid in sorted(common)]
                paired.append({"left": left, "right": right, "n": len(diffs), "by_case": diffs,
                               "mean_brier_difference": average([r["difference"] for r in diffs]),
                               "interpretation": "Negative favors left; no significance claim."})
        # Embed evaluation inputs: later edits to external labels cannot rewrite a saved score.
        body = {"evaluation_kind": "historical_replay", "created_at": now(), "policy": policy,
                "cases_bundle": bundle, "labels_bundle": labels, "bundle_manifest": manifest,
                "selected": rows, "exclusions": exclusions, "summaries": summaries, "comparisons": paired,
                "input_manifest": inputs, "limitations": bundle.get("limitations", LIMITATIONS) + [
                    "Label separation is a process convention, not a filesystem sandbox.",
                    "No calibration or group uncertainty estimates on this smoke cohort."]}
        eid = Store.put(c, "replay_evaluation", body)
        return {"evaluation_id": eid, **body}
