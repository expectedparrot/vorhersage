#!/usr/bin/env python3
"""Seed Epiq through its CLI, freeze evidence, and replay the Patriots forecast.

No direct database access, web requests, or model calls. The original research
is imported as analyst transcriptions; this is a storage integration experiment.
"""

import argparse
import copy
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence_packet import fingerprint, materialize_case, validate_packet
from simulate import HERE, replay, save

ACTOR = 'agent:vorhersage-import'
PROJECT_NAME = 'Vorhersage Patriots evidence integration'


class Epiq:
    def __init__(self, db, source=None):
        self.db = Path(db).resolve()
        self.source = Path(source).resolve() if source else None

    def call(self, *args, payload=None):
        env = os.environ.copy()
        prefix = ['epiq']
        if self.source:
            if not (self.source / 'epiq' / '__main__.py').is_file():
                raise ValueError('--epiq-source must point to Epiq\'s src directory.')
            env['PYTHONPATH'] = str(self.source)
            prefix = [sys.executable, '-m', 'epiq']
        result = subprocess.run(
            [*prefix, '--db', str(self.db), '--actor', ACTOR, *args],
            input=json.dumps(payload, allow_nan=False) if payload is not None else None,
            text=True, capture_output=True, env=env, timeout=60, check=False)
        if result.returncode:
            raise ValueError('Epiq command failed: ' + ' '.join(args) + '\n' + (result.stderr or result.stdout))
        envelope = json.loads(result.stdout)
        if envelope.get('schema_version') != '1.0' or envelope.get('status') != 'ok':
            raise ValueError('Unsupported or unsuccessful Epiq response.')
        return envelope['data']


def import_documents(case):
    """Build narrow, inspectable Epiq schema and atomic evidence/claim batch."""
    entities = [{'kind': 'ResearchEntity', 'name': e['name'],
                 'attributes': {'vorhersage_id': e['id']}} for e in case['entities']]
    entity_names = {e['id']: e['name'] for e in case['entities']}
    questions = [
        {'name': 'source_capture', 'subject_kind': 'ResearchCapture', 'value_type': 'Json'},
        {'name': 'finding_record', 'subject_kind': 'ResearchFinding', 'value_type': 'Json'},
        {'name': 'finding_text', 'subject_kind': 'ResearchFinding', 'value_type': 'String'},
        {'name': 'about', 'subject_kind': 'ResearchFinding', 'value_type': 'Ref[ResearchEntity]',
         'definition': {'cardinality': 'many'}},
    ]
    operations = []
    captures = case['captures']
    for id, capture in captures.items():
        entities.append({'kind': 'ResearchCapture', 'name': id, 'role': 'observation',
                         'identity': {'collection': 'patriots_2027_v1', 'capture_id': id}})
        operations.append({
            'op': 'evidence.add', 'ref': id, 'url': capture['url'], 'title': capture['title'],
            'retrieved_at': capture['observed_at'], 'published_at': capture['published_at'],
            'source_type': 'other',
            'locator': {'description': capture['locator'], 'capture_kind': capture['capture_kind']},
            'excerpt': 'Structured analyst transcription, not a verbatim source excerpt:\n'
                       + json.dumps(capture, sort_keys=True, allow_nan=False),
        })
        operations.append({'op': 'claim.assert', 'subject': id, 'question': 'source_capture',
                           'value': capture, 'valid_from': capture['observed_at'],
                           'temporal_basis': 'observed', 'confidence': 'medium', 'evidence_refs': [id]})
    seen = set()
    for response in case['responses'].values():
        for finding in response['payload'].get('findings', []):
            id = finding['id']
            if id in seen:
                raise ValueError('Duplicate finding ID in input: ' + id)
            seen.add(id)
            entities.append({'kind': 'ResearchFinding', 'name': id, 'role': 'observation',
                             'identity': {'collection': 'patriots_2027_v1', 'finding_id': id}})
            base = {'op': 'claim.assert', 'subject': id,
                    'valid_from': max(captures[i]['observed_at'] for i in finding['source_ids']),
                    'temporal_basis': 'observed', 'confidence': 'medium',
                    'evidence_refs': finding['source_ids']}
            operations += [{**base, 'question': 'finding_record', 'value': finding},
                           {**base, 'question': 'finding_text', 'value': finding['claim']}]
            operations += [{**base, 'question': 'about', 'value': entity_names[e]}
                           for e in finding['entity_ids']]
    schema = {'project': {'name': PROJECT_NAME},
              'entity_kinds': ['ResearchEntity', 'ResearchCapture', 'ResearchFinding'],
              'entities': entities, 'questions': questions}
    return schema, operations


def seed(client, case):
    manifest_path = client.db.with_suffix('.seed.json')
    case_hash = fingerprint(case)
    if client.db.exists():
        if not manifest_path.exists():
            raise ValueError('Existing database has no integration manifest; choose a new database.')
        manifest = json.loads(manifest_path.read_text())
        project = client.call('schema')['project']
        if manifest['case_sha256'] != case_hash or manifest['project_id'] != project['project_id']:
            raise ValueError('Seed case or Epiq project changed; choose a new database.')
    schema, operations = import_documents(case)
    client.db.parent.mkdir(parents=True, exist_ok=True)
    client.call('apply', '--input', '-', payload=schema)
    project = client.call('schema')['project']
    save(manifest_path, {'case_sha256': case_hash, 'project_id': project['project_id']})
    result = client.call('batch-write', '--input', '-', payload=operations)
    doctor = client.call('doctor')
    if not doctor['ok']:
        raise ValueError('Epiq integrity check failed.')
    return {'database': str(client.db), 'project_id': project['project_id'],
            'operations': result['count'], 'doctor': doctor,
            'note': 'Original observation times retained; Epiq records the actual import time.'}


def select_records(table, question, ids, prefix):
    rows = {r['name']: r for r in table['rows']}
    records = {}
    for id in ids:
        if id not in rows:
            raise ValueError('Missing Epiq research row: ' + id)
        cell = rows[id]['cells'][question]
        if cell['state'] != 'Answered':
            raise ValueError('Epiq evidence must be assessed before freezing: ' + id + ' / ' + cell['state'])
        record = {'value': cell['value'], 'lineage': cell['lineage'],
                  'subject_id': rows[id]['entity_id'], 'question': question}
        record['sha256'] = fingerprint(record)
        records[prefix + id] = record
    return records


def freeze(client, case, destination):
    destination = Path(destination)
    # Never replace an earlier frozen packet or its replay outputs.
    destination.mkdir(parents=True, exist_ok=False)
    snapshot = destination / 'epiq_snapshot.sqlite'
    client.call('export', '--format', 'sqlite', '--output-path', str(snapshot.resolve()))
    frozen = Epiq(snapshot, client.source)
    project = frozen.call('schema')['project']
    history = frozen.call('history')
    template = copy.deepcopy(case)
    template['capture_ids'] = list(template.pop('captures'))
    finding_ids = []
    for response in template['responses'].values():
        payload = response['payload']
        if 'findings' in payload:
            payload['finding_ids'] = [f['id'] for f in payload.pop('findings')]
            finding_ids.extend(payload['finding_ids'])
    records = select_records(frozen.call('matrix', '--kind', 'ResearchCapture'),
                             'source_capture', template['capture_ids'], 'capture:')
    records.update(select_records(frozen.call('matrix', '--kind', 'ResearchFinding'),
                                  'finding_record', finding_ids, 'finding:'))
    packet = {
        'schema_version': 'vorhersage.epiq-evidence.v1',
        'project': project, 'epiq_version': frozen.call('version'),
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'epiq_recorded_cutoff': max(event['recorded_at'] for event in history),
        'epiq_events': history, 'case_template': template, 'records': records,
        'selection': 'Explicit case capture and finding IDs from one consistent Epiq snapshot.',
        'time_policy': 'Epiq recorded cutoff is actual ingestion history, not the earlier research cutoff. '
                       'Imported observations retain their claimed original capture dates; this does not prove historical availability.',
        'scope': 'Recorded research and judgments; no live research or refitted probabilities.',
    }
    packet['sha256'] = fingerprint(packet)
    validate_packet(packet)
    save(destination / 'evidence_packet.json', packet)
    save(destination / 'case.json', materialize_case(packet))
    return {'packet': str(destination / 'evidence_packet.json'), 'sha256': packet['sha256'],
            'project_id': project['project_id'], 'records': len(records)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['seed', 'freeze', 'replay'])
    parser.add_argument('--epiq-source', type=Path, help='Optional local Epiq src directory; otherwise use installed epiq.')
    parser.add_argument('--db', type=Path, default=HERE / 'epiq_integration' / 'patriots.sqlite')
    parser.add_argument('--case', type=Path, default=HERE / 'researched_case.json')
    parser.add_argument('--out', type=Path, default=HERE / 'epiq_integration' / 'frozen')
    parser.add_argument('--packet', type=Path, help='Frozen packet required for offline replay.')
    args = parser.parse_args()
    try:
        if args.command == 'replay':
            if args.packet is None:
                raise ValueError('--packet is required.')
            case = materialize_case(json.loads(args.packet.read_text()))
            if args.out.exists():
                raise ValueError('Replay output exists; choose a new directory.')
            result = replay(case, args.out)
        else:
            client = Epiq(args.db, args.epiq_source)
            case = json.loads(args.case.read_text())
            result = seed(client, case) if args.command == 'seed' else freeze(client, case, args.out)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
