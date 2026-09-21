import pytest
from vorhersage import approval_handoff, report_context
from vorhersage.common import Error
from test_research_v2 import begin


def receipt(scope='design_approval', action='approved'):
    return {'receipt_ref': 'receipt-1', 'actor_kind': 'user', 'subject_sha256': 'fixture-hash', 'scope': scope,
        'action': action, 'occurred_at': '2020-02-01T00:00:00Z', 'recorded_at': '2020-02-03T00:00:00Z',
        'imported': True, 'private_message': 'Private user content must not be exported.'}


def test_no_new_gate_and_actor_labels_are_not_verification():
    assert approval_handoff.inspect('fixture-hash')['status'] == 'not_required'
    result = approval_handoff.inspect('fixture-hash', ['receipt-1'], required_scopes=['design_approval'])
    assert result['status'] == 'missing' and result['records'][0]['verification'] == 'unverified'
    with pytest.raises(Error, match='opaque receipt'):
        approval_handoff.inspect('fixture-hash', [{'by': 'user', 'verified': True}])
    with pytest.raises(Error, match='Host did not verify'):
        approval_handoff.inspect('fixture-hash', ['receipt-1'], verifier=lambda ref: None)


def test_host_receipt_is_scoped_versioned_and_redacted():
    record = receipt()
    result = approval_handoff.inspect('fixture-hash', ['receipt-1'], required_scopes=['design_approval'], verifier=lambda ref: record)
    assert result['status'] == 'verified'
    assert result['records'][0]['occurred_at'] != result['records'][0]['recorded_at']
    assert 'private_message' not in str(result) and 'Private user content' not in str(result)
    for scope, action in [('task_authorization', 'approved'), ('optional_review', 'skipped')]:
        result = approval_handoff.inspect('fixture-hash', ['receipt-1'], required_scopes=['design_approval'], verifier=lambda ref: receipt(scope, action))
        assert result['status'] == 'missing'
    with pytest.raises(Error, match='different artifact'):
        approval_handoff.inspect('changed-hash', ['receipt-1'], verifier=lambda ref: record)


def test_handoff_does_not_confuse_forecast_readiness_with_approval(tmp_path):
    w, _ = begin(tmp_path)
    context = report_context.export(w.store)
    assert context['authoring']['approvals']['status'] == 'not_required'
    assert not context['reportability']['ready_for_report_agent']
    other = report_context.export(w.store, required_approval_scopes=['design_approval'])
    assert other['record_sha256'] == context['record_sha256']
    assert other['authoring']['approvals']['status'] == 'missing'
