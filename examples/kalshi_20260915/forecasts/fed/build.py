#!/usr/bin/env python3
"""Rebuild arithmetic; --issue creates the single original workflow only if no database exists.
No network. Frozen observations are researcher paraphrases, not archived full pages.
"""
import argparse,copy,datetime,hashlib,json,math,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from vorhersage import timeline,timeline_reports
from vorhersage.workflow import Workflow
from vorhersage.store import Store
from vorhersage.evidence import validate_packet
NOW=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
CUTOFF='2026-09-16T01:20:26+00:00'
OUT=ROOT/'outputs';OUT.mkdir(exist_ok=True)
def dump(name,value): (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def read(name): return json.loads((ROOT/name).read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
SOURCES=[
('history','https://www.federalreserve.gov/monetarypolicy/openmarket.htm','Official target rate change history','2026-09-16T01:19:13+00:00',None,'Latest listed change is the December 2025 reduction to 3.50–3.75%; the page has no 2026 change and is marked updated December 12, 2025.','Absence alone is not proof of no 2026 change; the page is dated before the window.'),
('calendar','https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm','FOMC meeting calendar','2026-09-16T01:19:13+00:00',None,'2026 scheduled decision dates are January 28, March 18, April 29, June 17, July 29, September 16, October 28 and December 9. Links are available through July; September has no statement yet.','Schedule dates do not guarantee policy outcomes; unscheduled decisions are possible.'),
('jan','https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm','January 28 FOMC statement','2026-09-16T01:19:13+00:00','2026-01-28T14:00:00-05:00','January decision maintained the target range at 3.50–3.75%. Two members preferred a quarter-point cut.','Outside contract window; establishes pre-window baseline only.'),
('mar','https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318a.htm','March 18 FOMC statement','2026-09-16T01:19:13+00:00','2026-03-18T14:00:00-04:00','March decision maintained the 3.50–3.75% target range. One member preferred a quarter-point cut.','A dissent favoring a cut is not an actual qualifying reduction.'),
('apr','https://www.federalreserve.gov/newsevents/pressreleases/monetary20260429a.htm','April 29 FOMC statement','2026-09-16T01:19:13+00:00','2026-04-29T14:00:00-04:00','April decision maintained 3.50–3.75%. One dissenter favored a cut; three supported holding but objected to the easing bias.','Dissents do not alter the announced target range.'),
('jun','https://www.federalreserve.gov/newsevents/pressreleases/monetary20260617a.htm','June 17 FOMC statement','2026-09-16T01:19:13+00:00','2026-06-17T14:00:00-04:00','June decision unanimously maintained 3.50–3.75%. The statement described solid activity, stable unemployment and elevated inflation partly due to supply shocks.','Official assessment, not a calibrated policy-response model.'),
('jul','https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm','July 29 FOMC statement','2026-09-16T01:19:13+00:00','2026-07-29T14:00:00-04:00','July decision maintained 3.50–3.75%. Three dissenters preferred a quarter-point increase. The majority continued to characterize inflation as elevated and activity as solid.','Hike preferences are contrary evidence to easing but are not a commitment.'),
('jobs','https://www.bls.gov/news.release/empsit.nr0.htm','August 2026 Employment Situation','2026-09-16T01:19:19+00:00','2026-09-04T08:30:00-04:00','August payrolls rose 162,000; unemployment held at 4.1%. Prior-year average monthly hiring was 31,000. Revised June and July gains were 31,000 and 21,000. Annual wage growth was 3.1%.','Survey estimates are revisable. Strong August contrasts with weak recent hiring; neither alone establishes recession risk.'),
('cpi','https://www.bls.gov/news.release/cpi.nr0.htm','August 2026 CPI','2026-09-16T01:19:28+00:00','2026-09-11T08:30:00-04:00','August headline CPI rose 0.4% monthly and 3.4% annually; core rose 0.3% monthly and 2.4% annually. Annual core eased from 2.5%; energy rose 16.3% annually.','CPI differs from the Fed preferred PCE index. Falling annual core coexists with a firmer monthly reading.'),
('pce','https://www.bea.gov/news/2026/personal-income-and-outlays-july-2026','July 2026 Personal Income and Outlays','2026-09-16T01:19:28+00:00','2026-08-26T08:30:00-04:00','July PCE prices rose 0.2% monthly and 3.7% annually. Core rose 0.2% monthly and 3.3% annually. Real consumption rose less than 0.1% monthly.','July lags August CPI; core PCE and core CPI use different coverage and weights, so their different rates are not necessarily a contradiction.'),
('archive','https://www.federalreserve.gov/newsevents/pressreleases/2026-press.htm','2026 Federal Reserve press-release index','2026-09-16T01:19:54+00:00',None,'Index shows releases through September 11 and no additional rate-cut announcement after July. August monetary releases concern July minutes and discount-rate minutes.','Index omits some known scheduled statement entries; not independently exhaustive. Used with calendar, actual statements and change history.'),
('mpr','https://www.federalreserve.gov/monetarypolicy/2026-07-mpr-summary.htm','July 2026 Monetary Policy Report summary','2026-09-16T01:20:26+00:00','2026-07-10T12:00:00+00:00','The report says the FOMC maintained 3.50–3.75% since the beginning of the year. It describes broadly stable labor markets and elevated inflation.','Publication time is date-only normalized to noon UTC; no exact release time inferred. Confirms elapsed period through July 10 only.'),
('warsh','https://www.federalreserve.gov/newsevents/speech/warsh20260828a.htm','Chairman Warsh Jackson Hole remarks','2026-09-16T01:20:26+00:00','2026-08-28T10:00:00-04:00','Warsh viewed employment as consistent with full employment and said prices should be the predominant policy focus. Better summer inflation readings had not convinced him the underlying trend had improved. He avoided committing to a decision.','Chair opinion is influential but not the full committee vote. Policy focus can change after shocks.'),
]
LIMITS=['Weights and future dates are subjective assumptions, not estimates calibrated from a historical sample.','Small paper pilot; no trading, exhaustive macro review or claim of accuracy from procedural compliance.','No affirmative evidence of an elapsed qualifying cut was found; negative archive evidence has indexing limits.','Future first-cut dates are scenario representatives. Emergency date represents any first unscheduled qualifying cut before expiry; never means no qualifying cut in this contract window, not no cut forever.','Target-range reductions count even if preceded by a hike; unrelated administered-rate changes and mere votes for a cut do not.','External model calls and costs are unmetered; workflow numeric zeros are placeholders.']
EXPOSURE={'market_prices_sought':False,'market_prices_seen':False,'event_probabilities_sought':False,'event_probabilities_seen':False,'incidental_exposure':[{'source':'warsh','description':'Official remarks mentioned market measures of inflation expectations and swaps qualitatively; no rate-cut probabilities or numeric market prices were provided in inspected text. Not used as a probability input.'}],'search_snippets':'Two official-domain searches returned Fed statements, historical 2024/2025 dissents, discount-rate minutes, an August calendar and July report. No prediction-market prices, FedWatch or other forecasters event probabilities were observed.','isolation':'Only supplied workspace inputs, generic package code and public primary sources were used; no sibling forecasts or parent repository inspected. Training knowledge is not erased.'}
REGIMES={'persistent':.58,'disinflation':.25,'labor_downturn':.12,'acute_shock':.05}
ROWS=[
('persistent_none','persistent',1.,'never','Inflation and resilient employment prevent any qualifying cut. Hikes or holds are allowed.'),
('disinflation_sep','disinflation',.04,'2026-09-16T14:00:00-04:00','Unexpectedly fast reassessment permits a September first cut.'),
('disinflation_oct','disinflation',.16,'2026-10-28T14:00:00-04:00','Additional disinflation produces an October first cut.'),
('disinflation_dec','disinflation',.28,'2026-12-09T14:00:00-05:00','Disinflation accumulates slowly enough for a December first cut.'),
('disinflation_none','disinflation',.52,'never','Disinflation occurs but Fed waits into 2027.'),
('labor_oct','labor_downturn',1/12,'2026-10-28T14:00:00-04:00','Abrupt labor weakening generates an October first cut.'),
('labor_dec','labor_downturn',5/12,'2026-12-09T14:00:00-05:00','Labor weakening generates a December first cut.'),
('labor_none','labor_downturn',.5,'never','Labor weakening arrives too late or inflation prevents easing in 2026.'),
('shock_cut','acute_shock',.6,'2026-11-15T12:00:00-05:00','Severe financial or demand disruption generates a first unscheduled cut; representative date only.'),
('shock_none','acute_shock',.4,'never','Severe disruption is met by liquidity tools, inflation caution or arrives too late; no target-range cut.')]
PARTITION='Conditional on the elapsed audit finding no prior cut, every path is assigned once: acute disruption requiring crisis consideration takes priority; otherwise material labor deterioration; otherwise material disinflation; otherwise persistence. Within each regime, first qualifying cut is at the represented scheduled decision, unscheduled before expiry, or none. Regime labels define dominant economic mechanisms, not independent events. The zero-weight already-occurred branch in the preliminary research plan is eliminated by the eligibility audit; later dates are refined into October and December. Minor date variation within success branches does not change this binary event.'
def packet():
 records=[]
 for i,url,title,t,pub,claim,limit in SOURCES:
  src={'id':i,'url':url,'title':title,'excerpt':claim,'excerpt_kind':'paraphrase','retrieved_at':t,'published_at':pub,'capture':{'method':'manual','captured_at':t,'metadata':{'tool':'web.run','capture_scope':'Short researcher paraphrase after inspecting returned source text; no complete page body retained.','timestamp_semantics':'Actual post-retrieval clock checkpoint; for batched reads an upper bound on page retrieval, not a claimed HTTP timestamp.','limit':limit}}}
  records.append({'id':i,'claim':claim,'value':{'limit':limit},'entity_ids':['Federal_Reserve' if i not in ('jobs','cpi','pce') else i],'observed_at':t,'sources':[src],'provenance':{'method':'manual_primary_source_research','limitations':[limit]},'claim_type':'official_statement' if i not in ('jobs','cpi','pce') else 'observation'})
 return validate_packet({'schema_version':'vorhersage.evidence.v1','kind':'manual','information_as_of':CUTOFF,'created_at':NOW(),'records':records,'limitations':LIMITS})
def verify(model,analysis):
 start=datetime.datetime.fromisoformat('2026-02-26T00:00:00-05:00');end=datetime.datetime.fromisoformat('2027-01-01T00:00:00-05:00'); cutoff=datetime.datetime.fromisoformat(CUTOFF)
 success=[]
 for s in model['scenarios']:
  value=s['assessments'][0]['value']; ok=value!='never' and start<=datetime.datetime.fromisoformat(value)<end
  if value!='never': assert datetime.datetime.fromisoformat(value)>cutoff
  if ok:success.append(s['weight'])
 assert math.isclose(math.fsum(s['weight'] for s in model['scenarios']),1,abs_tol=1e-12)
 assert math.isclose(math.fsum(success),analysis['probability'],abs_tol=1e-12)
 return {'ok':True,'independent_sum':math.fsum(success),'weights_sum':math.fsum(s['weight'] for s in model['scenarios']),'window_start':start.isoformat(),'window_end_exclusive':end.isoformat(),'deadline_utc':end.astimezone(datetime.timezone.utc).isoformat(),'cutoff_before_september_decision':cutoff<datetime.datetime.fromisoformat('2026-09-16T14:00:00-04:00'),'elapsed_audit_dates':['2026-03-18','2026-04-29','2026-06-17','2026-07-29'],'already_known':False,'no_extra_cut_found':True}
def sensitivity(model):
 cases=[]
 for name,w in [('baseline',REGIMES),('more_persistence',{'persistent':.75,'disinflation':.15,'labor_downturn':.07,'acute_shock':.03}),('more_easing_and_shocks',{'persistent':.35,'disinflation':.35,'labor_downturn':.20,'acute_shock':.10})]:
  m=copy.deepcopy(model)
  for s,row in zip(m['scenarios'],ROWS):s['weight']=w[row[1]]*row[2]
  cases.append({'name':name,'regime_weights':w,'probability':timeline.analyze(m)['probability']})
 return {'subjective_regime_weight_stress':cases,'conditional_response_stress':[{'case':'Inflation caution halves within-regime easing responses; move removed mass to each regime none branch.','probability':.105},{'case':'Disinflation response 0.70, labor response 0.75, acute response 0.80; regime weights unchanged.','probability':.25*.7+.12*.75+.05*.8}],'date_stress':{'shift_december_success_to_january_probability':.09,'explanation':'December disinflation and labor branches jointly move beyond the deadline; all other weights unchanged.'},'package_input_swaps':timeline.sensitivity(model),'warning':'Declared subjective stress tests, not a confidence interval, calibration or value-of-information estimate.'}
def issue():
 if (ROOT/'project/.vorhersage/state.sqlite').exists(): raise SystemExit('Refusing to issue again or overwrite history. Run without --issue to verify sealed arithmetic.')
 evidence=packet();dump('evidence.json',evidence)
 w=Workflow(ROOT/'project');w.store.init('Blind Fed paper pilot');w.question(read('question.json'));pid=w.import_packet(evidence)['packet_id']
 refs=[{'packet_id':pid,'record_id':r['id']} for r in evidence['records']]
 original=read('structure_before_research.json');original_id=timeline.add(w.store,original)['timeline_model_id']
 structure=copy.deepcopy(original);structure.update(id='fed_refined_structure',information_as_of=CUTOFF,derived_from_model_id=original_id,scenarios=[],limitations=LIMITS)
 structure['nodes'][0]['evidence_refs']=refs
 for sid,reg,cond,date,desc in ROWS:
  structure['scenarios'].append({'id':sid,'description':desc,'assessments':[{'parameter_id':'first_cut_date','basis':'unresolved','rationale':'Await parameter research submission; regime weights not yet supplied.','evidence_refs':[]}],'evidence_refs':refs})
 sid=timeline.add(w.store,structure)['timeline_model_id']
 run=w.start({'question_id':'kalshi_fed_20260915','forecaster':'kalshi_blind_20260915','method':'Independent first-cut timeline with economic regime mixture','mode':'prospective','information_as_of':CUTOFF,'workflow':'timeline','cutoff_policy':'fixed','research_status':'completed','max_searches':20,'max_extra_tasks':0})['run_id']
 def submit(payload):
  n=w.next(run);return w.submit(run,{'task_id':n['task']['id'],'expected_revision':n['revision'],'idempotency_key':'fed_'+n['task']['id'],'payload':payload,'usage':{'searches':0,'cost_usd':0,'model_calls':0}})
 submit({'timeline_model_id':sid,'rationale':'Pre-browsing original preserved. After elapsed audit, refine prospective branches by economic regime and scheduled date; no starting probability. Costs/calls unmetered, numeric zeros placeholders.'})
 assessments=[]
 for sid,reg,cond,date,desc in ROWS:
  assessments.append({'scenario_id':sid,'assessment':{'parameter_id':'first_cut_date','basis':'assumed','value':date,'rationale':desc+' Calendar dates are observed; occurrence, timing within a regime and never are subjective. Emergency date is only a binary-outcome representative.','evidence_refs':refs}})
 submit({'assessments':assessments,'rationale':'No qualifying elapsed cut was found in actual statements or supplementary official indexes; all future event assignments are assumptions. Regime weights assessed separately.'})
 n=w.next(run);current=n['task']['timeline_context']['timeline_model_id'];model=copy.deepcopy(n['task']['timeline_context']['model'])
 model.update(version=model['version']+1,previous_model_id=current,partition_justification=PARTITION)
 rationales={'persistent':'Largest regime given current price focus, hike dissenters, core PCE above target and stable unemployment.','disinflation':'Meaningful minority because annual core CPI eased, recent core PCE monthly readings were moderate and energy can reverse; chair remains unconvinced.','labor_downturn':'Minority downside despite strong August because June/July hiring was weak and real July consumption flat.','acute_shock':'Small tail for geopolitical or financial disruption; many shocks produce inflation or liquidity action rather than rate cuts.'}
 for s,row in zip(model['scenarios'],ROWS):
  s.update(weight=REGIMES[row[1]]*row[2],weight_rationale=f"Assumed regime weight {REGIMES[row[1]]} times assumed conditional branch weight {row[2]}. "+rationales[row[1]]+' Conditional responses are judgmental, not historical frequencies.')
 mid=timeline.add(w.store,model)['timeline_model_id']
 submit({'method':'timeline_model','timeline_model_id':mid,'rationale':'Sum disjoint first-cut paths after elapsed eligibility audit. Strong current inflation emphasis makes no-cut path dominant, but improving inflation and weak prior hiring leave easing paths. All weight inputs are explicitly subjective.','limitations':LIMITS,'evidence_refs':refs})
 review={'decision':'retain','rationale':'Retain after challenges in both directions; no claim of calibration. Economic-regime sensitivity is the main uncertainty.','objections':[{'direction':'too_high','objection':'July hike dissents, above-target PCE and chairman inflation focus may mean virtually no cuts this year.','response':'Persistence dominates; September easing is a small branch. A more-persistent stress case tests this objection.'},{'direction':'too_low','objection':'Falling annual core CPI and weak prior hiring could cause policy to pivot quickly; a hike followed by a reversal also qualifies.','response':'Disinflation, labor and acute-shock branches preserve these routes. A higher-easing stress case tests larger regime weights. No cut branch permits hikes only if no later reduction occurs.'}],'evidence_refs':refs}
 submit(review);dump('review.json',review)
 result=submit({'stopping_reason':'Focused primary-source pilot complete; numerical workflow usage zeros are placeholders for unmetered external costs and model calls. Source query log records tool activity. No market probability inputs.','review_at':'2026-09-16T18:15:00+00:00','triggers':[{'description':'September FOMC decision or any unscheduled announcement changes eligibility immediately.','at':'2026-09-16T18:00:00+00:00','evidence_refs':refs},{'description':'New payrolls, PCE/CPI, material labor deterioration or financial shock changes regime weights.','evidence_refs':refs}]})
 fid=result['forecast_id']
 with w.store.connect() as c: forecast=Store.artifact(c,fid,'forecast')
 dump('model.json',model);analysis=timeline.analyze(model);dump('analysis.json',analysis);dump('sensitivity.json',sensitivity(model));dump('forecast.json',{'forecast_id':fid,**forecast});dump('verification.json',verify(model,analysis));dump('doctor.json',w.doctor())
 timeline_reports.export(w.store,mid,OUT/'forecast.html',forecast=forecast)
 dump('eligibility.json',{'status':'eligible','already_known':False,'information_as_of':CUTOFF,'evidence_refs':refs,'elapsed_window_audit':'January baseline and March/April/June/July holds inspected. July report confirms unchanged since beginning of year; calendar, target history and press index reveal no unscheduled cut. Index limitations are disclosed. No qualifying cut found by cutoff.','frozen_start':'2026-02-26','target_range_semantics':'FOMC announced reduction of target federal funds range, including reversal after a hike; discount-rate changes excluded.'})
 return fid

def main():
 args=argparse.ArgumentParser();args.add_argument('--issue',action='store_true');a=args.parse_args()
 if a.issue: fid=issue();print('Original workflow issued; seal is created separately after final artifact review.')
 else:
  model=json.loads((OUT/'model.json').read_text());analysis=timeline.analyze(model);v=verify(model,analysis);assert analysis==json.loads((OUT/'analysis.json').read_text());assert Workflow(ROOT/'project').doctor()['ok'];print('Reproduced weighted sum, dates, stored analysis and doctor without writing or reissuing.')
if __name__=='__main__': main()
