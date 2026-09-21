"""Offline report fidelity checks against a hash-bound reporting snapshot.

Checks verify declared claims and citations, not source truth or completeness of
an author's claim inventory. Semantic reading remains part of report authoring.
"""
import json
import math
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
from pathlib import Path

from .common import digest, require, time
from .evidence import citation_anchor


def pointer(document, path):
    require(isinstance(path, str) and path.startswith('/material/'), 'Claim pointers must start with /material/.')
    value = document
    for part in path[1:].split('/'):
        key = part.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def equivalent(actual, recorded):
    if type(actual) in (int, float) and type(recorded) in (int, float):
        if not math.isfinite(actual) or not math.isfinite(recorded):
            return False
        return actual == recorded or abs(actual - recorded) <= 4 * max(math.ulp(actual), math.ulp(recorded))
    return type(actual) is type(recorded) and actual == recorded


def rendered(value, style, *, precision=None, rounding="half_even"):
    require(rounding in ("half_even", "half_up"), "Rounding must be half_even or half_up.")
    require(precision is None or (type(precision) is int and 0 <= precision <= 12),
            "Precision must be an integer from 0 to 12.")
    require(precision is None or style in ("percent", "literal"), "Precision applies only to numbers.")
    if precision is not None:
        require(type(value) in (int, float) and math.isfinite(value), "Precision requires a finite number.")
        require(style != "percent" or 0 <= value <= 1, "Percent claims require a probability.")
        number = Decimal(str(value)) * (100 if style == "percent" else 1)
        with localcontext() as context:
            context.prec = max(28, number.adjusted() + precision + 2)
            rounded = number.quantize(Decimal(1).scaleb(-precision),
                                     rounding=ROUND_HALF_EVEN if rounding == "half_even" else ROUND_HALF_UP)
        return format(rounded, f".{precision}f") + ("%" if style == "percent" else "")
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



def required_evidence(full, path):
    """Resolve recorded dependencies; the author cannot delete them from a claim."""
    if path.startswith('/material/evidence/'):
        return {full['material']['evidence'][int(path.split('/')[3])]['evidence_id']}
    refs = []
    if path.startswith('/material/prediction/issued/'):
        model = full['material'].get('model', {})
        for support in model.get('parameter_support', []):
            refs.extend(support.get('evidence_refs', []))
        refs.extend((model.get('assessment') or {}).get('answer', {}).get('evidence_refs', []))
    else:
        parts = path.split('/')
        for end in range(len(parts) - 1, 1, -1):
            parent = pointer(full, '/'.join(parts[:end]))
            if isinstance(parent, dict) and 'evidence_refs' in parent:
                refs = parent['evidence_refs']
                break
        if not refs and path.startswith('/material/model/model_inputs/'):
            key = path.removeprefix('/material/model/model_inputs/').replace('~1', '/').replace('~0', '~')
            refs = next((r.get('evidence_refs', []) for r in full['material'].get('model', {}).get('parameter_support', [])
                         if r['model_input'] == key), [])
    return {r['packet_id'] + ':' + r['record_id'] for r in refs}


def cited(evidence_id, record, report):
    for source in record['sources']:
        if source.get('kind', 'public') == 'public':
            if '](' + source.get('url', '') + ')' in report:
                return True
        else:
            anchor = citation_anchor(evidence_id)
            definition = re.search(r'^\[\^' + re.escape(anchor) + r'\]: (.+)$', report, re.M)
            if definition and source.get('attribution') in definition.group(1) and re.search(
                    r'\[\^' + re.escape(anchor) + r'\](?!:)', report):
                return True
    return False

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
            expected = rendered(recorded, row.get('format', 'literal'), precision=row.get('precision'), rounding=row.get('rounding', 'half_even'))
            if not equivalent(row['value'], recorded):
                problem('value_mismatch', f'Declared value {row["value"]!r} differs from recorded {recorded!r} at {path}; expected display {expected!r}')
            if not passage or passage not in report or not re.search(r'(?<![\w.])' + re.escape(expected) + r'(?!\w|[.,]\d|%)', passage):
                problem('passage_mismatch', 'Report passage must contain the recorded rendered value: ' + path)
            seen.add(path)
            evidence_ids = row.get('evidence_ids', [])
            required = required_evidence(full, path)
            if not path.startswith('/material/prediction/issued/') and not required <= set(evidence_ids):
                problem('missing_claim_citation', 'Preserve recorded evidence connections for ' + path)
            for eid in set(evidence_ids) | required:
                require(eid in sources, 'Unknown evidence ID: ' + eid)
                if not cited(eid, sources[eid], report):
                    problem('missing_source_link', 'Cite the original source or attributed private footnote for ' + eid)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            problem('invalid_claim', str(exc))
    issued = material.get('prediction', {}).get('issued')
    if issued and '/material/prediction/issued/probability' not in seen:
        problem('missing_forecast', 'Check the issued probability through a recorded claim.')
    if sources and not any(cited(eid, e, report) for eid, e in sources.items()):
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
    return {'ok': not issues, 'issues': issues, 'claims_checked': len(rows),
            'citation_scope': 'Recorded dependencies and attributed private footnotes; public sources use original links.', 'record_sha256': context['record_sha256'],
            'qualification': 'Checks declared claims, arithmetic and source links. Does not certify source truth, semantic support or an exhaustive claim inventory.'}
