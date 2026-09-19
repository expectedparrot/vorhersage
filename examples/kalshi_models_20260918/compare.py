"""Fixed-input model arms; no live research or market access during inference."""

import argparse
import copy
import hashlib
import json
import math
import sys
from datetime import timedelta
from pathlib import Path

from vorhersage import experiments
from vorhersage.common import digest, load, now, require, time
from vorhersage.schemas import check
from vorhersage.store import Store
from vorhersage.workflow import Workflow

HERE = Path(__file__).resolve().parent
OUT = HERE / "run"
SOURCE = HERE.parent / "kalshi_blind_20260918" / "run"
sys.path.insert(0, str(SOURCE.parent))
from study import MARKET_TEXT, evidence_view, metrics, write

CONDITIONS = ("question_only", "outside_research")
MODELS = {
    "astra": {"provider": "openai", "name": "gpt-6-astra",
              "parameters": {"max_tokens": 8192, "reasoning_effort": "high", "temperature": 1}},
    "fable": {"provider": "anthropic", "name": "claude-fable-5-1",
              "parameters": {"max_tokens": 8192, "thinking": {"type": "adaptive"},
                             "output_config": {"effort": "high"}}},
    "gemini": {"provider": "google", "name": "gemini-3.1-pro-preview",
               "parameters": {"maxOutputTokens": 8192, "temperature": .5,
                              "thinking_budget": 2048, "topK": 40, "topP": 1}},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_inputs():
    """Read only the original registered inputs, never its scores or forecasts."""
    reg, jobs = load(SOURCE / "registration.json"), load(SOURCE / "jobs.json")
    prompts = {s["trial_id"]: s["prompt"] for s in jobs["scenarios"]}
    by_condition = {}
    for t in reg["trials"]:
        condition = reg["arm_names"][t["arm_id"]]
        prompt = prompts[t["trial_id"]]
        require(prompt == (SOURCE / "tasks" / (t["trial_id"] + ".txt")).read_text(),
                "Original task and job prompt disagree.")
        by_condition[t["question_id"], condition] = (t["trial_id"], prompt)
    require(len(by_condition) == 12, "Expected six questions and two conditions.")
    return reg, jobs, by_condition


def prepare():
    from edsl.inference_services.services.open_ai_service import OpenAIService
    from edsl.inference_services.services.anthropic_service import AnthropicService
    from edsl.inference_services.services.google_service import GoogleService
    require(not (OUT / "registration.json").exists(), "Already registered; do not overwrite.")
    old, jobs, prompts = original_inputs()
    w = Workflow(OUT / "researcher")
    w.store.init("Fixed-data cross-model comparison")
    cases = load(SOURCE / "cases.json")
    packet_ids = {}
    for case in cases:
        w.question(case["question"])
        packet = load(SOURCE / "packets" / (case["id"] + ".json"))
        pid = w.import_packet(packet)["packet_id"]
        evidence_view(packet, pid)  # Recheck the same source allowlist and content guard.
        packet_ids[case["question"]["id"]] = pid
    method = load(SOURCE / "method.json")
    mid = experiments.add_method(w.store, method)["method_id"]
    write(OUT / "method.json", method)
    services = {"openai": OpenAIService, "anthropic": AnthropicService, "google": GoogleService}
    models, arm_info = {}, {}
    for key, spec in MODELS.items():
        model = services[spec["provider"]].create_model(spec["name"])(**spec["parameters"])
        models[key] = model.to_dict()
        for condition in CONDITIONS:
            arm = {"id": key + "-" + condition, "version": 1,
                   "description": "Exact original prompts, " + condition, "method_id": mid,
                   "model": {**spec, "parameters": models[key]["parameters"]},
                   "data": {"label": condition, "questions": [
                       {**q, "packet_ids": [] if condition == "question_only" else [packet_ids[q["question_id"]]]}
                       for q in old["specification"]["questions"]]}}
            aid = experiments.add_arm(w.store, arm)["arm_id"]
            arm_info[aid] = {"model_key": key, "condition": condition}
            write(OUT / "arms" / (arm["id"] + ".json"), arm)
    stamp = now()
    spec = {"id": "kalshi-fixed-data-models-20260918", "version": 1,
            "description": "Later model calls on the original frozen inputs and market targets; coordinator unblinded, model prompts isolated.",
            "questions": old["specification"]["questions"], "arm_ids": list(arm_info),
            "repetitions": 1, "mode": "retrospective",
            "information_as_of": old["specification"]["information_as_of"],
            "forecast_cutoff": (time(stamp) + timedelta(hours=4)).isoformat(),
            "evidence_policy": "frozen_packets", "order_seed": "fixed-data-three-models-v1"}
    eid = experiments.add_experiment(w.store, spec)["experiment_id"]
    trials = experiments.start(w.store.root, eid)["trials"]
    source_paths = [SOURCE / "registration.json", SOURCE / "jobs.json", SOURCE / "method.json", SOURCE / "cases.json"]
    source_paths += sorted((SOURCE / "packets").glob("*.json"))
    reg = {"experiment_id": eid, "specification": spec, "registered_at": stamp,
           "arm_info": arm_info, "models": models, "trials": trials,
           "source_files": {str(p.relative_to(HERE.parent)): sha(p) for p in source_paths},
           "design": {"intended_calls": 36, "draws_per_cell": 1, "manual_repairs": 0,
                      "automatic_study_retries": 0, "planning_budget_usd": 15,
                      "budget_note": "Planning estimate, not a provider-enforced cap. Record provider retries and unknown usage.",
                      "primary_cohort": "All six original contracts; matched valid cells across models and conditions.",
                      "sensitivity_cohort": "Exclude same-day weather, whose outcome may be known at later inference time.",
                      "score": "Mean absolute distance from the original opening midpoint; also RMSE and outside-spread distance.",
                      "missing": "Never impute. Report acceptance and available-case results separately from the common cohort.",
                      "blinding": "Coordinator saw original prices/results. Fresh model calls see only byte-identical original prompts and agent instruction, no tools or other forecasts.",
                      "timing": "Historical information cutoff, actual later execution timestamps; no new outcome-status claim.",
                      "settings": "Provider-specific reasoning settings; not a compute-matched comparison. EDSL serialization includes defaults that adapters may omit; raw responses retained."}}
    write(OUT / "registration.json", reg)
    transport = {"registration_sha256": digest(reg), "jobs": {}, "tasks": {}}
    for key in MODELS:
        body = copy.deepcopy(jobs)
        body["models"] = [models[key]]
        body["scenarios"] = []
        for t in trials:
            info = arm_info[t["arm_id"]]
            if info["model_key"] != key:
                continue
            tid = t["trial_id"]
            original_tid, prompt = prompts[t["question_id"], info["condition"]]
            step = w.next(t["run_id"])
            write(OUT / "tasks" / (tid + ".json"), step)
            (OUT / "tasks" / (tid + ".txt")).write_text(prompt)
            body["scenarios"].append({"trial_id": tid, "prompt": prompt})
            transport["tasks"][tid] = {"source_trial_id": original_tid, "task_sha256": digest(step),
                                       "prompt_sha256": sha(OUT / "tasks" / (tid + ".txt"))}
        write(OUT / key / "jobs.json", body)
        transport["jobs"][key] = digest(body)
    write(OUT / "transport.json", transport)
    return {"registered": len(trials), "experiment_id": eid, "models": models}


def verify_inputs():
    reg, transport = load(OUT / "registration.json"), load(OUT / "transport.json")
    require(digest(reg) == transport["registration_sha256"], "Registration changed.")
    for path, expected in reg["source_files"].items():
        require(sha(HERE.parent / path) == expected, "Original input changed: " + path)
    _, original_jobs, prompts = original_inputs()
    for key, expected in transport["jobs"].items():
        job = load(OUT / key / "jobs.json")
        require(digest(job) == expected, "Job changed.")
        require(job["agents"] == original_jobs["agents"] and job["survey"] == original_jobs["survey"],
                "System instruction or survey changed.")
        for s in job["scenarios"]:
            record = transport["tasks"][s["trial_id"]]
            require(s["prompt"] == (SOURCE / "tasks" / (record["source_trial_id"] + ".txt")).read_text(),
                    "Forecast prompt changed.")
            require(sha(OUT / "tasks" / (s["trial_id"] + ".txt")) == record["prompt_sha256"], "Prompt hash mismatch.")
    return reg, transport


def validate_row(row, scenario, job, *, content_check=None):
    # EDSL adds serialization metadata to plain scenarios when loading Jobs.
    # Accept exactly that metadata, never additional substantive context.
    expected_scenario = {"edsl_version": job["edsl_version"], "edsl_class_name": "Scenario", **scenario}
    require(row["scenario"] == expected_scenario and row["model"] == job["models"][0]
            and row["agent"] == job["agents"][0], "Result identity mismatch.")
    payload = json.loads(row["answer"]["forecast"])
    check(payload, "assessment")
    require(payload["method"] == "judgment", "Unexpected assessment method.")
    if content_check is None:
        require(not MARKET_TEXT.search(payload["rationale"] + " " + " ".join(payload["limitations"])),
                "Excluded-content mention; exposure review required, excluded from primary scores.")
    else:
        content_check(payload)
    return payload


def accept(key, path, *, out=None, verify=None, validate=None):
    from edsl import Results
    output = OUT if out is None else out
    reg, transport = (verify_inputs if verify is None else verify)()
    dest = output / key
    require(not (dest / "sealed-forecasts.json").exists(), "Already accepted; no overwrite.")
    job = load(dest / "jobs.json")
    rows = [r.to_dict() for r in Results.load(str(path))]
    write(dest / "raw-records.json", rows)
    expected = {s["trial_id"]: s for s in job["scenarios"]}
    ids = [r["scenario"]["trial_id"] for r in rows]
    require(len(ids) == len(set(ids)) and set(ids) <= set(expected), "Duplicate or unregistered results.")
    returned = dict(zip(ids, rows))
    trials = {t["trial_id"]: t for t in reg["trials"]}
    w, attempts, forecasts = Workflow(output / "researcher"), [], []
    for tid, scenario in expected.items():
        t = trials[tid]
        row = returned.get(tid)
        cost = row.get("raw_model_response", {}).get("forecast_cost") if row else None
        if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
            cost = None
        a = {"trial_id": tid, "model_key": key, "question_id": t["question_id"],
             "condition": reg["arm_info"][t["arm_id"]]["condition"],
             "reported_cost_usd": cost, "accepted": False, "recorded_at": now()}
        attempts.append(a)
        try:
            require(row is not None, "No returned result; cost unknown.")
            payload = (validate_row if validate is None else validate)(row, scenario, job)
            # Unknown usage stays unknown and is never silently charged as zero.
            require(cost is not None, "Unknown cost; cannot issue through the budgeted workflow.")
            step = load(output / "tasks" / (tid + ".json"))
            require(digest(step) == transport["tasks"][tid]["task_sha256"], "Task changed.")
            submission = {"task_id": step["task"]["id"], "expected_revision": step["revision"],
                          "idempotency_key": tid + "-assessment", "payload": payload,
                          "usage": {"searches": 0, "model_calls": 1, "cost_usd": cost}}
            w.submit(t["run_id"], submission)
            write(dest / "submissions" / (tid + ".json"), submission)
            issue = w.next(t["run_id"])
            require(issue["task"]["kind"] == "issue", "Unexpected next task.")
            w.submit(t["run_id"], {"task_id": issue["task"]["id"], "expected_revision": issue["revision"],
                     "idempotency_key": tid + "-issue", "usage": {"searches": 0, "model_calls": 0, "cost_usd": 0},
                     "payload": {"stopping_reason": "One frozen-input model call, no repair or additional research.",
                                 "review_at": reg["specification"]["forecast_cutoff"],
                                 "triggers": [{"description": "Separate future-data study.", "evidence_refs": payload["evidence_refs"]}]}})
            status = w.next(t["run_id"])
            with w.store.connect() as c:
                forecast = Store.artifact(c, status["forecast_id"], "forecast")
            write(dest / "forecasts" / (tid + ".json"), forecast)
            forecasts.append({"trial_id": tid, "question_id": t["question_id"], "condition": a["condition"],
                              "probability": forecast["probability"], "forecast_id": status["forecast_id"],
                              "forecast_sha256": digest(forecast)})
            a["accepted"] = True
        except (ValueError, KeyError, TypeError) as exc:
            a["error"] = str(exc)
        write(dest / "attempts.json", attempts)
    seal = {"sealed_at": now(), "registration_sha256": digest(reg), "raw_results_sha256": digest(rows),
            "forecasts": forecasts, "attempts": attempts, "doctor": w.doctor()}
    write(dest / "sealed-forecasts.json", seal)
    write(dest / "seal-commitment.json", {"sha256": digest(seal)})
    return {"model": key, "accepted": len(forecasts), "attempted": len(attempts),
            "known_cost_usd": sum(a["reported_cost_usd"] or 0 for a in attempts),
            "unknown_cost_records": sum(a["reported_cost_usd"] is None for a in attempts)}


def score():
    reg, _ = verify_inputs()
    all_forecasts, costs, acceptance = {}, {}, {}
    for key in MODELS:
        seal = load(OUT / key / "sealed-forecasts.json")
        require(digest(seal) == load(OUT / key / "seal-commitment.json")["sha256"], "Seal changed.")
        require(seal["registration_sha256"] == digest(reg), "Wrong registration.")
        for f in seal["forecasts"]:
            require(digest(load(OUT / key / "forecasts" / (f["trial_id"] + ".json"))) == f["forecast_sha256"], "Forecast changed.")
            all_forecasts[key, f["question_id"], f["condition"]] = f["probability"]
        costs[key] = {"known_usd": sum(a["reported_cost_usd"] or 0 for a in seal["attempts"]),
                      "unknown_records": sum(a["reported_cost_usd"] is None for a in seal["attempts"])}
        acceptance[key] = {"accepted": len(seal["forecasts"]), "registered": 12}
    # Evaluator targets are read only after every model's forecasts are sealed.
    original = load(SOURCE / "comparison.json")
    pairs = []
    for p in original["pairs"]:
        item = {k: p[k] for k in ("id", "question_id", "question", "target", "bid", "ask", "target_captured_at")}
        item["forecasts"] = {key: {c: all_forecasts.get((key, p["question_id"], c)) for c in CONDITIONS} for key in MODELS}
        item["original_gemini"] = {c: p[c] for c in CONDITIONS}
        pairs.append(item)
    common = [p for p in pairs if all(p["forecasts"][k][c] is not None for k in MODELS for c in CONDITIONS)]
    research_common = [p for p in pairs if all(p["forecasts"][k]["outside_research"] is not None for k in MODELS)]
    def summarize(cohort, key, condition):
        rows = [{**p, "p": p["forecasts"][key][condition]} for p in cohort if p["forecasts"][key][condition] is not None]
        return metrics(rows, "p")
    result = {"scored_at": now(), "registration_sha256": digest(reg), "target_file_sha256": sha(SOURCE / "comparison.json"),
              "pairs": pairs, "acceptance": acceptance, "costs": costs,
              "common_question_ids": [p["question_id"] for p in common],
              "common_metrics": {k: {c: summarize(common, k, c) for c in CONDITIONS} for k in MODELS},
              "research_common_question_ids": [p["question_id"] for p in research_common],
              "research_common_metrics": {k: summarize(research_common, k, "outside_research") for k in MODELS},
              "research_excluding_weather": {k: summarize([p for p in research_common if p["id"] != "weather"], k, "outside_research") for k in MODELS},
              "original_gemini_research_on_same_cohort": metrics(
                  [{**p, "p": p["original_gemini"]["outside_research"]} for p in research_common], "p"),
              "available_metrics": {k: {c: summarize(pairs, k, c) for c in CONDITIONS} for k in MODELS},
              "excluding_weather": {k: {c: summarize([p for p in common if p["id"] != "weather"], k, c) for c in CONDITIONS} for k in MODELS},
              "note": "Fixed-data market-agreement comparison, registered after original target reveal. No live market or outcome lookup. One draw per cell; descriptive differences only."}
    write(OUT / "comparison.json", result)
    return {k: result[k] for k in ("acceptance", "costs", "common_metrics", "excluding_weather")}


def audit():
    reg, transport = verify_inputs()
    original = {r["scenario"]["trial_id"]: r for r in load(SOURCE / "raw-records.json")}
    records = []
    for key in MODELS:
        rows = load(OUT / key / "raw-records.json")
        for r in rows:
            tid = r["scenario"]["trial_id"]
            prior = original[transport["tasks"][tid]["source_trial_id"]]
            require(r["prompt"] == prior["prompt"], "Actual system/user prompt differs from original.")
            raw = r["raw_model_response"]["forecast_raw_model_response"]
            returned_model = raw.get("model", raw.get("model_version"))
            require(returned_model == reg["models"][key]["model"], "Raw provider model identity mismatch.")
            records.append({"trial_id": tid, "model_key": key, "full_prompt_matches_original": True,
                            "prompt_sha256": digest(r["prompt"]), "returned_model": returned_model,
                            "raw_response_sha256": digest(raw)})
    result = {"audited_at": now(), "records": records, "full_prompt_matches": len(records),
              "note": "Verifies returned system/user prompt receipts, model IDs and registered input hashes. Provider is trusted; no independent service isolation or metering claim."}
    write(OUT / "audit.json", result)
    return {"full_prompt_matches": len(records), "raw_model_ids_verified": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify", "accept", "score", "audit"))
    parser.add_argument("--model", choices=MODELS)
    parser.add_argument("--results", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare()
    elif args.action == "verify":
        verify_inputs()
        result = {"unchanged_inputs": True, "original_prompts": 12, "new_calls": 36}
    elif args.action == "accept":
        require(args.model and args.results, "Supply --model and --results.")
        result = accept(args.model, args.results)
    elif args.action == "audit":
        result = audit()
    else:
        result = score()
    print(json.dumps(result, indent=2))
