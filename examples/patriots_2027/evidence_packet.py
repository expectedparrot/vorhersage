"""Portable Epiq evidence packets; verification and replay need only stdlib."""

import copy
import hashlib
import json
from datetime import datetime


def fingerprint(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Evidence times must include a timezone.')
    return parsed


def validate_packet(packet):
    if packet.get('schema_version') != 'vorhersage.epiq-evidence.v1':
        raise ValueError('Unsupported evidence packet version.')
    body = {k: v for k, v in packet.items() if k != 'sha256'}
    if fingerprint(body) != packet.get('sha256'):
        raise ValueError('Evidence packet hash mismatch.')
    if not packet['project'].get('project_id'):
        raise ValueError('Missing Epiq project identity.')
    template = packet['case_template']
    cutoff = timestamp(template['information_as_of'])
    recorded_cutoff = timestamp(packet['epiq_recorded_cutoff'])
    assertions = {}
    for event in packet['epiq_events']:
        if timestamp(event['recorded_at']) > recorded_cutoff:
            raise ValueError('Event is after the Epiq recorded cutoff.')
        if event['event_type'] == 'claim.assert':
            assertions[event['payload']['claim_id']] = event['payload']
    expected = {'capture:' + i for i in template['capture_ids']}
    for response in template['responses'].values():
        expected.update('finding:' + i for i in response['payload'].get('finding_ids', []))
    if set(packet['records']) != expected:
        raise ValueError('Evidence packet is missing records or contains unselected records.')
    for key, record in packet['records'].items():
        if fingerprint({k: v for k, v in record.items() if k != 'sha256'}) != record['sha256']:
            raise ValueError('Evidence record hash mismatch: ' + key)
        if not record['lineage'] or not all(x.get('claim_id') and x.get('evidence_id')
                                            and x.get('excerpt') and x.get('source')
                                            for x in record['lineage']):
            raise ValueError('Missing claim/evidence lineage: ' + key)
        for link in record['lineage']:
            assertion = assertions.get(link['claim_id'], {})
            if (link.get('value') != record['value'] or assertion.get('value') != record['value']
                    or assertion.get('subject_id') != record['subject_id']
                    or link['evidence_id'] not in assertion.get('evidence_ids', [assertion.get('evidence_id')])):
                raise ValueError('Record does not match its Epiq assertion: ' + key)
        if key.startswith('capture:'):
            if timestamp(record['value']['observed_at']) > cutoff:
                raise ValueError('Capture is after the research cutoff: ' + key)
        else:
            finding = record['value']
            if key != 'finding:' + finding['id']:
                raise ValueError('Finding identity mismatch.')
            if not finding['source_ids'] or any('capture:' + i not in expected for i in finding['source_ids']):
                raise ValueError('Finding references an uncaptured source.')
            expected_evidence = {link['evidence_id'] for i in finding['source_ids']
                                 for link in packet['records']['capture:' + i]['lineage']}
            if {link['evidence_id'] for link in record['lineage']} != expected_evidence:
                raise ValueError('Finding and capture evidence disagree; review is required: ' + key)
    return packet


def materialize_case(packet):
    """Load evidence exclusively from packet records; judgments remain fixtures."""
    validate_packet(packet)
    case = copy.deepcopy(packet['case_template'])

    def value(key):
        record = packet['records'][key]
        result = copy.deepcopy(record['value'])
        result['epiq_reference'] = {
            'project_id': packet['project']['project_id'],
            'record_key': key, 'record_sha256': record['sha256'],
            'claim_ids': sorted({x['claim_id'] for x in record['lineage']}),
            'evidence_ids': sorted({x['evidence_id'] for x in record['lineage']}),
        }
        return result

    case['captures'] = {i: value('capture:' + i) for i in case.pop('capture_ids')}
    for response in case['responses'].values():
        payload = response['payload']
        if 'finding_ids' in payload:
            payload['findings'] = [value('finding:' + i) for i in payload.pop('finding_ids')]
    case['run_id'] = 'patriots_2027_epiq_' + packet['sha256'][:12]
    case['evidence_packet'] = copy.deepcopy(packet)
    return case
