"""Repeated prospective model arms with pre-reveal content review."""
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
    require((OUT / "protocol.json").exists(), "Freeze the protocol before selecting.")
    require(digest(inventory) == load(OUT / "protocol.json")["candidate_inventory_sha256"], "Inventory changed.")
    w = Workflow(OUT / "researcher")
    w.store.init("Repeated blinded model comparison")
    cases = load(OUT / "cases.json") if (OUT / "cases.json").exists() else []
    attempts = load(OUT / "selection-attempts.json") if (OUT / "selection-attempts.json").exists() else []
    done = {a["id"] for a in attempts}
    for candidate in inventory["candidates"]:
        if candidate["id"] in done:
            continue
        c, cid = candidate["contract"], candidate["id"]
        # Use a conservative pre-game deadline instead of the exchange's delayed close.
        deadline = candidate.get("event_deadline", c["scheduled_close"])
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
    require(time(now()) < time("2026-09-19T03:30:00Z"), "Too late to start this weather cohort.")
    definition_notes = load(OUT / "definition-notes.json")
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
            arm = {"id": key + "-" + condition, "version": 1, "description": "Repeated batch: " + condition,
                   "method_id": mid, "model": {**m, "parameters": models[key]["parameters"]},
                   "data": {"label": condition, "questions": [{**q, "packet_ids": [] if condition == "question_only" else [packet_ids[q["question_id"]]]} for q in questions]}}
            aid = experiments.add_arm(w.store, arm)["arm_id"]
            arms[aid] = {"model_key": key, "condition": condition}
            write(OUT / "arms" / (arm["id"] + ".json"), arm)
    stamp = now()
    specification = {"id": "kalshi-repeated-20260918", "version": 1,
        "description": "New prospective price-blind model comparison on the nominated expansion cohort",
        "questions": questions, "arm_ids": list(arms), "repetitions": 3, "mode": "prospective",
        "information_as_of": stamp, "forecast_cutoff": min(time(stamp) + timedelta(hours=2), time("2026-09-19T03:45:00Z")).isoformat(),
        "evidence_policy": "frozen_packets", "order_seed": "repeated-three-models-v2"}
    eid = experiments.add_experiment(w.store, specification)["experiment_id"]
    trials = experiments.start(w.store.root, eid)["trials"]
    reg = {"experiment_id": eid, "specification": specification, "registered_at": stamp, "definition_notes": definition_notes,
           "implementation_hashes": implementation_hashes(), "cases": cases, "cases_sha256": digest(load(OUT / "cases.json")),
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
            q = copy.deepcopy(step["context"]["run"]["question"])
            if q["id"] in definition_notes:
                q["definition_supplement"] = definition_notes[q["id"]]
            evidence = {"records": [], "limitations": ["No current research supplied."]} if info["condition"] == "question_only" else views[q["id"]]
            prompt = ("Replicate identifier (administrative; contains no evidence): " + str(t["repetition"]) + "\nForecast information cutoff: " + stamp + "\nDEFINITION ONLY:\n" + json.dumps(q)
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
    require(reg["definition_notes"] == load(OUT / "definition-notes.json"), "Definition supplement changed.")
    for name, field in (("cases.json", "cases_sha256"), ("protocol.json", "protocol_sha256"), ("outcome-eligibility.json", "eligibility_sha256")):
        require(digest(load(OUT / name)) == reg[field], "Registered input changed: " + name)
    for cid, expected in reg["packet_hashes"].items():
        require(digest(load(OUT / "packets" / (cid + ".json"))) == expected, "Packet changed.")
    require(reg["implementation_hashes"] == implementation_hashes(), "Registered implementation changed.")
    prompts = {}
    trials = {x["trial_id"]: x for x in reg["trials"]}
    for key, expected in t["jobs"].items():
        job = load(OUT / key / "jobs.json")
        require(digest(job) == expected, "Job changed.")
        for s in job["scenarios"]:
            trial = trials[s["trial_id"]]
            condition = reg["arm_info"][trial["arm_id"]]["condition"]
            slot = trial["question_id"], condition, trial["repetition"]
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


def implementation_hashes():
    from vorhersage import market_screen, market_evaluation
    paths = [HERE/'batch.py', HERE/'sources.py', Path(market_screen.__file__), Path(market_evaluation.__file__), previous,
             HERE.parent/'kalshi_blind_20260918/study.py']
    return {str(p.relative_to(HERE.parents[1])): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def screen_payload(payload):
    from vorhersage.market_screen import screen_market_mentions
    fields = {'rationale': screen_market_mentions(payload['rationale']),
              **{f'limitation-{i}': screen_market_mentions(s) for i,s in enumerate(payload['limitations'])}}
    return {'fields': fields, 'requires_review': any(v['status']=='review_required' for v in fields.values())}


def screen_results(key, path):
    from edsl import Results
    require(not list((OUT/'reveals').glob('*.json')), 'Cannot review after target reveal.')
    verify_inputs()
    job=load(OUT/key/'jobs.json')
    expected={s['trial_id']:s for s in job['scenarios']}
    rows=[r.to_dict() for r in Results.load(str(path))]
    ids=[r['scenario']['trial_id'] for r in rows]
    require(len(ids)==len(set(ids)) and set(ids)<=set(expected),'Unexpected response identities.')
    records=[]
    for row in rows:
        tid=row['scenario']['trial_id']
        try:
            payload=transport_module.validate_row(row,expected[tid],job,content_check=lambda p: None)
            screening=screen_payload(payload)
        except (ValueError,KeyError,TypeError) as exc:
            screening={'requires_review':False,'structural_error':str(exc)}
        records.append({'trial_id':tid,'row_sha256':digest(row),**screening})
    result={'screened_at':now(),'raw_results_sha256':digest(rows),'records':records}
    dest=OUT/key/'screening.json'
    require(not dest.exists(),'Already screened; preserve original receipt.')
    write(dest,result)
    return {'screened':len(records),'review_required':[r for r in records if r['requires_review']]}


def review_check(key):
    screening=load(OUT/key/'screening.json')
    path=OUT/key/'content-reviews.json'
    reviews=load(path) if path.exists() else {'reviews':[]}
    required={r['trial_id']:r for r in screening['records'] if r['requires_review']}
    entries={r['trial_id']:r for r in reviews['reviews']}
    require(len(entries)==len(reviews['reviews']) and set(entries)==set(required),'Every flagged output needs exactly one pre-reveal review, with no unrelated decisions.')
    for tid,r in entries.items():
        require(r['row_sha256']==required[tid]['row_sha256'],'Review is for different output.')
        require(r['decision'] in ('accept','exclude') and bool(r['rationale'].strip()),'Invalid content decision.')
        require(time(r['reviewed_at'])>=time(screening['screened_at']),'Review predates screening.')
        if r['decision']=='accept':
            require(r['category'] in ('explicit_non_use','definition_only'),'Only benign non-use or definition references can be accepted.')
    return screening,reviews,entries


def accept_results(key,path):
    require(not list((OUT/'reveals').glob('*.json')),'Cannot alter acceptance after reveal.')
    require(time(now()) < time(load(OUT/'registration.json')['specification']['forecast_cutoff']), 'Forecast issuance window passed.')
    screening,reviews,entries=review_check(key)
    from edsl import Results
    rows=[r.to_dict() for r in Results.load(str(path))]
    require(digest(rows)==screening['raw_results_sha256'],'Results changed after screening.')
    def validator(row,scenario,job):
        def content(payload):
            if screen_payload(payload)['requires_review']:
                require(entries[scenario['trial_id']]['decision']=='accept','Pre-reveal content review excluded response.')
        return transport_module.validate_row(row,scenario,job,content_check=content)
    result=transport_module.accept(key,path,out=OUT,verify=verify_inputs,validate=validator)
    write(OUT/key/'review-seal.json',{'sealed_at':now(),'screening_sha256':digest(screening),
          'reviews_sha256':digest(reviews),'forecast_seal_sha256':digest(load(OUT/key/'sealed-forecasts.json'))})
    return result


def audit_reviews(seals):
    for key,seal in seals.items():
        screening,reviews,entries=review_check(key)
        rs=load(OUT/key/'review-seal.json')
        require(rs['screening_sha256']==digest(screening) and rs['reviews_sha256']==digest(reviews)
                and rs['forecast_seal_sha256']==digest(seal),'Content review commitment changed.')
        require(screening['raw_results_sha256']==seal['raw_results_sha256'],'Screening covers different results.')
        require(all(time(r['reviewed_at'])<time(seal['sealed_at']) for r in entries.values()),'Review after forecast seal.')
        expected={t['trial_id'] for t in load(OUT/'registration.json')['trials'] if load(OUT/'registration.json')['arm_info'][t['arm_id']]['model_key']==key}
        require(len(screening['records'])==len({r['trial_id'] for r in screening['records']}) and {r['trial_id'] for r in screening['records']}<=expected,'Invalid screening coverage.')


def summarize(pairs):
    from math import sqrt
    from vorhersage.market_evaluation import score_draws
    common=[p for p in pairs if all(len(p['draws'][k][c])==3 for k in MODELS for c in CONDITIONS)]
    def cohort(rows):
        result={}
        for k in MODELS:
            result[k]={}
            for c in CONDITIONS:
                cells=[score_draws(p['draws'][k][c],p['target'],bid=p['bid'],ask=p['ask']) for p in rows]
                result[k][c]={'questions':len(cells),
                    'mean_draw_mae_pp':mean(x['mean_draw_absolute_error_pp'] for x in cells) if cells else None,
                    'draw_rmse_pp':sqrt(mean(x['root_mean_draw_squared_error_pp']**2 for x in cells)) if cells else None,
                    'three_draw_mean_mae_pp':mean(x['mean_forecast_absolute_error_pp'] for x in cells) if cells else None,
                    'mean_within_question_sd_pp':mean(x['sample_sd_pp'] for x in cells) if cells else None,
                    'mean_draw_outside_spread_pp':mean(x['mean_draw_outside_spread_pp'] for x in cells) if cells else None}
        return result
    for p in pairs:
        p['cell_scores']={k:{c:score_draws(p['draws'][k][c],p['target'],bid=p['bid'],ask=p['ask']) if p['draws'][k][c] else None for c in CONDITIONS} for k in MODELS}
    ens=[{**p,'p':mean(mean(p['draws'][k]['outside_research']) for k in MODELS)} for p in common]
    return {'common_question_ids':[p['id'] for p in common], 'common_metrics':cohort(common),
            'domain_metrics':{g:cohort([p for p in common if p['dependence_cluster']==g]) for g in sorted({p['dependence_cluster'] for p in common})},
            'equal_weight_research_metrics':transport_module.metrics(ens,'p'),
            'constant_50_metrics':transport_module.metrics([{**p,'p':.5} for p in common],'p'),
            'later_quote_metrics':cohort([{**p,'target':p['followup_quote']['midpoint'],'bid':p['followup_quote']['bid'],'ask':p['followup_quote']['ask']} for p in common if p['followup_quote']])}


def reveal():
    reg,seals=verify_seals()
    audit_reviews(seals)
    require(not (OUT/'comparison.json').exists(),'Already revealed and compared.')
    w=Workflow(OUT/'researcher')
    pairs,exclusions=[],[]
    for case in reg['cases']:
        qid,cid=case['id'],case['case_id']
        available=[(k,f) for k,s in seals.items() for f in s['forecasts'] if f['question_id']==qid]
        if not available:
            exclusions.append({'id':qid,'reason':'No accepted forecasts; target unrevealed.'});continue
        path=OUT/'reveals'/(qid+'.json')
        if path.exists():
            result=load(path)
        else:
            k,f=available[0]
            workbench.submit(w.store,cid,{'kind':'initial','expected_revision':0,'idempotency_key':cid+'-initial',
                'payload':{'probability':f['probability'],'rationale':'Representative sealed forecast; all registered repetitions scored separately from their immutable records.',
                    'assumptions':['Three independent calls per cell; no repair.'],'uncertainties':['Frozen packet limitations and within-model variation.'],
                    'research_status':'completed','evidence_refs':[],'model_artifact_ids':[f['forecast_id']]}})
            workbench.submit(w.store,cid,{'kind':'finish','expected_revision':1,'idempotency_key':cid+'-finish',
                'payload':{'stopping_reason':'Every call has a terminal receipt; forecasts and pre-reveal content reviews are sealed.',
                    'outcome_status':'unresolved','market_exposure':'none','exposure_notes':'Exact provider inputs checked; strict source screening; market-mentions-v2 content review before reveal. Procedural coordinator separation, no independently enforced sandbox.'}})
            result=workbench.reveal(w.store,cid,VAULT)
            write(path,result)
        require(all(time(s['sealed_at'])<time(result['revealed_at']) for s in seals.values()),'Premature reveal.')
        require(all(time(load(OUT/k/'review-seal.json')['sealed_at'])<time(result['revealed_at']) for k in MODELS),'Review sealed after reveal.')
        comp=result['comparison']
        if not comp['eligible_for_blind_comparison']:
            exclusions.append({'id':qid,'reason':comp['qualification_reasons']});continue
        with Store(VAULT).connect() as conn:
            target=Store.artifact(conn,case['start']['target_id'],'market_target')
        require(digest(target)==case['start']['target_sha256'],'Target commitment mismatch.')
        write(OUT/'revealed-targets'/(qid+'.json'),target)
        quote=target['baseline']['quote']
        require(quote==comp['target'],'Target changed.')
        p={'id':qid,'question':case['question']['text'],'series':case['series'],'dependence_cluster':case['dependence_cluster'],
           'target':quote['midpoint'],'bid':quote['bid'],'ask':quote['ask'],'target_captured_at':comp['target_captured_at'],
           'followup_quote':comp.get('followup_quote'),'qualification':comp,
           'draws':{k:{c:[f['probability'] for kk,f in available if kk==k and f['condition']==c] for c in CONDITIONS} for k in MODELS}}
        pairs.append(p)
    report={'created_at':now(),'registration_sha256':digest(reg),'pairs':pairs,'exclusions':exclusions,
            **summarize(pairs), 'costs':{k:{'known_usd':sum(a['reported_cost_usd'] or 0 for a in s['attempts']),
                                          'unknown_records':sum(a['reported_cost_usd'] is None for a in s['attempts'])} for k,s in seals.items()},
            'acceptance':{k:{'registered':len(s['attempts']),'accepted':len(s['forecasts'])} for k,s in seals.items()},'doctor':w.doctor()}
    write(OUT/'comparison.json',report)
    return {k:report[k] for k in ['common_question_ids','common_metrics','equal_weight_research_metrics','costs','acceptance']}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('select','prepare','verify','screen','accept','audit','reveal'))
    p.add_argument('--model',choices=MODELS)
    p.add_argument('--results',type=Path)
    a=p.parse_args()
    if a.action in ('screen','accept'):
        require(a.model and a.results,'Supply model and results.')
        result=(screen_results if a.action=='screen' else accept_results)(a.model,a.results)
    elif a.action=='audit':
        reg,seals=verify_seals();audit_reviews(seals)
        result={'verified':True,'calls':len(reg['trials'])}
    elif a.action=='verify':
        reg,_=verify_inputs();result={'verified':True,'calls':len(reg['trials'])}
    else:
        result={'select':select,'prepare':prepare,'reveal':reveal}[a.action]()
    print(json.dumps(result,indent=2))
