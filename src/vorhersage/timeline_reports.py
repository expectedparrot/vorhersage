"""Offline scenario and milestone comparisons; unweighted cases stay unweighted."""

import json
from pathlib import Path

from . import timeline
from .store import Store


def export(store, model_id, output, other_id=None, *, forecast=None):
    from .workflow import evidence_refs, verify_refs
    with store.connect() as c:
        models = []
        for id in [model_id] + ([other_id] if other_id else []):
            body = timeline.read(c, id)
            spec = body["specification"]
            models.append({"model_id": id, "record": body, "analysis": timeline.analyze(spec),
                           "evidence": verify_refs(c, evidence_refs(spec), spec["information_as_of"])})
        q = models[0]["record"]["specification"]["question"]
        question = Store.question(c, q["question_id"], q["version"])
    comparison = timeline.compare_specs(*(m["record"]["specification"] for m in models)) if other_id else None
    data = {"question": question, "models": models, "comparison": comparison, "forecast": forecast}
    path = Path(output)
    path.write_text(render(data), encoding="utf-8")
    return {"path": str(path.resolve()), "model_ids": [m["model_id"] for m in models],
            "probabilities": [m["analysis"]["probability"] for m in models],
            "dispositions": [m["analysis"]["disposition"] for m in models]}


def render(data):
    encoded = json.dumps(data, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.replace("__DATA__", encoded)


TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vorhersage · Deadline model</title><style>
:root{color-scheme:light;--ink:#19333f;--muted:#566c76;--line:#cfddd9;--accent:#096f72}
*{box-sizing:border-box}body{margin:0;background:#f4f7f4;color:var(--ink);font:16px/1.5 system-ui,sans-serif}
main{max-width:1180px;margin:auto;padding:38px 24px}h1{font-size:clamp(26px,4vw,42px);line-height:1.2}h2{font-size:21px}
.eyebrow{color:var(--accent);text-transform:uppercase;font-weight:700;font-size:12px;letter-spacing:.12em}
.card{background:white;border:1px solid var(--line);border-radius:12px;padding:22px;margin:20px 0}.muted,small{color:var(--muted)}
.models{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}.models .card{margin:0}
.number{font-size:32px;font-weight:650}.notice{border-left:4px solid #b47e30;background:#fff7e5;padding:14px}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:10px;vertical-align:top}
.yes{color:#096c48;font-weight:650}.no{color:#aa3c27;font-weight:650}.unknown{color:#806014;font-weight:650}
select{font:inherit;padding:8px;max-width:100%;border:1px solid var(--line);border-radius:5px}
.milestone{padding:12px 0;border-bottom:1px solid var(--line)}.row{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
.track{height:14px;background:#eef3f0;position:relative;margin:8px 0}.bar{position:absolute;top:3px;height:8px;min-width:3px;background:var(--accent)}
.deadline{position:absolute;height:14px;border-left:2px solid #aa3c27;top:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
summary{cursor:pointer}.id{overflow-wrap:anywhere} @media(max-width:600px){main{padding:20px 14px}.models{grid-template-columns:1fr}}
</style></head><body><main>
<div class="eyebrow">Vorhersage / Milestones and deadlines</div><h1 id="title"></h1><p id="contract" class="muted"></p>
<p id="issued" class="notice" hidden></p>
<p class="notice">Scenarios are explicit joint assumptions. Unweighted cases show possible schedules; their success fraction is not a forecast probability.</p>
<div id="summary" class="models"></div>
<section class="card"><h2>Outcomes by scenario</h2><p id="changes" class="muted"></p><div id="outcomes" class="table-wrap"></div></section>
<section class="card"><h2>Inspect a schedule</h2><label for="scenario">Scenario </label><select id="scenario"></select>
<p class="muted">Bars show elapsed work; markers show milestones. Red marks the deadline. Dates are UTC. An in-progress task shows remaining work from the information cutoff.</p><div id="schedules" class="models"></div></section>
<section class="card"><h2>Research targets</h2><div id="gaps"></div></section>
<details class="card"><summary>Exact event definition, models, evidence and assumptions</summary><pre id="audit"></pre></details>
<noscript>Enable JavaScript to inspect the scenario schedules.</noscript>
</main><script id="record" type="application/json">__DATA__</script><script>
'use strict';
const data=JSON.parse(document.getElementById('record').textContent),el=id=>document.getElementById(id);
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
const date=t=>t?new Date(t).toISOString().slice(0,10):'—';
const outcome=r=>r.meets_deadline===null?'Unresolved':r.meets_deadline?'Meets deadline':'Misses deadline';
const cls=r=>r.meets_deadline===null?'unknown':r.meets_deadline?'yes':'no';
el('title').textContent=data.question.specification.text;
el('contract').textContent='Deadline: '+data.models[0].analysis.deadline+' · '+data.models[0].analysis.deadline_rule.replaceAll('_',' ');
if(data.forecast){el('issued').hidden=false;el('issued').textContent='Issued forecast: '+(100*data.forecast.probability).toFixed(2)+'% · '+data.forecast.issued_at+' · '+data.forecast.probability_basis+'. The model assessment is shown below.';}
for(const m of data.models){
 const a=m.analysis,s=m.record.specification,card=node('section',undefined,'card');card.append(node('h2',s.id+' · v'+s.version,'id'));
 card.append(node('div',a.probability===null?(a.disposition==='incomplete'?'Unresolved outcomes':'Unweighted'):(100*a.probability).toFixed(2)+'%','number'));
 card.append(node('p',s.description),node('small','Information cutoff: '+s.information_as_of));
 if(a.probability===null&&a.probability_bounds)card.append(node('p','Bounds from unresolved weight: '+a.probability_bounds.map(p=>(100*p).toFixed(2)+'%').join(' – ')));
 el('summary').append(card);
 const gaps=node('section');gaps.append(node('h3',s.id));
 for(const row of a.gaps.unresolved)gaps.append(node('p',row.scenario_id+' / '+row.parameter_id+': '+row.research_task+' — '+row.rationale));
 gaps.append(node('p',a.gaps.assumed_inputs.length+' parameter assignments are assumed. Dependency rationales and evidence are in the audit.','muted'));
 if(a.gaps.unweighted)gaps.append(node('p','No scenario weights declared.'));
 el('gaps').append(gaps);
}
const ids=[...new Set(data.models.flatMap(m=>m.analysis.scenarios.map(s=>s.scenario_id)))];
const table=node('table'),head=node('tr');head.append(node('th','Scenario'));
for(const m of data.models)head.append(node('th',m.record.specification.id));table.append(head);
for(const id of ids){const option=node('option',id);option.value=id;el('scenario').append(option);const tr=node('tr');tr.append(node('td',id));
 for(const m of data.models){const r=m.analysis.scenarios.find(s=>s.scenario_id===id),td=node('td');if(r)td.append(node('div',outcome(r),cls(r)),node('small',r.status==='never'?'Never completes':date(r.launch_at)));else td.textContent='Scenario absent';tr.append(td);}table.append(tr);}
el('outcomes').append(table);
el('changes').textContent=data.comparison?'Changed fields: '+data.comparison.changed_fields.join(', ')+'. Matching labels do not establish equal assumptions.':'Each row uses its complete declared set of inputs.';
function show(){
 el('schedules').replaceChildren();const selected=el('scenario').value;
 const selectedRows=data.models.map(m=>m.analysis.scenarios.find(s=>s.scenario_id===selected));
 const timestamps=data.models.flatMap(m=>[Date.parse(m.analysis.information_as_of),Date.parse(m.analysis.deadline)]);
 for(const r of selectedRows)if(r)for(const n of r.schedule){if(n.start_at)timestamps.push(Date.parse(n.start_at));if(n.finish_at)timestamps.push(Date.parse(n.finish_at));}
 const lo=Math.min(...timestamps),hi=Math.max(...timestamps),span=Math.max(1,hi-lo),pos=t=>100*(Date.parse(t)-lo)/span;
 for(let i=0;i<data.models.length;i++){
  const m=data.models[i],r=selectedRows[i],card=node('div',undefined,'card');card.append(node('h3',m.record.specification.id));
  if(!r){card.append(node('p','Scenario absent'));el('schedules').append(card);continue;}
  card.append(node('p',outcome(r),cls(r)));
  for(const n of r.schedule){
   const definition=m.record.specification.nodes.find(x=>x.id===n.node_id),box=node('div',undefined,'milestone');
   const label=node('div',undefined,'row');label.append(node('strong',n.node_id),node('span',n.status==='finite'?date(n.finish_at):n.status));box.append(label);
   box.append(node('small',definition.completion_condition+' · Prerequisites: '+(definition.parents.join(', ')||'none')));
   const track=node('div',undefined,'track'),deadline=node('div',undefined,'deadline');deadline.style.left=pos(m.analysis.deadline)+'%';track.append(deadline);
   if(n.finish_at){const bar=node('div',undefined,'bar'),start=n.start_at||n.finish_at;bar.style.left=pos(start)+'%';bar.style.width=Math.max(0,pos(n.finish_at)-pos(start))+'%';track.append(bar);}box.append(track);
   if(n.controlling_parents.length)box.append(node('small','Date controlled by: '+n.controlling_parents.join(', ')));
   card.append(box);
  }el('schedules').append(card);
 }
}
el('audit').textContent=JSON.stringify(data,null,2);el('scenario').onchange=show;el('scenario').value=ids[0];show();
</script></body></html>'''
