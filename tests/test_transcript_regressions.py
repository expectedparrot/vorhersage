"""Cape Cod transcript regressions: live research, recovery and report handoff."""
import copy
import json
import subprocess
import sys

import pytest

from vorhersage import evidence, report_context, research_model, study, timeline
from vorhersage.common import Error, now
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_study import challenge, intake, model_map, study_payload, support
from test_timeline import model, weighted
from test_workflow import question, run_spec


def timeline_study(tmp_path):
    w = Workflow(tmp_path)
    q = question(kind='real')
    q.update(event_deadline='2029-01-01T00:00:00Z', resolve_after='2029-01-01T00:00:00Z')
    study.start(tmp_path, q['text'], q, workflow_name='timeline', research_effort='standard')
    return w


def answer(w, payload):
    task = study.next_task(w)
    return study.submit(w, task, payload)


def test_live_timeline_research_keeps_reference_date_and_structured_contract(tmp_path):
    w = timeline_study(tmp_path)
    initial = study.next_task(w)['context']['run']['information_as_of']
    answer(w, intake([{'id': 'fact', 'question': 'What is the launch status?', 'input_ids': ['outcome'],
                      'route': 'search', 'why_it_matters': 'Constrains launch', 'action': 'Read the release log'}]))
    fresh = evidence.capture_finding('Launch preparations continue.', url='https://example.org/status',
        title='Release log', excerpt='Launch preparations continue.', claim_type='observation')
    refs = [w.import_packet(fresh)['records'][0]['evidence_ref']]
    answer(w, {'status': 'answered', 'answer': 'Preparations continue.', 'evidence_refs': refs})
    spec = weighted(model()); spec['information_as_of'] = now()
    original = timeline.add(w.store, spec)['timeline_model_id']
    answer(w, {'timeline_model_id': original, 'rationale': 'Fictional launch dependency model.'})
    start_schedule = study.next_task(w)['task']['timeline_context']['analysis']['scenarios']
    while (task := study.next_task(w))['task']['kind'] == 'timeline_research':
        # Research really occurs after model creation, not at a backdated fixture cutoff.
        fresh = evidence.capture_finding('Release team confirms plan.', url='https://example.org/update',
            title='Update', excerpt='Release team confirms plan.', claim_type='observation')
        current_refs = [w.import_packet(fresh)['records'][0]['evidence_ref']]
        pid = task['task']['parameter_id']; current = task['task']['timeline_context']['model']
        assignments = []
        for scenario in current['scenarios']:
            a = copy.deepcopy(next(a for a in scenario['assessments'] if a['parameter_id'] == pid))
            a['evidence_refs'] = current_refs
            assignments.append({'scenario_id': scenario['id'], 'assessment': a})
        answer(w, {'assessments': assignments, 'rationale': 'Keep declared values with newly captured evidence.'})
    current = task['task']['timeline_context']['model']
    assert current['schedule_as_of'] == spec['information_as_of']
    assert current['information_as_of'] > initial
    assert task['task']['timeline_context']['analysis']['scenarios'] == start_schedule
    assessment = dict(task['submission']['payload'], rationale='Declared fixture', limitations=['Synthetic'], evidence_refs=refs)
    assessment['parameter_support'] = support(assessment, current)
    assessment['model_map'] = model_map(assessment, task['context'])
    stale = dict(assessment, timeline_model_id=original)
    with pytest.raises(Error, match='current researched model') as exc:
        answer(w, stale)
    assert exc.value.code == 'stale_timeline_model'
    answer(w, assessment)
    task = study.next_task(w)
    assert task['task']['kind'] == 'model_challenge'
    audit = challenge(task['context'], [s['id'] for s in current['scenarios']])
    missing = dict(audit); del missing['event_alignment']
    with pytest.raises(Error, match='event_alignment'):
        answer(w, missing)
    answer(w, audit)
    task = study.next_task(w)
    review = study_payload('review', refs, context=task['context'])
    review['sensitivity_review']['influential_inputs'] = list(task['context']['model_inputs'])
    answer(w, review); answer(w, study_payload('issue', refs))
    report = report_context.export(w.store)
    assert report['material']['prediction']['status'] == 'issued'
    assert report['material']['summary']['workflow_requirements']['omitted'] == []
    assert report['material']['summary']['scenario_results']
    assert report['material']['evidence'] and report['material']['latest_work']['review']


def test_resume_fixed_run_preserves_work_and_invalidates_old_tasks(tmp_path):
    w = timeline_study(tmp_path)
    task = study.next_task(w); rid = task['run_id']
    # Represents a study persisted by the old default, before this fix.
    with w.store.connect(True) as c:
        body = json.loads(c.execute('SELECT body FROM runs WHERE id=?', (rid,)).fetchone()[0])
        body['cutoff_policy'] = 'fixed'
        c.execute('UPDATE runs SET body=? WHERE id=?', (json.dumps(body), rid))
    before = w.next(rid)
    resumed = w.resume(rid, live=True, reason='Continue prospective research with actual capture times')
    assert resumed['revision'] == before['revision'] + 1
    assert resumed['task']['id'] == before['task']['id']
    assert resumed['context']['run']['research_contract'] == 'structured_v2'
    assert resumed['context']['run']['initial_information_as_of'] == before['context']['run']['initial_information_as_of']
    with pytest.raises(Error, match='revision is stale'):
        study.submit(w, task, intake())
    answer(w, intake())
    assert len(w.status()['runs']) == 1
    assert w.resume(rid)['task']['kind'] == 'timeline_structure'
    assert w.resume(rid, live=True, reason='Retry')['revision'] == w.next(rid)['revision']


def test_fixed_timeline_rejects_new_model_and_historical_resume(tmp_path):
    w = Workflow(tmp_path); w.store.init('Fixed fixture')
    q = question(); q.update(event_deadline='2029-01-01T00:00:00Z', resolve_after='2029-01-01T00:00:00Z'); w.question(q)
    rid = w.start(run_spec(workflow='timeline', cutoff_policy='fixed'))['run_id']
    spec = weighted(model()); spec['information_as_of'] = now()
    mid = timeline.add(w.store, spec)['timeline_model_id']
    task = study.next_task(w, run_id=rid)
    with pytest.raises(Error, match='cutoff is after'):
        study.submit(w, task, {'timeline_model_id': mid, 'rationale': 'Later model'}, run_id=rid)
    with pytest.raises(Error, match='Only ordinary prospective'):
        w.resume(rid, live=True, reason='Not allowed for simulation')


def test_large_model_cannot_erase_report_sources_and_review():
    material = {'model': {'rows': [{'text': 'x' * 10000} for _ in range(200)]},
                'latest_work': {'review': {'answer': 'Unresolved delay risk'}},
                'evidence': [{'evidence_id': 'packet:claim', 'sources': [{'url': 'https://example.org'}]}],
                'usage': {'used_searches': 9},
                'summary': {'scenario_results': [{'scenario_id': 'optimistic', 'weight': .1}],
                            'concerns': [{'question': 'Initial opening or full completion?'}]}}
    omissions = []; bounded = report_context.bounded_material(material, omissions)
    assert bounded['evidence'] == material['evidence']
    assert bounded['latest_work'] == material['latest_work']
    assert bounded['usage'] == material['usage']
    assert bounded['summary'] == material['summary']
    assert omissions


def test_sensitivity_computes_weight_changes_and_deadline_crossings():
    spec = weighted(model())
    p = {'method': 'timeline_model'}
    declared = support(p, spec)
    for row in declared:
        if row['model_input'] == 'scenarios/late/weight': row['plausible_range'] = [.3, .6]
        if row['model_input'] == 'scenarios/late/inputs/rollout_days': row['plausible_range'] = [61, 200]
    result = research_model.timeline_sensitivity(spec, declared)
    varied = {(r['model_input'], r['value']): r['probability'] for r in result['substitutions']}
    assert varied['scenarios/late/weight', .3] == pytest.approx(.58)
    assert varied['scenarios/late/weight', .6] == pytest.approx(.76)
    assert varied['scenarios/late/inputs/rollout_days', 200] == pytest.approx(.2)


def test_portfolio_exports_same_task_contract_and_accepts_json_anywhere(tmp_path):
    w = Workflow(tmp_path / 'project'); w.store.init('Portfolio'); w.question(question())
    rid = w.start(run_spec())['run_id']
    taskfile = tmp_path / 'task.json'
    cmd = [sys.executable, '-m', 'vorhersage', '--json', 'next', '--project', str(w.store.root), '--run', rid, '--output', str(taskfile)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)['data']
    assert data['submission'] == json.loads(taskfile.read_text())['submission']
    result = subprocess.run([sys.executable, '-m', 'vorhersage', 'run', 'list', '--project', str(w.store.root), '--json'], capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)['status'] == 'ok'
    result = subprocess.run([sys.executable, '-m', 'vorhersage', 'timeline', 'new', str(tmp_path / 'plan.toml'), '--project', str(w.store.root), '--json'], capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)['status'] == 'ok'


def test_event_mismatch_requires_concern_and_cannot_be_retained(tmp_path):
    from test_research_v2 import concern, resolution
    w = timeline_study(tmp_path)
    rid = study.binding(w.store)['run_id']
    # Exercise validation at the review boundary with a declared target mismatch.
    task = {'id': 'review-fixture', 'kind': 'review'}
    mapping = {'version': 1, 'inputs': [{'model_input': 'probability', 'input_ids': ['outcome']}]}
    audit = {'map_version': 1, 'transfers': [{'model_input': 'probability', 'verdict': 'assumption', 'reason': 'Fixture', 'evidence_refs': []}],
             'boundary_cases': [], 'partition_review': 'Fixture', 'concerns': [],
             'event_alignment': {'target': 'full_completion', 'matches_question': False,
                                 'rationale': 'Question requires initial opening.', 'concern_ids': []}}
    state = {'model_map': mapping, 'model_inputs': {'probability': .1},
             'parameter_support': [{'model_input': 'probability', 'basis': 'assumed', 'evidence_refs': []}],
             'event_alignment': {'target': 'full_completion'}}
    with pytest.raises(Error, match='mismatch needs a concern'):
        research_model.validate_challenge(audit, state)
    audit['concerns'] = [concern()]; audit['event_alignment']['concern_ids'] = ['transfer']
    research_model.validate_challenge(audit, state)
    state['model_challenge'] = audit
    with w.store.connect() as c:
        run = Store.run(c, rid)[0]
        review = study_payload('review', [], context={'run': run})
        review['concern_resolutions'] = [resolution('retain_assumption')]
        with pytest.raises(Error, match='target does not match'):
            w._apply(c, run, state, task, review)
