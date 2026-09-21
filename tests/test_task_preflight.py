import json
import subprocess
import sys
import pytest
from vorhersage import study
from vorhersage.common import Error
from vorhersage.schemas import check
from test_research_v2 import begin
from test_study import intake


def dump(w):
    with w.store.connect() as c:
        return list(c.iterdump())


def test_preflight_rolls_back_every_table_and_real_submit_still_checks_revision(tmp_path):
    w, refs = begin(tmp_path)
    task = study.next_task(w)
    assert task['answer_template']['rationale'] is None
    before = dump(w)
    with pytest.raises(Error):
        study.submit(w, task, answer=task['answer_template'], check_only=True)
    assert dump(w) == before
    assert study.submit(w, task, answer=intake(), check_only=True)['valid']
    assert dump(w) == before
    accepted = study.submit(w, task, answer=intake())
    assert accepted['revision'] > task['revision']
    assert study.submit(w, task, answer=intake(), check_only=True)['duplicate']
    task['submission']['idempotency_key'] = 'new-attempt'
    with pytest.raises(Error, match='stale'):
        study.submit(w, task, answer=intake(), check_only=True)


def test_structural_errors_and_file_recovery_are_actionable(tmp_path):
    with pytest.raises(Error) as e:
        check({'rationale': 12, 'inputs': False, 'unknowns': []}, 'intake')
    assert len(e.value.details) == 2
    with pytest.raises(Error) as e:
        check({'status': 'imaginary', 'answer': 42}, 'inquiry')
    assert e.value.details[0]['missing_fields'] == ['evidence_refs']
    assert any(x['expected'].get('enum') == ['answered', 'unresolved'] for x in e.value.details)
    w, refs = begin(tmp_path)
    out = tmp_path / 'task.json'; out.write_text('user edits')
    with pytest.raises(Error) as e:
        study.next_task(w, out)
    assert e.value.code == 'task_output_exists' and out.read_text() == 'user edits'


def test_cli_check_is_nonmutating(tmp_path):
    w, refs = begin(tmp_path)
    out = tmp_path / 'task.json'; task = study.next_task(w, out)
    task['submission']['payload'] = intake(); out.write_text(json.dumps(task))
    before = dump(w)
    result = subprocess.run([sys.executable, '-m', 'vorhersage', 'submit', '--project', str(w.store.root),
        '--from', str(out), '--check', '--json'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['data']['check_only']
    assert dump(w) == before


def test_assessment_preflight_does_not_store_model_or_consume_usage(tmp_path):
    from test_research_v2 import advance
    from test_study import study_payload
    w, refs = begin(tmp_path)
    task = advance(w, refs, 'assessment')
    task = study.next_task(w)
    answer = study_payload('assessment', refs, context=task['context'])
    before = dump(w)
    assert study.submit(w, task, answer=answer, usage={'searches': 1, 'model_calls': 1, 'cost_usd': .1}, check_only=True)['valid']
    assert dump(w) == before
    assert study.next_task(w)['task']['kind'] == 'assessment'
