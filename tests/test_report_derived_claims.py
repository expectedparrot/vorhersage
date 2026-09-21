import json
import pytest
from vorhersage import report_check
from vorhersage.report_claims import evaluate
from vorhersage.common import Error, digest
from test_report_check import bundle


def dated(tmp_path):
    args = bundle(tmp_path); full = json.loads(args[3].read_text())
    full['material']['question'] = {'start': '2032-02-01T00:00:00Z', 'end': '2032-03-01T00:00:00Z'}
    args[3].write_text(json.dumps(full)); sha = digest(full)
    args[0].write_text(json.dumps({'record_sha256': sha, 'full_material': {'path': str(args[3]), 'sha256': sha}}))
    claims = json.loads(args[2].read_text()); claims['record_sha256'] = sha
    return args, full, claims


def test_deadline_arithmetic_and_inventory_gaps(tmp_path):
    args, full, claims = dated(tmp_path)
    args[1].write_text(args[1].read_text() + '\nOpening is 28 days away.\n')
    args[2].write_text(json.dumps(claims))
    assert any(x['token'] == '28' for x in report_check.check(*args[:3])['coverage']['unchecked'])
    row = dict(expression={'op': 'duration', 'terms': ['/material/question/start', '/material/question/end'],
        'mode': 'calendar_days', 'timezone': 'UTC'}, value=28, text='Opening is 28 days away.')
    claims['claims'].append(row); args[2].write_text(json.dumps(claims))
    assert not report_check.check(*args[:3])['ok']
    row.update(value=29, text='Opening is 29 days away.')
    args[1].write_text(args[1].read_text().replace('28 days', '29 days')); args[2].write_text(json.dumps(claims))
    assert report_check.check(*args[:3])['ok']
    suggested = report_check.suggest(args[0], args[1])
    assert suggested['claims'] == [] and any(r['pointer'].endswith('/probability') for r in suggested['suggestions'])


def test_elapsed_calendar_and_inclusive_are_distinct():
    full = {'material': {'start': '2032-03-14T00:00:00-05:00', 'end': '2032-03-15T00:00:00-04:00', 'a': .4, 'b': .7}}
    expression = {'op': 'duration', 'terms': ['/material/start', '/material/end'], 'mode': 'elapsed', 'unit': 'hours'}
    assert evaluate(expression, full) == 23
    expression.update(mode='calendar_days', timezone='America/New_York')
    assert evaluate(expression, full) == 1
    expression['inclusive'] = True
    assert evaluate(expression, full) == 2
    assert evaluate({'op': 'product', 'terms': ['/material/a', '/material/b']}, full) == pytest.approx(.28)
    with pytest.raises(Error, match='Unsupported'):
        evaluate({'op': 'eval', 'terms': ['/material/a']}, full)
    expression['mode'] = 'business_days'
    with pytest.raises(Error, match='business calendars'):
        evaluate(expression, full)


def test_exclusions_require_reason_and_do_not_hide_fidelity_errors(tmp_path):
    args, full, claims = dated(tmp_path)
    args[1].write_text(args[1].read_text() + '\nReferences: 2030 edition.\n')
    claims['exclusions'] = [{'text': 'References: 2030 edition.', 'reason': 'Bibliography year, not a forecast input.'}]
    args[2].write_text(json.dumps(claims))
    result = report_check.check(*args[:3])
    assert result['ok'] and not any(x['token'] == '2030' for x in result['coverage']['unchecked'])
    claims['claims'][0]['value'] = .2
    args[2].write_text(json.dumps(claims))
    assert not report_check.check(*args[:3])['ok']
    claims['exclusions'][0]['reason'] = ''
    args[2].write_text(json.dumps(claims))
    assert 'invalid_exclusion' in {x['code'] for x in report_check.check(*args[:3])['issues']}
