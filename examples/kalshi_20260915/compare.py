"""Compare frozen paper forecasts; score only recorded final binary settlements.

Run after capture.py --stage resolution to incorporate the latest saved results.
This script is offline, preserves the baseline, and places no orders.
"""
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read(path):
    return json.loads(path.read_text())

def timestamp(value):
    return datetime.fromisoformat(value.replace('Z','+00:00'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def score_pair(model, market, outcome):
    assert all(type(p) in (int,float) and math.isfinite(p) and 0<=p<=1 for p in (model,market))
    assert outcome in (0,1)
    left=(model-outcome)**2; right=(market-outcome)**2
    return {'model_brier':left,'market_brier':right,'difference':left-right}

def seal_path(folder, relative):
    candidate=folder/'outputs'/relative
    if not candidate.is_file(): candidate=folder/relative
    assert candidate.resolve().is_relative_to(folder.resolve()), 'Seal path escapes forecast directory'
    return candidate

def build():
    baseline=read(ROOT/'baseline.json'); policy=read(ROOT/'evaluation_policy.json')
    assert sha(ROOT/'baseline.json')==policy['baseline_sha256'], 'Frozen baseline changed'
    assert sha(ROOT/baseline['snapshot_file'])==baseline['snapshot_sha256'], 'Raw baseline changed'
    latest_paths=sorted((ROOT/'raw').glob('resolution-*.json'))
    latest=read(latest_paths[-1]) if latest_paths else None
    resolutions={r['key']:r for r in latest['records']} if latest else {}
    post_paths=sorted((ROOT/'raw').glob('post_forecast-*.json'))
    post=read(post_paths[-1]) if post_paths else None
    post_quotes={r['key']:r['quote'] for r in post['records']} if post else {}
    rows=[]
    for record in baseline['records']:
        key=record['key']; m=record['market_response']['data']['market']; q=record['quote']
        folder=ROOT/'forecasts'/key
        row={'key':key,'ticker':record['ticker'],'question':read(folder/'question.json')['text'],
             'kalshi_url':'https://kalshi.com/markets/'+record['series_ticker'].lower(),
             'baseline':q,'post_forecast_quote':post_quotes.get(key), 'model_probability':None,
             'probability_difference_pp':None,'state':'awaiting_forecast','outcome':None,'scores':None,
             'forecast_report':f'forecasts/{key}/outputs/forecast.html',
             'forecast_summary':f'forecasts/{key}/outputs/forecast_summary.md',
             'event_deadline':read(folder/'question.json')['event_deadline']}
        seal_file=folder/'outputs/sealed_result.json'
        if seal_file.exists():
            seal=read(seal_file)
            files=seal.get('files',seal.get('sha256',seal.get('hashes',{})))
            assert files, 'Missing sealed file inventory'
            for relative, expected in files.items():
                assert sha(seal_path(folder,relative))==expected, 'Changed sealed output: '+key+'/'+relative
            forecast=read(folder/'outputs/forecast.json')
            p=forecast['probability']
            assert math.isclose(p,seal['probability'],abs_tol=1e-12)
            assert forecast['question_id']==read(folder/'question.json')['id']
            assert forecast['question']==read(folder/'question.json'), 'Forecast changed the frozen question contract'
            assert forecast['question_version']==1, 'Forecast used a revised question'
            assert forecast['mode']=='prospective'
            assert timestamp(forecast['issued_at'])<timestamp(row['event_deadline'])
            assert timestamp(q['captured_at'])<timestamp(forecast['issued_at'])
            row.update(model_probability=p,probability_difference_pp=100*(p-q['midpoint']),
                       issued_at=forecast['issued_at'],information_as_of=forecast['information_as_of'],
                       forecast_id=forecast.get('id',seal.get('forecast_id')),exposure=seal.get('exposure_declaration',seal.get('exposure')),
                       state='unresolved',hypothetical_yes=score_pair(p,q['midpoint'],1),
                       hypothetical_no=score_pair(p,q['midpoint'],0))
            if key in resolutions:
                current=resolutions[key]['market_response']['data']['market']
                row['resolution_snapshot_at']=resolutions[key]['market_response']['retrieved_at']
                row['exchange_status']=current['status']
                changed=[field for field in ('rules_primary','rules_secondary') if current.get(field,'')!=m.get(field,'')]
                if changed:
                    row.update(state='rule_change_requires_review',changed_fields=changed)
                elif current['status']=='finalized' and current.get('result') in ('yes','no'):
                    settled=current.get('settlement_ts')
                    if isinstance(settled,(int,float)):
                        settled=datetime.fromtimestamp(settled,timezone.utc).isoformat()
                    if settled and timestamp(settled)<=timestamp(forecast['issued_at']):
                        row['state']='known_before_forecast_excluded'
                    else:
                        y=int(current['result']=='yes')
                        row.update(state='resolved',outcome=y,scores=score_pair(p,q['midpoint'],y),settlement_at=settled)
                elif current['status']=='finalized':
                    row['state']='nonbinary_or_canceled_excluded'
        rows.append(row)
    matched=[r for r in rows if r['scores'] is not None]
    n=len(matched)
    summary={'selected_n':len(rows),'forecasts_n':sum(r['model_probability'] is not None for r in rows),
             'matched_resolved_n':n,'model_mean_brier':math.fsum(r['scores']['model_brier'] for r in matched)/n if n else None,
             'market_mean_brier':math.fsum(r['scores']['market_brier'] for r in matched)/n if n else None,
             'paired_mean_difference':math.fsum(r['scores']['difference'] for r in matched)/n if n else None,
             'interpretation':'Negative paired difference favors the model. No statistical superiority claim; purposively selected n=3.'}
    report={'created_at':datetime.now(timezone.utc).isoformat(),'policy':policy,'rows':rows,'summary':summary,
            'resolution_snapshot':str(latest_paths[-1].relative_to(ROOT)) if latest_paths else None,
            'post_forecast_snapshot':str(post_paths[-1].relative_to(ROOT)) if post_paths else None,
            'limitations':['Midpoints are comparison estimates, not executable prices; no fees, slippage or trading returns are modeled.',
                           'The baseline preceded research; the later quote snapshot discloses subsequent market movement. Inspect actual timestamps; the later check need not coincide with forecast completion.',
                           'Finalized exchange outcomes are the settlement target; changed text requires review and unresolved cases remain excluded.',
                           'Fresh supplied context does not erase training knowledge; incidental market exposure is recorded per forecast.',
                           'Prices can be informative without being the truth. Current disagreement is not realized accuracy.']}
    return report

def render(data):
    encoded=json.dumps(data,ensure_ascii=True,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return TEMPLATE.replace('__DATA__',encoded)

TEMPLATE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kalshi forecast pilot</title>
<style>body{background:#f5f7f4;color:#193540;font:16px/1.55 system-ui;margin:0}main{max-width:1150px;margin:auto;padding:36px 24px}h1{font-size:38px;line-height:1.15}h2{font-size:21px}.muted,small{color:#576b70}.card{background:white;border:1px solid #cdd9d3;border-radius:10px;padding:22px;margin:20px 0}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:780px}th,td{text-align:left;border-bottom:1px solid #dae3de;padding:12px;vertical-align:top}th{font-size:13px}a{color:#0b7075}select{font:inherit;padding:7px}.big{font-size:28px;font-weight:650}.notice{border-left:4px solid #af7b29;padding:12px;background:#fff7e5}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}summary{cursor:pointer}</style></head><body><main>
<small>VORHERSAGE · PROSPECTIVE PAPER COMPARISON</small><h1>Three questions. Frozen prices. Independent forecasts.</h1><p id="timing" class="muted"></p>
<p class="notice">Current disagreement is not an accuracy result. Brier scores appear only for final binary settlements. Lower scores are better.</p>
<section class="card"><h2>Model and market</h2><div id="table" class="scroll"></div><p class="muted">Market baseline is the captured YES bid–ask midpoint. Bid, ask and last trade are shown separately. Differences are percentage points.</p></section>
<section class="card"><h2>Recorded accuracy</h2><div id="summary" class="grid"></div><p>Score = (probability − outcome)², where YES is 1 and NO is 0. Paired difference = model score − market score. This small, selected pilot supports descriptive comparisons.</p></section>
<section class="card"><h2>What would each outcome mean?</h2><p class="muted">These selectors are hypothetical. They do not change recorded outcomes or the accuracy summary.</p><div id="simulations" class="grid"></div></section>
<details class="card"><summary>Frozen policy, timestamps, exposure declarations and audit data</summary><pre id="audit"></pre></details>
</main><script type="application/json" id="data">__DATA__</script><script>
const data=JSON.parse(document.getElementById('data').textContent),el=id=>document.getElementById(id);
function n(tag,text){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}function pct(p){return p===null?'Pending':(100*p).toFixed(1)+'%';}
el('timing').textContent='Baseline captured '+data.rows[0].baseline.captured_at+' · Report updated '+data.created_at;
const table=n('table'),head=n('tr');for(const t of ['Question','Kalshi baseline','Independent model','Difference','State / detail'])head.append(n('th',t));table.append(head);
for(const r of data.rows){const tr=n('tr'),q=n('td'),a=n('a',r.question);a.href=r.kalshi_url;q.append(a,n('br'),n('small',r.ticker));tr.append(q);
const market=n('td');market.append(n('strong',pct(r.baseline.midpoint)),n('br'),n('small','Bid '+pct(r.baseline.yes_bid)+' / ask '+pct(r.baseline.yes_ask)),n('br'),n('small','Last '+pct(r.baseline.last_trade)));tr.append(market);
const model=n('td',pct(r.model_probability));if(r.post_forecast_quote){model.append(n('br'),n('small','Later market: '+pct(r.post_forecast_quote.midpoint)));}tr.append(model,n('td',r.probability_difference_pp===null?'—':(r.probability_difference_pp>0?'+':'')+r.probability_difference_pp.toFixed(1)+' pp'));
const status=n('td',r.state.replaceAll('_',' '));if(r.model_probability!==null){const link=n('a','Inspect model');link.href=r.forecast_report;status.append(n('br'),link);}tr.append(status);table.append(tr);
if(r.model_probability!==null){const card=n('div'),select=n('select'),output=n('p');card.append(n('strong',r.key));for(const [v,t] of [['','Choose hypothetical outcome'],['1','Suppose YES'],['0','Suppose NO']]){const o=n('option',t);o.value=v;select.append(o);}select.onchange=()=>{if(select.value===''){output.textContent='';return;}const y=Number(select.value),m=(r.model_probability-y)**2,k=(r.baseline.midpoint-y)**2;output.textContent='Model '+m.toFixed(4)+' · Market '+k.toFixed(4)+' · Difference '+(m-k).toFixed(4)+' (hypothetical)';};card.append(n('br'),select,output);el('simulations').append(card);}}
el('table').append(table);for(const [label,value] of [['Resolved pairs',data.summary.matched_resolved_n],['Model mean Brier',data.summary.model_mean_brier],['Market mean Brier',data.summary.market_mean_brier],['Paired difference',data.summary.paired_mean_difference]]){const c=n('div');c.append(n('small',label),n('div',value===null?'Awaiting outcomes':typeof value==='number'&&label!=='Resolved pairs'?value.toFixed(4):String(value)));el('summary').append(c);}el('audit').textContent=JSON.stringify(data,null,2);
</script></body></html>'''

if __name__=='__main__':
    report=build()
    (ROOT/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (ROOT/'comparison.html').write_text(render(report))
    print(json.dumps(report['summary'],indent=2))
