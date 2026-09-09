#!/usr/bin/env python3
"""Offline workflow demo: recorded agent judgments plus deterministic operations.

This is a simulation harness, not an autonomous football model or the package CLI.
Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from evidence_packet import materialize_case, validate_packet

HERE = Path(__file__).resolve().parent


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def probability(value):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
            "Probability must be a finite number in [0, 1].")
    return value


def implied(american):
    require(type(american) in (int, float) and math.isfinite(american)
            and abs(american) >= 100, "Invalid American odds.")
    return 100 / (american + 100) if american > 0 else -american / (100 - american)


def normalize_board(board):
    require(len(board) == 32 and len({row['team'] for row in board}) == 32,
            "Need a complete board of 32 distinct teams.")
    raw = {row['team']: implied(row['american_odds']) for row in board}
    require('NE' in raw, "Board must include New England.")
    total = math.fsum(raw.values())
    return {'raw_implied': raw, 'implied_sum': total, 'overround': total - 1,
            'normalized': {team: p / total for team, p in raw.items()},
            'method': 'proportional_normalization',
            'assumption': 'Allocate the entire margin proportionally across teams; this is not a unique fair-probability estimate.'}


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    instruction: str
    input_ids: tuple[str, ...]
    required_fields: tuple[str, ...]
    completion_condition: str


TASKS = {
    'define': Task('define', 'agent', 'Operationalize the named championship and resolution rule.', (),
                   ('question',), 'A binary question with explicit YES, NO, and void rules.'),
    'fundamentals': Task('fundamentals', 'research', 'Research prior performance, quarterback, coaching, roster turnover, and schedule before synthesis.', ('q_ne_lxi_v1',),
                         ('capture_ids', 'findings', 'coverage'), 'Each required domain needs findings and an interpretation, or a documented unknown.'),
    'prior': Task('prior', 'agent_and_calculation', 'Choose and label an initial baseline.', ('q_ne_lxi_v1',),
                  ('method', 'rationale'), 'Distinguish an empirical reference class from a symmetry assumption.'),
    'drivers': Task('drivers', 'agent', 'Map the path to a title and identify what remains unestimated.', ('q_ne_lxi_v1', 'b_prior'),
                    ('drivers', 'probability_identity', 'unestimated'), 'Describe dependencies without inventing conditional probabilities.'),
    'market': Task('market', 'research_and_calculation', 'Read a complete title-odds board and inspect a comparison quote.', ('q_ne_lxi_v1', 'drivers'),
                   ('capture_ids', 'findings', 'conflicts'), 'Record board, locations, timing uncertainty, and discrepancies.'),
    'reconcile': Task('reconcile', 'research_and_calculation', 'Investigate the quote conflict using a second complete primary board.', ('c_betus', 'c_covers', 'conflicts'),
                      ('capture_ids', 'findings', 'decisions', 'remaining_unknowns'), 'Explain which inputs are comparable; inconclusive timing is allowed.'),
    'health': Task('health', 'research', 'Check current official injury information and its relevance to a season forecast.', ('q_ne_lxi_v1', 'drivers'),
                   ('capture_ids', 'findings', 'unknowns'), 'Separate an opening-game absence from a season-long effect.'),
    'update': Task('update', 'agent_and_calculation', 'Form an estimate, separating sourced facts, elicited assumptions, arithmetic, and market comparison.', ('b_prior', 'calc_betus', 'drivers'),
                   ('calculation_ids', 'weights', 'adjustment', 'rationale', 'limitations'), 'Keep arithmetic and judgment separate; acknowledge shared market information.'),
    'review': Task('review', 'agent', 'Challenge the estimate in both directions and answer each objection.', ('b_updated', 'drivers'),
                   ('objections', 'decision', 'rationale'), 'A reasoned no-change decision is valid.'),
    'check': Task('check', 'calculation', 'Check probability ranges, normalized board sums, and artifact references.', ('b_reviewed',),
                  ('request',), 'Run checks; do not fabricate unestimated playoff probabilities.'),
    'issue': Task('issue', 'agent_and_storage', 'Freeze the estimate, record limitations, and set monitoring triggers.', ('b_reviewed', 'checks'),
                  ('stopping_reason', 'review_at', 'triggers'), 'Issue a local demonstration forecast and leave the outcome unresolved.'),
}


class Workflow:
    def __init__(self, case, state=None):
        self.case = case
        self.state = copy.deepcopy(state) if state is not None else {
            'schema_version': '1', 'case_digest': digest(case), 'run_id': case.get('run_id', 'patriots_2027_demo'),
            'mode': 'offline_replay_of_recorded_agent_responses', 'revision': 0,
            'pending': ['define', 'prior', 'drivers', 'market', 'health', 'update', 'review', 'check', 'issue'],
            'artifacts': {}, 'accepted': {}, 'journal': [], 'resolution': None,
            'budget': {'max_research_tasks': case.get('max_research_tasks', 3), 'used_research_tasks': 0},
        }
        if state is None and case.get('required_research_domains'):
            self.state['pending'].insert(1, 'fundamentals')
        require(self.state['case_digest'] == digest(case), 'Case changed; initialize a separate run.')
        if 'evidence_packet' in case:
            packet = validate_packet(case['evidence_packet'])
            require(case == materialize_case(packet), 'Case differs from its frozen Epiq packet.')
            if state is None:
                self.put('epiq_packet', 'external_evidence_packet', packet=packet)

    def next(self):
        if not self.state['pending']:
            return {'disposition': 'waiting', 'revision': self.state['revision'],
                    'forecast_id': 'forecast_ne_lxi', 'resolution': None,
                    'next_review_at': self.state['artifacts']['forecast_ne_lxi']['review_at'],
                    'reason': 'Forecast issued; wait for a trigger or review time. No live resolution exists.'}
        task = TASKS[self.state['pending'][0]]
        require(all(i in self.state['artifacts'] for i in task.input_ids), 'Missing task dependency.')
        return {'disposition': 'actionable', 'revision': self.state['revision'],
                'task': asdict(task), 'result_schema': {'type': 'object',
                'required': ['task_id', 'expected_revision', 'idempotency_key', 'disposition', 'payload'],
                'payload_required': list(task.required_fields),
                'disposition_enum': ['completed', 'inconclusive']},
                'budget': copy.deepcopy(self.state['budget']),
                'context': copy.deepcopy(self.state['artifacts'])}

    def submit(self, result):
        fingerprint = digest(result)
        key = result.get('idempotency_key')
        require(isinstance(key, str) and bool(key), 'Idempotency key required.')
        if key in self.state['accepted']:
            require(self.state['accepted'][key] == fingerprint, 'Idempotency key reused with different content.')
            return {'accepted': True, 'duplicate': True, 'revision': self.state['revision']}
        require(result.get('expected_revision') == self.state['revision'], 'Stale state revision.')
        require(bool(self.state['pending']), 'Run is already waiting.')
        task_id = self.state['pending'][0]
        require(result.get('task_id') == task_id, 'Submit the currently actionable task.')
        disposition = result.get('disposition')
        require(disposition in ('completed', 'inconclusive'), 'Invalid task disposition.')
        require(disposition != 'inconclusive' or task_id in ('fundamentals', 'reconcile', 'health'),
                'This task requires a completed result.')
        payload = result.get('payload')
        require(isinstance(payload, dict), 'Payload must be an object.')
        require(all(k in payload for k in TASKS[task_id].required_fields), 'Missing required payload fields.')
        # Work on a copy; failed validation never partially changes the run.
        candidate = Workflow(self.case, self.state)
        candidate._apply(task_id, copy.deepcopy(payload))
        candidate.state['pending'].pop(0)
        candidate.state['revision'] += 1
        candidate.state['accepted'][key] = fingerprint
        candidate.state['journal'].append({'sequence': candidate.state['revision'],
            'task_id': task_id, 'disposition': disposition, 'result': copy.deepcopy(result)})
        self.state = candidate.state
        return {'accepted': True, 'duplicate': False, 'revision': self.state['revision']}

    def put(self, id, kind, inputs=(), **fields):
        require(id not in self.state['artifacts'], f'Immutable artifact already exists: {id}')
        require(all(i in self.state['artifacts'] for i in inputs), f'Missing artifact input for {id}')
        self.state['artifacts'][id] = {'id': id, 'kind': kind, 'input_ids': list(inputs), **fields}

    def research(self, task_id, payload):
        budget = self.state['budget']
        require(budget['used_research_tasks'] < budget['max_research_tasks'], 'Research budget exhausted.')
        for id in payload['capture_ids']:
            require(id in self.case['captures'], 'Unknown capture ID.')
            capture = self.case['captures'][id]
            require(capture['observed_at'] <= self.case['information_as_of'], 'Capture is after the information cutoff.')
            self.put(id, 'source_observation', ['epiq_packet'] if 'epiq_packet' in self.state['artifacts'] else [],
                     **capture, content_sha256=digest(capture['observation']))
            if 'board' in capture['observation']:
                self.put('calc_' + id.removeprefix('c_'), 'market_calculation', [id],
                         **normalize_board(capture['observation']['board']))
        for finding in payload['findings']:
            self.put(finding['id'], 'finding', finding['source_ids'], claim=finding['claim'],
                     role=finding['role'], entity_ids=finding['entity_ids'],
                     **({'epiq_reference': finding['epiq_reference']} if 'epiq_reference' in finding else {}))
        budget['used_research_tasks'] += 1
        self.put('research_' + task_id, 'research_result', payload['capture_ids'], result=payload)

    def _apply(self, task_id, p):
        a = self.state['artifacts']
        if task_id == 'define':
            q = p['question']
            require(q['id'] == 'q_ne_lxi_v1' and q['event_id'] == 'super_bowl_lxi', 'Wrong championship identity.')
            require(q['season'] == 2026 and q['target_type'] == 'binary', 'Wrong season or target type.')
            require(all(q.get(k) for k in ('yes', 'no', 'void', 'resolution_source', 'text')), 'Incomplete resolution criteria.')
            capture = self.case['captures']['c_calendar']
            self.put('c_calendar', 'source_observation', ['epiq_packet'] if 'epiq_packet' in a else [],
                     **capture, content_sha256=digest(capture['observation']))
            self.put(q['id'], 'question_version', ['c_calendar'], specification=q)
        elif task_id == 'prior':
            if p['method'] == 'uniform_32_team_symmetry':
                self.put('b_prior', 'belief_revision', ['q_ne_lxi_v1'], probability=1/32,
                         basis='symmetry_assumption_not_empirical_reference_class', rationale=p['rationale'])
            else:
                require(p['method'] == 'previous_runner_up_2000_2024', 'Unknown prior method.')
                games = a['c_history']['observation']['super_bowl_results']
                by_season = {game['season']: game for game in games}
                require(len(games) == 26 and set(by_season) == set(range(2000, 2026)), 'Need consecutive season results 2000–2025.')
                cases = [{'season': year, 'runner_up': by_season[year]['runner_up'],
                          'next_winner': by_season[year+1]['winner'],
                          'won_next': by_season[year]['runner_up'] == by_season[year+1]['winner']}
                         for year in range(2000, 2025)]
                rate = sum(row['won_next'] for row in cases) / len(cases)
                self.put('reference_class', 'reference_class', ['c_history'], cases=cases,
                         frequency=rate, sample_size=len(cases),
                         limitations=['Small selected class; repeated franchises; era and roster differences; not a calibrated Patriots probability.'])
                self.put('b_prior', 'belief_revision', ['q_ne_lxi_v1', 'reference_class'], probability=rate,
                         basis='raw_reference_class_frequency', rationale=p['rationale'])
        elif task_id == 'drivers':
            require(bool(p['drivers']) and bool(p['unestimated']), 'Need drivers and explicit gaps.')
            self.put('drivers', 'driver_map', ['q_ne_lxi_v1'], **p)
        elif task_id in ('fundamentals', 'market', 'reconcile', 'health'):
            self.research(task_id, p)
            if task_id == 'fundamentals':
                required = set(self.case['required_research_domains'])
                require(set(p['coverage']) == required, 'Missing required research domain.')
                for domain, entry in p['coverage'].items():
                    require(entry.get('disposition') in ('assessed', 'unknown') and entry.get('interpretation'),
                            f'Missing interpretation for {domain}.')
                    ids = entry.get('finding_ids', [])
                    require(all(i in a and a[i]['kind'] == 'finding' for i in ids), 'Unknown coverage finding.')
                    require(entry['disposition'] == 'unknown' or bool(ids), 'Assessed domain needs evidence.')
                self.put('coverage', 'research_coverage', [f['id'] for f in p['findings']], domains=p['coverage'])
            elif task_id == 'market':
                self.put('conflicts', 'source_conflicts', p['capture_ids'], items=p['conflicts'])
                if p['conflicts']:
                    self.state['pending'].insert(1, 'reconcile')
            elif task_id == 'reconcile':
                require(bool(p['decisions']), 'Record a decision even if timing remains inconclusive.')
        elif task_id == 'update':
            if self.case.get('required_research_domains'):
                require('coverage' in a, 'Fundamentals research coverage is required.')
            if p.get('method') == 'elicited_conditional_path':
                keys = ('playoffs', 'afc_given_playoffs', 'title_given_afc')
                assumptions = p['assumptions']
                require(set(assumptions) == set(keys), 'Need the three nested conditional probabilities.')
                for assumption in assumptions.values():
                    probability(assumption['value'])
                    require(assumption.get('basis') == 'agent_judgment_not_fitted' and assumption.get('rationale'),
                            'Elicited numbers must be identified as judgments.')
                    require(bool(assumption.get('finding_ids')) and all(i in a for i in assumption['finding_ids']),
                            'Each judgment needs evidence references.')
                estimate = math.prod(assumptions[key]['value'] for key in keys)
                scenarios = []
                for scenario in p['sensitivity_scenarios']:
                    require(set(scenario['values']) == set(keys), 'Invalid scenario inputs.')
                    values = [probability(scenario['values'][key]) for key in keys]
                    scenarios.append({**scenario, 'title_probability': math.prod(values)})
                inputs = ['b_prior', 'drivers', 'coverage', 'research_health']
                inputs += sorted({i for v in assumptions.values() for i in v['finding_ids']})
                self.put('conditional_path', 'elicited_probability_model', inputs, assumptions=assumptions,
                         sensitivity_scenarios=scenarios, probability=estimate,
                         identity='P(title)=P(playoffs)*P(AFC|playoffs)*P(title|AFC)',
                         scope='Conditional on a completed championship; no independence assumption is required.',
                         limitations=p['limitations'])
                self.put('b_updated', 'belief_revision', ['b_prior', 'conditional_path'], probability=estimate,
                         previous_id='b_prior', agent_synthesis=p)
                return
            ids, weights = p['calculation_ids'], p['weights']
            require(bool(ids) and len(ids) == len(weights) and len(set(ids)) == len(ids), 'Invalid ensemble membership.')
            require(all(type(w) in (int, float) and math.isfinite(w) and w >= 0 for w in weights)
                    and math.isclose(math.fsum(weights), 1), 'Weights must be nonnegative and sum to one.')
            require(all(i in a and a[i]['kind'] == 'market_calculation' for i in ids), 'Unknown market calculation.')
            require(type(p['adjustment']) in (int, float) and math.isfinite(p['adjustment']), 'Invalid adjustment.')
            estimate = probability(math.fsum(a[i]['normalized']['NE'] * w for i, w in zip(ids, weights)) + p['adjustment'])
            self.put('b_updated', 'belief_revision', ['b_prior', 'drivers', 'research_health', *ids],
                     probability=estimate, previous_id='b_prior', agent_synthesis=p)
        elif task_id == 'review':
            require(p['decision'] == 'retain', 'This fixture demonstrates a justified unchanged review.')
            require(bool(p['objections']) and all(o.get('response') for o in p['objections']), 'Respond to each objection.')
            self.put('review', 'review', ['b_updated'], **p)
            self.put('b_reviewed', 'belief_revision', ['b_updated', 'review'],
                     probability=a['b_updated']['probability'], previous_id='b_updated', rationale=p['rationale'])
        elif task_id == 'check':
            checks = []
            for id, artifact in a.items():
                require(all(i in a for i in artifact['input_ids']), 'Dangling artifact reference.')
                if artifact['kind'] == 'belief_revision':
                    probability(artifact['probability'])
                if artifact['kind'] == 'market_calculation':
                    require(math.isclose(math.fsum(artifact['normalized'].values()), 1), 'Board does not normalize.')
                    checks.append(id + ': 32 mutually exclusive title probabilities sum to 1')
            skipped = ['Playoff/AFC numeric inequalities: component probabilities are unestimated']
            if 'conditional_path' in a:
                assumptions = a['conditional_path']['assumptions']
                playoff = assumptions['playoffs']['value']
                afc = playoff * assumptions['afc_given_playoffs']['value']
                require(a['b_reviewed']['probability'] <= afc <= playoff, 'Nested event probabilities inconsistent.')
                checks.append('P(title) <= P(AFC champion) <= P(playoffs)')
                skipped = []
            self.put('checks', 'validation', list(a), passed=True, checks=checks + [
                'All belief probabilities are finite and in range', 'All artifact references exist'],
                skipped=skipped,
                limitations=['Checks do not establish that claims are true or that the estimate is calibrated.'])
        elif task_id == 'issue':
            require(a['checks']['passed'], 'Checks have not passed.')
            require(bool(p['stopping_reason']) and bool(p['triggers']), 'Need a stopping reason and update triggers.')
            require(p['review_at'] > self.case['information_as_of'], 'Review must follow the information cutoff.')
            manifest = {id: digest(value) for id, value in a.items()}
            self.put('forecast_ne_lxi', 'forecast', ['q_ne_lxi_v1', 'b_reviewed', 'checks'],
                     probability=a['b_reviewed']['probability'], information_as_of=self.case['information_as_of'],
                     run_id=self.state['run_id'], assessment_method=self.case.get('assessment_method', 'market_baseline'),
                     issued_at=datetime.now(timezone.utc).isoformat(),
                     scope='local_workflow_demonstration', external_submission=False,
                     **({'evidence_packet_sha256': self.case['evidence_packet']['sha256'],
                         'epiq_project_id': self.case['evidence_packet']['project']['project_id']}
                        if 'evidence_packet' in self.case else {}),
                     input_manifest=manifest, manifest_sha256=digest(manifest), **p)

    def affected_forecasts(self, changed_id):
        require(changed_id in self.state['artifacts'], 'Unknown changed artifact.')
        reached = {changed_id}
        while True:
            added = {id for id, artifact in self.state['artifacts'].items()
                     if any(i in reached for i in artifact['input_ids'])} - reached
            if not added:
                break
            reached |= added
        return sorted(id for id in reached if self.state['artifacts'][id]['kind'] == 'forecast')

    def score_scenarios(self):
        f = self.state['artifacts']['forecast_ne_lxi']
        return {'hypothetical_only': True, 'forecast_id': f['id'], 'actual_resolution': None,
                'cases': [{'hypothetical_outcome': y, 'brier_loss': (f['probability'] - y)**2}
                          for y in (0, 1)], 'void_case': {'score': None, 'reason': 'Excluded under resolution policy'}}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temporary.replace(path)


def replay(case, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    workflow = Workflow(case)
    transcript = ['# Patriots 2027 workflow transcript\n',
                  'Offline replay of recorded agent responses. Research was inspected on September 9, 2026.\n',
                  'The harness calculates and validates; it does not call an LLM or refresh the web.\n']
    while (task := workflow.next())['disposition'] == 'actionable':
        id = task['task']['id']
        fixture = case['responses'][id]
        result = {'task_id': id, 'expected_revision': task['revision'], 'idempotency_key': 'demo_' + id,
                  'disposition': fixture.get('disposition', 'completed'), 'payload': fixture['payload']}
        save(out / 'tasks' / f'{task["revision"]:02d}_{id}.json', task)
        save(out / 'responses' / f'{task["revision"]:02d}_{id}.json', result)
        workflow.submit(result)
        save(out / 'state.json', workflow.state)
        transcript.append(f'## {workflow.state["revision"]}. {id}\n\n**Task:** {task["task"]["instruction"]}\n\n'
                          f'**Recorded agent result:** {fixture["summary"]}\n\n'
                          f'**Disposition:** {result["disposition"]}. State revision: {workflow.state["revision"]}.\n')
    f = workflow.state['artifacts']['forecast_ne_lxi']
    transcript.append(f'## Result\n\nLocal demonstration forecast: **{f["probability"]:.2%}**. '
                      'Actual outcome unresolved; next action is waiting for monitoring.\n')
    (out / 'TRANSCRIPT.md').write_text('\n'.join(transcript))
    save(out / 'forecast.json', f)
    save(out / 'next.json', workflow.next())
    save(out / 'hypothetical_scores.json', workflow.score_scenarios())
    save(out / 'trigger_demo.json', {'synthetic_event': True, 'description': 'Suppose the captured BetUS board changes.',
         'affected_forecasts': workflow.affected_forecasts('c_betus'),
         'action': 'Request new research and assessment; do not overwrite the issued probability.',
         'issued_probability_unchanged': f['probability']})
    return {'forecast_probability': f['probability'], 'tasks_completed': workflow.state['revision'],
            'disposition': workflow.next()['disposition'], 'output': str(out)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'next', 'submit', 'replay'])
    parser.add_argument('--case', type=Path, default=HERE / 'case.json')
    parser.add_argument('--state', type=Path, default=HERE / 'working_state.json')
    parser.add_argument('--result', type=Path)
    parser.add_argument('--out', type=Path, default=HERE / 'output')
    args = parser.parse_args()
    try:
        case = json.loads(args.case.read_text())
        if args.command == 'replay':
            response = replay(case, args.out)
        elif args.command == 'init':
            require(not args.state.exists(), 'State exists; choose a new state path.')
            workflow = Workflow(case)
            save(args.state, workflow.state)
            response = workflow.next()
        else:
            workflow = Workflow(case, json.loads(args.state.read_text()))
            if args.command == 'submit':
                require(args.result is not None, '--result is required.')
                response = workflow.submit(json.loads(args.result.read_text()))
                save(args.state, workflow.state)
            else:
                response = workflow.next()
        print(json.dumps(response, indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({'error': str(error)}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
