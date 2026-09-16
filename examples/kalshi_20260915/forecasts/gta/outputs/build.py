"""Reproduce with PYTHONPATH=../src python3 build.py --project ../repro_project --out ../repro_outputs.
Uses frozen research, never browses; refuses an existing project/output seal.
Default paths are for original issuance; use fresh alternate paths for replay.
"""
import argparse,copy,datetime,hashlib,json,math,pathlib,sqlite3
from vorhersage import timeline,timeline_reports
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from vorhersage.evidence import validate_packet
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent
ap=argparse.ArgumentParser();ap.add_argument('--project',default=str(ROOT/'project'));ap.add_argument('--out',default=str(HERE));args=ap.parse_args()
out=pathlib.Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
if (out/'sealed_result.json').exists(): raise SystemExit('Sealed output is immutable: select a fresh --out and --project.')
def read(n):return json.loads((HERE/n).read_text())
def dump(n,x): (out/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
packet=validate_packet(read('evidence.json'));dump('evidence.json',packet)
conclusion=read('research_conclusion.json');cut=conclusion['information_as_of'];limits=conclusion['limitations']
w=Workflow(args.project);w.store.init('GTA VI blind timeline pilot');q=json.loads((ROOT/'question.json').read_text());w.question(q)
pkt=w.import_packet(packet)['packet_id'];refs=[{'packet_id':pkt,'record_id':r['id']} for r in packet['records']]
def ref(*ids): return [r for r in refs if r['record_id'] in ids]
# Preserve the original pre-research model in the same immutable store.
original=read('structure_before_research.json');original_id=timeline.add(w.store,original)['timeline_model_id']
s=copy.deepcopy(original);s.update(id='gta_research_structure',derived_from_model_id=original_id,information_as_of=cut,description='Full US first-platform release or passing-announced-date contract route; aggregate remaining work at research cutoff.',limitations=limits)
s['nodes'][0]['evidence_refs']=ref('may_delay','rockstar_current');s['nodes'][1]['evidence_refs']=ref('support','xbox');s['nodes'][2]['evidence_refs']=ref('rockstar_current','q1_2027');s['nodes'][3]['evidence_refs']=ref('nov_delay','may_delay')
# The partition is based on realized first release date and alternate clause, not on independently sampled gates.
definitions={
'scheduled':('First qualifying full US release occurs on or before November 19, 2026.',.88,'Subjective dominant case: current November date, active preorders, detailed preload plan and completed August preview roughly two months before launch. This is evidence-informed judgment, not a measured completion probability.'),
'brief_delay':('First qualifying full US release occurs November 20–30, 2026.',.025,'Subjective small tail: only eleven calendar days of slippage fit. Prior large postponements suggest most new quality delays would exceed this narrow window.'),
'long_delay':('No qualifying full release by November 30 and no announced-date YES; full release occurs later.',.085,'Subjective material residual: prior public dates were revised, internal completion and certification are unobserved, and major remaining bugs could move launch by months.'),
'silent_date':('No qualifying full release by deadline, but an announced release date passes before the deadline without any indication of delay.',.005,'Explicit small subjective rule-route residual. Silence despite a missed release is unusual for a major title; an obvious outage/delay indication would disqualify this route.'),
'disruption':('No announced-date YES by deadline and no eventual qualifying full US release.',.005,'Explicit residual assumption for cancellation, permanent platform exclusion or other terminal disruption; commercial commitments make this very small.')}
for row in s['scenarios']: row['description']=definitions[row['id']][0]
s['partition_justification']='Partition by first qualifying full US release: (1) by Nov19; (2) Nov20–30; otherwise (3) alternate announced-date clause satisfied; otherwise (4) eventual later release; or (5) no eventual qualifying release. These branches are mutually exclusive and exhaustive conditional on binary frozen-rule settlement. Representative dates approximate each branch; void/disputed settlement is handled separately, not misclassified NO. Early surprise release belongs to scheduled; a sole-platform release qualifies. Weights describe joint scenarios; gates are not multiplied independently.'
structure_id=timeline.add(w.store,s)['timeline_model_id']
run=w.start(dict(question_id=q['id'],forecaster='kalshi_blind_20260915',method='Independent finite joint milestone scenarios',mode='prospective',information_as_of=cut,max_searches=20,max_extra_tasks=2,workflow='timeline',cutoff_policy='fixed',research_status='completed'))['run_id']
receipts=[]
def submit(payload):
 n=w.next(run)
 r=w.submit(run,dict(task_id=n['task']['id'],expected_revision=n['revision'],idempotency_key='task_'+str(n['revision']),payload=payload))
 receipts.append(r);return r
submit(dict(timeline_model_id=structure_id,rationale='Registered pre-browse unresolved unweighted structure, then cutoff-matched refinement; no starting probability.'))
values={
 'scheduled':(45,56,'2026-11-19T12:00:00-05:00','2026-11-20T00:00:00-05:00'),
 'brief_delay':(68,72,'2026-11-27T12:00:00-05:00','2026-11-28T00:00:00-05:00'),
 'long_delay':(120,135,'2027-02-18T12:00:00-05:00','never'),
 'silent_date':(90,97,'2027-01-15T12:00:00-05:00','2026-11-20T00:00:00-05:00'),
 'disruption':('never','never','never','never')}
parameter_notes={
 'content_ready':'Representative remaining elapsed days from cutoff to content readiness. Exact internal state unobserved. Joint branch assumption chosen to represent on-time, brief-slip, longer rework or terminal paths; not a measured duration.',
 'platform_ready':'Representative remaining elapsed days to the first qualifying platform becoming distributable; includes certification, preload and distribution readiness in parallel with content work. No internal certification milestone observed. Digital-first boxed codes reduce disc-manufacturing dependence, not software-readiness risk.',
 'launch_slot':'Representative full-release commercial gate. On-time November date is evidence-informed, but noon US Eastern is only a modeling convention; late dates are assumptions, not announced revisions.',
 'announcement_trigger':'Applies only when an applicable announced release date has passed with no indication of delay. Modeled at next US Eastern midnight. Never means this alternative route does not trigger in the scenario, not that full release is impossible.'}
for i,param in enumerate(s['parameters']):
 pid=param['id'];assign=[]
 for sid in definitions:
  basis='estimated' if pid=='launch_slot' and sid=='scheduled' else 'assumed'
  a=dict(parameter_id=pid,basis=basis,value=values[sid][i],rationale=parameter_notes[pid],evidence_refs=ref('rockstar_current','support','q1_2027') if basis=='estimated' else [])
  assign.append(dict(scenario_id=sid,assessment=a))
 submit(dict(assessments=assign,rationale=parameter_notes[pid]))
current=w.next(run)['task']['timeline_context']['timeline_model_id'] if 'timeline_context' in w.next(run)['task'] else None
# Read the current cloned-and-revised model from run state, never the original model.
with w.store.connect() as c:
 _,state,_=Store.run(c,run);current=state['timeline_model_id'];final=copy.deepcopy(timeline.read(c,current)['specification'])
for row in final['scenarios']:
 row['weight']=definitions[row['id']][1];row['weight_rationale']=definitions[row['id']][2];row['evidence_refs']=refs
final.update(version=final['version']+1,previous_model_id=current)
final_id=timeline.add(w.store,final)['timeline_model_id'];dump('model.json',final)
analysis=timeline.analyze(final);dump('analysis.json',analysis)
submit(dict(method='timeline_model',timeline_model_id=final_id,rationale='Probability is the exact sum of successful declared joint-scenario weights; no prior task or market-price input.',limitations=limits,evidence_refs=refs))
review=dict(decision='retain',rationale='Bounded pilot review retains subjective weights with explicit schedule and weight stresses. Process integrity does not establish calibration.',objections=[dict(direction='too_high',objection='Preorders and previews do not prove a finished build; repeated delays and only eleven days of slack could conceal a substantial miss probability.',response='Long-delay and terminal branches remain nonzero; shift ten points from on-time to long-delay in downside sensitivity. No claim of gold or certification complete.'),dict(direction='too_low',objection='Specific preorder/preload commitments and an August preview make a major two-month-out delay increasingly costly. One qualifying platform suffices.',response='On-time branch dominates; upside sensitivity shifts five points from long-delay to on-time. Sole-platform completion is already sufficient.')],evidence_refs=refs)
submit(review);dump('review.json',review)
issue=submit(dict(stopping_reason='Focused primary-source checks completed; remaining material uncertainty is private production status, not a missing public schedule. Paper forecast only.',review_at='2026-10-01T12:00:00-04:00',triggers=[dict(description=t,evidence_refs=refs) for t in ['Rockstar revises or reaffirms US launch date.','Verified gold/certification or final release-build milestone.','November 12 preload opens or is postponed.','First full US release on any qualifying platform; do not mistake preloading, alpha or beta for full release.','Announced date passes: inspect any indication of delay before applying the alternate YES clause.']]))
fid=issue['forecast_id']
with w.store.connect() as c: forecast=Store.artifact(c,fid,'forecast')
forecast={'id':fid,**forecast};dump('forecast.json',forecast);dump('workflow_receipts.json',receipts)
timeline_reports.export(w.store,final_id,out/'forecast.html',forecast=forecast)
# Package sensitivity plus weight stresses. These are judgments, not uncertainty intervals.
sens=timeline.sensitivity(final)
weight_stresses=[]
for label,shift in [('downside',-.10),('upside',.05)]:
 alt=copy.deepcopy(final)
 for row in alt['scenarios']:
  if row['id']=='scheduled':row['weight']+=shift
  if row['id']=='long_delay':row['weight']-=shift
 weight_stresses.append(dict(name=label,transfer='long_delay to scheduled',signed_weight=shift,probability=timeline.analyze(alt)['probability']))
# Preserve correlation when shifting both real release and announced-date paths.
shifted=copy.deepcopy(final)
for row in shifted['scenarios']:
 if row['id']=='scheduled':
  for a in row['assessments']:
   if a['parameter_id']=='launch_slot':a['value']='2026-12-03T12:00:00-05:00'
   if a['parameter_id']=='announcement_trigger':a['value']='never'
sens['declared_weight_stresses']=weight_stresses
sens['correlated_delay_stress']={'description':'Scheduled branch suffers announced two-week slip: release moves to December 3 and old announced-date route is invalidated. Delaying release alone would incorrectly leave alternate YES active.','probability':timeline.analyze(shifted)['probability']}
sens['interpretation']='Scenario-substitution outputs may violate branch definitions and are mechanical stresses, not coherent new forecasts. Weight stresses are not a confidence interval.'
dump('sensitivity.json',sens)
# Independent arithmetic: datetime and Decimal; no call to timeline schedule implementation.
from decimal import Decimal
D=datetime.datetime.fromisoformat;asof=D(cut);deadline=D(final['deadline']);rows=[];total=Decimal('0')
for row in final['scenarios']:
 v={a['parameter_id']:a['value'] for a in row['assessments']}
 real=None if any(v[x]=='never' for x in ['content_ready','platform_ready','launch_slot']) else max(asof+datetime.timedelta(days=v['content_ready']),asof+datetime.timedelta(days=v['platform_ready']),D(v['launch_slot']))
 clause=None if v['announcement_trigger']=='never' else D(v['announcement_trigger'])
 target=min([x for x in (real,clause) if x is not None],default=None);yes=target is not None and target<deadline
 if yes:total+=Decimal(str(row['weight']))
 expected=next(x for x in analysis['scenarios'] if x['scenario_id']==row['id'])
 assert yes==expected['meets_deadline'] and (target is None or target==D(expected['launch_at']))
 rows.append(dict(scenario_id=row['id'],full_release_at=real.isoformat() if real else None,announcement_trigger_at=clause.isoformat() if clause else None,target_at=target.isoformat() if target else None,success=yes,weight=row['weight']))
assert float(total)==analysis['probability']
assert sum(Decimal(str(x['weight'])) for x in final['scenarios'])==Decimal('1')
dump('independent_verification.json',dict(ok=True,method='Independent datetime max/min and Decimal sum, not timeline internals',rows=rows,weighted_success_sum=str(total),deadline_utc=deadline.astimezone(datetime.timezone.utc).isoformat(),nov19_to_deadline_elapsed_days=(deadline-D('2026-11-19T00:00:00-05:00')).total_seconds()/86400,days_from_cutoff_to_deadline=(deadline-asof).total_seconds()/86400))
dump('doctor.json',w.doctor())
summary=f'''# GTA VI deadline forecast\n\n**YES: {analysis['probability']:.1%}.** Prospective; information cutoff {cut} (September 15 US Eastern).\n\n## Frozen event\n\n{q['text']}\n\n{q['yes']}\n\nDeadline is exclusive December 1, 2026 at 00:00 US Eastern, covering all November 30. No trading. Void/disputed settlement remains separate from a binary forecast.\n\n## Current status and drivers\n\nRockstar still advertises November 19 on PS5 and Xbox Series X|S, with preorders and an August 27 preview. Its August support page specifies November 12 preload and digital codes in boxed copies. Take-Two reaffirmed the date August 7; Xbox US repeats it. These related announcements support the dominant on-time case but do not establish completed internal production or certification. The old May 26 date was explicitly postponed in November 2025, so passing it did not already satisfy the contract. No verified full release or already-triggered alternate clause was found.\n\n## Joint scenario partition\n\n| Scenario | Weight | Representative contract trigger | YES |\n|---|---:|---|---|\n'''
for row in analysis['scenarios']:summary+=f"| {row['scenario_id']} | {row['weight']:.1%} | {row['launch_at'] or 'never'} | {row['meets_deadline']} |\n"
summary+='''\nWeights are subjective, not empirical frequency estimates. Early release belongs to scheduled; a release on only one qualifying US platform is sufficient. Otherwise branch by the alternate clause, then eventual later release versus terminal nonrelease. Dates within broad branches are representative.\n\n## Milestones and sensitivity\n\nContent and first-platform readiness proceed in parallel from cutoff and join the commercial launch slot. The earliest of full release and the separate announced-date clause controls the contract. Durations are remaining elapsed days, not total historical development time. No internal milestone is falsely marked completed.\n\nTransferring ten percentage points from on-time to late yields 81%; transferring five back yields 96%. These are subjective stress tests, not a confidence interval. A two-week announced slip would cross the deadline and must disable the stale-date shortcut as well as move launch. Full parameter substitutions and a correlated-delay stress are in sensitivity.json.\n\n## Limitations and review triggers\n\nThis is a small paper pilot, with no fitted delay reference class or internal build access. Prior delay notices demonstrate feasibility of another postponement but do not calibrate its frequency. Marketing milestones and source agreement are not independent gates. Future dates are estimates or assumptions, not observed facts. Exact US release hour is a harmless noon convention here; real resolution uses actual US calendar date. Two Newswire opens returned empty extracted bodies. Costs and model calls are unmetered; zero workflow counters are not zero cost.\n\nReview on October 1 or after a date change, verified gold/certification milestone, preload opening/postponement, or first full qualifying US release. Check any indication of delay when an announced date passes.\n\n## Exposure\n\nNo prediction-market page or price was sought or seen, and no numeric external event probability was seen. Unrequested search snippets included a categorical Spanish claim against another delay, a Reddit supposed-release claim, and a Take-Two equity quote; all are logged and excluded from evidence weighting. Training-memory exposure cannot be ruled out.\n\n## Sources\n\n'''
for r in packet['records']:source=r['sources'][0];summary+=f"- [{source['title']}]({source['url']}) — retrieved {source['retrieved_at']}.\n"
summary+=f'\nForecast ID: `{fid}`. Doctor and independent calendar/weight checks passed. History is preserved in project/.vorhersage. Run build.py with fresh --project and --out paths to reproduce from frozen inputs.\n'
(out/'forecast_summary.md').write_text(summary)
# Checkpoint SQLite before hashing; no further writes after the seal.
with sqlite3.connect(w.store.path) as c: c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
files=[x for x in out.iterdir() if x.is_file() and x.name!='sealed_result.json']+[ROOT/x for x in ['question.json','contract.json','contract_terms.txt','input_manifest.json']]+[w.store.path]
hashes={str(x.relative_to(ROOT)) if x.is_relative_to(ROOT) else str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(files)}
seal=dict(schema_version='blind_forecast_seal.v1',sealed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),information_as_of=cut,probability=analysis['probability'],forecast_id=fid,status='prospective',exposure_declaration=read('source_query_log.json')['exposure_declaration'],sha256=hashes)
dump('sealed_result.json',seal)
print(json.dumps({'sealed_result':str(out/'sealed_result.json'),'forecast_id':fid,'probability':analysis['probability'],'doctor':w.doctor()},indent=2))
