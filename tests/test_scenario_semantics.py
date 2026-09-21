import copy
import pytest
from vorhersage.common import Error
from vorhersage.scenarios import calculate
from test_research_v2 import begin, advance, submit
from test_study import support, model_map, challenge
from vorhersage import study


def mixture():
    return {'scenarios': [dict(id=sid, description=sid, weight=.5, probability=p, rationale='Fixture',
            evidence_refs=[], unknowns=[], semantics={'version': 1, 'conditioning_event': sid,
                'target_relation': relation}) for sid, p, relation in [('opened', 1, 'entails_yes'), ('late', 0, 'entails_no')]],
            'partition_justification': 'Opened by deadline or not.'}


def test_entailment_and_residual_risk():
    model = mixture()
    assert calculate(model)['probability'] == .5
    bad = copy.deepcopy(model); bad['scenarios'][0]['probability'] = .7
    with pytest.raises(Error, match='definitionally fixed'):
        calculate(bad)
    bad = copy.deepcopy(model); bad['scenarios'][0]['probability_range'] = [.7, 1]
    with pytest.raises(Error, match='definitionally fixed'):
        calculate(bad)
    model['scenarios'][0].update(probability=.7, semantics={'version': 1, 'conditioning_event': 'Permits cleared',
        'target_relation': 'unresolved'})
    with pytest.raises(Error, match='residual_event'):
        calculate(model)
    model['scenarios'][0]['semantics'].update(residual_event='Opening by deadline', non_overlap_rationale='Permits do not establish opening.')
    assert calculate(model)['probability'] == .35
    for row in model['scenarios']:
        row.pop('semantics')
    assert calculate(model)['semantic_review_gaps'] == ['opened', 'late']


def test_new_workflow_requires_semantics_and_exact_event_review(tmp_path):
    w, refs = begin(tmp_path); task = advance(w, refs, 'assessment')
    answer = dict(mixture(), method='scenario_mixture', rationale='Synthetic', limitations=[], evidence_refs=[])
    answer['parameter_support'] = support(answer); answer['model_map'] = model_map(answer, task['context'])
    bad = copy.deepcopy(answer); bad['scenarios'][0].pop('semantics')
    with pytest.raises(Error, match='semantics version 1'):
        submit(w, bad)
    submit(w, answer)
    task = study.next_task(w)
    assert task['context']['event_alignment']['yes'] == task['context']['run']['question']['yes']
    review = challenge(task['context'], ['opened', 'late'])
    review.pop('event_alignment')
    with pytest.raises(Error, match='event_alignment'):
        submit(w, review)
    submit(w, challenge(task['context'], ['opened', 'late']))


def test_new_runs_cannot_opt_out_of_semantics(tmp_path):
    from test_workflow import question, run_spec
    from vorhersage.workflow import Workflow
    w = Workflow(tmp_path); w.store.init('Museum'); w.question(question())
    with pytest.raises(Error, match='cannot downgrade model_semantics_version'):
        w.start(run_spec(research_contract='structured_v2', model_semantics_version=0))


def test_conditional_path_receives_component_guidance(tmp_path):
    w, refs = begin(tmp_path); t = advance(w, refs, 'assessment')
    answer = {'method': 'conditional_path', 'rationale': 'Single final event.', 'limitations': [], 'evidence_refs': [],
        'components': [{'id': 'target', 'conditional_on': None, 'probability': .6, 'rationale': 'Assumed.', 'evidence_refs': []}],
        'nested_events_justification': 'The only component is the target.'}
    answer['parameter_support'] = support(answer); answer['model_map'] = model_map(answer, t['context'])
    submit(w, answer); task = study.next_task(w)
    assert 'final component' in task['task']['instruction'] and 'funding/delay' not in task['task']['instruction']
    submit(w, challenge(task['context']))
