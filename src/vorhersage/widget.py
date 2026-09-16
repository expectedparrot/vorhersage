"""Self-contained, offline exploration of a forecast's frozen odds ledger."""

import json
from pathlib import Path

from .common import digest, require
from .odds import calculate
from .store import Store


def export(store, forecast_id, output):
    with store.connect() as c:
        forecast = Store.artifact(c, forecast_id, "forecast")
        manifest = forecast["input_manifest"]
        require(digest(manifest) == forecast["manifest_sha256"], "Forecast manifest integrity check failed.", "integrity_error")
        artifacts = {id: Store.artifact(c, id) for id in manifest}
        require(all(digest(artifacts[id]) == sha for id, sha in manifest.items()),
                "Forecast input integrity check failed.", "integrity_error")
        assessments = [(id, a) for id, a in artifacts.items()
                       if a.get("task", {}).get("kind") == "assessment"]
        require(assessments, "Forecast has no assessment to export.")
        assessment_id, assessment = max(assessments, key=lambda item: item[1]["revision"])
        if assessment["payload"]["method"] == "timeline_model":
            from .timeline_reports import export as export_timeline
            return export_timeline(store, assessment["payload"]["timeline_model_id"], output,
                                   forecast={"id": forecast_id, **forecast})
        require(assessment["payload"]["method"] == "odds_ledger", "Latest assessment does not use an odds ledger.")
        ledger = assessment["payload"]["odds_ledger"]
        data = {"forecast_id": forecast_id, "assessment_id": assessment_id,
                "question": forecast["question"]["text"], "issued_probability": forecast["probability"],
                "issued_at": forecast["issued_at"], "probability_basis": forecast["probability_basis"],
                "ledger": ledger, "calculation": calculate(ledger), "input_manifest": manifest,
                "anchor_prior": artifacts.get(ledger["anchor"].get("prior_artifact_id")),
                "assessment_rationale": assessment["payload"]["rationale"],
                "assessment_limitations": assessment["payload"]["limitations"],
                "reviews": [a for a in sorted(artifacts.values(), key=lambda a: a.get("revision", -1))
                            if a.get("task", {}).get("kind") == "review" and a["revision"] > assessment["revision"]],
                "findings": [next(r for r in artifacts[e["evidence_refs"][0]["packet_id"]]["records"]
                                   if r["id"] == e["finding_id"]) for e in ledger["entries"]]}
    path = Path(output)
    path.write_text(render(data), encoding="utf-8")
    return {"path": str(path.resolve()), "forecast_id": forecast_id, "assessment_id": assessment_id,
            "issued_probability": forecast["probability"], "ledger_probability": data["calculation"]["probability"]}


def render(data):
    # JSON in a raw-text script element must not contain an HTML closing tag.
    encoded = json.dumps(data, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.replace("__DATA__", encoded)


TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vorhersage · Odds ledger</title>
<style>
:root{color-scheme:light;--ink:#182c36;--muted:#526875;--accent:#006d77;--line:#cbdad9}
*{box-sizing:border-box}body{margin:0;background:#f4f7f4;color:var(--ink);font:16px/1.55 system-ui,sans-serif}
main{max-width:1080px;margin:auto;padding:40px 24px}h1{font-size:clamp(25px,4vw,40px);line-height:1.2;max-width:900px}
h2{font-size:20px;margin:0 0 14px}.eyebrow{letter-spacing:.15em;text-transform:uppercase;color:var(--accent);font-size:12px;font-weight:700}
.muted,small{color:var(--muted)}.stats,.columns{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:24px 0}
.card{background:white;border:1px solid var(--line);border-radius:14px;padding:24px}.number{font-size:42px;font-weight:650;font-variant-numeric:tabular-nums}
.term{border-top:1px solid var(--line);padding:18px 0}.term:first-child{border:0}.title{font-weight:650;overflow-wrap:anywhere}
input[type=range]{width:100%;accent-color:var(--accent)}input[type=number]{width:110px;padding:6px;border:1px solid var(--line);border-radius:5px;font:inherit}
input[type=checkbox]{accent-color:var(--accent)}label{cursor:pointer}button{background:var(--accent);color:white;border:0;padding:10px 18px;border-radius:6px;font:inherit;cursor:pointer}
.bar{height:9px;background:#e3ece8;border-radius:6px;margin:6px 0 15px;overflow:hidden}.fill{height:100%;background:var(--accent)}
.notice{border-left:4px solid #ae7132;padding:10px 15px;background:#fff6e7}.row{display:flex;justify-content:space-between;gap:10px;align-items:center}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer}output{font-variant-numeric:tabular-nums}
@media(max-width:720px){.columns,.stats{grid-template-columns:1fr}main{padding:24px 16px}.card{padding:18px}}
</style></head><body><main>
<div class="eyebrow">Vorhersage / Declared odds ledger</div><h1 id="question"></h1>
<p class="muted" id="identity"></p>
<div class="stats"><section class="card"><div class="eyebrow">Issued forecast · fixed</div><div class="number" id="issued"></div><small id="basis"></small></section>
<section class="card" aria-live="polite"><div class="eyebrow">Explored posterior</div><div class="number" id="posterior"></div><small id="comparison"></small></section></div>
<p class="notice" id="review-note" hidden></p>
<p>Likelihood ratios are declared judgments. Editing this page explores assumptions; the issued forecast and its history stay fixed.</p>
<div class="columns"><section class="card"><h2>Assumptions</h2><div class="term"><label class="title" for="anchor">Anchor probability</label>
<div class="row"><input id="anchor" type="range" min="0.0001" max="0.9999" step="any"><input id="anchor-value" aria-label="Anchor probability between zero and one" type="number" min="0.0001" max="0.9999" step="any"></div><small id="anchor-note"></small></div>
<div id="terms"></div><button id="reset" type="button">Reset to recorded ledger</button></section>
<section class="card"><h2>Odds waterfall</h2><p class="muted">Cumulative probabilities after each odds multiplier.</p><div id="waterfall"></div>
<h2>Single-ratio sensitivity</h2><p class="muted">Vary one active ratio over its declared range, holding the other controls fixed. These are assumption ranges.</p><div id="sensitivity"></div></section></div>
<p class="notice" id="dependence"></p><p class="muted" id="independence"></p>
<details class="card"><summary>Frozen ledger, findings, and audit references</summary><pre id="audit"></pre></details>
<noscript><p>Enable JavaScript to inspect the interactive ledger.</p></noscript>
</main><script id="record" type="application/json">__DATA__</script><script>
'use strict';
const record=JSON.parse(document.getElementById('record').textContent);
const ledger=record.ledger, original=record.calculation;
const el=id=>document.getElementById(id), pct=p=>(100*p).toFixed(2)+'%';
const logit=p=>Math.log(p)-Math.log1p(-p);
const logistic=x=>x>=0?1/(1+Math.exp(-x)):Math.exp(x)/(1+Math.exp(x));
const controls=[];
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
el('question').textContent=record.question;
el('identity').textContent=record.forecast_id+' · '+record.issued_at;
el('issued').textContent=pct(record.issued_probability);
el('basis').textContent='Recorded basis: '+record.probability_basis;
el('anchor-note').textContent=ledger.anchor.basis+' anchor · '+ledger.anchor.rationale+(ledger.anchor.prior_artifact_id?' · '+ledger.anchor.prior_artifact_id:'');
el('anchor').min=el('anchor-value').min=Math.min(0.0001,ledger.anchor.probability);
el('anchor').max=el('anchor-value').max=Math.max(0.9999,ledger.anchor.probability);
el('independence').textContent='Declared independence across groups: '+ledger.independence_rationale;
el('audit').textContent=JSON.stringify(record,null,2);
if(record.probability_basis==='review_judgment'){
 el('review-note').hidden=false;el('review-note').textContent='Review supplied the final issued judgment. This ledger produced '+pct(original.probability)+' before that review; the controls explain the assessment.';
}
const jointCount=original.terms.filter(t=>t.joint).length;
el('dependence').textContent=jointCount?jointCount+' dependence group(s) use a joint ratio. Each joint control replaces its member ratios; the members are never multiplied separately.':'Each finding declares a separate dependence group. This is an assumption supplied by the author.';
for(const term of original.terms){
 const box=node('div',undefined,'term'), label=node('label',undefined,'title'), check=node('input');check.type='checkbox';check.checked=true;
 label.append(check,document.createTextNode(' '+term.id+(term.joint?' · joint ratio':'')));box.append(label,node('p',term.rationale,'muted'));
 box.append(node('small','Findings: '+term.finding_ids.join(', ')));
 const row=node('div',undefined,'row'), range=node('input'), number=node('input');
 range.type='range';range.min=Math.log(term.lr_range[0]);range.max=Math.log(term.lr_range[1]);range.step='any';range.value=Math.log(term.lr);
 range.disabled=term.lr_range[0]===term.lr_range[1];range.setAttribute('aria-label',term.id+' likelihood ratio slider');
 number.type='number';number.min=term.lr_range[0];number.max=term.lr_range[1];number.step='any';number.value=term.lr;number.setAttribute('aria-label',term.id+' likelihood ratio');
 row.append(range,number);box.append(row,node('small','Declared range: ×'+term.lr_range[0]+' to ×'+term.lr_range[1]));el('terms').append(box);
 controls.push({term,check,range,number});
 range.oninput=()=>{number.value=Math.max(term.lr_range[0],Math.min(term.lr_range[1],Math.exp(Number(range.value))));update();};
 number.oninput=()=>{range.value=Math.log(Number(number.value));update();};check.onchange=update;
}
function metric(parent,title,value){const row=node('div',undefined,'row');row.append(node('span',title),node('output',pct(value)));const bar=node('div',undefined,'bar'),fill=node('div',undefined,'fill');fill.style.width=(100*value)+'%';bar.append(fill);parent.append(row,bar);}
function update(){
 const anchor=Number(el('anchor-value').value), valid=Number.isFinite(anchor)&&anchor>0&&anchor<1&&controls.every(c=>Number.isFinite(Number(c.number.value))&&Number(c.number.value)>0&&Number(c.number.value)>=c.term.lr_range[0]&&Number(c.number.value)<=c.term.lr_range[1]);
 el('waterfall').replaceChildren();el('sensitivity').replaceChildren();
 if(!valid){el('posterior').textContent='Invalid input';el('comparison').textContent='Use a probability strictly between 0 and 1 and ratios within declared ranges.';return;}
 const active=controls.filter(c=>c.check.checked), base=logit(anchor), logs=active.map(c=>Math.log(Number(c.number.value)));
 let total=base;metric(el('waterfall'),'Anchor',anchor);
 active.forEach((c,i)=>{total+=logs[i];metric(el('waterfall'),c.term.id+' ×'+Number(c.number.value).toPrecision(4),logistic(total));});
 const posterior=logistic(total);el('posterior').textContent=pct(posterior);
 const target=ledger.comparison_probability;
 el('comparison').textContent=target===undefined?'':((posterior-target)*100).toFixed(2)+' percentage points vs comparison '+pct(target);
 const sensitivities=active.map((c,i)=>{const other=base+logs.reduce((sum,v,j)=>sum+(j===i?0:v),0),lo=logistic(other+Math.log(c.term.lr_range[0])),hi=logistic(other+Math.log(c.term.lr_range[1]));return {c,other,lo,hi};}).sort((a,b)=>(b.hi-b.lo)-(a.hi-a.lo));
 for(const {c,other,lo,hi} of sensitivities){
  el('sensitivity').append(node('div',c.term.id+': '+pct(lo)+' – '+pct(hi),'title'));
  if(target!==undefined){const threshold=Math.exp(logit(target)-other);el('sensitivity').append(node('small','Matches comparison at ×'+(Number.isFinite(threshold)?threshold.toPrecision(4):'beyond numeric range')+(lo<target&&target<hi?' · crosses within range':' · no crossing within range')));}
  const bar=node('div',undefined,'bar'),fill=node('div',undefined,'fill');fill.style.marginLeft=(100*lo)+'%';fill.style.width=(100*(hi-lo))+'%';bar.append(fill);el('sensitivity').append(bar);
 }
}
function reset(){el('anchor').value=ledger.anchor.probability;el('anchor-value').value=ledger.anchor.probability;for(const c of controls){c.check.checked=true;c.range.value=Math.log(c.term.lr);c.number.value=c.term.lr;}update();}
el('anchor').oninput=()=>{el('anchor-value').value=el('anchor').value;update();};
el('anchor-value').oninput=()=>{el('anchor').value=el('anchor-value').value;update();};el('reset').onclick=reset;reset();
</script></body></html>'''
