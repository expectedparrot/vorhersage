#!/usr/bin/env python3
"""Run the README's fictional app-launch forecast through the public CLI.

Python standard library only. Requires an installed vorhersage executable.
All evidence and probabilities are authored teaching inputs, not real research.
"""
import argparse
import json
import math
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


def run(project, executable):
    project = Path(project).resolve()
    if project.exists():
        raise SystemExit(f'Choose a new directory; {project} already exists.')
    if not shutil.which(executable):
        raise SystemExit('Install vorhersage first, or pass --cli /path/to/vorhersage.')
    project.mkdir(parents=True)
    (project / 'inputs').mkdir()
    (project / 'receipts').mkdir()
    (project / 'tasks').mkdir()
    started = datetime.now(timezone.utc)
    deadline = (started + timedelta(days=7)).isoformat()
    review_at = (started + timedelta(days=1)).isoformat()
    count = 0

    def save(path, value):
        target = project / path
        target.write_text(json.dumps(value, indent=2) + '\n')
        return target

    def cli(*args):
        nonlocal count
        completed = subprocess.run([executable, '--project', str(project), *map(str, args)],
                                   capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError(completed.stderr or completed.stdout)
        envelope = json.loads(completed.stdout)
        save(f'receipts/{count:02d}-{args[0]}.json', envelope)
        count += 1
        return envelope['data']

    def register(name, commands, data):
        return cli(*commands, '--from', save(f'inputs/{name}.json', data))

    cli('init', '--name', 'README: fictional app launch')
    register('profile', ['profile', 'add'], {
        'id': 'launch_demo', 'description': 'Two-domain teaching profile for a fictional release.',
        'domains': ['qa_readiness', 'release_process']})
    register('question', ['question', 'add'], {
        'id': 'app-launch', 'text': 'Will the fictional app launch publicly within seven days?',
        'yes': 'By the deadline, QA is passed and at least one external user can access the public release.',
        'no': 'The public release does not meet both requirements by the deadline.',
        'void': 'The teaching fixture is withdrawn.', 'event_deadline': deadline,
        'resolve_after': deadline, 'resolution_source': 'urn:vorhersage:demo:release-log',
        'event_group': 'app-launch-demo', 'domain': 'software', 'profile': 'launch_demo',
        'kind': 'simulation'})
    captured = datetime.now(timezone.utc).isoformat()
    briefing = ('Fictional release briefing: public launch requires completed QA. '
                'The last QA checks are scheduled. The engineering lead assigns a 90% '
                'chance of QA passing by the deadline. Given that QA passes by then, '
                'the release lead assigns an 80% chance of approval and public deployment '
                'also completing by the same deadline. Both probabilities are assumptions.')
    evidence = register('evidence', ['research', 'capture'], {
        'sources': [{'id': 'briefing', 'url': 'urn:vorhersage:demo:release-briefing',
                     'title': 'Fictional release briefing', 'excerpt': briefing,
                     'retrieved_at': captured, 'excerpt_kind': 'quotation',
                     'capture': {'method': 'manual', 'captured_at': captured, 'content': briefing}}],
        'findings': [
            {'id': 'qa', 'claim': 'QA is required; its completion probability by the deadline is assumed to be 90%.',
             'source_ids': ['briefing'], 'claim_type': 'inference'},
            {'id': 'release', 'claim': 'Given QA passes by the deadline, timely approval and public deployment have an assumed 80% chance.',
             'source_ids': ['briefing'], 'claim_type': 'inference'}],
        'limitations': ['All material is fictional. Lead estimates are subjective, not measured success rates.']})
    refs = {r['record_id']: r['evidence_ref'] for r in evidence['records']}
    all_refs = list(refs.values())
    run_id = register('run', ['run', 'start'], {
        'question_id': 'app-launch', 'forecaster': 'demo:agent', 'method': 'two-stage conditional path',
        'mode': 'simulation', 'information_as_of': datetime.now(timezone.utc).isoformat(),
        'research_status': 'in_progress', 'max_searches': 0, 'max_extra_tasks': 0})['run_id']
    payloads = {
        'prior': {'method': 'judgment', 'probability': .5,
                  'rationale': 'An assumed 50% comparison baseline; the authored briefing is already available.',
                  'limitations': ['This is not an independently elicited pre-research prior.'], 'evidence_refs': []},
        'drivers': {'drivers': [
            {'name': 'Pass QA', 'mechanism': 'The release policy requires QA before public launch.', 'evidence_refs': [refs['qa']]},
            {'name': 'Approval and deployment', 'mechanism': 'Even after QA, approval and deployment must finish before the same deadline.', 'evidence_refs': [refs['release']]}],
            'yes_path': 'QA passes and the app becomes publicly accessible by the deadline.',
            'no_path': 'QA fails or is late, or subsequent approval/deployment misses the deadline.',
            'unknowns': ['The briefing gives subjective probabilities without an empirical reference class.']},
        'qa_readiness': {'disposition': 'assessed',
            'interpretation': 'The fixture schedules the remaining checks; the 90% estimate is an engineering judgment.',
            'evidence_refs': [refs['qa']], 'sources_checked': ['Fictional engineering briefing'],
            'unknowns': ['Defect severity and actual remaining QA duration.'], 'conflicts': []},
        'release_process': {'disposition': 'assessed',
            'interpretation': 'The 80% estimate includes approval, deployment, and time remaining after QA; it is conditional.',
            'evidence_refs': [refs['release']], 'sources_checked': ['Fictional release briefing'],
            'unknowns': ['Approval delays and deployment failures.'], 'conflicts': []},
        'assessment': {'method': 'conditional_path',
            'rationale': 'Launch requires QA. Multiply P(QA by deadline) by P(launch by deadline given QA by deadline).',
            'nested_events_justification': 'The target event includes passing QA; no release bypasses it. Both stages use the same deadline.',
            'components': [
                {'id': 'qa', 'conditional_on': None, 'probability': .9,
                 'rationale': 'Subjective QA estimate in the fictional briefing.', 'evidence_refs': [refs['qa']]},
                {'id': 'target', 'conditional_on': 'qa', 'probability': .8,
                 'rationale': 'Conditional approval/deployment estimate already includes remaining time.', 'evidence_refs': [refs['release']]}],
            'limitations': ['No empirical calibration. The conditional estimate must account for late QA completion.'],
            'evidence_refs': all_refs},
        'review': {'decision': 'retain',
            'rationale': 'Retain the declared teaching assumptions while preserving objections in both directions.',
            'objections': [
                {'direction': 'too_high', 'objection': 'QA might finish too late to leave enough time for launch.',
                 'response': 'The 80% term explicitly conditions on launch by the same deadline; its value remains unvalidated.'},
                {'direction': 'too_low', 'objection': 'Approval could be prepared during QA, making deployment almost certain.',
                 'response': 'The fixture supplies no evidence for raising the 80% term. A real forecast would investigate this.'}],
            'evidence_refs': all_refs},
        'issue': {'stopping_reason': 'The two fixture research domains and both review directions are complete.',
                  'review_at': review_at,
                  'triggers': [{'description': 'QA results arrive or the approval/deployment schedule changes.',
                                'evidence_refs': all_refs}]}}
    steps = []
    while True:
        task = cli('next', '--run', run_id)
        save(f'tasks/{task["revision"]:02d}.json', task)
        if task['disposition'] != 'actionable':
            forecast_id = task['forecast_id']
            break
        kind = task['task']['kind']
        name = task['task']['domain'] if kind == 'research' else kind
        payload = payloads[name]  # Fail on unexpected tasks; never fabricate generic answers.
        save(f'inputs/{name}.json', payload)
        submission = {'task_id': task['task']['id'], 'expected_revision': task['revision'],
                      'idempotency_key': task['task']['id'], 'payload': payload,
                      'usage': {'searches': 0, 'model_calls': 0, 'cost_usd': 0}}
        cli('submit', '--run', run_id, '--from', save(f'inputs/submit-{name}.json', submission))
        steps.append(name)
        print('Completed:', name)
    forecast = cli('forecast', 'show', forecast_id)
    assert math.isclose(forecast['probability'], .72)
    cli('report', '--question', 'app-launch', '--output', project/'report.html')
    cli('report', '--question', 'app-launch', '--output', project/'report.json')
    doctor = cli('doctor')
    assert doctor['ok']
    summary = {'question_id': 'app-launch', 'run_id': run_id, 'forecast_id': forecast_id,
               'probability': forecast['probability'], 'steps': steps,
               'mode': 'simulation', 'actual_model_calls': 0, 'actual_cost_usd': 0,
               'report': str(project/'report.html')}
    save('summary.json', summary)
    print('Issued forecast: 72.0% (0.90 × 0.80)')
    print('Report:', project/'report.html')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path, help='New output directory; existing directories are refused.')
    parser.add_argument('--cli', default='vorhersage', help='Installed CLI executable (default: vorhersage on PATH).')
    args = parser.parse_args()
    run(args.project, args.cli)
