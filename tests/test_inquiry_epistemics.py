import pytest
from vorhersage import study, evidence, reference_research
from vorhersage.common import Error
from test_research_v2 import begin, submit
from test_study import intake


def test_original_qualifiers_and_partial_coverage_are_preserved(tmp_path):
    w, _ = begin(tmp_path)
    text = 'I do not know of any other applicants.'
    refs = [w.import_packet(evidence.capture_finding(text, title='Testimony', excerpt=text,
        source_kind='testimony', attribution='Museum organizer'))['records'][0]['evidence_ref']]
    q = dict(id='competition', input_ids=['outcome'], question='Other applicants?', route='ask_user',
             why_it_matters='Approval uncertainty', action='Ask organizer')
    submit(w, intake([q]))
    answer = dict(status='unresolved', response_state='partial', answer='Competition remains unknown.', evidence_refs=refs,
        reported_facts=[dict(passage='There are no other applicants.', evidence_refs=refs)],
        unresolved_fields=['Actual applicant count'], coverage=[dict(domain='current_state', interpretation='Applicant count', completeness='partial')])
    with pytest.raises(Error, match='preserve its qualifiers'):
        submit(w, answer)
    answer['reported_facts'][0]['passage'] = text
    submit(w, answer)
    t = study.next_task(w)
    assert t['context']['inquiry_answers']['competition']['reported_facts'][0]['passage'] == text
    assert t['context']['coverage']['current_state']['disposition'] == 'unknown'
    with w.store.connect() as c:
        from vorhersage.store import Store
        state = Store.run(c, t['run_id'])[1]
    assert any(x.get('domain') == 'current_state' for x in state['pending'])


def test_declined_answers_do_not_repeat_user_priority():
    q = dict(id='authority', input_ids=['outcome'], route='ask_user')
    state = {'research_plan': {'unknowns': [q]}, 'parameter_support': [dict(model_input='probability', input_id='outcome',
             basis='assumed', target='Opening', transfer_assumptions='Unknown authority')], 'inquiry_answers': {}}
    assert reference_research.priorities(state)[0]['suggested_route'] == 'ask_user'
    for response_state in ('declined', 'inaccessible', 'unknown_to_user', 'deferred'):
        state['inquiry_answers']['authority'] = {'response_state': response_state}
        assert reference_research.priorities(state)[0]['suggested_route'] == 'search'


def test_whole_statements_can_be_selected_without_losing_qualifiers():
    from vorhersage.research_model import verbatim_statement
    text = 'The application is filed. I do not know of any other applicants. Review is next.'
    assert verbatim_statement('I do not know of any other applicants.', text)
    assert not verbatim_statement('know of any other applicants.', text)


def test_answer_state_must_agree_with_status(tmp_path):
    w, refs = begin(tmp_path)
    q = dict(id='authority', input_ids=['outcome'], question='Who reviews?', route='search', why_it_matters='Review gate', action='Read notice')
    submit(w, intake([q]))
    with pytest.raises(Error, match='Answered response_state requires'):
        submit(w, dict(status='unresolved', response_state='answered', answer='Committee reviews.', evidence_refs=refs))


def test_partial_followup_preserves_previous_research_and_conflicts(tmp_path):
    from test_research_v2 import advance, concern, resolution
    from test_study import challenge, study_payload
    w, refs = begin(tmp_path); t = advance(w, refs, 'model_challenge')
    previous = t['context']['coverage']['current_state']
    audit = challenge(t['context']); audit['concerns'] = [concern()]; submit(w, audit)
    t = study.next_task(w)
    review = study_payload('review', refs, context=t['context'])
    review.update(decision='research', concern_resolutions=[resolution()]); submit(w, review)
    submit(w, {'status': 'unresolved', 'response_state': 'partial', 'answer': 'Timing unknown.', 'evidence_refs': [],
        'unresolved_fields': ['Opening date'], 'coverage': [{'domain': 'current_state', 'interpretation': 'Date remains unknown.', 'completeness': 'partial'}]})
    current = study.next_task(w)['context']['coverage']['current_state']
    assert current['previous_coverage'] == previous
    assert current['evidence_refs'] == previous['evidence_refs'] and current['sources_checked'] == previous['sources_checked']
    assert current['disposition'] == 'unknown' and 'Opening date' in current['unknowns']
