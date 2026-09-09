"""Behavioral checks for the offline workflow demo."""

import copy
import json
import math
import unittest

from simulate import HERE, Workflow, digest, implied, normalize_board, probability


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads((HERE / 'case.json').read_text())
        self.run = Workflow(self.case)

    def response(self):
        next_task = self.run.next()
        id = next_task['task']['id']
        fixture = self.case['responses'][id]
        return {'task_id': id, 'expected_revision': next_task['revision'],
                'idempotency_key': 'test_' + id, 'disposition': fixture.get('disposition', 'completed'),
                'payload': copy.deepcopy(fixture['payload'])}

    def advance_to(self, id):
        while self.run.next()['task']['id'] != id:
            self.run.submit(self.response())

    def finish(self):
        while self.run.next()['disposition'] == 'actionable':
            self.run.submit(self.response())

    def test_odds_and_probability_validation(self):
        self.assertAlmostEqual(implied(2000), 1 / 21)
        self.assertAlmostEqual(implied(-200), 2 / 3)
        for bad in (True, float('nan'), float('inf'), -0.1, 1.1):
            with self.assertRaises(ValueError):
                probability(bad)
        board = self.case['captures']['c_betus']['observation']['board']
        result = normalize_board(board)
        self.assertAlmostEqual(result['implied_sum'], 1.199973134428064)
        self.assertAlmostEqual(result['normalized']['NE'], 0.03968342811420024)
        self.assertAlmostEqual(math.fsum(result['normalized'].values()), 1)
        with self.assertRaises(ValueError):
            normalize_board(board[:-1])
        with self.assertRaises(ValueError):
            normalize_board(board[:-1] + [board[0]])

    def test_next_is_read_only_and_repeatable(self):
        before = digest(self.run.state)
        self.assertEqual(self.run.next(), self.run.next())
        self.assertEqual(digest(self.run.state), before)

    def test_conflict_inserts_reconciliation(self):
        self.advance_to('market')
        self.assertNotIn('reconcile', self.run.state['pending'])
        self.run.submit(self.response())
        self.assertEqual(self.run.next()['task']['id'], 'reconcile')
        # Inconclusive source timing is accepted; it doesn't force invented certainty.
        self.run.submit(self.response())
        self.assertEqual(self.run.next()['task']['id'], 'health')

    def test_retry_is_idempotent_and_collision_rejected(self):
        result = self.response()
        self.run.submit(result)
        before = digest(self.run.state)
        self.assertTrue(self.run.submit(result)['duplicate'])
        self.assertEqual(digest(self.run.state), before)
        changed = copy.deepcopy(result)
        changed['payload']['question']['text'] = 'Different question'
        with self.assertRaises(ValueError):
            self.run.submit(changed)
        self.assertEqual(digest(self.run.state), before)

    def test_stale_and_wrong_task_rejected_without_mutation(self):
        self.run.submit(self.response())
        result = self.response()
        before = digest(self.run.state)
        result['expected_revision'] = 0
        with self.assertRaises(ValueError):
            self.run.submit(result)
        result = self.response()
        result['task_id'] = 'issue'
        with self.assertRaises(ValueError):
            self.run.submit(result)
        self.assertEqual(digest(self.run.state), before)

    def test_invalid_probability_update_is_atomic(self):
        self.advance_to('update')
        before = digest(self.run.state)
        result = self.response()
        result['payload']['adjustment'] = 2
        with self.assertRaises(ValueError):
            self.run.submit(result)
        self.assertEqual(digest(self.run.state), before)
        self.run.submit(self.response())
        self.assertAlmostEqual(self.run.state['artifacts']['b_updated']['probability'], 0.04271133548480065)

    def test_capture_after_cutoff_is_rejected(self):
        self.case['captures']['c_betus']['observed_at'] = '2026-09-10T00:00:00Z'
        self.run = Workflow(self.case)
        self.advance_to('market')
        before = digest(self.run.state)
        with self.assertRaises(ValueError):
            self.run.submit(self.response())
        self.assertEqual(digest(self.run.state), before)

    def test_json_resume_then_issue_and_keep_scenarios_separate(self):
        self.advance_to('health')
        self.run = Workflow(self.case, json.loads(json.dumps(self.run.state)))
        self.finish()
        self.assertEqual(self.run.next()['disposition'], 'waiting')
        self.assertEqual(self.run.state['revision'], 10)
        self.assertEqual(self.run.state['budget']['used_research_tasks'], 3)
        artifacts = self.run.state['artifacts']
        self.assertEqual(artifacts['b_reviewed']['probability'], artifacts['b_updated']['probability'])
        forecast = artifacts['forecast_ne_lxi']
        for id, expected_digest in forecast['input_manifest'].items():
            self.assertEqual(digest(artifacts[id]), expected_digest)
        before = digest(self.run.state)
        self.assertEqual(self.run.affected_forecasts('c_betus'), ['forecast_ne_lxi'])
        cases = self.run.score_scenarios()
        self.assertTrue(cases['hypothetical_only'])
        self.assertAlmostEqual(cases['cases'][0]['brier_loss'], forecast['probability']**2)
        self.assertAlmostEqual(cases['cases'][1]['brier_loss'], (1-forecast['probability'])**2)
        self.assertIsNone(self.run.state['resolution'])
        self.assertEqual(digest(self.run.state), before)

    def test_changed_fixture_cannot_silently_resume(self):
        changed_case = copy.deepcopy(self.case)
        changed_case['responses']['prior']['payload']['rationale'] = 'Changed'
        with self.assertRaises(ValueError):
            Workflow(changed_case, self.run.state)


class ResearchedWorkflowTests(unittest.TestCase):
    response = WorkflowTests.response
    advance_to = WorkflowTests.advance_to
    finish = WorkflowTests.finish

    def setUp(self):
        self.case = json.loads((HERE / 'researched_case.json').read_text())
        self.run = Workflow(self.case)

    def test_missing_domain_blocks_completion_atomically(self):
        self.advance_to('fundamentals')
        result = self.response()
        del result['payload']['coverage']['coaching']
        before = digest(self.run.state)
        with self.assertRaises(ValueError):
            self.run.submit(result)
        self.assertEqual(digest(self.run.state), before)
        self.assertEqual(self.run.next()['task']['id'], 'fundamentals')

    def test_unknown_domain_can_advance_without_invented_evidence(self):
        self.advance_to('fundamentals')
        result = self.response()
        result['payload']['coverage']['coaching'] = {
            'disposition': 'unknown', 'finding_ids': [],
            'interpretation': 'Unable to establish the effect of coaching changes.'}
        self.run.submit(result)
        self.assertEqual(self.run.next()['task']['id'], 'prior')

    def test_reference_class_and_conditional_forecast(self):
        self.finish()
        artifacts = self.run.state['artifacts']
        cohort = artifacts['reference_class']
        self.assertEqual(cohort['sample_size'], 25)
        self.assertEqual(cohort['frequency'], 0.04)
        successes = [r['season'] for r in cohort['cases'] if r['won_next']]
        self.assertEqual(successes, [2017])
        forecast = artifacts['forecast_ne_lxi']
        self.assertAlmostEqual(forecast['probability'], 0.06048)
        scenarios = artifacts['conditional_path']['sensitivity_scenarios']
        self.assertEqual(len(scenarios), 3)
        for scenario, expected in zip(scenarios, [0.0288, 0.06048, 0.11]):
            self.assertAlmostEqual(scenario['title_probability'], expected)
        self.assertEqual(self.run.state['budget']['used_research_tasks'], 4)
        self.assertEqual(artifacts['checks']['skipped'], [])
        for id, expected_digest in forecast['input_manifest'].items():
            self.assertEqual(digest(artifacts[id]), expected_digest)
        self.assertIn('forecast_ne_lxi', self.run.affected_forecasts('c_kuhr'))
        self.assertIsNone(self.run.state['resolution'])

    def test_invalid_conditional_and_missing_provenance_are_atomic(self):
        self.advance_to('update')
        before = digest(self.run.state)
        for key, bad in [('value', 1.1), ('basis', 'statistically_fitted'), ('finding_ids', [])]:
            result = self.response()
            result['payload']['assumptions']['playoffs'][key] = bad
            with self.assertRaises(ValueError):
                self.run.submit(result)
            self.assertEqual(digest(self.run.state), before)


if __name__ == '__main__':
    unittest.main()
