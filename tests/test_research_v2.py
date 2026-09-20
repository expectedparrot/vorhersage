"""Exercise model repair, evidence transfer and denominator integrity through real submissions."""
import copy

import pytest

from vorhersage import evidence, reference, study
from vorhersage.common import Error, now
from vorhersage.store import Store
from vorhersage.workflow import Workflow
from test_workflow import packet, question, stamp
from test_study import challenge, intake, model_map, study_payload, support


def begin(tmp_path):
    w = Workflow(tmp_path / 'study')
    q = question(kind="real")
    study.start(w.store.root, q['text'], q, research_effort="standard", max_extra_tasks=2)
    refs = [w.import_packet(packet())['records'][0]['evidence_ref']]
    return w, refs


def submit(w, answer):
    t = study.next_task(w)
    t['submission']['payload'] = answer
    return study.submit(w, t)


def advance(w, refs, until):
    while (t := study.next_task(w))['task']['kind'] != until:
        submit(w, study_payload(t['task']['kind'], refs, context=t['context']))
    return t


def concern(path='probability'):
    return {'id': 'transfer', 'model_inputs': [path], 'question': 'Does the source measure this quantity?',
            'disposition': 'investigate', 'rationale': 'The cited claim concerns a different outcome.',
            'action': 'Find a direct measurement, or record that it remains unknown.'}


def resolution(disposition='investigate'):
    return {'concern_id': 'transfer', 'disposition': disposition,
            'rationale': 'This uncertainty changes the estimate.',
            'action': 'Check the release log for the relevant outcome.'}


def test_research_repair_loop_preserves_maps_and_returns_to_challenge(tmp_path):
    w, refs = begin(tmp_path)
    t = advance(w, refs, 'assessment')
    answer = study_payload('assessment', refs, context=t['context'])
    missing = copy.deepcopy(answer)
    del missing['model_map']
    with pytest.raises(Error, match='model_map'):
        submit(w, missing)
    submit(w, answer)
    t = study.next_task(w)
    assert t['task']['kind'] == 'model_challenge'
    audit = challenge(t['context'])
    audit['transfers'][0]['verdict'] = 'mismatch'
    with pytest.raises(Error, match='mismatched'):
        submit(w, audit)
    audit['concerns'] = [concern()]
    submit(w, audit)
    t = study.next_task(w)
    review = study_payload('review', refs, context=t['context'])
    with pytest.raises(Error, match='each model challenge'):
        submit(w, review)
    review.update(decision='research', concern_resolutions=[resolution()])
    submit(w, review)
    t = study.next_task(w)
    assert t['task']['kind'] == 'inquiry'
    assert t['task']['inquiry']['model_inputs'] == ['probability']
    assert t['task']['inquiry']['input_ids'] == ['outcome']
    submit(w, {'status': 'unresolved', 'answer': 'The release log gives no empirical probability.', 'evidence_refs': refs})
    t = study.next_task(w)
    assert t['task']['kind'] == 'assessment'
    with pytest.raises(Error, match='version is stale'):
        submit(w, answer)
    answer['model_map'] = model_map(answer, t['context'])
    answer['model_map']['rationale'] = 'Keep a declared assumption after an unsuccessful targeted search.'
    submit(w, answer)
    t = study.next_task(w)
    audit = challenge(t['context'])
    audit['concerns'] = [dict(concern(), disposition='retain_assumption')]
    submit(w, audit)
    t = study.next_task(w)
    review = study_payload('review', refs, context=t['context'])
    review['concern_resolutions'] = [resolution('retain_assumption')]
    submit(w, review)
    submit(w, study_payload('issue', refs))
    result = study.show(w.store)
    assert result['issued'] and result['model_map']['version'] == 2
    with w.store.connect() as c:
        forecast = Store.artifact(c, result['forecast_id'])
        artifacts = [Store.artifact(c, aid) for aid in forecast['input_manifest']]
    assert forecast['concern_resolutions'][0]['disposition'] == 'retain_assumption'
    assert sorted(a['payload']['model_map']['version'] for a in artifacts
                  if a.get('task', {}).get('kind') == 'assessment') == [1, 2]
    assert w.doctor()['ok']
    study.revise(w, reason='New review', refs=refs)
    submit(w, intake())
    t = study.next_task(w)
    answer['model_map'] = model_map(answer, t['context'])
    assert answer['model_map']['version'] == 3
    submit(w, answer)
    assert study.next_task(w)['task']['kind'] == 'model_challenge'


def test_inquiry_coverage_reuses_research_without_repeating_domain_tasks(tmp_path):
    w, refs = begin(tmp_path)
    unknown = {'id': 'ready', 'input_ids': ['outcome'], 'question': 'Is dispatch ready?',
               'route': 'search', 'why_it_matters': 'Dispatch gates release.', 'action': 'Read release log.'}
    submit(w, intake([unknown]))
    t = study.next_task(w)
    domains = t['context']['run']['profile']['domains']
    answer = {'status': 'answered', 'answer': 'Fixture readiness is documented.', 'evidence_refs': refs,
              'coverage': [{'domain': d, 'interpretation': 'The fixture addresses this domain.'} for d in domains]}
    submit(w, answer)
    t = advance(w, refs, 'assessment')
    assert set(t['context']['coverage']) == set(domains)
    assert all(r['inquiry_id'] == 'ready' for r in t['context']['coverage'].values())
    assert not any(a.get('task', {}).get('kind') == 'research' for a in t['context']['artifacts'].values())


def test_quantity_types_and_boundary_gaps_are_checked(tmp_path):
    w, refs = begin(tmp_path)
    t = advance(w, refs, 'assessment')
    a = {'method': 'scenario_mixture', 'rationale': 'Two synthetic trajectories.', 'limitations': [],
         'evidence_refs': refs, 'partition_justification': 'Partition needs a boundary test.',
         'scenarios': [{'id': name, 'description': name, 'weight': .5, 'probability': p,
                        'rationale': 'Assumed.', 'evidence_refs': [], 'unknowns': []}
                       for name, p in [('stable', .1), ('crisis', .4)]]}
    a['parameter_support'] = support(a)
    a['model_map'] = model_map(a, t['context'])
    a['model_map']['inputs'][0]['quantity'] = 'conditional_probability'
    with pytest.raises(Error, match='Wrong quantity'):
        submit(w, a)
    a['model_map'] = model_map(a, t['context'])
    submit(w, a)
    t = study.next_task(w)
    audit = challenge(t['context'], ['stable', 'crisis'])
    audit['boundary_cases'][1]['scenario_ids'] = []
    with pytest.raises(Error, match='boundary case needs'):
        submit(w, audit)
    audit['concerns'] = [concern('scenarios/crisis/weight')]
    audit['boundary_cases'][1]['concern_ids'] = ['transfer']
    submit(w, audit)
    t = study.next_task(w)
    review = study_payload('review', refs, context=t['context'])
    review['sensitivity_review']['influential_inputs'] = ['scenarios/crisis/weight']
    review.update(decision='revise', concern_resolutions=[resolution('retain_assumption')])
    submit(w, review)
    assert study.next_task(w)['task']['kind'] == 'assessment'


def test_claim_passages_and_inference_are_preserved_and_checked():
    kwargs = dict(url='urn:test', title='Release log', excerpt='The review is complete.')
    with pytest.raises(Error, match='inference-rationale'):
        evidence.capture_finding('Release may be closer.', claim_type='inference', **kwargs)
    p = evidence.capture_finding('Release may be closer.', claim_type='inference',
                                 inference_rationale='A completed review removes one prerequisite.', **kwargs)
    assert evidence.audit(p)['inference_records'] == ['finding']
    assert not any(g['missing'] == 'claim_support' for g in evidence.audit(p)['provenance_gaps'])
    p.pop('sha256')
    p['records'][0]['claim_support'][0]['passage'] = 'Release is certain.'
    with pytest.raises(Error, match='must occur'):
        evidence.validate_packet(p)


def test_reference_denominator_excludes_unresolved_and_detects_shared_episodes(tmp_path):
    w, refs = begin(tmp_path)
    def case(name, start, end, episode):
        return {'id': name, 'description': 'Synthetic policy proposal.', 'tags': ['policy'],
                'episode_id': episode, 'eligibility': 'Same policy and comparable horizon.',
                'trigger_at': stamp(start), 'observed_until': stamp(end), 'known_at': now(),
                'event_at': None, 'evidence_refs': refs}
    reference.add(w.store, case('completed', -20, -3, 'old_crisis'))
    reference.add(w.store, case('pending', -3, 0, 'current_crisis'))
    query = {'tags': ['policy'], 'horizon_days': 10, 'known_as_of': now(), 'selection_rule': 'Comparable policy episodes.'}
    result = reference.query(w.store, query)
    assert result['sample_size'] == 1 and result['probability'] == 0
    assert result['censored'] == ['pending']
    t = advance(w, refs, 'prior')
    prior = dict(result['prior_payload'], research_status_at_estimate='in_progress')
    bad = copy.deepcopy(prior)
    bad['cases'].append({'id': 'pending', 'outcome': 0, 'evidence_refs': refs})
    with pytest.raises(Error, match='censored cases are not failures'):
        submit(w, bad)
    reference.add(w.store, case('other_bill', -3, 0, 'current_crisis'))
    query['known_as_of'] = now()
    result = reference.query(w.store, query)
    assert result['dependent_episodes'] == {'current_crisis': ['other_bill', 'pending']}
    assert result['prior_payload'] is None
    prior['reference_query'] = query
    with pytest.raises(Error, match='one case per episode'):
        submit(w, prior)
    # The original selection remains cutoff-pinned; the newly recorded case is excluded.
    prior['reference_query'] = bad['reference_query']
    submit(w, prior)
    assert study.next_task(w)['context']['current_probability'] == 0


def test_review_defer_and_budget_failure_are_explicit_and_atomic(tmp_path):
    w, refs = begin(tmp_path)
    t = advance(w, refs, 'model_challenge')
    audit = challenge(t['context'])
    audit['concerns'] = [dict(concern(), id=f'gap{i}') for i in range(3)]
    submit(w, audit)
    t = study.next_task(w)
    review = study_payload('review', refs, context=t['context'])
    review.update(decision='research', concern_resolutions=[dict(resolution(), concern_id=f'gap{i}') for i in range(3)])
    before = w.status()
    with pytest.raises(Error, match='budget exhausted'):
        submit(w, review)
    assert w.status() == before
    review.update(decision='retain', concern_resolutions=[dict(resolution('await_evidence'), concern_id=f'gap{i}') for i in range(3)])
    submit(w, review)
    submit(w, study_payload('issue', refs))
    assert all(c['disposition'] == 'await_evidence' for c in study.show(w.store)['concern_resolutions'])


def test_user_followup_and_stale_challenge_are_checked(tmp_path):
    w, refs = begin(tmp_path)
    t = advance(w, refs, 'model_challenge')
    audit = challenge(t['context'])
    audit['map_version'] = 7
    with pytest.raises(Error, match='stale model map'):
        submit(w, audit)
    audit['map_version'] = 1
    audit['transfers'][0]['verdict'] = 'supported'
    audit['transfers'][0]['evidence_refs'] = refs
    with pytest.raises(Error, match='cannot be marked supported'):
        submit(w, audit)
    audit['transfers'][0]['verdict'] = 'assumption'
    audit['concerns'] = [concern()]
    submit(w, audit)
    t = study.next_task(w)
    review = study_payload('review', refs, context=t['context'])
    review.update(decision='research', concern_resolutions=[dict(resolution(), route='ask_user')])
    submit(w, review)
    assert study.next_task(w)['task']['inquiry']['route'] == 'ask_user'


def test_bundle_preserves_each_claims_passage():
    source = {'id': 'log', 'url': 'urn:test', 'title': 'Log', 'retrieved_at': now(),
              'excerpt': 'QA passed. Signup is blocked.'}
    findings = [{'id': id, 'claim': passage, 'claim_type': 'observation', 'source_ids': ['log'],
                 'claim_support': [{'source_id': 'log', 'passage': passage, 'relation': 'direct',
                                    'rationale': 'Reported status of one prerequisite.'}]}
                for id, passage in [('qa', 'QA passed.'), ('signup', 'Signup is blocked.')]]
    p = evidence.capture_bundle({'sources': [source], 'findings': findings, 'limitations': ['Fixture.']})
    assert [r['claim_support'][0]['passage'] for r in p['records']] == ['QA passed.', 'Signup is blocked.']
