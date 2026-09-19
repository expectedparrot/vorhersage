"""New prospective model arms on the previously collected candidate inventory."""
import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path
from statistics import mean

from vorhersage import experiments, workbench
from vorhersage.common import digest, load, now, require, time
from vorhersage.store import Store
from vorhersage.workflow import Workflow

HERE = Path(__file__).resolve().parent
OUT = HERE / "run"
VAULT = HERE / "private-evaluator"
previous = HERE.parent / "kalshi_models_20260918" / "compare.py"
spec = importlib.util.spec_from_file_location("model_transport", previous)
transport_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport_module)
MODELS = transport_module.MODELS
CONDITIONS = transport_module.CONDITIONS
write = transport_module.write


def select():
    require(not (OUT / "selection-complete.json").exists(), "Selection already completed.")
    inventory = load(HERE / "candidates.json")
    if not (OUT / "protocol.json").exists():
        write(OUT / "protocol.json", {
            "registered_at": now(), "candidate_inventory_sha256": digest(inventory),
            "selection": "Use the exact 20 nominated contracts, in their existing order. No replacement after quote eligibility or outcome checks.",
            "eligibility": {"max_spread": .1, "min_contracts_each_side": 1,
                            "require_unknown_outcome": True, "minimum_hours_before_event": 12},
            "design": "Three models crossed with question-only/outside research; one independent call per cell; shared evidence.",
            "models": MODELS, "maximum_model_calls": 120, "planning_budget_usd": 20,
            "budget_note": "Not a provider-enforced cap. Include rejected response costs and report unknown usage.",
            "sources": "Primary nonmarket domains, captured receipts, no price-bearing search results or market-derived evidence.",
            "blinding": "Opening prices sealed before research. No quote inspection until all calls have terminal records and forecasts are sealed.",
            "output_rule": "Strict JSON and exact identities; no forecast repairs or study retries. Excluded market mentions remain excluded.",
            "analysis": "Same-contract comparisons, MAE/RMSE/outside-spread distance. All-available and fully matched cohorts separately. Equal-weight ensemble only where all members accepted.",
            "nfl": "Forecast probability of a win. Ties pay 0.5, so the market price is a payout proxy rather than exactly a win probability; also report non-NFL scores.",
            "calibration": "Exploratory expansion only. No correction fitted or deployed; reserve a separate future cohort for validation.",
            "dependence": "Report macroeconomic, labor/inflation, launch-count, and NFL clusters. Distinct contracts are not independent observations."})
    require(digest(inventory) == load(OUT / "protocol.json")["candidate_inventory_sha256"], "Inventory changed.")
    w = Workflow(OUT / "researcher")
    w.store.init("Expanded blinded model comparison")
    cases = load(OUT / "cases.json") if (OUT / "cases.json").exists() else []
    attempts = load(OUT / "selection-attempts.json") if (OUT / "selection-attempts.json").exists() else []
    done = {a["id"] for a in attempts}
    for candidate in inventory["candidates"]:
        if candidate["id"] in done:
            continue
        c, cid = candidate["contract"], candidate["id"]
        # Use a conservative pre-game deadline instead of the exchange's delayed close.
        deadline = "2026-09-20T16:00:00Z" if candidate["series"] == "KXNFLGAME" else c["scheduled_close"]
        if candidate["series"] == "KXNOBELPEACE":
            deadline = "2026-10-08T00:00:00Z"
        if candidate["series"] == "KXOSCARPIC":
            deadline = "2027-03-01T00:00:00Z"
        q = {"id": cid, "text": c["title"] + " — " + c["yes_description"],
             "yes": c["rules"], "no": "The stated YES event does not occur, subject to the frozen contract rules.",
             "void": "Nonbinary fair-value settlement, NFL ties, and cancelled or invalid events are excluded from eventual binary outcome scoring.",
             "event_deadline": deadline, "resolve_after": c["scheduled_close"],
             "resolution_source": "Contract-defined primary source; see frozen rules.",
             "event_group": c["event_group"], "domain": candidate["dependence_cluster"],
             "profile": "general", "kind": "real"}
        w.question(q)
        try:
            start = workbench.start(w.store, {"question": {"question_id": cid, "version": 1},
                "venue": "kalshi", "market_id": c["market_id"], "mode": "prospective",
                "method": "Three-model question-only versus outside-research comparison",
                "eligibility_rationale": "Candidate quote screen only. Primary-source outcome eligibility must pass before inference.",
                "contract_match_rationale": "Frozen full contract rules. Earlier conservative pre-event deadlines for NFL and awards.",
                "max_spread": .1, "min_contracts_each_side": 1}, VAULT)
            require(start["contract"] == c, "Contract changed since nomination; exclude rather than silently update.")
            cases.append({"id": cid, "question": q, "contract": c, "case_id": start["case_id"],
                          "start": start, "series": candidate["series"], "dependence_cluster": candidate["dependence_cluster"]})
            attempts.append({"id": cid, "quote_eligible": True})
            print(cid, "quote eligible; target sealed", flush=True)
        except ValueError as exc:
            attempts.append({"id": cid, "quote_eligible": False, "reason": str(exc)})
            print(cid, "excluded:", str(exc), flush=True)
        write(OUT / "cases.json", cases)
        write(OUT / "selection-attempts.json", attempts)
    write(OUT / "selection-complete.json", {"completed_at": now(), "cases_sha256": digest(cases), "attempts_sha256": digest(attempts)})
    return {"quote_eligible": len(cases), "screened": len(attempts)}


def prepare():
    from edsl.inference_services.services.open_ai_service import OpenAIService
    from edsl.inference_services.services.anthropic_service import AnthropicService
    from edsl.inference_services.services.google_service import GoogleService
    from edsl import Scenario
    require(not (OUT / "registration.json").exists(), "Already registered.")
    eligibility = load(OUT / "outcome-eligibility.json")
    cases = [c for c in load(OUT / "cases.json") if eligibility[c["id"]]["eligible"]]
    require(cases, "No eligible cases.")
    w = Workflow(OUT / "researcher")
    packets, packet_ids, views = {}, {}, {}
    for c in cases:
        packet = load(OUT / "packets" / (c["id"] + ".json"))
        pid = w.import_packet(packet)["packet_id"]
        packets[c["id"]], packet_ids[c["id"]] = packet, pid
        views[c["id"]] = evidence_view(packet, pid)
    method = load(HERE.parent / "kalshi_blind_20260918/run/method.json")
    mid = experiments.add_method(w.store, method)["method_id"]
    write(OUT / "method.json", method)
    services = {"openai": OpenAIService, "anthropic": AnthropicService, "google": GoogleService}
    models, arms = {}, {}
    questions = [{"question_id": c["id"], "version": 1} for c in cases]
    for key, m in MODELS.items():
        models[key] = services[m["provider"]].create_model(m["name"])(**m["parameters"]).to_dict()
        for condition in CONDITIONS:
            arm = {"id": key + "-" + condition, "version": 1, "description": "Expanded batch: " + condition,
                   "method_id": mid, "model": {**m, "parameters": models[key]["parameters"]},
                   "data": {"label": condition, "questions": [{**q, "packet_ids": [] if condition == "question_only" else [packet_ids[q["question_id"]]]} for q in questions]}}
            aid = experiments.add_arm(w.store, arm)["arm_id"]
            arms[aid] = {"model_key": key, "condition": condition}
            write(OUT / "arms" / (arm["id"] + ".json"), arm)
    stamp = now()
    specification = {"id": "kalshi-expansion-20260918", "version": 1,
        "description": "New prospective price-blind model comparison on the nominated expansion cohort",
        "questions": questions, "arm_ids": list(arms), "repetitions": 1, "mode": "prospective",
        "information_as_of": stamp, "forecast_cutoff": (time(stamp) + timedelta(hours=6)).isoformat(),
        "evidence_policy": "frozen_packets", "order_seed": "expansion-three-models-v1"}
    eid = experiments.add_experiment(w.store, specification)["experiment_id"]
    trials = experiments.start(w.store.root, eid)["trials"]
    reg = {"experiment_id": eid, "specification": specification, "registered_at": stamp,
           "cases": cases, "cases_sha256": digest(load(OUT / "cases.json")),
           "protocol_sha256": digest(load(OUT / "protocol.json")), "eligibility_sha256": digest(eligibility),
           "packet_hashes": {k: digest(v) for k, v in packets.items()}, "arm_info": arms, "models": models, "trials": trials}
    write(OUT / "registration.json", reg)
    transport = {"registration_sha256": digest(reg), "jobs": {}, "tasks": {}}
    template = load(HERE.parent / "kalshi_blind_20260918/run/jobs.json")
    for key in MODELS:
        body = copy.deepcopy(template)
        body["models"], body["scenarios"] = [models[key]], []
        for t in trials:
            info = arms[t["arm_id"]]
            if info["model_key"] != key:
                continue
            tid = t["trial_id"]
            step = w.next(t["run_id"])
            q = step["context"]["run"]["question"]
            evidence = {"records": [], "limitations": ["No current research supplied."]} if info["condition"] == "question_only" else views[q["id"]]
            prompt = ("Forecast information cutoff: " + stamp + "\nDEFINITION ONLY:\n" + json.dumps(q)
                      + "\nTASK:\n" + method["instructions"] + "\nSUPPLIED OUTSIDE EVIDENCE:\n" + json.dumps(evidence)
                      + '\nReturn exactly one JSON object with these keys only: method ("judgment"), probability (number from 0 to 1), '
                        'rationale (string, at most 300 words), limitations (array of strings), evidence_refs (array of objects with packet_id and record_id). '
                        'Use only supplied references. With no evidence, use evidence_refs: []. Include the too-high/too-low considerations within rationale. '
                        'No Markdown fences, schema, tool calls, or extra commentary.')
            write(OUT / "tasks" / (tid + ".json"), step)
            (OUT / "tasks" / (tid + ".txt")).write_text(prompt)
            body["scenarios"].append(Scenario({"trial_id": tid, "prompt": prompt}).to_dict())
            transport["tasks"][tid] = {"task_sha256": digest(step), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
        write(OUT / key / "jobs.json", body)
        transport["jobs"][key] = digest(body)
    write(OUT / "transport.json", transport)
    return {"contracts": len(cases), "calls": len(trials), "experiment_id": eid}


def evidence_view(packet, pid):
    # Import uses the current expanded allowlist, without changing the original study.
    from sources import check_text, check_url
    check_text(json.dumps(packet))
    records = []
    for r in packet["records"]:
        for s in r["sources"]:
            check_url(s["url"])
        records.append({"reference": {"packet_id": pid, "record_id": r["id"]}, "claim": r["claim"], "value": r["value"],
                        "sources": [{k: s[k] for k in ("url", "title", "excerpt", "retrieved_at")} for s in r["sources"]]})
    return {"records": records, "limitations": packet["limitations"]}


def verify_inputs():
    reg, t = load(OUT / "registration.json"), load(OUT / "transport.json")
    require(digest(reg) == t["registration_sha256"], "Registration changed.")
    for name, field in (("cases.json", "cases_sha256"), ("protocol.json", "protocol_sha256"), ("outcome-eligibility.json", "eligibility_sha256")):
        require(digest(load(OUT / name)) == reg[field], "Registered input changed: " + name)
    for cid, expected in reg["packet_hashes"].items():
        require(digest(load(OUT / "packets" / (cid + ".json"))) == expected, "Packet changed.")
    prompts = {}
    trials = {x["trial_id"]: x for x in reg["trials"]}
    for key, expected in t["jobs"].items():
        job = load(OUT / key / "jobs.json")
        require(digest(job) == expected, "Job changed.")
        for s in job["scenarios"]:
            trial = trials[s["trial_id"]]
            condition = reg["arm_info"][trial["arm_id"]]["condition"]
            slot = trial["question_id"], condition
            require(slot not in prompts or prompts[slot] == s["prompt"], "Models received different data.")
            prompts[slot] = s["prompt"]
            require(hashlib.sha256(s["prompt"].encode()).hexdigest() == t["tasks"][s["trial_id"]]["prompt_sha256"], "Prompt changed.")
    return reg, t


def terminal_gate(reg, seals):
    """Every registered call must have one terminal record before any reveal."""
    require(set(seals) == set(MODELS), "All model batches must be sealed.")
    for key, seal in seals.items():
        expected = {t["trial_id"] for t in reg["trials"] if reg["arm_info"][t["arm_id"]]["model_key"] == key}
        ids = [a["trial_id"] for a in seal["attempts"]]
        require(len(ids) == len(set(ids)) and set(ids) == expected, "Missing or duplicate terminal attempts.")
        accepted = {a["trial_id"] for a in seal["attempts"] if a["accepted"]}
        forecast_ids = [f["trial_id"] for f in seal["forecasts"]]
        require(len(forecast_ids) == len(set(forecast_ids)) and set(forecast_ids) == accepted, "Accepted calls and forecasts disagree.")


def verify_seals():
    reg, t = verify_inputs()
    seals = {key: load(OUT / key / "sealed-forecasts.json") for key in MODELS}
    terminal_gate(reg, seals)
    original = load(HERE.parent / "kalshi_blind_20260918/run/raw-records.json")[0]
    old_prompt = original["scenario"]["prompt"]
    user_text = original["prompt"]["forecast_user_prompt"]["text"]
    require(user_text.startswith(old_prompt), "Unexpected original EDSL prompt rendering.")
    suffix = user_text[len(old_prompt):]
    records = []
    for key, seal in seals.items():
        require(digest(seal) == load(OUT / key / "seal-commitment.json")["sha256"], "Forecast seal changed.")
        require(seal["registration_sha256"] == digest(reg), "Seal registration mismatch.")
        rows = load(OUT / key / "raw-records.json")
        require(digest(rows) == seal["raw_results_sha256"], "Raw responses changed.")
        job = load(OUT / key / "jobs.json")
        scenarios = {s["trial_id"]: s for s in job["scenarios"]}
        for r in rows:
            tid = r["scenario"]["trial_id"]
            require(r["scenario"] == scenarios[tid] and r["model"] == job["models"][0] and r["agent"] == job["agents"][0], "Returned identity mismatch.")
            require(r["prompt"]["forecast_system_prompt"] == original["prompt"]["forecast_system_prompt"], "System prompt changed.")
            require(r["prompt"]["forecast_user_prompt"]["text"] == scenarios[tid]["prompt"] + suffix, "Provider user prompt differs from submitted data.")
            raw = r["raw_model_response"]["forecast_raw_model_response"]
            returned = raw.get("model", raw.get("model_version"))
            require(returned == reg["models"][key]["model"], "Raw model identity mismatch.")
            records.append({"trial_id": tid, "model": returned, "prompt_sha256": digest(r["prompt"]), "raw_response_sha256": digest(raw)})
        for f in seal["forecasts"]:
            require(digest(load(OUT / key / "forecasts" / (f["trial_id"] + ".json"))) == f["forecast_sha256"], "Issued forecast changed.")
    audit = {"checked_at": now(), "registration_sha256": digest(reg), "model_seals": {k: digest(s) for k, s in seals.items()},
             "terminal_attempts": sum(len(s["attempts"]) for s in seals.values()), "prompt_receipts_verified": len(records), "records": records}
    if not (OUT / "pre-reveal-audit.json").exists():
        write(OUT / "pre-reveal-audit.json", audit)
    return reg, seals


def reveal():
    reg, seals = verify_seals()
    require(not (OUT / "comparison.json").exists(), "Already compared; inspect saved results.")
    w = Workflow(OUT / "researcher")
    pairs, exclusions = [], []
    for c in reg["cases"]:
        cid, qid = c["case_id"], c["id"]
        by_model = {k: {f["condition"]: f for f in s["forecasts"] if f["question_id"] == qid} for k, s in seals.items()}
        available = [(k, f) for k, rows in by_model.items() for f in rows.values()]
        if not available:
            exclusions.append({"id": qid, "reason": "No accepted forecasts; target remains sealed."})
            continue
        path = OUT / "reveals" / (qid + ".json")
        if path.exists():
            result = load(path)
        else:
            # The journal stores one representative issued forecast; all sealed
            # model/condition forecasts are scored against the same target below.
            key, f = next(((k, rows["outside_research"]) for k, rows in by_model.items() if "outside_research" in rows), available[0])
            exported = load(OUT / key / "forecasts" / (f["trial_id"] + ".json"))
            workbench.submit(w.store, cid, {"kind": "initial", "expected_revision": 0, "idempotency_key": cid + "-initial",
                "payload": {"probability": f["probability"], "rationale": "Representative of the sealed model-arm forecasts; see the trial archive for all forecasts and rationales.",
                            "assumptions": ["One registered call per model and information condition."],
                            "uncertainties": ["Recorded packet and model limitations."], "research_status": "completed",
                            "evidence_refs": [], "model_artifact_ids": [f["forecast_id"]]}})
            workbench.submit(w.store, cid, {"kind": "finish", "expected_revision": 1, "idempotency_key": cid + "-finish",
                "payload": {"stopping_reason": "All registered model calls have terminal records; accepted forecasts are sealed.",
                            "outcome_status": "unresolved", "market_exposure": "none",
                            "exposure_notes": "No detected price exposure. Primary source allowlist, separate target store, identical model inputs and no forecast-worker tools; procedural safeguards, not independently enforced isolation."}})
            result = workbench.reveal(w.store, cid, VAULT)
            write(path, result)
        require(all(time(s["sealed_at"]) < time(result["revealed_at"]) for s in seals.values()), "Premature target reveal.")
        comparison = result["comparison"]
        if not comparison["eligible_for_blind_comparison"]:
            exclusions.append({"id": qid, "reason": comparison["qualification_reasons"]})
            continue
        with Store(VAULT).connect() as conn:
            target = Store.artifact(conn, c["start"]["target_id"], "market_target")
        require(digest(target) == c["start"]["target_sha256"], "Target commitment mismatch.")
        require(target["baseline"]["quote"] == comparison["target"], "Scoring target changed.")
        write(OUT / "revealed-targets" / (qid + ".json"), target)
        quote = comparison["target"]
        pairs.append({"id": qid, "question_id": qid, "question": c["question"]["text"], "series": c["series"],
                      "dependence_cluster": c["dependence_cluster"], "target": quote["midpoint"], "bid": quote["bid"], "ask": quote["ask"],
                      "target_captured_at": comparison["target_captured_at"], "followup_quote": comparison.get("followup_quote"),
                      "followup_captured_at": comparison.get("followup_captured_at"), "qualification": comparison,
                      "forecasts": {k: {condition: rows.get(condition, {}).get("probability") for condition in CONDITIONS} for k, rows in by_model.items()}})
    def stats(cohort, key, condition):
        return transport_module.metrics([{**p, "p": p["forecasts"][key][condition]} for p in cohort if p["forecasts"][key][condition] is not None], "p")
    common = [p for p in pairs if all(p["forecasts"][k][c] is not None for k in MODELS for c in CONDITIONS)]
    research = [p for p in pairs if all(p["forecasts"][k]["outside_research"] is not None for k in MODELS)]
    ensemble = []
    for p in research:
        ensemble.append({**p, "p": mean(p["forecasts"][k]["outside_research"] for k in MODELS)})
    for p in pairs:
        p["equal_weight_research"] = mean(p["forecasts"][k]["outside_research"] for k in MODELS) if p in research else None
    costs = {k: {"known_usd": sum(a["reported_cost_usd"] or 0 for a in s["attempts"]),
                 "unknown_records": sum(a["reported_cost_usd"] is None for a in s["attempts"])} for k, s in seals.items()}
    report = {"revealed_at": now(), "registration_sha256": digest(reg), "pairs": pairs, "exclusions": exclusions,
        "costs": costs, "acceptance": {k: {"accepted": len(s["forecasts"]), "registered": len(s["attempts"])} for k, s in seals.items()},
        "common_question_ids": [p["id"] for p in common], "research_common_question_ids": [p["id"] for p in research],
        "common_metrics": {k: {c: stats(common, k, c) for c in CONDITIONS} for k in MODELS},
        "available_metrics": {k: {c: stats(pairs, k, c) for c in CONDITIONS} for k in MODELS},
        "research_common_metrics": {k: stats(research, k, "outside_research") for k in MODELS},
        "non_nfl_research_metrics": {k: stats([p for p in research if p["series"] != "KXNFLGAME"], k, "outside_research") for k in MODELS},
        "equal_weight_research_metrics": transport_module.metrics(ensemble, "p"),
        "constant_50_research_cohort": transport_module.metrics([{**p, "p": .5} for p in research], "p"),
        "later_quote_research_metrics": {k: stats([{**p, **{field: p["followup_quote"][qfield] for field, qfield in (("target", "midpoint"), ("bid", "bid"), ("ask", "ask"))}}
            for p in research if p["followup_quote"]], k, "outside_research") for k in MODELS},
        "doctor": w.doctor(), "interpretation": "Prospective input-blinded market-agreement experiment; no realized outcomes used, no fitted calibration. Correlated questions and selected source packets limit generalization."}
    write(OUT / "comparison.json", report)
    return {k: report[k] for k in ("acceptance", "costs", "common_metrics", "research_common_metrics", "equal_weight_research_metrics")}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("select", "prepare", "verify", "accept", "audit", "reveal"))
    p.add_argument("--model", choices=MODELS)
    p.add_argument("--results", type=Path)
    a = p.parse_args()
    if a.action == "select":
        result = select()
    elif a.action == "prepare":
        result = prepare()
    elif a.action == "verify":
        reg, _ = verify_inputs()
        result = {"verified": True, "trials": len(reg["trials"])}
    elif a.action == "audit":
        reg, seals = verify_seals()
        result = {"verified": True, "trials": len(reg["trials"])}
    elif a.action == "reveal":
        result = reveal()
    else:
        require(a.model and a.results, "Supply model and results.")
        result = transport_module.accept(a.model, a.results, out=OUT, verify=verify_inputs)
    print(json.dumps(result, indent=2))
