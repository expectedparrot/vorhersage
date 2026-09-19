"""Build a new, Firecrawl-assisted evidence arm from saved retrieval receipts."""
import json
from pathlib import Path
from vorhersage.common import digest, now
from vorhersage.store import Store

HERE = Path(__file__).resolve().parent
TMP = Path('/private/tmp/vorhersage_real_research')
OUT = HERE / 'run' / 'packets'

def main():
    store = Store(TMP)
    with store.connect() as c:
        rows = Store.all(c, 'research')
        retrievals = []
        for row in rows:
            artifact = Store.artifact(c, row['id'], 'research')
            artifact['id'] = row['id']
            retrievals.append(artifact)
    records = {'measles': [], 'global_heat': []}
    for r in retrievals:
        query = r['request']['body'].get('query', '')
        for s in r.get('sources', []):
            url = s['url']
            official = any(x in url for x in ('cdc.gov', 'giss.nasa.gov', 'nasa.gov', 'noaa.gov', 'ncep.noaa.gov'))
            if not official or s['capture'].get('method') != 'fetched':
                continue
            if 'measles' in query.lower() and 'cdc.gov/measles' in url:
                records['measles'].append((r, s))
            elif ('temperature' in query.lower() or 'nasa' in query.lower()) and ('giss.nasa.gov' in url or 'nasa.gov' in url):
                records['global_heat'].append((r, s))
            elif 'enso' in query.lower() and ('noaa.gov' in url or 'ncep.noaa.gov' in url):
                records['global_heat'].append((r, s))
    for qid, items in records.items():
        # Keep the first full official page per URL; source captures retain all provider receipts.
        unique = {}
        for r, s in items:
            unique.setdefault(s['url'], (r, s))
        findings = []
        for i, (r, s) in enumerate(unique.values(), 1):
            content = s['capture'].get('content', '')
            findings.append({'id': f'{qid}_firecrawl_{i}',
                'claim': s['excerpt'], 'claim_type': 'reporting',
                'value': {'provider': 'firecrawl', 'retrieval_id': r['id'], 'url': s['url']},
                'entity_ids': [],
                'sources': [{'id': f'{r["id"]}_{s["id"]}', 'url': s['url'], 'title': s['title'],
                             'excerpt': content[:2000] or s['excerpt'], 'excerpt_kind': 'quotation',
                             'retrieved_at': s['retrieved_at'], 'capture': s['capture']}],
                'observed_at': s.get('published_at') or s['retrieved_at'],
                'provenance': {'adapter': 'vorhersage.research_bundle.v1'}})
        base = json.loads((OUT / f'{qid}.json').read_text())
        base.pop('research_receipts', None)
        base.pop('sha256', None)
        base['records'].extend(findings)
        base['limitations'] = list(dict.fromkeys(base.get('limitations', []) + [
            'Firecrawl-assisted packet: sources were discovered and retrieved before the model call; market information was excluded from the worker input.',
            'Provider retrieval may be incomplete or cached; inspect receipts and source capture content.',
            'The packet is coordinator-collected; this arm is research-assisted, not live model tool-use.'
        ]))
        base['information_as_of'] = now()
        base['created_at'] = base['information_as_of']
        base['sha256'] = digest(base)
        (OUT / f'{qid}.json').write_text(json.dumps(base, indent=2) + '\n')
        print(qid, len(findings))

if __name__ == '__main__': main()
