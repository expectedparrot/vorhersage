"""Offline report fidelity checks against a hash-bound reporting snapshot.

Checks verify declared claims and citations, not source truth or completeness of
an author's claim inventory. Semantic reading remains part of report authoring.
"""
import json
import math
import re
from datetime import datetime
from pathlib import Path

from .common import digest, require, time


def pointer(document, path):
    require(isinstance(path, str) and path.startswith('/material/'), 'Claim pointers must start with /material/.')
    value = document
    for part in path[1:].split('/'):
        key = part.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def rendered(value, style):
    if style == 'percent':
        require(type(value) in (int, float) and 0 <= value <= 1, 'Percent claims require a probability.')
        return f'{value * 100:g}%'
    if style in ('date', 'month_year'):
        time(value)  # Validate timezone while retaining the recorded calendar date.
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return stamp.strftime('%Y-%m-%d' if style == 'date' else '%B %Y')
    require(style == 'literal', 'Claim format must be literal, percent, date or month_year.')
    require(type(value) in (str, int, float, bool), 'Report claims must select scalar recorded values.')
    return str(value)


def check(context_path, report_path, claims_path):
    context_path = Path(context_path)
    context = json.loads(context_path.read_text())
    archive_path = Path(context['full_material']['path'])
    if not archive_path.is_absolute():
        archive_path = context_path.parent / archive_path
    full = json.loads(archive_path.read_text())
    require(digest(full) == context['record_sha256'] == context['full_material']['sha256'],
            'Report snapshot hash mismatch.', 'integrity_error')
    report = Path(report_path).read_text()
    claims = json.loads(Path(claims_path).read_text())
    issues = []
    def problem(code, message):
        issues.append({'code': code, 'message': message})
    if claims.get('record_sha256') != context['record_sha256']:
        problem('stale_claims', 'Claim inventory belongs to a different report snapshot.')
    material = full['material']
    sources = {e['evidence_id']: e for e in material.get('evidence', [])}
    rows = claims.get('claims', [])
    if not rows:
        problem('missing_claims', 'Declare recorded numerical/date claims and their exact report passages.')
    seen = set()
    for row in rows:
        try:
            path, passage = row['pointer'], row['text']
            recorded = pointer(full, path)
            expected = rendered(recorded, row.get('format', 'literal'))
            if row['value'] != recorded:
                problem('value_mismatch', 'Declared value differs from the record: ' + path)
            if not passage or passage not in report or not re.search(r'(?<![\w.])' + re.escape(expected) + r'(?!\w|[.,]\d|%)', passage):
                problem('passage_mismatch', 'Report passage must contain the recorded rendered value: ' + path)
            seen.add(path)
            evidence_ids = row.get('evidence_ids', [])
            if '/evidence/' in path:
                index = int(path.split('/')[3])
                if material['evidence'][index]['evidence_id'] not in evidence_ids:
                    problem('missing_claim_citation', 'Evidence claim must cite its selected evidence record: ' + path)
            for eid in evidence_ids:
                require(eid in sources, 'Unknown evidence ID: ' + eid)
                urls = [s['url'] for s in sources[eid]['sources']]
                if not any('](' + url + ')' in passage or '](' + url + ')' in report for url in urls):
                    problem('missing_source_link', 'Link an original source for ' + eid)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            problem('invalid_claim', str(exc))
    issued = material.get('prediction', {}).get('issued')
    if issued and '/material/prediction/issued/probability' not in seen:
        problem('missing_forecast', 'Check the issued probability through a recorded claim.')
    if sources and not any('](' + source['url'] + ')' in report for e in sources.values() for source in e['sources']):
        problem('missing_citations', 'The report has evidence but no original source citations.')
    for row in claims.get('arithmetic', []):
        try:
            values = [pointer(full, p) for p in row['terms']]
            total = pointer(full, row['total'])
            if not all(type(v) in (int, float) for v in [*values, total]) or not math.isclose(math.fsum(values), total, rel_tol=1e-6):
                problem('arithmetic_mismatch', 'Recorded components do not sum to the reported total: ' + row['total'])
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            problem('invalid_arithmetic', str(exc))
    if re.search(r'\b(?:issued|produced|provides?|is|was) (?:a |an )?(?:well-)?calibrated probability', report, re.I):
        problem('unsupported_calibration', 'Issuance and deterministic calculation do not establish calibration; cite an actual calibration evaluation.')
    if re.search(r'\bno (?:language model|LLM) was used to generate the probability', report, re.I):
        problem('misleading_attribution', 'Disclose forecaster-supplied weights and inputs; arithmetic does not remove their authorship.')
    return {'ok': not issues, 'issues': issues, 'claims_checked': len(rows), 'record_sha256': context['record_sha256'],
            'qualification': 'Checks declared claims, arithmetic and source links. Does not certify source truth, semantic support or an exhaustive claim inventory.'}
