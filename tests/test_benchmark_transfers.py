import copy
import pytest
from vorhersage.common import Error
from vorhersage.research_model import validate_transfer
from test_research_v2 import begin, advance, submit
from test_study import study_payload, challenge
from vorhersage import study


def transfer():
    measure = {k: 'not applicable' for k in ('quantity', 'units', 'population', 'denominator', 'outcome',
               'horizon', 'clock_origin', 'stage', 'commitment_term')}
    measure.update(quantity='duration', units='days', population='Museum projects', denominator='Completed projects',
                   outcome='Opening', horizon='Full cycle', clock_origin='Application', stage='Application')
    target = dict(measure, quantity='probability', units='probability', horizon='Remaining 45 days', stage='Permits cleared')
    return {'version': 1, 'source': measure, 'target': target, 'mapping': 'Assume a broad completion probability after conditioning on progress.',
            'quantitative_support': 'judgment'}


def test_estimand_mismatches_cannot_be_direct_measurements():
    row = {'basis': 'measured', 'transfer': transfer()}
    with pytest.raises(Error, match='Different source/target'):
        validate_transfer(row)
    row['basis'] = 'extrapolated'
    assert 'stage' in validate_transfer(row)
    row['transfer']['quantitative_support'] = 'direct'
    with pytest.raises(Error, match='cannot provide direct'):
        validate_transfer(row)
    row['transfer']['target'] = copy.deepcopy(row['transfer']['source'])
    row['basis'] = 'measured'
    assert validate_transfer(row) == []
    row['transfer']['target']['commitment_term'] = '12 months'
    with pytest.raises(Error, match='commitment_term'):
        validate_transfer(row)


def test_workflow_keeps_qualitative_support_separate_from_numeric_support(tmp_path):
    w, refs = begin(tmp_path); t = advance(w, refs, 'assessment')
    answer = study_payload('assessment', refs, context=t['context'])
    row = answer['parameter_support'][0]
    row.update(basis='extrapolated', evidence_refs=refs)
    with pytest.raises(Error, match='versioned transfer'):
        submit(w, answer)
    row['transfer'] = transfer()
    submit(w, answer)
    t = study.next_task(w); audit = challenge(t['context'])
    with pytest.raises(Error, match='separately'):
        submit(w, audit)
    audit['transfers'][0].update(source_fidelity='verified', directional_relevance='relevant', quantitative_support='judgment',
                                 verdict='supported', evidence_refs=refs)
    with pytest.raises(Error, match='cannot be marked quantitatively'):
        submit(w, audit)
    audit['transfers'][0]['verdict'] = 'assumption'
    with pytest.raises(Error, match='needs a concern'):
        submit(w, audit)
    audit['concerns'] = [{'id': 'transfer', 'model_inputs': ['probability'], 'question': 'Can remaining duration be observed?',
        'disposition': 'retain_assumption', 'rationale': 'No eligible cohort.', 'action': 'Ask for a dated remaining-work schedule.'}]
    submit(w, audit)
    assert study.next_task(w)['context']['model_challenge']['transfers'][0]['quantitative_support'] == 'judgment'
