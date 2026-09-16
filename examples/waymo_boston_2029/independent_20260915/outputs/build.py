#!/usr/bin/env python3
"""Rebuild the independent forecast from preserved inputs; no web calls.

Verify without another issuance: python3 outputs/build.py --verify-existing
Rebuild elsewhere: python3 outputs/build.py --destination /private/tmp/a-new-empty-directory
Default writes the initial project and artifacts in this clean workspace.
Research costs were unmetered. Engine cost_usd=0 is an unpopulated counter,
not a claim of free research. See usage.json and the report notice.
"""
import argparse, copy, datetime as dt, hashlib, html, json, math, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from vorhersage import timeline, timeline_reports
from vorhersage.evidence import validate_packet
from vorhersage.store import Store
from vorhersage.workflow import Workflow

def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')

def iso(x):
    return dt.datetime.strptime(x, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=dt.timezone.utc).isoformat()

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--destination', type=pathlib.Path, default=ROOT)
    parser.add_argument('--verify-existing', action='store_true', help='Recompute frozen analysis and validate existing history without issuing another forecast.')
    args=parser.parse_args(); dest=args.destination.resolve(); out=dest/'outputs'; project=dest/'project'
    if args.verify_existing:
        frozen=json.loads((out/'model.json').read_text())
        assert timeline.analyze(frozen)==json.loads((out/'analysis.json').read_text())
        validate_packet(json.loads((out/'evidence.json').read_text()))
        result=Workflow(project).doctor(); assert result['ok']
        print(json.dumps({'frozen_analysis_reproduced':True,'doctor':result})); return
    if (project/'.vorhersage/state.sqlite').exists():
        raise SystemExit('Existing project preserved. Use --verify-existing or a new empty --destination to rebuild.')
    out.mkdir(parents=True,exist_ok=True); project.mkdir(parents=True,exist_ok=True)
    logs=json.loads((ROOT/'outputs/source_query_log.json').read_text())
    cutoff=iso(logs['research_completed_at']); question=json.loads((ROOT/'question.json').read_text())
    # Short paraphrases only. All capture dates are actual web-call completion times.
    # discovery records preserve search extracts; manual records were opened via web.
    data=[
      ('boston_return',0,'https://waymo.com/blog/shorts/back-to-boston/','Waymo returns to Boston','2026-02-05',
       'Waymo says it returned to Boston to build on its prior road trip, adapt to local streets, and prepare future service. It explicitly says Massachusetts must legalize fully autonomous vehicles before autonomous passenger rides.',
       'Company statement verifies intent and activity, not technical readiness or an opening date. Winter capability claims are not an independent performance audit.','official_statement','discovery'),
      ('upcoming',2,'https://waymo.com/rides/','Waymo service locations',None,
       'The service page places Boston under Up Next rather than Serving Riders In.',
       'Dynamic page; broad marketing language elsewhere on the page does not establish paid public Boston service. No qualifying Boston launch was verified.','official_statement','manual'),
      ('state_testing',6,'https://www.mass.gov/info-details/general-requirements-safe-testing-of-automated-driving-systems','MassDOT general testing requirements',None,
       'MassDOT testing guidance requires an in-vehicle trained test driver able to take immediate control; testing conditions and road owners also require approval.',
       'Direct page access returned an internal error; the detailed search extract supplied this text. Testing guidance is not a comprehensive legal opinion on commercial service.','official_statement','discovery'),
      ('house_bill',3,'https://malegislature.gov/Bills/194/H3634','H.3634 official bill history',None,
       'The House enabling bill history records referral to a study order, H5326, on April 6, 2026.',
       'A study order is not enabling enactment. This history alone does not prove that every alternative legislative route is unavailable.','official_statement','manual'),
      ('senate_bill',6,'https://malegislature.gov/Bills/194/S2379/BillHistory','S.2379 official bill history',None,
       'The current Senate bill history records referral to study order S3245 on July 31, 2026, after earlier reporting extensions.',
       'Earlier search extracts stopped at the April extension; the later opened history supplied the July action. No enabling enactment was verified.','official_statement','manual'),
      ('preemption_proposal',1,'https://malegislature.gov/Bills/194/H3634.Html','H.3634 proposed statutory text',None,
       'The proposed bill would create an autonomous-vehicle framework and prevent municipalities from imposing separate prohibitions or additional requirements specific to autonomous vehicles.',
       'Proposed text is not current law. The eventual form of preemption and local authority remains unknown.','official_statement','discovery'),
      ('boston_proposal',1,'https://www.boston.gov/sites/default/files/file/2025/10/Docket%20%231432.pdf','Boston proposed commercial autonomous vehicle ordinance','2025-08-06',
       'The proposal would condition commercial operations on a study and permit process and require an in-vehicle human safety operator.',
       'This is proposed text, not evidence of enactment; its July 2026 study deadline is not evidence a study occurred.','official_statement','manual'),
      ('boston_status',6,'https://boston.legistar.com/ViewReport.ashx?GID=847&GUID=311445A0-001C-4CA7-ADB2-714EBFC16391&ID=7504068&M=R&N=Master&Title=Legislation+Details','Boston 2025-1432 legislative status',None,
       'The official report marks docket 2025-1432 Filed, with final action dated December 10, 2025; the action list shows committee referral and retention, not adoption.',
       'Report print date is May 26, 2026. Direct detail-page access failed. Newer replacement proposals or administrative actions were not comprehensively ruled out.','official_statement','manual'),
      ('denver_entry',5,'https://waymo.com/blog/shorts/were-elevating-the-waymo-experience-in-the-mile-high-city/','Waymo announces Denver preparation','2025-09-02',
       'Waymo announced arrival in Denver that fall with fifth- and sixth-generation vehicles, preparation for future service, and support from Colorado and Denver leaders.',
       'Announcement is not an exact first-work date. Denver political support differs from Boston; weather experience does not remove Boston validation needs.','official_statement','discovery'),
      ('denver_driverless',1,'https://waymo.com/blog/shorts/ro-den-lv-sd-tmpa/','Waymo prepares driverless operations in four cities','2026-07-08',
       'Waymo said fully autonomous operations in Denver, Las Vegas, San Diego and Tampa would begin soon, initially for employees.',
       'Soon is not an observed start date, and employee access does not satisfy the forecast contract.','official_statement','discovery'),
      ('denver_selected',7,'https://waymo.com/blog/2026/09/ride-in-denver-san-diego-tampa/','First riders in Denver, San Diego and Tampa','2026-09-01',
       'Waymo began admitting first public riders in Denver, San Diego and Tampa while progressively offering access from an interest list toward opening to everyone.',
       'This does not establish unrestricted public access. Denver had not yet demonstrated a complete commercial winter in this record.','official_statement','manual'),
      ('miami_driverless',7,'https://waymo.com/blog/2025/11/safe-routine-ready-autonomous-driving-in-new-cities/','Driverless operations expand to five cities','2025-11-18',
       'Waymo said fully autonomous operations began in Miami on November 18, with four other cities to follow, ahead of rider access the next year. Its deployment process compares local performance with a baseline.',
       'Company account; not an independent estimate of Boston completion times.','official_statement','manual'),
      ('orlando_selected',5,'https://waymo.com/blog/2026/02/dallas-houston-san-antonio-orlando/','First public riders in four markets','2026-02-24',
       'Waymo began inviting selected app users in Dallas, Houston, San Antonio and Orlando, with wider access to follow.',
       'Invitation stage is not unrestricted access. Cities share a company and rollout strategy, so they are not independent trials.','official_statement','manual'),
      ('florida_open',6,'https://waymo.com/blog/2026/04/floridas-new-way-to-ride/','Miami and Orlando open to everyone','2026-04-15',
       'Waymo opened Miami and Orlando to anyone able to download the app and request a fully autonomous ride on April 15, after initially admitting riders from interest lists.',
       'Useful access-stage analogue, not a representative empirical distribution. Miami driverless-to-open elapsed time was 148 days; Orlando selected-to-open was 50 days.','official_statement','manual'),
      ('capital',6,'https://waymo.com/blog/2026/02/waymo-raises-usd16-billion-investment-round/','Waymo financing announcement','2026-02-02',
       'Waymo announced a $16 billion financing round and plans to prepare more than twenty additional markets in 2026.',
       'Funding lowers near-term corporate resource risk but is no Boston fleet, depot, staffing, or launch commitment.','official_statement','manual'),
      ('safety_investigation',7,'https://www-s.ntsb.gov/investigations/Pages/HWY26FH007.aspx','NTSB school-bus investigation','2026-03-03',
       'NTSB described a January 2026 Waymo vehicle passing a stopped school bus loading students and said similar incidents remained under investigation. It noted the earlier software recall.',
       'Preliminary investigation, not a final causal determination or a national ban. Demonstrates continuing technical and regulatory risk.','official_statement','discovery'),
      ('ballot_uncertain',7,'https://ma.omniballot.us/sites/25/vg/app/vig/voter-guide/instructions','Official linked 2026 voter guide',None,
       'The official election page links a guide for nine November statewide questions, but the linked guide returned no readable text. Research did not verify whether the earlier autonomous-vehicle petition reached the ballot.',
       'Do not treat initial petition certification as ballot placement or enacted prohibition. This consequential negative claim remains unresolved.','unknown','manual'),
    ]
    records=[]
    for id,idx,url,title,pub,claim,limit,ctype,method in data:
        when=iso(logs['logs'][idx]['at'])
        source={'id':'src_'+id,'url':url,'title':title,'excerpt':claim,'excerpt_kind':'paraphrase','retrieved_at':when,'published_at':pub,'origin_id':('waymo' if 'waymo.com' in url else 'mass_general_court' if 'malegislature' in url else 'boston_city' if 'boston.' in url else id), 'capture':{'method':method,'captured_at':when,'metadata':{'access':'web search extract' if method=='discovery' else 'web open/find/click','limitations':limit,'query_log_index':idx,'raw_tool_response_preserved':'source_query_log.json'}}}
        records.append({'id':id,'claim':claim,'claim_type':ctype,'value':{'classification':'verified_source_statement' if ctype!='unknown' else 'failed_verification','limitations':limit},'entity_ids':['waymo','boston'] if id.startswith('boston') else ['waymo'],'observed_at':when,'sources':[source],'provenance':{'researcher':'independent_question_only','status':'source observation; forecast implications are separate estimates','limitations':limit}})
    limits=['Independent question-only run; no conversation history or prior forecasts supplied.','Web extracts and opened pages are evidence snapshots, not exhaustive legal research. Repeated Waymo statements share a corporate origin.','No empirical estimate of Massachusetts legislation timing, local approval time, Boston depot completion, or launch probability was available; scenario weights and legal/operational timing are subjective assumptions.','No qualifying Boston launch or paid-driverless permit was verified. No Boston depot or fleet readiness dates were verified.','Ballot placement of the earlier AV petition and replacement Boston legislation were not verified; neither is assumed enacted.','Research and model costs were unmetered, not zero-cost; engine zero counters are placeholders.']
    packet=validate_packet({'schema_version':'vorhersage.evidence.v1','kind':'manual','information_as_of':cutoff,'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'records':records,'limitations':limits,'relationships':[{'from_record':'boston_status','to_record':'boston_proposal','relation':'contradicts','rationale':'Contradicts treating the proposal as an enacted ban; does not contradict its proposed content.'}]})
    save(out/'evidence.json',packet)
    usage={'cost_status':'unmetered','cost_usd':None,'model_calls_status':'unmetered','search_queries':sum(len(x['request'].get('search_query',[])) for x in logs['logs']),'web_tool_calls':len(logs['logs']),'note':'Workflow numeric cost and model-call counters are unpopulated placeholders, not zero resource use.'}
    save(out/'usage.json',usage)
    wf=Workflow(project); wf.store.init('Independent Boston Waymo deadline forecast')
    wf.add_profile({'id':'robotaxi_launch','description':'Independent legal, technical, operational and public-access timeline','domains':['state_permission','local_permission','technical','fleet','validation','public_access']})
    wf.question(question); imported=wf.import_packet(packet); packet_id=imported['packet_id']
    refs=lambda *ids:[{'packet_id':packet_id,'record_id':i} for i in ids]
    allrefs=refs(*(r['id'] for r in records))
    provisional=json.loads((ROOT/'outputs/structure_before_research.json').read_text())
    initial_id=timeline.add(wf.store,provisional)['timeline_model_id']
    parameters=[('state_permission','date','Legally effective state enabling framework allowing driverless validation and a path to paid public service'),('technical','duration_days','Remaining Boston mapping, adaptation and pre-driverless technical readiness at cutoff'),('fleet','duration_days','Elapsed remaining fleet, depot, support and fare-system preparation from cutoff'),('local_permission','duration_days','Final Boston-specific commercial authorization and operating arrangements after state framework'),('validation','duration_days','Driverless validation and restricted passenger phase after state and technical readiness'),('public_access','duration_days','Final ramp to paid access for general public with Boston municipal pickup and dropoff')]
    nodes=[]
    parents={'state_permission':[],'technical':[],'fleet':[],'local_permission':['state_permission'],'validation':['state_permission','technical'],'public_access':['local_permission','validation','fleet']}
    nr={'state_permission':('Enabling text and testing rules establish state permission as a gate; event date includes legal effectiveness, not just bill passage.',refs('state_testing','house_bill','senate_bill','boston_return')),'technical':('Waymo returned by February 5; all durations here are remaining at cutoff, not time since first Boston mapping.',refs('boston_return','denver_entry','denver_selected')),'fleet':('Physical and support preparation can proceed before final permission; no Boston completion date verified. This parallelism is assumed.',refs('capital')),'local_permission':('Separate final Boston arrangements from state permission because current local rules and eventual preemption are uncertain. Preparatory dialogue can happen earlier; this duration is the residual after enabling.',refs('boston_proposal','boston_status','preemption_proposal')),'validation':('Driverless work follows state permission and technical readiness. Assume it may overlap the residual commercial approval process; if local approval also gates all driverless tests, use serial-approval sensitivity.',refs('state_testing','miami_driverless','denver_driverless','denver_selected')),'public_access':('Paid unrestricted access needs all permissions, sufficient operations, and driverless validation. Selected riders and free trials do not qualify; ramp duration starts only after the three prerequisites.',refs('orlando_selected','florida_open','denver_selected'))}
    for i,k,d in parameters:
        node={'id':i,'kind':'event' if k=='date' else 'task','completion_condition':d,'parents':parents[i],'parameter_id':i,'state':'in_progress' if i=='technical' else 'pending','rationale':nr[i][0],'evidence_refs':nr[i][1]}
        if i=='technical': node['started_at']='2026-02-05T12:00:00+00:00'
        nodes.append(node)
    # An ordered causal partition, jointly assigned. No independence assumptions.
    # Weights are explicitly subjective. All elapsed durations use 86400-second days.
    cases=[
      ('early_normal',.22,'No corporate or severe technical disruption; enabling effective through 2027, with ordinary Boston approvals.','2027-06-01T12:00:00+00:00',270,300,120,90,90,'Largest successful cohort: substantial political obstacles are offset by two further years, lobbying, continued Boston preparation, and a modest geofence. Weight is assumed, not a legislative frequency.'),
      ('early_local_delay',.08,'Same early state cohort, but persistent Boston-specific legal, operating or implementation friction.','2027-06-01T12:00:00+00:00',300,365,600,120,90,'Local opposition and unresolved preemption justify a distinct delay branch. Filed status argues against treating a ban as already permanent. Weight and 600 days are assumed.'),
      ('mid2028_normal',.12,'Enabling effective in first half of 2028; ordinary readiness and approvals.','2028-04-01T12:00:00+00:00',450,365,90,90,90,'Allows another legislative cycle and advance preparation to yield launch later in 2028. The timing and mass are assumed given 2026 study orders.'),
      ('late2028_accelerated',.05,'Enabling effective in third quarter 2028 with a prepared, expedited small-area rollout.','2028-08-01T12:00:00+00:00',450,450,45,45,45,'Small geofence can support a fast route, but current access-stage examples argue for only a small weight. This is an explicitly optimistic assumed compression.'),
      ('late2028_ordinary',.05,'Enabling effective in third quarter 2028 with ordinary residual approval and public-access work.','2028-09-15T12:00:00+00:00',450,450,120,120,120,'An approval late in the horizon need not produce an immediate qualifying opening. Ordinary validation and access work are jointly slower here.'),
      ('technical_operational_tail',.05,'Timely state path but major Boston technical or operating problems persist despite company continuation.','2027-06-01T12:00:00+00:00',850,800,120,180,120,'Boston winter/streets and ongoing safety investigations justify a residual long tail even with permission. Small weight reflects progress in Denver and national scaling; the magnitude is assumed.'),
      ('state_delay',.40,'Company continues, but no effective enabling route by September 30, 2028; encompasses legislative inertia, prohibition and delayed administrative implementation.','2029-07-01T12:00:00+00:00',450,450,120,120,90,'Both 2026 enabling bills went to study, existing testing requires humans, and no replacement enabling route was verified. Still below half because the horizon includes 2027 and 2028 and company advocacy is active. Entire weight and representative 2029 date are assumed.'),
      ('corporate_or_national_disruption',.03,'Priority class: corporate withdrawal from Boston or a nationwide disruption prevents service within the horizon.','2027-06-01T12:00:00+00:00',450,'never',120,120,90,'Large financing and geographic growth keep this tail small. Safety investigations and reprioritization make zero unjustified. Never means model failure path, not an assertion the company can never operate in Boston.'),
    ]
    rationales={
      'state_permission':('assumed','No empirical passage-time model is available. Scenario date is effective legal readiness, not predicted bill signing alone.',refs('house_bill','senate_bill','state_testing','boston_return')),
      'technical':('estimated','Evidence-informed remaining-work estimate: Boston preparation predates cutoff and Denver progressed from 2025 entry to selected rides in September 2026. Boston-specific readiness is unobserved; long tails and scenario dependence are subjective.',refs('boston_return','denver_entry','denver_selected','safety_investigation')),
      'fleet':('assumed','No Boston depot/fleet schedule verified. Durations allocate residual operational readiness from cutoff, with advance work assumed possible; financing supports feasibility but does not measure duration.',refs('capital')),
      'local_permission':('assumed','No enacted future process or empirical local approval duration exists in the evidence. Residual work after state enablement may include permits, implementation, local operating arrangements or litigation.',refs('boston_proposal','boston_status','preemption_proposal')),
      'validation':('estimated','Evidence-informed, not sampled: Miami driverless operations to open access took 148 days; Denver employee phase preceded selected public riders. This parameter covers validation/restricted rides, with open-access ramp separately represented.',refs('miami_driverless','denver_driverless','denver_selected','florida_open')),
      'public_access':('estimated','Orlando selected-to-unrestricted access took 50 days; multi-city staged openings establish an extra access gate. Estimates of 45-120 remaining days after prerequisites are approximate and exclude citywide or all-weather requirements.',refs('orlando_selected','florida_open','denver_selected'))}
    scenarios=[]
    for row in cases:
        id,w,desc,*tail=row; vals=tail[:-1]; rationale=tail[-1]; assessments=[]
        for (pid,_,_),v in zip(parameters,vals):
            basis,why,rr=rationales[pid]
            if v=='never' or id in ('technical_operational_tail','late2028_accelerated'):
                basis='assumed'
            assessments.append({'parameter_id':pid,'basis':basis,'value':v,'rationale':why+' Joint case: '+desc,'evidence_refs':rr})
        scenarios.append({'id':id,'description':desc,'weight':w,'weight_rationale':rationale,'evidence_refs':allrefs,'assessments':assessments})
    partition=('Ordered exhaustive subjective partition: first corporate/national disruption; among remaining worlds, no effective state path by 2028-09-30; among timely state worlds, severe Boston technical/operational tail; among the rest, state readiness through 2027 (ordinary/local-friction split), first half 2028, or third quarter 2028 (accelerated/ordinary split). Dates and durations are representative joint points inside broad classes, not independent draws. Late-state rapid launches in Q4 2028 are absorbed into the state-delay class; this coarse approximation is a potential downward bias and is tested by weight transfer. Residual ordinary timing variation inside classes is represented by duration sensitivity, not falsely claimed resolved by a single point. Weights sum to one by declaration; their values are judgmental, not counts.')
    model={'id':'independent_researched_structure','version':1,'derived_from_model_id':initial_id,'question':{'question_id':question['id'],'version':1},'information_as_of':cutoff,'deadline':question['event_deadline'],'deadline_rule':'before','description':'Independent question-only forecast: state gate, residual Boston commercial permission, parallel predeployment and operations, driverless validation, paid unrestricted access.','target':'public_access','parameters':[{'id':i,'kind':k,'description':d} for i,k,d in parameters],'nodes':nodes,'scenarios':scenarios,'partition_justification':partition,'limitations':limits+['Representative joint scenarios compress within-class date variation; displayed calendar precision is arithmetic, not predictive precision.','Local commercial permission overlapping driverless validation is an assumption, exposed in structural sensitivity.','A small Boston geofence and weather restrictions qualify; Cambridge-only, invitation access, and free rides do not.','Severe failures are assigned explicitly and elapsed Boston work is not added again.']}
    save(out/'structure_after_research.json',model)
    (out/'structure_changes.md').write_text('Research changed the provisional structure as follows:\n\n- Split the single legal gate into effective state permission and residual Boston commercial authorization because state enabling bills may preempt local rules, while Boston opposition remains distinct.\n- Treat technical preparation as in progress since the verified February 5 return; durations mean remaining work at the research cutoff.\n- Let technical preparation and fleet readiness overlap state deliberation. Fleet timing remains assumed because no Boston schedule was verified.\n- Driverless validation follows state and technical readiness, while the final commercial approval work may overlap it. This is tested against full serialization.\n- Keep a separate paid unrestricted-access ramp because recent launches explicitly used invitation lists.\n- Replace five unweighted hypotheses with eight jointly weighted causal classes, separating early local delay, late expedited/ordinary launches, state delay, major technical delay and corporate disruption. No empirical frequencies are claimed.\n')
    mid=timeline.add(wf.store,model)['timeline_model_id']
    run=wf.start({'question_id':question['id'],'forecaster':'independent_question_only_20260916','method':'independent_researched_joint_timeline','mode':'prospective','information_as_of':cutoff,'max_searches':100,'max_extra_tasks':10,'cutoff_policy':'fixed','research_status':'completed','workflow':'timeline'})['run_id']
    history=[]; first=True
    while True:
        nxt=wf.next(run)
        if nxt['disposition']!='actionable': break
        task=nxt['task']; kind=task['kind']
        if kind=='timeline_structure': payload={'timeline_model_id':mid,'rationale':'Bind separately preserved researched structure. Provisional unweighted structure was saved before browsing and is registered as its ancestor.'}
        elif kind=='timeline_research':
            current=task['timeline_context']['model']; pid=task['parameter_id']
            payload={'assessments':[{'scenario_id':s['id'],'assessment':next(a for a in s['assessments'] if a['parameter_id']==pid)} for s in current['scenarios']], 'rationale':'Preserve explicitly declared joint assessments and evidence rationales for '+pid+'. Values labeled assumed were not empirically identified. Each submission creates a new model version.'}
        elif kind=='assessment':
            # Retrieve the actual latest specification after all parameter submissions.
            mid=task['timeline_context']['timeline_model_id']; model=task['timeline_context']['model']; analysis=timeline.analyze(model)
            payload={'method':'timeline_model','timeline_model_id':mid,'rationale':'Aggregate scenario weights only when their computed launch precedes the exact deadline. State legislative timing drives the result; preparation overlaps permitting and public-access work is separate.','limitations':model['limitations'],'evidence_refs':allrefs}
        elif kind=='review':
            payload={'decision':'retain','rationale':'Retain this subjective forecast with broad political and duration sensitivities. Procedural validation establishes arithmetic and provenance, not forecasting skill or empirical calibration.','objections':[{'direction':'too_high','objection':'Two enabling bills stalled; Boston opposition and the undefined future permit process could consume another legislative cycle. Denver selected riders do not establish unrestricted winter performance.','response':'Substantial state-delay mass and separate local/technical tails account for this. Increase the state-delay weight in the pessimistic sensitivity; do not claim those weights are measured.'},{'direction':'too_low','objection':'Waymo is financed and scaling quickly; preemption, a pilot framework or a small geofence could produce public rides soon after state permission. Filed local proposals are not current bans.','response':'Early and accelerated paths recognize this, with a favorable political-weight sensitivity. Q4 permission plus an exceptionally rapid launch is underrepresented by coarse state bins and merits upward revision if such a framework appears.'}],'evidence_refs':allrefs}
        elif kind=='issue': payload={'stopping_reason':'Primary facts and deployment-stage analogues support an explicit scenario forecast. Further public searches did not identify legislative probabilities or Boston internal schedules; retain assumptions and failed verification rather than invent precision. Costs remain unmetered.','review_at':'2027-02-01T12:00:00+00:00','triggers':[{'description':'Enabling law or legally effective pilot authorizes driverless paid operations, with known preemption and local requirements.','evidence_refs':refs('senate_bill','house_bill','preemption_proposal')},{'description':'Boston issues or denies a relevant permit; Waymo announces actual driverless passenger operations, depot readiness or a public-access date.','evidence_refs':refs('boston_status','boston_return','upcoming')},{'description':'Denver winter performance, major safety suspension, or Boston withdrawal changes readiness and disruption assumptions.','evidence_refs':refs('denver_selected','safety_investigation')}]}
        else: raise RuntimeError(kind)
        submit={'task_id':task['id'],'expected_revision':nxt['revision'],'idempotency_key':'independent_'+str(nxt['revision']),'payload':payload}
        if first:
            submit['usage']={'searches':usage['search_queries'],'cost_usd':0,'model_calls':0}; first=False
        response=wf.submit(run,submit); history.append({'kind':kind,'request':submit,'response':response})
    forecast_id=nxt['forecast_id']
    with wf.store.connect() as c:
        forecast=Store.artifact(c,forecast_id,'forecast'); current_record=timeline.read(c,forecast['timeline_model_id']); model=current_record['specification']
    analysis=timeline.analyze(model)
    # Independent weighted arithmetic and calendar recursion, without timeline internals.
    def parse(x): return dt.datetime.fromisoformat(x)
    manual=[]
    for s in model['scenarios']:
        vals={a['parameter_id']:a['value'] for a in s['assessments']}; dates={}
        pending=list(model['nodes'])
        while pending:
            for n in list(pending):
                if not all(p in dates for p in n['parents']): continue
                v=vals[n['parameter_id']]
                if v=='never' or any(dates[p] is None for p in n['parents']): finish=None
                elif n['kind']=='event': finish=parse(v)
                else:
                    start=max([parse(cutoff)]+[dates[p] for p in n['parents']]); finish=start+dt.timedelta(days=v)
                dates[n['id']]=finish; pending.remove(n)
        d=dates[model['target']]; manual.append({'scenario_id':s['id'],'launch_at':d.isoformat() if d else None,'weight':s['weight'],'success':d is not None and d<parse(question['event_deadline'])})
    from decimal import Decimal
    exact=sum(Decimal(str(r['weight'])) for r in manual if r['success'])
    assert float(exact)==analysis['probability']
    for r,a in zip(manual,analysis['scenarios']): assert r['success']==a['meets_deadline'] and r['launch_at']==a['launch_at']
    checks={'independent_probability':str(exact),'weighted_sum':str(sum(Decimal(str(r['weight'])) for r in manual)),'all_calendars_match':True,'scenarios':manual,'doctor':wf.doctor()}
    save(out/'verification.json',checks); save(out/'model.json',model); save(out/'analysis.json',analysis); save(out/'forecast.json',forecast); save(out/'workflow_history.json',history); save(out/'registered_model.json',current_record)
    stresses=[]
    for label,delta in [('More persistent legislative blockage',.15),('Faster political accommodation',-.15)]:
        m=copy.deepcopy(model)
        for s in m['scenarios']:
            if s['id']=='state_delay': s['weight']+=delta
            if s['id']=='early_normal': s['weight']-=delta
        stresses.append({'name':label,'change':'Transfer '+str(abs(delta))+' joint probability mass between early_normal and state_delay; other assignments unchanged.','probability':timeline.analyze(m)['probability']})
    for days in (90,180):
        m=copy.deepcopy(model)
        for s in m['scenarios']:
            for a in s['assessments']:
                if a['parameter_id']=='public_access': a['value']+=days
        stresses.append({'name':f'Public access takes {days} additional days','change':'Add elapsed days after all prerequisites in every scenario.','probability':timeline.analyze(m)['probability']})
    m=copy.deepcopy(model)
    next(n for n in m['nodes'] if n['id']=='validation')['parents'].append('local_permission')
    stresses.append({'name':'Local approval gates all driverless validation','change':'Add local_permission as a validation prerequisite; prevents their overlap.','probability':timeline.analyze(m)['probability']})
    save(out/'sensitivity.json',{'stress_tests':stresses,'note':'Declared-input alternatives, not a statistical confidence interval. Political range is not empirically calibrated.','engine_one_parameter_swaps':timeline.sensitivity(model)})
    table='\n'.join(f"| {s['id']} | {s['weight']:.0%} | {a['launch_at'] or 'No launch'} | {'YES' if a['meets_deadline'] else 'NO'} | {s['weight_rationale']} |" for s,a in zip(model['scenarios'],analysis['scenarios']))
    st='\n'.join(f"| {x['name']} | {x['probability']:.0%} | {x['change']} |" for x in stresses)
    sources='\n'.join(f"- [{r['id']}: {r['sources'][0]['title']}]({r['sources'][0]['url']}): {r['claim']} Limitation: {r['value']['limitations']}" for r in records)
    summary=f'''# Independent Boston Waymo forecast

**Probability: {analysis['probability']:.0%}.** Paid, general-public driverless Waymo service with pickups and dropoffs inside Boston before January 1, 2029, Eastern time.

Information cutoff: **{cutoff}**. Research retrievals were captured on September 16 UTC (September 15 in Boston), not backdated. Independent forecaster: `independent_question_only_20260916`. Conversation history was absent. No other event probability or prediction-market price was seen or searched; incidental qualitative advocacy and Reddit snippets were encountered but not treated as independent evidence.

## What drives the forecast

The largest uncertainty is Massachusetts creating an effective legal path. Both principal enabling bills were sent to study orders in 2026. Waymo itself says the state must legalize the technology first, and current state testing guidance requires an in-vehicle operator. These observations justify substantial delay risk but do not identify a numerical passage probability. [House history](https://malegislature.gov/Bills/194/H3634), [Senate history](https://malegislature.gov/Bills/194/S2379/BillHistory), [Waymo Boston statement](https://waymo.com/blog/shorts/back-to-boston/).

Boston is preparing for possible service and remains listed as upcoming. The city's restrictive proposal was filed rather than verified enacted. Future state preemption could reduce local obstacles, while permitting, operating arrangements or opposition could delay service after state legislation. These are separate stages in the model. [Boston status](https://boston.legistar.com/ViewReport.ashx?GID=847&GUID=311445A0-001C-4CA7-ADB2-714EBFC16391&ID=7504068&M=R&N=Master&Title=Legislation+Details), [proposed preemption](https://malegislature.gov/Bills/194/H3634.Html).

National deployment progress makes a technically feasible small-area launch plausible within the horizon. Denver went from announced preparation in September 2025 to selected riders in September 2026; that is useful evidence for the scale of work, not proof of all-weather Boston readiness. Miami moved from driverless operations to open access in 148 days, while Orlando's selected-to-open stage lasted 50 days. These stages support explicit remaining validation and access durations. They are a few dependent analogues, not an empirical launch-rate sample. [Denver](https://waymo.com/blog/2026/09/ride-in-denver-san-diego-tampa/), [Miami driverless](https://waymo.com/blog/2025/11/safe-routine-ready-autonomous-driving-in-new-cities/), [Florida open access](https://waymo.com/blog/2026/04/floridas-new-way-to-ride/).

## Joint scenarios and weights

All weights are subjective assumptions informed by evidence. They are not inferred by the engine and are not equal case counts. Every row jointly sets correlated political and operational timings. Calendar dates are representative arithmetic outputs, not precise date forecasts.

| Scenario | Weight | Computed launch (UTC) | Deadline | Weight rationale |
|---|---:|---|---|---|
{table}

{partition}

Independent decimal arithmetic: successful weights sum to **{exact}**, all weights sum to **1.00**. A separate calendar recursion matches every engine outcome. The workflow issued one forecast; parameter submissions each created a new model version and the final assessment retrieved the latest version.

## Sensitivity and structural uncertainty

| Alternative assumption | Probability | Explicit change |
|---|---:|---|
{st}

The political weight stress gives **24%–54%**; this is a judgmental sensitivity range, not a statistical confidence interval. Longer access work can produce results outside that range. The exact legal process, legislative coalition, future preemption, and Boston operating schedule were not empirically identified. A late-2028 expedited pilot could defeat the coarse state-delay classification. Local authority might also gate all driverless validation, requiring serialization. Both issues matter more than the model's displayed date precision.

Technical preparation is in progress, with durations measured as **remaining at cutoff**. Fleet preparation and predeployment technical work overlap political deliberation; residual commercial approval overlaps driverless validation only in the base structure. Final paid general-public access waits for all prerequisites. A limited geofence and weather restrictions qualify; no airport, citywide operation or all-weather capability is required. A safety driver, invitations, waitlist, free trials or service only outside Boston do not qualify.

## Unverified consequential claims and disconfirming evidence

No Boston depot completion date, paid-driverless permit, or binding opening date was verified. Mass.gov direct page accesses and the Boston detail page failed; detailed search extracts and the official docket report were retained with those limitations. Senate search extracts were initially stale, but an opened history exposed the July study order. The earlier AV petition's ballot placement could not be verified because the official linked guide returned no readable text; no ballot prohibition is assumed. No recent replacement Boston ordinance was verified. The NTSB school-bus investigation supports a real residual safety/approval tail, without being treated as a shutdown. [NTSB](https://www-s.ntsb.gov/investigations/Pages/HWY26FH007.aspx).

## Observations that would change this forecast

- Effective enabling legislation or a paid-driverless pilot with clear local authority would remove the dominant gate; bill introduction alone would not.
- A Boston permit, resolved preemption, depot opening, or actual driverless passenger phase would shorten residual durations.
- A paid launch announcement must be checked for invitations and geofence boundaries before marking the event accomplished.
- Another legislative cycle ending without enablement, an enacted human-operator requirement, withdrawal, or a serious safety suspension would move mass into delay/failure.
- Successful Denver winter operations would improve the technical analogue; substantial winter restrictions alone need not prevent a qualifying Boston launch.

## Audit and costs

Research costs and model-call costs are **unmetered**, not zero. Numeric zero counters inside the generic workflow are unpopulated placeholders. {usage['search_queries']} search queries across {usage['web_tool_calls']} web calls are logged, including access failures. Doctor and independent arithmetic results are in `verification.json`. Source material is evidence, never instructions. Procedural compliance does not establish calibration or forecast accuracy.

## Source packet

{sources}
'''
    (out/'forecast_summary.md').write_text(summary)
    timeline_reports.export(wf.store,forecast['timeline_model_id'],out/'forecast.html',forecast=forecast)
    report=(out/'forecast.html').read_text()
    report=report.replace('<div class="eyebrow">','<section class="notice"><strong>Independent forecast; subjective weights.</strong> Research costs are unmetered. Zero workflow cost counters are placeholders. Political-weight sensitivity: 24%–54%, not a confidence interval. See the preserved summary below.</section><details class="card"><summary>Independent forecast reasoning, assumptions and source limitations</summary><pre>'+html.escape(summary)+'</pre></details><div class="eyebrow">',1)
    (out/'forecast.html').write_text(report)
    # Preserve registered artifacts and event log for inspection without sqlite tooling.
    with wf.store.connect() as c:
        save(out/'workflow_artifacts.json',[{'id':r['id'],'kind':r['kind'],'body':json.loads(r['body'])} for r in c.execute('SELECT id,kind,body FROM artifacts')])
        save(out/'workflow_events.json',[dict(r) for r in c.execute('SELECT * FROM events')])
    print(json.dumps({'forecast_id':forecast_id,'output_dir':str(out),'doctor':checks['doctor'],'probability':analysis['probability']}))

if __name__=='__main__': main()
