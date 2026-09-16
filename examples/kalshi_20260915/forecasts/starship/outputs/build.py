#!/usr/bin/env python3
"""Reproduce arithmetic offline. First run initializes/ issues exactly one forecast.
After a forecast exists, this script only verifies saved arithmetic and hashes.
Run: PYTHONPATH=../src python3 build.py (working directory immaterial).
"""
import copy, json, math, sys, hashlib
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
sys.path.insert(0,str(ROOT/'src'))
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from vorhersage import timeline,timeline_reports
from vorhersage.evidence import validate_packet

def load(n):return json.loads((OUT/n).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def iso(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def independent(model):
    cutoff=iso(model['information_as_of']); deadline=iso(model['deadline'])
    rows=[]
    for sc in model['scenarios']:
        vals={v['parameter_id']:v['value'] for v in sc['assessments']}
        ready=cutoff+timedelta(days=vals['vehicle_ready'])
        permit=iso(vals['permission_ready'])
        launch=max(cutoff,ready,permit)+timedelta(days=vals['launch_delay'])
        rows.append({'scenario_id':sc['id'],'vehicle_ready_at':ready.isoformat(),'permission_ready_at':permit.isoformat(),'launch_at':launch.isoformat(),'launch_site_local':launch.astimezone(ZoneInfo('America/Chicago')).isoformat(),'after_issuance':launch>iso('2026-07-30T22:26:00Z'),'success':launch<deadline,'weight':sc['weight']})
    p=math.fsum(r['weight'] for r in rows if r['success'] and r['after_issuance'])
    assert deadline.astimezone(timezone.utc).isoformat()=='2026-10-01T05:00:00+00:00'
    return {'probability':p,'weight_sum':math.fsum(r['weight'] for r in rows),'deadline_utc':deadline.astimezone(timezone.utc).isoformat(),'strict_boundary_check':not(deadline<deadline),'rows':rows,'method':'Independent stdlib datetime max-plus arithmetic, not timeline._schedule.'}

store=Store(ROOT/'project'); w=Workflow(ROOT/'project')
if (OUT/'forecast.json').exists():
    model=load('model.json'); expected=load('analysis.json'); actual=timeline.analyze(model); check=independent(model)
    assert actual==expected
    assert check['probability']==actual['probability']
    assert all(iso(r['launch_at'])==iso(a['launch_at']) for r,a in zip(check['rows'],actual['scenarios']))
    doctor=w.doctor(); assert doctor['ok']
    if (OUT/'sealed_result.json').exists():
        for file,sha in load('sealed_result.json')['sha256'].items():
            assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==sha,file
    print(json.dumps({'verified':True,'probability':actual['probability'],'doctor':doctor}))
    sys.exit()

assert not store.path.exists(),'Existing partial project: inspect history rather than overwrite.'
store.init('Independent blinded Starship Flight 14 pilot')
question=json.loads((ROOT/'question.json').read_text()); w.question(question)
packet=validate_packet(load('evidence.json')); save('evidence.json',packet)
packet_id=w.import_packet(packet)['packet_id']
refs=[{'packet_id':packet_id,'record_id':r['id']} for r in packet['records']]
ref={r['record_id']:r for r in refs}
cutoff=packet['information_as_of']; limits=packet['limitations']
pre=load('structure_before_research.json')
pre_id=timeline.add(store,pre)['timeline_model_id']
structure=copy.deepcopy(pre)
structure.update(version=2,previous_model_id=pre_id,information_as_of=cutoff,limitations=limits,description='Post-research structure: same parallel vehicle and regulatory readiness dependencies. Flight 14 verified upcoming in current official operator content. All durations are remaining work from cutoff.')
structure['nodes'][0]['evidence_refs']=[ref['operator']]
structure['nodes'][1]['evidence_refs']=[ref['operator'],ref['faa_plan'],ref['environment']]
structure['nodes'][2]['evidence_refs']=[ref['operator']]
structure['scenarios'][0]['description']='Rapid campaign: qualifying Flight 14 by September 23 local, represented by September 22.'
structure['scenarios'][1]['description']='Moderate delay: no qualifying launch by September 23, then launch September 24–30 local, represented by September 28.'
structure['scenarios'][2]['description']='Long delay: no qualifying launch by September 30, then launch during October, represented by October 7.'
structure['scenarios'][3]['description']='Severe interruption: no qualifying launch by October 31, represented by November campaign recovery; includes cancellation mass conservatively for this deadline.'
structure_id=timeline.add(store,structure)['timeline_model_id']
save('structure_at_cutoff.json',structure)
run=w.start({'question_id':question['id'],'forecaster':'kalshi_blind_20260915','method':'independent_joint_timeline','mode':'prospective','information_as_of':cutoff,'max_searches':10,'max_extra_tasks':0,'workflow':'timeline','cutoff_policy':'fixed','research_status':'completed'})['run_id']
def submit(payload,searches=0):
    n=w.next(run)
    return w.submit(run,{'task_id':n['task']['id'],'expected_revision':n['revision'],'idempotency_key':n['task']['id']+'-submit','payload':payload,'usage':{'searches':searches,'cost_usd':0,'model_calls':0}})
submit({'timeline_model_id':structure_id,'rationale':'Structure saved before browsing with unresolved inputs and no weights. Research verifies upcoming Flight 14 from Starbase; retain dependencies and replace stale cutoff with actual research completion.'},7)
values={'rapid':(5,'2026-09-21T12:15:00Z',1),'moderate':(10,'2026-09-26T12:15:00Z',2),'late':(18,'2026-10-05T12:15:00Z',2),'no_launch':(60,'2026-10-05T12:15:00Z',3)}
rationales={
'vehicle_ready':'Evidence-informed remaining-work estimate, not an observed completion date. Operator target and specified modifications support a near-ready case; 10/18/60-day alternatives explicitly cover discovered hardware work. Official static-fire posts were not verified, so engine-test completion is not assumed as fact.',
'permission_ready':'Estimated clearance and usable range date. Operator says regulatory approval remains pending, whereas FAA plans September 22 with backup. Neither environmental assessment nor advisory is a final license. Later cases represent review or range delays.',
'launch_delay':'Assumed elapsed countdown/retry duration after both prerequisites. No local weather or empirical scrub-frequency calibration obtained; 1/2/3-day points are coarse and stress-tested.'}
for idx,pid in enumerate(['vehicle_ready','permission_ready','launch_delay']):
    assessments=[]
    for sid,vals in values.items():
        assessments.append({'scenario_id':sid,'assessment':{'parameter_id':pid,'basis':'assumed' if pid=='launch_delay' else 'estimated','value':vals[idx],'rationale':rationales[pid],'evidence_refs':[] if pid=='launch_delay' else [ref['operator'],ref['faa_plan'],ref['faa_prior']]}})
    submit({'assessments':assessments,'rationale':rationales[pid]})
n=w.next(run); current_id=n['task']['timeline_context']['timeline_model_id']; model=copy.deepcopy(n['task']['timeline_context']['model'])
model.update(version=model['version']+1,previous_model_id=current_id,partition_justification='Four mutually exclusive and exhaustive launch-date bins: by September 23; September 24–30; October; after October or never. Each is represented by one joint assignment of remaining hardware, regulatory/range date, and post-readiness delay. Finite discretization is explicit; weights are subjective distribution masses, not inferred by the engine. Binning near the deadline makes weighting partly a direct deadline judgment and must not be mistaken for empirical calibration.')
weights={'rapid':.55,'moderate':.25,'late':.15,'no_launch':.05}
wr={'rapid':'Largest mass: current operator target is six days away, FAA has matching target and backup, and official mission describes specific next-flight fixes. Still reserve substantial slip risk because approval remains pending.', 'moderate':'Meaningful mass for several days of clearance, hardware or scrub delay beyond September 23; remaining September calendar provides recovery opportunities. Not an observed frequency.', 'late':'Long delay receives material mass because first orbital profile approval is pending and schedule already moved four days in FAA planning; hardware and regulatory tails can compound.', 'no_launch':'Small but nonzero severe campaign interruption mass: unexpected hardware damage, sustained authorization difficulty, cancellation or much longer repair. No current evidence such a disruption has happened.'}
for sc in model['scenarios']:sc.update(weight=weights[sc['id']],weight_rationale=wr[sc['id']],evidence_refs=refs)
final_id=timeline.add(store,model)['timeline_model_id']; save('model.json',model)
analysis=timeline.analyze(model); save('analysis.json',analysis)
verification=independent(model)
assert math.isclose(verification['weight_sum'],1,abs_tol=1e-12)
assert verification['probability']==analysis['probability']
assert all(iso(r['launch_at'])==iso(a['launch_at']) for r,a in zip(verification['rows'],analysis['scenarios']))
save('independent_verification.json',verification)
# Arithmetic and scenario-weight sensitivity, no false confidence interval.
stress=[]
for field in ['vehicle_ready','launch_delay','permission_ready']:
    for days in [2,5,9]:
        m=copy.deepcopy(model)
        for sc in m['scenarios']:
            a=next(a for a in sc['assessments'] if a['parameter_id']==field)
            a['value']=(iso(a['value'])+timedelta(days=days)).isoformat() if field=='permission_ready' else a['value']+days
        stress.append({'change':f'Add {days} days to every {field} value','probability':timeline.analyze(m)['probability']})
for label,ws in [('skeptical',[.40,.20,.30,.10]),('optimistic',[.65,.25,.08,.02])]:
    m=copy.deepcopy(model)
    for sc,wt in zip(m['scenarios'],ws):sc['weight']=wt
    stress.append({'change':label+' subjective weights','weights':ws,'probability':timeline.analyze(m)['probability']})
save('sensitivity.json',{'engine':timeline.sensitivity(model),'additional_stress_tests':stress,'note':'Assumption stress tests only, not a confidence interval. Uniform shifts can move representative dates outside original bins; these deliberately test the coarse representative timing choice.'})
submit({'method':'timeline_model','timeline_model_id':final_id,'rationale':'Compute prerequisite completion and launch dates using the current researched workflow model with declared joint weights. Liftoff is the event; orbital success and landing success are irrelevant after qualifying ascent.','limitations':limits,'evidence_refs':refs})
review={'decision':'retain','rationale':'Retain as an independently judged pilot forecast, with explicit timing and weight fragility. No observed outcome yet: current official mission remains upcoming. Package validity is not a claim of accuracy.','objections':[{'direction':'too_high','objection':'Pending approval for orbital flight and hardware surprises could consume the remaining launch opportunities; date bins hide continuous tail risk.','response':'A substantial late/interruption mass and delay stress tests cover this concern, but no empirical calibration supports the exact allocation; skeptical weights are also reported.'},{'direction':'too_low','objection':'Operator target, FAA target and next-day backup may mean remaining clearance and hardware work is routine.','response':'Largest mass assigned near the target, with additional mass to a short delay; optimistic weights expose upside. Advisory alone cannot establish final license.'}],'evidence_refs':refs}
save('review.json',review); submit(review)
triggers=[{'description':d,'evidence_refs':refs} for d in ['Final Flight 14 authorization or a new regulatory restriction.','SpaceX publishes launch target changes, stacking/readiness progress, or hardware anomaly.','September 22–23 attempts scrub; reassess remaining calendar slack.','Qualifying Flight 14 liftoff occurs; mark outcome already known and stop prospective forecasting.','Launch site changes: recompute launch-site local deadline before updating.']]
issued=submit({'stopping_reason':'Bounded independent research completed; primary operator and FAA facts checked, missing inputs represented as estimates/assumptions, arithmetic independently verified and sensitivity exposed. Costs/model calls unmetered.','review_at':'2026-09-19T12:00:00Z','triggers':triggers})
with store.connect() as c:forecast={'id':issued['forecast_id'],**Store.artifact(c,issued['forecast_id'],'forecast')}
save('forecast.json',forecast); timeline_reports.export(store,final_id,OUT/'forecast.html',forecast=forecast)
save('doctor.json',w.doctor()); save('workflow_status.json',w.status())
rows='\n'.join(f"| {r['scenario_id']} | {r['weight']:.0%} | {r['launch_site_local']} | {'Yes' if r['success'] else 'No'} |" for r in verification['rows'])
summary=f'''# Starship Flight 14: independent paper forecast\n\n**Probability: {analysis['probability']:.0%}.** Eligible prospective forecast; event not already known.\n\nInformation cutoff: {cutoff}. Forecast issued: {forecast['issued_at']}.\n\nExactly flight test 14 must lift off with sustained ascent after July 30 issuance and strictly before **October 1, 2026, 00:00 America/Chicago** (05:00 UTC), assuming the verified Starbase, Texas site. A subsequent flight failure counts. Static fires and scrubs do not. Frozen trading close is earlier than the event boundary and was not substituted for it.\n\n## Joint scenarios\n\n| Scenario | Subjective weight | Representative launch, Texas time | Meets deadline |\n|---|---:|---|---|\n{rows}\n\nWeights sum to one. Success weights sum to {analysis['probability']:.2f}; dates computed by `timeline.py` and independently checked with Python calendar arithmetic. Readiness branches run in parallel; launch follows their maximum plus retry delay. In-progress work is modeled as remaining days from cutoff, not total historical duration. Scenario date bins are exclusive and exhaustive, but representative dates and weights are judgments rather than measured frequencies.\n\n## Evidence and drivers\n\n[Official SpaceX mission content](https://content.spacex.com/api/spacex-website/missions/starship-flight-14) says Flight 14 is preparing for September 22, with regulatory approval pending; the [public mission page](https://www.spacex.com/launches/starship-flight-14) serves a JavaScript shell. This establishes that the event remains upcoming. SpaceX describes hardware filtering and software changes following Flight 13 booster relight difficulties.\n\nThe [FAA operational advisory](https://www.fly.faa.gov/adv/adv_spt) matches September 22 at 12:15 UTC and September 23 backup at Starbase. Earlier September 13 FAA planning listed September 18: the target has already slipped. Planning is not licensing. The [FAA environmental page](https://www.faa.gov/space/stakeholder_engagement/spacex_starship) shows relevant environmental work complete, but this does not establish final flight authorization.\n\n## Uncertainty and review\n\nAll future completion dates and durations are estimates or assumptions. No independent complete hardware inventory, final launch license, local closures, or launch-day weather assessment was obtained. Static-fire reports found in search were not upgraded into primary-verified facts. The model's weights are subjective and partially equivalent to direct deadline judgment because bins straddle the deadline. This limits what the milestone formalism adds.\n\nAlternative declared weights give 60%–90%; this is a stress range, **not a confidence interval**. Adding five days to every post-readiness delay drops success to 55%; adding nine days drops it to 0%. Such shifts test sensitivity of representative dates, not literal revisions to unchanged bins. Full tests are in sensitivity.json.\n\nNo market prices or numerical outside event probabilities were observed. Search snippets incidentally exposed community timing opinions and an unverified historical timing aggregate, logged in exposure.json; neither calibrated the weights. Source access failures and contradictory interpretations are retained in source_query_log.json. Costs and model calls are unmetered; package zero counters do not mean zero cost.\n\nReview on September 19 or upon final authorization, hardware changes, schedule slips, scrubs, site change, or qualifying liftoff. No trading was performed. A clean doctor result confirms package integrity, not forecast accuracy.\n'''
(OUT/'forecast_summary.md').write_text(summary)
print(json.dumps({'issued':True,'forecast_id':forecast['id'],'doctor':w.doctor()}))
