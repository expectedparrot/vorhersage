"""Reporting handoff preserves numbers, provenance, selection, and disclosure."""
import json
import subprocess
import sys

import pytest

from vorhersage import report_context, study, workbench
from vorhersage.common import Error, digest
from vorhersage.store import Store
from test_research_v2 import begin, submit
from test_study import study_payload
from test_workflow import run_spec
from test_workbench import case, post, initial, finish, checkpoint, plan


def complete(w, refs):
    while (t := study.next_task(w))['disposition'] == 'actionable':
        submit(w, study_payload(t['task']['kind'], refs, context=t['context']))
    return study.show(w.store)


def test_issued_context_contains_forecast_model_sources_and_preserves_state(tmp_path):
    w, refs = begin(tmp_path)
    result = complete(w, refs)
    before = w.status()
    path = tmp_path / 'analysis' / 'context.json'
    receipt = report_context.export(w.store, output=path)
    context = json.loads(path.read_text())
    archive = json.loads(open(receipt['full_material']['path']).read())
    assert context['reportability']['ready_for_report_agent']
    assert context['material']['prediction']['issued']['forecast_id'] == result['forecast_id']
    assert context['material']['prediction']['issued']['probability'] == .6
    assert context['material']['model']['model_map']['version'] == 1
    assert context['material']['model']['model_challenge']['transfers']
    assert context['material']['evidence'][0]['evidence_id'] == refs[0]['packet_id'] + ':' + refs[0]['record_id']
    assert digest(archive) == context['record_sha256']
    assert report_context.export(w.store, output=path)['record_sha256'] == context['record_sha256']
    assert w.status() == before
    assert not (w.store.root / 'report.html').exists()


def test_working_revision_does_not_present_previous_assessment_as_current(tmp_path):
    w, refs = begin(tmp_path)
    issued = complete(w, refs)
    study.revise(w, reason='New source', refs=refs)
    c = report_context.export(w.store)
    assert not c['reportability']['ready_for_report_agent']
    assert c['material']['prediction']['status'] == 'revision_in_progress'
    assert c['material']['prediction']['issued'] is None
    assert c['material']['prediction']['previous_issued']['forecast_id'] == issued['forecast_id']
    assert c['material']['model']['assessment'] is None
    assert c['material']['latest_work'] == {}


def test_portfolio_selection_rejects_ambiguity_and_cross_question_runs(tmp_path):
    w, refs = begin(tmp_path)
    first = study.binding(w.store)['run_id']
    other = w.start(run_spec(forecaster='second', mode='prospective'))['run_id']
    with pytest.raises(Error, match='Select --run explicitly'):
        report_context.export(w.store, question_id='factory')
    c = report_context.export(w.store, run_id=other)
    assert c['selection']['run_id'] == other
    assert report_context.export(w.store)['selection']['run_id'] == first
    with pytest.raises(Error, match='different question'):
        report_context.export(w.store, question_id='other', run_id=other)


def test_bounded_view_keeps_full_passages_in_snapshot(tmp_path):
    w, refs = begin(tmp_path)
    t = study.next_task(w)
    answer = study_payload('intake', refs)
    answer['rationale'] = 'z' * 100000
    submit(w, answer)
    path = tmp_path / 'context.json'
    receipt = report_context.export(w.store, output=path)
    c = json.loads(path.read_text())
    full = json.loads(open(receipt['full_material']['path']).read())
    assert c['omission_count'] > 0 and len(path.read_text()) < 70000
    assert len(full['material']['methodology']['research_plan']['rationale']) == 100000
    assert any('research_plan/rationale' in o['path'] for o in c['omissions'])


def test_workbench_handoff_never_reveals_private_prices(case, tmp_path):
    w, vault, cid, _ = case
    post(case, 'initial', initial())
    post(case, 'plan', plan())
    post(case, 'checkpoint', checkpoint())
    path = tmp_path / 'context.json'
    receipt = report_context.export(w.store, case_id=cid, output=path)
    text = path.read_text() + open(receipt['full_material']['path']).read()
    assert 'secret_price' not in text and 'midpoint' not in text
    assert not receipt['reportability']['ready_for_report_agent']
    post(case, 'finish', finish())
    c = report_context.export(w.store, case_id=cid)
    assert c['reportability']['ready_for_report_agent']
    assert c['material']['prediction']['issued'] is None
    assert c['material']['market']['disclosure'] == 'hidden'
    workbench.reveal(w.store, cid, vault, skip_refresh=True)
    c = report_context.export(w.store, case_id=cid)
    assert c['material']['market']['comparison']['target']['midpoint'] == pytest.approx(.7)


def test_cli_handoff_and_output_protection(tmp_path):
    w, refs = begin(tmp_path)
    output = tmp_path / 'context.json'
    p = subprocess.run([sys.executable, '-m', 'vorhersage', 'report', 'context', '--project', str(w.store.root),
                        '--output', str(output)], text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)['data']['reportability']['draft_available']
    assert json.loads(output.read_text())['schema_version'] == 'vorhersage.report_context.v1'
    output.write_text('{"user_content":true}')
    with pytest.raises(Error, match='Output exists'):
        report_context.export(w.store, output=output)
    with pytest.raises(Error, match='internal project state'):
        report_context.export(w.store, output=w.store.path.parent / 'bad.json')
    with pytest.raises(Error, match='.json'):
        report_context.export(w.store, output=tmp_path / 'report.html')


def test_handoff_checks_the_forecast_manifest_before_export(tmp_path):
    w, refs = begin(tmp_path)
    result = complete(w, refs)
    # A valid artifact hash does not excuse a broken link in the issued manifest.
    with w.store.connect() as c:
        original = Store.artifact(c, result['forecast_id'])
    from unittest.mock import patch
    # Save the reader before replacing the class attribute to avoid recursion.
    reader = Store.artifact
    def altered(c, id, kind=None):
        value = reader(c, id, kind)
        if id == result['forecast_id']:
            value['input_manifest'][next(iter(value['input_manifest']))] = 'invalid'
        return value
    with patch.object(Store, 'artifact', side_effect=altered):
        with pytest.raises(Error, match='integrity failure'):
            report_context.export(w.store)
    with w.store.connect() as c:
        assert Store.artifact(c, result['forecast_id']) == original
