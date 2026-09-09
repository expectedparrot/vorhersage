"""Packet invariants and a real Epiq CLI round trip in disposable databases."""

import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from epiq_bridge import Epiq, freeze, import_documents, seed
from evidence_packet import fingerprint, materialize_case, validate_packet
from simulate import HERE, Workflow, digest


def finish(case):
    workflow = Workflow(case)
    while (task := workflow.next())['disposition'] == 'actionable':
        id = task['task']['id']
        fixture = case['responses'][id]
        workflow.submit({'task_id': id, 'expected_revision': task['revision'],
                         'idempotency_key': 'test_' + id,
                         'disposition': fixture.get('disposition', 'completed'),
                         'payload': fixture['payload']})
    return workflow


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((HERE / 'epiq_integration/frozen/evidence_packet.json').read_text())

    def test_portable_replay_pins_evidence_and_matches_researched_forecast(self):
        # No Epiq executable, import, database connection or original case is needed.
        case = materialize_case(self.packet)
        run = finish(case)
        a = run.state['artifacts']
        forecast = a['forecast_ne_lxi']
        self.assertAlmostEqual(forecast['probability'], 0.06048)
        self.assertEqual(forecast['evidence_packet_sha256'], self.packet['sha256'])
        self.assertEqual(forecast['epiq_project_id'], self.packet['project']['project_id'])
        self.assertEqual(a['epiq_packet']['packet'], self.packet)
        self.assertEqual(a['f_season']['epiq_reference']['claim_ids'],
                         [self.packet['records']['finding:f_season']['lineage'][0]['claim_id']])
        for id, expected in forecast['input_manifest'].items():
            self.assertEqual(digest(a[id]), expected)

    def test_tampering_and_bypassing_packet_are_rejected(self):
        self.packet['records']['capture:c_season']['value']['observation']['wins'] = 1
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            materialize_case(self.packet)
        self.setUp()
        case = materialize_case(self.packet)
        case['captures']['c_season']['observation']['wins'] = 1
        with self.assertRaisesRegex(ValueError, 'differs from its frozen'):
            Workflow(case)

    def test_rehashed_value_must_still_match_epiq_assertion(self):
        record = self.packet['records']['capture:c_season']
        record['value']['observation']['wins'] = 1
        record['sha256'] = fingerprint({k: v for k, v in record.items() if k != 'sha256'})
        self.packet['sha256'] = fingerprint({k: v for k, v in self.packet.items() if k != 'sha256'})
        with self.assertRaisesRegex(ValueError, 'does not match its Epiq assertion'):
            validate_packet(self.packet)

    def test_original_research_cutoff_is_enforced_separately(self):
        self.packet['case_template']['information_as_of'] = '2026-09-08T00:00:00Z'
        self.packet['sha256'] = fingerprint({k: v for k, v in self.packet.items() if k != 'sha256'})
        with self.assertRaisesRegex(ValueError, 'after the research cutoff'):
            validate_packet(self.packet)


class EpiqRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        default = HERE.parents[2] / 'epiq/epiq/src'
        source = Path(os.environ.get('EPIQ_SOURCE', default))
        cls.source = source if (source / 'epiq/__main__.py').is_file() else None
        if not cls.source and not shutil.which('epiq'):
            raise unittest.SkipTest('Install epiq or set EPIQ_SOURCE to its src directory.')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.client = Epiq(self.root / 'research.sqlite', self.source)
        self.case = json.loads((HERE / 'researched_case.json').read_text())
        seed(self.client, self.case)

    def test_seed_retry_is_idempotent_and_foreign_database_rejected(self):
        before = self.client.call('doctor')['counts']
        seed(self.client, self.case)
        self.assertEqual(self.client.call('doctor')['counts'], before)
        changed = copy.deepcopy(self.case)
        changed['information_as_of'] = '2026-09-10T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'Seed case or Epiq project changed'):
            seed(self.client, changed)
        foreign = Epiq(self.root / 'foreign.sqlite', self.source)
        foreign.call('init', '--name', 'Unrelated project')
        with self.assertRaisesRegex(ValueError, 'no integration manifest'):
            seed(foreign, self.case)

    def test_freeze_reads_epiq_not_case_values_and_keeps_entity_links(self):
        # Poison only the local source body. Freeze must read the actual stored claim.
        self.case['captures']['c_season']['observation']['wins'] = 1
        result = freeze(self.client, self.case, self.root / 'frozen')
        packet = json.loads(Path(result['packet']).read_text())
        case = materialize_case(packet)
        self.assertEqual(case['captures']['c_season']['observation']['wins'], 14)
        self.assertEqual(len(packet['records']), 31)
        related = self.client.call('related', 'New England Patriots')
        self.assertIn('f_season', json.dumps(related))
        self.assertAlmostEqual(finish(case).state['artifacts']['forecast_ne_lxi']['probability'], 0.06048)

    def test_retraction_blocks_new_freeze_but_preserves_old_packet(self):
        result = freeze(self.client, self.case, self.root / 'frozen')
        packet_path = Path(result['packet'])
        packet_bytes = packet_path.read_bytes()
        packet = json.loads(packet_bytes)
        id = packet['records']['finding:f_protection']['lineage'][0]['claim_id']
        self.client.call('retract', id, '--reason', 'Synthetic test: finding withdrawn.')
        with self.assertRaisesRegex(ValueError, 'must be assessed'):
            freeze(self.client, self.case, self.root / 'after_retraction')
        self.assertEqual(packet_path.read_bytes(), packet_bytes)
        self.assertAlmostEqual(finish(materialize_case(packet)).state['artifacts']['forecast_ne_lxi']['probability'], 0.06048)

    def test_contested_capture_requires_reconciliation(self):
        _, operations = import_documents(self.case)
        conflicting = next(copy.deepcopy(op) for op in operations
                           if op['op'] == 'claim.assert' and op['subject'] == 'c_season')
        evidence = next(op for op in operations if op['op'] == 'evidence.add' and op['ref'] == 'c_season')
        conflicting['value']['observation']['wins'] = 1
        self.client.call('batch-write', '--input', '-', payload=[evidence, conflicting])
        with self.assertRaisesRegex(ValueError, 'Contested'):
            freeze(self.client, self.case, self.root / 'contested')


if __name__ == '__main__':
    unittest.main()
