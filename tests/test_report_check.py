"""Recorded report claims must match the snapshot and the delivered prose."""
import json
import subprocess
import sys

import pytest

from vorhersage import report_check
from vorhersage.common import Error, digest


def bundle(tmp_path):
    full = {'material': {'prediction': {'issued': {'probability': .1}},
        'evidence': [{'evidence_id': 'packet:funding', 'claim': 'First span opens in 2033.',
            'sources': [{'url': 'https://example.org/bridge'}],
            'value': {'first_open': '2033-09-01T00:00:00Z', 'state': 700, 'federal': 1720, 'total': 2420}}]}}
    archive = tmp_path / 'records.json'; archive.write_text(json.dumps(full))
    sha = digest(full)
    context = tmp_path / 'context.json'
    context.write_text(json.dumps({'record_sha256': sha, 'full_material': {'path': str(archive), 'sha256': sha}}))
    report = tmp_path / 'report.md'
    report.write_text('**10% probability** from agent-supplied assumptions.\nFirst opening: September 2033. [Source](https://example.org/bridge)\n')
    claims = {'record_sha256': sha, 'claims': [
        {'pointer': '/material/prediction/issued/probability', 'value': .1, 'format': 'percent', 'text': '**10% probability**'},
        {'pointer': '/material/evidence/0/value/first_open', 'value': '2033-09-01T00:00:00Z', 'format': 'month_year',
         'text': 'First opening: September 2033.', 'evidence_ids': ['packet:funding']}],
        'arithmetic': [{'terms': ['/material/evidence/0/value/state', '/material/evidence/0/value/federal'], 'total': '/material/evidence/0/value/total'}]}
    inventory = tmp_path / 'claims.json'; inventory.write_text(json.dumps(claims))
    return context, report, inventory, archive


def test_checks_valid_recorded_claims_and_required_citations(tmp_path):
    args = bundle(tmp_path)
    assert report_check.check(*args[:3])['ok']
    args[1].write_text(args[1].read_text().replace('[Source](https://example.org/bridge)', ''))
    result = report_check.check(*args[:3])
    assert {'missing_citations', 'missing_source_link'} <= {i['code'] for i in result['issues']}


def test_date_drift_and_misleading_method_claims_fail(tmp_path):
    args = bundle(tmp_path)
    args[1].write_text(args[1].read_text().replace('September 2033', 'September 2037') +
        'The agent issued a calibrated probability estimate. No language model was used to generate the probability itself.')
    result = report_check.check(*args[:3])
    assert {'passage_mismatch', 'unsupported_calibration', 'misleading_attribution'} <= {i['code'] for i in result['issues']}


def test_stale_claims_wrong_values_and_component_total_fail(tmp_path):
    args = bundle(tmp_path)
    full = json.loads(args[3].read_text()); full['material']['evidence'][0]['value']['total'] = 2130
    args[3].write_text(json.dumps(full))
    context = json.loads(args[0].read_text()); context['record_sha256'] = context['full_material']['sha256'] = digest(full)
    args[0].write_text(json.dumps(context))
    claims = json.loads(args[2].read_text()); claims['claims'][0]['value'] = .2
    args[2].write_text(json.dumps(claims))
    result = report_check.check(*args[:3])
    assert {'stale_claims', 'value_mismatch', 'arithmetic_mismatch'} <= {i['code'] for i in result['issues']}


def test_modified_snapshot_rejected_and_cli_failure_is_nonzero(tmp_path):
    args = bundle(tmp_path)
    cmd = [sys.executable, '-m', 'vorhersage', 'report', 'check', '--context', str(args[0]), '--report', str(args[1]), '--claims', str(args[2])]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    args[1].write_text('No report citations or recorded numbers.')
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 1 and 'report_fidelity_failed' in result.stderr
    args[3].write_text('{}')
    with pytest.raises(Error, match='hash mismatch'):
        report_check.check(*args[:3])


def test_negated_calibration_disclosure_is_allowed(tmp_path):
    args = bundle(tmp_path)
    args[1].write_text(args[1].read_text() + 'This is not a calibrated probability estimate.')
    assert report_check.check(*args[:3])['ok']


def test_date_rendering_preserves_recorded_timezone():
    assert report_check.rendered('2035-12-31T23:59:59-05:00', 'date') == '2035-12-31'
    assert report_check.rendered('2035-12-31T23:59:59-05:00', 'month_year') == 'December 2035'


def test_private_testimony_and_dependencies_cannot_be_removed(tmp_path):
    from vorhersage.evidence import capture_finding, citation_anchor, audit
    record = capture_finding('Application filed.', title='Participant testimony', excerpt='I filed the application.',
                             source_kind='testimony', attribution='Museum organizer', message_ref='internal:message-7')['records'][0]
    assert audit(capture_finding('Filed.', title='Testimony', excerpt='Filed.', source_kind='testimony',
                                 attribution='Organizer'))['dependence_groups']
    args = bundle(tmp_path)
    full = json.loads(args[3].read_text())
    full['material']['evidence'].append({'evidence_id': 'private:filing', **record})
    full['material']['model'] = {'parameter_support': [{'model_input': 'probability', 'value': .1,
        'evidence_refs': [{'packet_id': 'private', 'record_id': 'filing'}]}]}
    args[3].write_text(json.dumps(full))
    sha = digest(full)
    args[0].write_text(json.dumps({'record_sha256': sha, 'full_material': {'path': str(args[3]), 'sha256': sha}}))
    claims = json.loads(args[2].read_text()); claims['record_sha256'] = sha
    row = {'pointer': '/material/model/parameter_support/0/value', 'value': .1, 'format': 'percent',
           'text': '**10% probability**', 'evidence_ids': ['private:filing']}
    claims['claims'].append(row)
    args[2].write_text(json.dumps(claims))
    anchor = citation_anchor('private:filing')
    args[1].write_text(args[1].read_text() + f'Application filed.[^{anchor}]\n\n[^{anchor}]: Museum organizer, private testimony.\n')
    assert report_check.check(*args[:3])['ok']
    assert 'internal:message-7' not in args[1].read_text()
    row['evidence_ids'] = []
    args[2].write_text(json.dumps(claims))
    assert 'missing_claim_citation' in {i['code'] for i in report_check.check(*args[:3])['issues']}
    # The issued forecast also retains dependencies even with an empty author inventory.
    claims['claims'].pop(); args[2].write_text(json.dumps(claims))
    args[1].write_text(args[1].read_text().replace('Museum organizer', 'Someone else'))
    assert 'missing_source_link' in {i['code'] for i in report_check.check(*args[:3])['issues']}


def test_private_source_requires_attribution_and_public_source_requires_url():
    from vorhersage.evidence import capture_finding
    with pytest.raises(Error, match='attribution'):
        capture_finding('Filed.', title='Testimony', excerpt='Filed.', source_kind='testimony')
    with pytest.raises(Error, match='URL'):
        capture_finding('Filed.', title='Public record', excerpt='Filed.')


def test_numeric_equivalence_is_not_display_tolerance():
    assert report_check.equivalent(.1 + .2, .3)
    assert not report_check.equivalent(.30001, .3)
    assert not report_check.equivalent(True, 1)
    assert not report_check.equivalent(float('nan'), float('nan'))
    assert not report_check.equivalent(float('inf'), float('inf'))
    assert report_check.rendered(.37625, 'percent', precision=1) == '37.6%'
    assert report_check.rendered(.125, 'percent', precision=0) == '12%'
    assert report_check.rendered(.125, 'percent', precision=0, rounding='half_up') == '13%'
    assert report_check.rendered(0, 'percent', precision=1) == '0.0%'
    assert report_check.rendered(1, 'percent', precision=1) == '100.0%'
    for invalid in (True, -1, 13):
        with pytest.raises(Error, match='Precision'):
            report_check.rendered(.3, 'percent', precision=invalid)


def test_explicit_report_precision_preserves_snapshot(tmp_path):
    args = bundle(tmp_path)
    full = json.loads(args[3].read_text())
    full['material']['prediction']['issued']['probability'] = .37625
    args[3].write_text(json.dumps(full)); original = args[3].read_bytes()
    sha = digest(full)
    args[0].write_text(json.dumps({'record_sha256': sha, 'full_material': {'path': str(args[3]), 'sha256': sha}}))
    claims = json.loads(args[2].read_text()); claims['record_sha256'] = sha
    claims['claims'][0].update(value=.37625, precision=1, text='**37.6% probability**')
    args[2].write_text(json.dumps(claims))
    args[1].write_text(args[1].read_text().replace('10%', '37.6%'))
    assert report_check.check(*args[:3])['ok']
    assert args[3].read_bytes() == original
    claims['claims'][0]['value'] = .3763
    args[2].write_text(json.dumps(claims))
    assert 'value_mismatch' in {i['code'] for i in report_check.check(*args[:3])['issues']}
