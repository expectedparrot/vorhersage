"""Freeze nominations and analysis before requesting any evaluation quotes."""
import json
from pathlib import Path
from vorhersage.common import digest, now
from vorhersage.market_screen import POLICY

HERE = Path(__file__).resolve().parent
picks = [
 ('mortgage', 'KX30YMORTW', 'KX30YMORTW-26SEP24-T7.01', 'US housing and interest rates'),
 ('travel', 'KXTSAW', 'KXTSAW-26SEP20-A2.30', 'US air travel'),
 ('gasoline', 'KXAAAGASW', 'KXAAAGASW-26SEP21-4.4000', 'US energy prices'),
 ('housing', 'KXHOUSINGSTART', 'KXHOUSINGSTART-26OCT20-T1.300', 'US housing and interest rates'),
 ('measles', 'KXMEASLES', 'KXMEASLES-26-6000', 'US infectious disease'),
 ('launches', 'KXRKLBCOUNT', 'KXRKLBCOUNT-27JAN-10', 'Rocket Lab launch operations'),
 ('global_heat', 'KXGTEMP', 'KXGTEMP-26-P0', 'Global climate'),
 ('miami', 'KXHIGHMIA', 'KXHIGHMIA-26SEP19-B88.5', 'US daily weather'),
 ('austin', 'KXHIGHAUS', 'KXHIGHAUS-26SEP19-B98.5', 'US daily weather'),
 ('dune', 'KXMOVIEDELAYDUNEPT3', 'KXMOVIEDELAYDUNEPT3-26DEC18', 'Film production'),
 ('arctic', 'KXARCTICICEMIN', 'KXARCTICICEMIN-26OCT01-T4.2', 'Global climate'),
]

def main():
    candidates = []
    for cid, series, ticker, group in picks:
        data = json.loads((HERE / 'definitions' / (series + '.json')).read_text())
        contract = next(c for c in data['candidates'] if c['market_id'] == ticker)
        candidates.append({'id': cid, 'series': series, 'contract': contract, 'dependence_cluster': group,
                           'event_deadline': '2027-01-01T00:00:00Z' if cid == 'launches' else contract['scheduled_close']})
    inventory = {'created_at': now(), 'candidates': candidates,
                 'rationale': 'One threshold per event, chosen from price-free definitions to broaden domains; no NFL, no re-use of earlier events. No replacements after screening.'}
    protocol = {'registered_at': now(), 'candidate_inventory_sha256': digest(inventory),
        'selection': 'Exact 11 nominations, no replacement. Spread <=0.10, size >=1 each side, nonextreme uncrossed active book. Unknown outcome verified from primary sources before inference. Exclude incomplete definitions or unavailable threshold-crossing checks.',
        'timing': 'At least 12 hours until defined event deadline; daily-weather forecasts must additionally be issued before the local target day begins. Global forecast cutoff 2026-09-19T03:45:00Z.',
        'design': {'models': ['gpt-6-astra','claude-fable-5-1','gemini-3.1-pro-preview'], 'conditions': ['question_only','outside_research'], 'repetitions': 3, 'maximum_calls': 198, 'planning_budget_usd': 20},
        'budget_note': 'Planning bound, not provider-enforced aggregate cap. Preserve cost of all attempts. No study retries or repairs.',
        'screening': {'policy': POLICY, 'benign': 'Narrow complete denials pass with flags retained. All other lexical mentions require a recorded pre-reveal decision. Allow only explicit non-use statements or definition-only references containing no quoted or reconstructed market information. Claimed or ambiguous price use is excluded. No content review after target reveal.',
                      'source_boundary': 'Strict primary-domain and excluded-market-text checks remain unchanged in purpose. The output denial exception never applies to sources.'},
        'research': 'Primary nonmarket receipts and curated frozen packets; no model tools, prior results, or other forecasts in prompts. All models see the same prompt per question/condition/repetition. Administrative replicate ID distinguishes fresh calls; remote cache disabled.',
        'analysis': {'primary': 'Complete across all models, conditions, and three repetitions. Average absolute loss within each question/model/condition, then equally across questions; calls are not independent questions.',
                     'secondary': 'Score each model\'s three-draw mean separately from expected single-draw loss. Equal-weight cross-model average uses three-draw research means. Report per-cell sample SD and ranges, acceptance, costs, domain-group summaries, and follow-up quote sensitivity.',
                     'uncertainty': 'Descriptive only: small selected sample of dependent groups. No confidence claim from repeated calls or pooled trials.',
                     'calibration': 'No fitted correction or weights in this batch. No reuse as an untouched validation cohort after examining its scores.'},
        'blinding': 'Commit evaluator prices before research. Verify actual prompts, model identities, all terminal attempts, pre-reveal reviews, and forecast seals before revealing any target.'}
    for path, data in [(HERE/'candidates.json',inventory),(HERE/'run/protocol.json',protocol)]:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as f: json.dump(data,f,indent=2); f.write('\n')
    print('Frozen 11 nominees; maximum 198 fresh calls, no quote targets read.')

if __name__ == '__main__': main()
