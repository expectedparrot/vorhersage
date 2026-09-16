"""Generic joint-session comparisons and explicitly eligible outcome scoring."""

import html
import json
import math
from pathlib import Path
from statistics import mean

from . import sessions
from .common import digest, now, require, time
from .schemas import check
from .session_runtime import audit_state
from .store import Store


def comparison(store, session_ids):
    sessions.unique(session_ids, "session IDs")
    require(session_ids, "Choose at least one session.")
    with store.connect() as c:
        states = [sessions._status(c, id) for id in session_ids]
        keys = sorted({(q["question_id"], q["version"], condition) for s in states
                       for q in s["specification"]["questions"] for condition in s["specification"]["condition_ids"]})
        maps = [{sessions.cell_key(cell): cell for cell in s["cells"]} if s["finalization"] else {} for s in states]
        rows = [{"question_id": q, "version": v, "condition_id": condition,
                 "question": Store.question(c, q, v)["specification"]["text"],
                 "condition": Store.artifact(c, condition, "condition")["specification"]["description"],
                 "probabilities": [m.get((q, v, condition), {}).get("probability") for m in maps]}
                for q, v, condition in keys]
    members = [{"session_id": s["session_id"], "forecaster": s["specification"]["forecaster"],
                "repetition": s["specification"]["repetition"], "wave": s["specification"]["wave"],
                "protocol": s["specification"]["protocol"], "information_as_of": s["specification"]["information_as_of"],
                "provenance": s["specification"]["provenance"],
                "finalized_at": s["finalization"]["finalized_at"] if s["finalization"] else None,
                "configuration": s["specification"]["configuration"], "audit": audit_state(s),
                "numeric_forecasts": s["specification"]["numeric_forecasts"], "bindings": s["specification"]["bindings"]}
               for s in states]
    return {"sessions": members, "rows": rows, "created_at": now(),
            "matched_cells": sum(all(p is not None for p in r["probabilities"]) for r in rows),
            "same_information_cutoff": len({time(m["information_as_of"]) for m in members}) == 1,
            "limitations": ["Only finalized sessions supply comparison probabilities; failed and partial sessions remain in the roster.",
                            "Differences are descriptive. Live evidence, bindings, configuration, protocol, and sampling may differ.",
                            "Related cells and repetitions are not independent observations."]}


def render(store, session_ids, path):
    report = comparison(store, session_ids)
    data = json.dumps(report, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    cards = "".join("<article><h2>" + html.escape(m["forecaster"]) + " · repetition " + str(m["repetition"]) +
                    "</h2><p>" + html.escape(m["audit"]["disposition"]) + " · protocol: " +
                    html.escape(m["audit"]["protocol_fidelity"]) + "</p><p>Reported cost: $" +
                    f'{m["audit"]["usage"]["cost_usd"]:.5f}' +
                    (" · usage incomplete" if m["audit"]["unknown_usage_attempts"] else "") +
                    "</p><details><summary>Configuration and audit</summary><pre>" +
                    html.escape(json.dumps(m, indent=2)) + "</pre></details></article>" for m in report["sessions"])
    document = r"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Joint-session comparison</title><style>body{font:16px system-ui;margin:2rem auto;padding:0 1rem;max-width:1200px;background:#faf9f6;color:#192a30}h1{font-size:2rem}article{padding:1rem;border:1px solid #ccd6d6;border-radius:8px}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem}h2{font-size:1.1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}table{border-collapse:collapse;width:100%}td,th{padding:.65rem;border-bottom:1px solid #ddd;text-align:left}label,button{display:inline-block;margin:.5rem}input,select,button{font:inherit;padding:.4rem}.table{overflow:auto}small{color:#526269}</style>
<h1>Joint-session comparison</h1><p>Compare finalized forecasts; inspect failures, research coverage, amendments, and requested settings alongside them.</p>
<section>__CARDS__</section><p id="summary"></p><label>Search <input id="search" type="search"></label><label>Baseline <select id="baseline"></select></label><button id="csv">Download filtered CSV</button><button id="prev">Previous</button><button id="next">Next</button><span id="page"></span>
<div class="table"><table><thead id="head"></thead><tbody id="rows"></tbody></table></div><p>Values are probabilities. Differences are percentage points relative to the selected baseline. Missing values remain missing.</p><p>__LIMITS__</p>
<script type="application/json" id="data">__DATA__</script><script>
const data=JSON.parse(document.getElementById('data').textContent), $=id=>document.getElementById(id);let page=0;
const label=m=>m.forecaster+' · r'+m.repetition;
data.sessions.forEach((m,i)=>{const o=document.createElement('option');o.value=i;o.textContent=label(m);$('baseline').append(o)});
const filtered=()=>data.rows.filter(r=>(r.question_id+' '+r.question+' '+r.condition).toLowerCase().includes($('search').value.toLowerCase()));
function cell(row,text,tag='td'){const c=document.createElement(tag);c.textContent=text;row.append(c)}
function draw(){const rows=filtered();page=Math.min(page,Math.max(0,Math.ceil(rows.length/50)-1));$('head').replaceChildren();const h=document.createElement('tr');['Question / version','Condition',...data.sessions.map(label)].forEach(t=>cell(h,t,'th'));$('head').append(h);$('rows').replaceChildren();rows.slice(page*50,page*50+50).forEach(r=>{const tr=document.createElement('tr');cell(tr,r.question_id+' / '+r.version);cell(tr,r.condition);const b=r.probabilities[+$('baseline').value];r.probabilities.forEach(p=>cell(tr,p===null?'—':(100*p).toFixed(3)+'%'+(b===null?'':' ('+((p-b)*100).toFixed(3)+' pp)')));$('rows').append(tr)});$('page').textContent=`Page ${page+1} · ${rows.length} cells`;$('summary').textContent=`${data.matched_cells} cells complete across all selected sessions. Information cutoffs ${data.same_information_cutoff?'match':'differ'}.`;$('prev').disabled=page===0;$('next').disabled=(page+1)*50>=rows.length}
$('search').oninput=()=>{page=0;draw()};$('baseline').onchange=draw;$('prev').onclick=()=>{page--;draw()};$('next').onclick=()=>{page++;draw()};$('csv').onclick=()=>{const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';const rows=[['question_id','version','condition_id',...data.sessions.map(m=>m.session_id)],...filtered().map(r=>[r.question_id,r.version,r.condition_id,...r.probabilities])];const url=URL.createObjectURL(new Blob([rows.map(r=>r.map(quote).join(',')).join('\r\n')],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='session-comparison.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};draw();
</script></html>"""
    document = document.replace("__CARDS__", cards).replace("__LIMITS__", html.escape(" ".join(report["limitations"]))).replace("__DATA__", data)
    Path(path).write_text(document)
    return {"path": str(Path(path).resolve()), "sessions": len(session_ids), "cells": len(report["rows"])}


def _calibration(rows):
    """Rank deciles per session; ties use question ID/version as a stable tiebreaker."""
    ordered = sorted(rows, key=lambda r: (r["probability"], r["question_id"], r["version"]))
    bins = []
    for i in range(10):
        own = [r for index, r in enumerate(ordered) if index * 10 // max(1, len(ordered)) == i]
        n = len(own)
        frequency = mean([r["outcome"] for r in own]) if n else None
        interval = None
        if n:
            z = 1.959963984540054
            center = (frequency + z*z/(2*n))/(1+z*z/n)
            half = z*math.sqrt(frequency*(1-frequency)/n+z*z/(4*n*n))/(1+z*z/n)
            interval = [max(0, center-half), min(1, center+half)]
        bins.append({"rank_bin": i, "n": n, "mean_probability": mean([r["probability"] for r in own]) if n else None,
                     "frequency": frequency, "wilson_95": interval})
    return bins


def evaluate(store, policy):
    """Score unconditional cells only, without injecting them into ordinary forecasts."""
    check(policy, "session_evaluation")
    sessions.unique(policy["session_ids"], "session IDs")
    require(time(policy["cutoff"]) <= time(now()) and time(policy["resolution_as_of"]) <= time(now()), "Evaluation cutoffs cannot be in the future.")
    with store.connect(True) as c:
        states = [sessions._status(c, id) for id in policy["session_ids"]]
        require(len({s["specification"]["mode"] for s in states}) == 1, "Do not mix evaluation modes.")
        selected, exclusions, manifest = [], [], {}
        resolutions = Store.all(c, "resolution")
        for state in states:
            id, spec, final = state["session_id"], state["specification"], state["finalization"]
            manifest[id] = digest(Store.artifact(c, id))
            for e in [*state["events"], *state["submissions"]]:
                manifest[e["id"]] = digest(Store.artifact(c, e["id"]))
            if final:
                manifest[final["id"]] = digest(final)
            unconditional = next(i for i in spec["condition_ids"] if Store.artifact(c, i, "condition")["specification"]["kind"] == "unconditional")
            cells = {sessions.cell_key(cell): cell for cell in state["cells"]}
            for q in spec["questions"]:
                key = {"session_id": id, **q}
                reason = None
                history = [r for r in resolutions if r["question_id"] == q["question_id"] and r["question_version"] == q["version"]
                           and time(r["recorded_at"]) <= time(policy["resolution_as_of"])]
                resolution = history[-1] if history else None
                for r in history:
                    manifest[r["id"]] = digest(Store.artifact(c, r["id"]))
                if final is None:
                    reason = "session_not_finalized"
                elif spec["provenance"]["kind"] == "external" and not policy["allow_source_reported"]:
                    reason = "source_reported_timing_not_enabled"
                elif time(final["finalized_at"]) > time(policy["cutoff"]):
                    reason = "after_forecast_cutoff"
                elif resolution is None or resolution["outcome"] in ("void", "disputed"):
                    reason = resolution["outcome"] if resolution else "unresolved"
                elif time(final["finalized_at"]) >= min(time(r["known_at"]) for r in history):
                    reason = "not_before_resolution_knowledge"
                if reason:
                    exclusions.append({**key, "reason": reason})
                    continue
                p = cells[(*sessions.question_key(q), unconditional)]["probability"]
                y = int(resolution["outcome"] == "yes")
                question = Store.question(c, q["question_id"], q["version"])
                selected.append({**key, "probability": p, "outcome": y, "brier": (p-y)**2,
                                 "event_group": question["specification"]["event_group"], "resolution_id": resolution["id"]})
        membership = {}
        for r in selected:
            membership.setdefault((r["question_id"], r["version"]), set()).add(r["session_id"])
        common = {q for q, members in membership.items() if members == set(policy["session_ids"])}
        summaries = []
        for state in states:
            own = [r for r in selected if r["session_id"] == state["session_id"]]
            matched = [r for r in own if (r["question_id"], r["version"]) in common]
            summaries.append({"session_id": state["session_id"], "forecaster": state["specification"]["forecaster"],
                              "repetition": state["specification"]["repetition"], "available_n": len(own), "matched_n": len(matched),
                              "available_brier": mean([r["brier"] for r in own]) if own else None,
                              "matched_brier": mean([r["brier"] for r in matched]) if matched else None,
                              "calibration": _calibration(own), "session_usage": state["usage"],
                              "unknown_usage_attempts": state["unknown_usage_attempts"]})
        arms = []
        for forecaster in sorted({s["forecaster"] for s in summaries}):
            own = [s for s in summaries if s["forecaster"] == forecaster]
            values = [s["matched_brier"] for s in own if s["matched_brier"] is not None]
            arms.append({"forecaster": forecaster, "repetitions": len(own), "matched_questions": len(common),
                         "mean_session_brier": mean(values) if len(values) == len(own) else None})
        body = {"policy": policy, "selected": selected, "exclusions": exclusions, "summaries": summaries, "arms": arms,
                "input_manifest": manifest, "created_at": now(),
                "limitations": ["Only unconditional cells are eligible; interventions and information conditions remain unscored.",
                                "Brier is averaged across session losses, not scored after averaging forecasts.",
                                "Wilson intervals are descriptive binomial intervals, not cluster-adjusted uncertainty.",
                                "Recorded timing and modes do not certify absence of hindsight or training contamination."]}
        id = Store.put(c, "session_evaluation", body)
    return {"evaluation_id": id, **body}


def distribution_score(spec):
    """Empirical CRPS or quantile loss; never infer a full distribution from five quantiles."""
    from .schemas import NUMBER, NUMERIC_FORECAST, validate
    require(isinstance(spec, dict) and set(spec) in ({"outcome", "samples"}, {"outcome", "forecast"}), "Supply outcome with either samples or a numeric forecast.")
    validate(spec["outcome"], NUMBER)
    y = spec["outcome"]
    if "samples" in spec:
        require(isinstance(spec["samples"], list) and 1 <= len(spec["samples"]) <= 100000, "Supply 1..100000 empirical samples.")
        for x in spec["samples"]:
            validate(x, NUMBER)
        xs = sorted(x-y for x in spec["samples"])
        require(all(math.isfinite(x) for x in xs), "Distribution differences are not representable.")
        n = len(xs)
        crps = math.fsum(abs(x)/n for x in xs) - math.fsum(((2*i-n+1)/(n*n))*x for i, x in enumerate(xs))
        require(math.isfinite(crps), "Distribution score is not representable.")
        return {"metric": "empirical_crps", "score": max(0.0, crps), "samples": n, "outcome": y}
    validate(spec["forecast"], NUMERIC_FORECAST)
    sessions.validate_bindings({"numeric_forecasts": [spec["forecast"]], "bindings": []}, {})
    losses = [{"level": q["level"], "value": q["value"], "loss": (q["level"] - int(y < q["value"]))* (y-q["value"])}
              for q in spec["forecast"]["quantiles"]]
    require(all(math.isfinite(q["loss"]) for q in losses), "Quantile losses are not representable.")
    return {"metric": "quantile_loss", "losses": losses, "mean_loss": mean([q["loss"] for q in losses]),
            "limitation": "Mean loss over supplied levels; this is not CRPS or a complete distributional forecast."}
