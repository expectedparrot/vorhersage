"""Bounded report arithmetic and heuristic inventory assistance; never execute code."""
import math
import re
from zoneinfo import ZoneInfo

from .common import require, time

UNITS = {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400, 'weeks': 604800}


def evaluate(expression, full):
    from .report_check import pointer
    op, terms = expression['op'], expression['terms']
    require(isinstance(terms, list) and 1 <= len(terms) <= 100, 'Expressions need 1..100 recorded terms.')
    values = [pointer(full, p) for p in terms]
    if op == 'duration':
        require(len(values) == 2, 'Duration requires start and end timestamps.')
        start, end = map(time, values)
        require(end >= start, 'Duration end precedes start.')
        mode = expression['mode']
        if mode == 'elapsed':
            require(expression.get('unit') in UNITS, 'Declare an elapsed duration unit.')
            return (end - start).total_seconds() / UNITS[expression['unit']]
        require(mode == 'calendar_days', 'Duration mode must be elapsed or calendar_days; business calendars are not inferred.')
        require(expression.get('timezone'), 'Calendar days require an explicit IANA timezone.')
        zone = ZoneInfo(expression['timezone'])
        require(type(expression.get('inclusive', False)) is bool, 'Inclusive must be boolean.')
        return (end.astimezone(zone).date() - start.astimezone(zone).date()).days + int(expression.get('inclusive', False))
    require(all(type(v) in (int, float) and math.isfinite(v) for v in values), 'Arithmetic requires finite numeric records.')
    if op == 'sum':
        result = math.fsum(values)
    elif op == 'product':
        result = math.prod(values)
    elif op == 'difference':
        require(len(values) == 2, 'Difference requires two terms.')
        result = values[0] - values[1]
    elif op == 'convert':
        require(len(values) == 1 and expression.get('from_unit') in UNITS and expression.get('to_unit') in UNITS,
                'Conversion requires one term and supported time units.')
        result = values[0] * UNITS[expression['from_unit']] / UNITS[expression['to_unit']]
    else:
        require(False, 'Unsupported expression operation: ' + str(op))
    require(math.isfinite(result), 'Derived result must be finite.')
    return result


def coverage(report, rows, exclusions, full):
    from .report_check import pointer, rendered
    checked, excluded, errors = [], [], []
    for row in rows:
        try:
            value = evaluate(row['expression'], full) if 'expression' in row else pointer(full, row['pointer'])
            expected = rendered(value, row.get('format', 'literal'), precision=row.get('precision'), rounding=row.get('rounding', 'half_even'))
            passage = row['text']
            if not passage:
                continue
            for occurrence in re.finditer(re.escape(passage), report):
                for token in re.finditer(re.escape(expected), passage):
                    checked.append((occurrence.start() + token.start(), occurrence.start() + token.end()))
        except (KeyError, TypeError, ValueError, IndexError, OverflowError):
            continue  # The fidelity checker reports malformed claims.
    for row in exclusions:
        if not row.get('reason', '').strip() or not row.get('text') or row['text'] not in report:
            errors.append('Every coverage exclusion needs an exact report passage and a reason.')
            continue
        excluded.extend((m.start(), m.end()) for m in re.finditer(re.escape(row['text']), report))
    unchecked = []
    for match in re.finditer(r'(?<![\w])\d+(?:[.,]\d+)*(?:%)?', report):
        if any(lo <= match.start() and match.end() <= hi for lo, hi in checked + excluded):
            continue
        line = report.count('\n', 0, match.start()) + 1
        unchecked.append({'line': line, 'token': match.group(), 'excerpt': report[max(0, match.start()-35):match.end()+35]})
    return {'unchecked_count': len(unchecked), 'unchecked': unchecked[:200], 'exclusions': exclusions, 'errors': errors,
            'qualification': 'Heuristic numeric/date coverage; unchecked tokens are review leads, not proof of error. Bibliography numbers may be explicitly excluded.'}


def suggestions(full, report):
    from .report_check import rendered, required_evidence
    candidates = []
    def walk(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, path + '/' + key.replace('~', '~0').replace('/', '~1'))
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, path + '/' + str(i))
        elif type(value) in (int, float):
            candidates.append((path, value, 'percent' if 0 <= value <= 1 and any(x in path for x in ('probability', 'bounded_range', 'parameter_support')) else 'literal'))
        elif isinstance(value, str):
            try:
                time(value)
                candidates.append((path, value, 'date'))
            except ValueError:
                pass
    material = full['material']
    walk(material.get('question', {}), '/material/question')
    issued = material.get('prediction', {}).get('issued') or {}
    if 'probability' in issued:
        walk(issued['probability'], '/material/prediction/issued/probability')
    for i, support in enumerate(material.get('model', {}).get('parameter_support', [])):
        value = support['value']
        path = f'/material/model/parameter_support/{i}/value'
        if type(value) in (int, float):
            probability = support['model_input'] == 'probability' or support['model_input'].endswith(('/weight', '/probability'))
            candidates.append((path, value, 'percent' if probability else 'literal'))
        else:
            walk(value, path)
    bounds = material.get('model', {}).get('sensitivity') or {}
    walk(bounds.get('bounded_range', []), '/material/model/sensitivity/bounded_range')
    for i, record in enumerate(material.get('evidence', [])):
        walk(record.get('value'), f'/material/evidence/{i}/value')
    result = []
    for path, value, style in candidates:
        display = rendered(value, style)
        lines = [line for line in report.splitlines() if re.search(r'(?<![\w.])' + re.escape(display) + r'(?!\w|[.,]\d|%)', line)]
        result.append({'pointer': path, 'value': value, 'format': style, 'text': None,
                       'candidate_passages': lines[:10], 'evidence_ids': sorted(required_evidence(full, path))})
    return result
