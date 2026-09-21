"""Link research questions and declared evidence transfers to actual model inputs.

These checks establish coverage and consistency, not substantive truth. The
forecaster supplies the transfer assumptions and ranges; the package checks
their links and calculates their consequences.
"""

import copy

from .common import Error, require, time


def validate_intake(plan):
    inputs = {r["id"] for r in plan["inputs"]}
    require(len(inputs) == len(plan["inputs"]), "Research input IDs must be unique.")
    questions = plan["unknowns"]
    require(len(questions) <= 100 and len({q["id"] for q in questions}) == len(questions),
            "Use at most 100 uniquely named research questions.")
    for q in questions:
        require(set(q["input_ids"]) <= inputs, "Research questions must link to declared input IDs.")


def model_inputs(payload, timeline_spec=None):
    """Stable paths identify each supplied number, not an inferred importance rank."""
    method = payload["method"]
    if method == "judgment":
        return {"probability": payload["probability"]}
    if method == "scenario_mixture":
        return {f"scenarios/{s['id']}/{field}": s[field]
                for s in payload["scenarios"] for field in ("weight", "probability")}
    if method == "conditional_path":
        return {f"components/{c['id']}/probability": c["probability"] for c in payload["components"]}
    if method == "odds_ledger":
        ledger = payload["odds_ledger"]
        values = {"anchor/probability": ledger["anchor"]["probability"]}
        values.update({f"entries/{e['finding_id']}/lr": e["lr"] for e in ledger["entries"]})
        values.update({f"joint/{e['dependence_group']}/lr": e["lr"] for e in ledger["joint_declarations"]})
        return values
    if method == "timeline_model":
        values = {}
        for s in timeline_spec["scenarios"]:
            if "weight" in s:
                values[f"scenarios/{s['id']}/weight"] = s["weight"]
            for a in s["assessments"]:
                if "value" in a:
                    values[f"scenarios/{s['id']}/inputs/{a['parameter_id']}"] = a["value"]
        return values
    weights = payload.get("weights", [1 / len(payload["members"])] * len(payload["members"]))
    return {f"members/{m}/weight": w for m, w in zip(payload["members"], weights)}


def validate_support(payload, plan, timeline_spec=None, *, transfer_version=0):
    expected = model_inputs(payload, timeline_spec)
    rows = payload.get("parameter_support", [])
    require(len({r["model_input"] for r in rows}) == len(rows) and
            {r["model_input"] for r in rows} == set(expected),
            "Supply parameter_support for every model input, separately for scenario weights and conditional probabilities. "
            "Expected model_input paths: " + ", ".join(expected))
    ids = {r["id"] for r in plan["inputs"]}
    for row in rows:
        require(row["input_id"] in ids, "Parameter support references an unknown intake input.")
        if row.get("transfer"):
            validate_transfer(row)
        elif transfer_version == 1 and row["basis"] != "assumed":
            require(False, "Evidence-backed inputs require a versioned transfer with source and target estimands.")
        value = expected[row["model_input"]]
        require(row["value"] == value, "Parameter support value differs from the actual model input: " + row["model_input"])
        bounds = row["plausible_range"]
        require(len(bounds) == 2, "Plausible ranges need exactly two endpoints.")
        if isinstance(value, (int, float)):
            require(all(type(v) in (int, float) for v in bounds) and bounds[0] <= value <= bounds[1],
                    "Plausible range must contain the model input.")
            require(bounds[0] >= 0, "Model input ranges cannot be negative.")
            if row["model_input"].endswith("/lr"):
                require(bounds[0] > 0, "Likelihood-ratio ranges must be strictly positive.")
            if row["model_input"] == "probability" or row["model_input"].endswith(("/probability", "/weight")):
                require(bounds[1] <= 1, "Probability ranges cannot exceed one.")
        elif value == "never":
            require(bounds == ["never", "never"], "Use separate scenarios to represent never versus a completion date.")
        else:
            require(all(isinstance(v, str) for v in bounds) and time(bounds[0]) <= time(value) <= time(bounds[1]),
                    "Date range must contain the model date.")
        require(row["basis"] == "assumed" or row["evidence_refs"],
                "Measured, calculated, or extrapolated inputs require evidence references; use assumed when unsupported.")
    return rows



def validate_transfer(row):
    transfer = row['transfer']
    source, target = transfer['source'], transfer['target']
    differences = [key for key in source if source[key] != target[key]]
    if differences:
        require(row['basis'] in ('extrapolated', 'assumed'),
                'Different source/target estimands require extrapolated or assumed basis: ' + ', '.join(differences))
        require(transfer['quantitative_support'] != 'direct',
                'A benchmark mismatch cannot provide direct quantitative support.')
    if transfer['quantitative_support'] == 'calculated':
        require(transfer.get('calculation'), 'Calculated transfers need a reproducible calculation description.')
    if row['basis'] == 'measured':
        require(transfer['quantitative_support'] == 'direct', 'Measured inputs need direct quantitative support.')
    if row['basis'] == 'calculated':
        require(transfer['quantitative_support'] == 'calculated', 'Calculated inputs need a calculation.')
    return differences

def mixture(payload):
    """Use the declared support ranges without silently replacing explicit ranges."""
    spec = {k: copy.deepcopy(payload[k]) for k in ("scenarios", "partition_justification")}
    support = {r["model_input"]: r for r in payload.get("parameter_support", [])}
    for row in spec["scenarios"]:
        for field in ("weight", "probability"):
            key = f"scenarios/{row['id']}/{field}"
            if key in support:
                bounds = support[key]["plausible_range"]
                require(field + "_range" not in row or row[field + "_range"] == bounds,
                        "Scenario range differs from its parameter support: " + key)
                row[field + "_range"] = bounds
    return spec


def quantity(path, method):
    if method == 'timeline_model' and '/inputs/' in path:
        return 'timeline_input'
    if path.endswith('/lr'):
        return 'likelihood_ratio'
    if path.endswith('/weight'):
        return 'ensemble_weight' if method == 'ensemble' else 'scenario_weight'
    if method in ('scenario_mixture', 'conditional_path'):
        return 'conditional_probability'
    return 'probability'


def validate_map(payload, plan, previous=None, timeline_spec=None):
    """Require an explicit, immutable mapping on every assessment pass."""
    require('model_map' in payload, 'Supply model_map: version the mapping from research questions to actual model quantities.')
    mapping = payload['model_map']
    version = previous['version'] if previous else 0
    require(mapping['previous_version'] == version and mapping['version'] == version + 1,
            'Model map version is stale; use previous_version from context.model_map and increment version.')
    expected = model_inputs(payload, timeline_spec)
    rows = mapping['inputs']
    require(len(rows) == len(expected) and {r['model_input'] for r in rows} == set(expected),
            'Model map must cover every actual model input exactly once.')
    ids = {i['id'] for i in plan['inputs']}
    support = {r['model_input']: r for r in payload['parameter_support']}
    for row in rows:
        path = row['model_input']
        require(set(row['input_ids']) <= ids, 'Model map references unknown research input IDs.')
        require(row['quantity'] == quantity(path, payload['method']),
                'Wrong quantity type for ' + path + '; scenario weights and conditional probabilities are distinct.')
        require(row['target'] == support[path]['target'] and support[path]['input_id'] in row['input_ids'],
                'Model map target/input IDs disagree with parameter support for ' + path)
    return mapping


def validate_challenge(payload, state):
    mapping = state['model_map']
    require(payload['map_version'] == mapping['version'], 'Challenge targets a stale model map.')
    paths = set(state['model_inputs'])
    rows = payload['transfers']
    require(len(rows) == len(paths) and {r['model_input'] for r in rows} == paths,
            'Challenge must inspect the evidence transfer for every model input exactly once.')
    support = {r['model_input']: r for r in state['parameter_support']}
    for row in rows:
        transfer = support[row['model_input']].get('transfer')
        if transfer:
            require(all(k in row for k in ('source_fidelity', 'directional_relevance', 'quantitative_support')),
                    'Review source fidelity, directional relevance and quantitative support separately.')
            require(row['quantitative_support'] == transfer['quantitative_support'],
                    'Challenge quantitative support disagrees with the recorded transfer.')
            if row['verdict'] == 'supported':
                require(row['source_fidelity'] == 'verified' and row['directional_relevance'] == 'relevant'
                        and row['quantitative_support'] != 'judgment',
                        'Qualitative relevance or a judgment transfer cannot be marked quantitatively supported.')
        if row['verdict'] == 'supported':
            require(row['evidence_refs'] and support[row['model_input']]['basis'] != 'assumed',
                    'An assumed or uncited input cannot be marked supported.')
            require(all(ref in support[row['model_input']]['evidence_refs'] for ref in row['evidence_refs']),
                    'A supported verdict must inspect the evidence cited for that model input.')
    concerns = payload['concerns']
    if state.get('event_alignment'):
        alignment = payload.get('event_alignment')
        require(alignment and alignment['target'] == state['event_alignment']['target'],
                'Challenge must map the actual target milestone to the question in event_alignment.')
        require(set(alignment['concern_ids']) <= {c['id'] for c in concerns}, 'Event alignment names an unknown concern.')
        require(alignment['matches_question'] or alignment['concern_ids'], 'A target/event mismatch needs a concern.')
    require(len({c['id'] for c in concerns}) == len(concerns), 'Concern IDs must be unique.')
    for concern in concerns:
        require(set(concern['model_inputs']) <= paths, 'Concern must link to actual model inputs.')
    mismatches = {r['model_input'] for r in rows if r['verdict'] == 'mismatch'}
    mismatches |= {path for path, item in support.items() if item.get('transfer') and
                   (item['transfer']['source'] != item['transfer']['target'] or
                    item['transfer']['quantitative_support'] == 'judgment')}

    require(mismatches <= {p for c in concerns for p in c['model_inputs']},
            'Each mismatched evidence transfer needs a concern and a disposition.')
    scenarios = state.get('scenario_ids', [])
    if scenarios:
        require(len(payload['boundary_cases']) >= 2,
                'Test at least two concrete boundary trajectories, including a reversal before the deadline.')
        for case in payload['boundary_cases']:
            require(len(set(case['scenario_ids'])) == len(case['scenario_ids']) and
                    set(case['scenario_ids']) <= set(scenarios), 'Boundary case names an unknown or duplicate scenario.')
            require(set(case.get('concern_ids', [])) <= {c['id'] for c in concerns},
                    'Boundary case links an unknown concern.')
            require(len(case['scenario_ids']) == 1 or case.get('concern_ids'),
                    'An uncovered or overlapping boundary case needs a concern.')
    else:
        require(not payload['boundary_cases'], 'Boundary scenarios require a scenario model.')


def followup_inquiries(payload, state):
    """Turn review dispositions into executable inquiries; retain deferred gaps."""
    challenge = state['model_challenge']
    concerns = {c['id']: c for c in challenge['concerns']}
    rows = payload.get('concern_resolutions', [])
    require(len(rows) == len(concerns) and {r['concern_id'] for r in rows} == set(concerns),
            'Resolve each model challenge concern exactly once in concern_resolutions.')
    mapping = {r['model_input']: r for r in state['model_map']['inputs']}
    inquiries = []
    for row in rows:
        concern = concerns[row['concern_id']]
        if row['disposition'] == 'investigate':
            ids = sorted({i for p in concern['model_inputs'] for i in mapping[p]['input_ids']})
            inquiries.append({'id': f"map{state['model_map']['version']}:{concern['id']}",
                              'question': concern['question'], 'input_ids': ids, 'route': row.get('route', 'search'),
                              'why_it_matters': row['rationale'], 'action': row['action'],
                              'concern_id': concern['id'], 'model_inputs': concern['model_inputs']})
        else:
            require('route' not in row, 'A research route applies only to an investigate disposition.')
    require(bool(inquiries) == (payload['decision'] == 'research'),
            'Use decision research exactly when a concern is marked investigate.')
    return inquiries


def timeline_sensitivity(spec, support):
    """Compute declared one-input range endpoints, retaining the joint scenarios."""
    from . import timeline
    base = timeline.analyze(spec)
    rows = []
    require(len(support) <= 2000, 'Timeline sensitivity is limited to 2000 supported inputs.')
    for item in support:
        path = item['model_input']
        _, sid, field, *parameter = path.split('/')
        for value in dict.fromkeys(item['plausible_range']):
            if value == item['value']:
                continue
            candidate = copy.deepcopy(spec)
            scenario = next(s for s in candidate['scenarios'] if s['id'] == sid)
            row = {'model_input': path, 'value': value}
            try:
                if field == 'weight':
                    remaining = 1 - scenario['weight']
                    require(remaining > 0, 'Cannot redistribute weight from a single positive-weight scenario.')
                    for other in candidate['scenarios']:
                        if other['id'] != sid:
                            other['weight'] *= (1 - value) / remaining
                    scenario['weight'] = value
                else:
                    assessment = next(a for a in scenario['assessments'] if a['parameter_id'] == parameter[0])
                    require(assessment['basis'] != 'observed', 'Observed inputs need new evidence, not a sensitivity substitution.')
                    assessment.update(value=value, basis='assumed', evidence_refs=[], rationale='Declared range stress test.')
                result = timeline.analyze(candidate)
                row.update(probability=result['probability'], delta=result['probability'] - base['probability'])
            except Error as exc:
                row['invalid_combination'] = str(exc)
            rows.append(row)
    return {'probability': base['probability'], 'substitutions': sorted(rows, key=lambda r: -abs(r.get('delta', 0))),
            'successful_scenarios': [s['scenario_id'] for s in base['scenarios'] if s['meets_deadline']],
            'point_ranges': [r['model_input'] for r in support if r['plausible_range'][0] == r['plausible_range'][1]],
            'limitations': ['One-input range endpoints are stress tests, not confidence intervals or calibration evidence.',
                            'Weight changes redistribute other weights proportionally; this is an explicit sensitivity convention.',
                            'Joint movements, structural alternatives and intermediate thresholds are not covered.'],
            'range_status': ('declared_ranges' if rows else 'All declared ranges are point values; no variation was tested.')
                            if support else 'No declared input ranges; sensitivity remains unassessed.'}
