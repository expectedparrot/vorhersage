"""Host approval boundary. Agent-authored labels are never authenticated receipts.

Only a trusted host callback may resolve opaque receipt IDs. This package does
not authenticate host users or enforce the external EP workflow's gates.
"""
import re
from .common import now, require, time

SCOPES = {'task_authorization', 'design_approval', 'optional_review'}
GUIDANCE = (
    'Task authorization, factual answers, model-design approval and optional-review choices are distinct. '
    'Do not invent user attestations or backdate workflow gates. Reuse real authorization within its scope. '
    'No approval is required by this handoff by default; do not introduce confirmation prompts to fill optional fields. '
    'Only the host can verify user receipts and enforce its own required gates. Agent-supplied by=user is not verification. '
    'Keep private messages out of reports; genuine retrospective imports preserve occurrence and recording times.'
)


def inspect(subject_sha256, receipt_refs=(), *, required_scopes=(), verifier=None):
    """Resolve receipts through trusted host code, exporting only a safe summary.

    verifier(ref) must independently retrieve/authenticate the host record; it
    must not trust a caller's actor label or verification boolean. Its record
    binds scope/action/actor_kind, subject_sha256, occurred_at, recorded_at and
    imported to that opaque ref. Required scopes are host policy, not inferred.
    """
    require(set(required_scopes) <= SCOPES, 'Unknown required approval scope.')
    records = []
    satisfied = set()
    for ref in receipt_refs:
        require(isinstance(ref, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', ref), 'Use opaque receipt IDs, not messages or URLs.')
        if verifier is None:
            records.append({'receipt_ref': ref, 'verification': 'unverified'})
            continue
        record = verifier(ref)
        require(isinstance(record, dict) and record.get('receipt_ref') == ref, 'Host did not verify this receipt.')
        require(record.get('actor_kind') == 'user' and record.get('scope') in SCOPES, 'Receipt lacks a host-authenticated user scope.')
        require(record.get('subject_sha256') == subject_sha256, 'Approval applies to a different artifact/version.')
        require(record.get('action') in ('approved', 'declined', 'skipped'), 'Unknown receipt action.')
        require(time(record.get('occurred_at')) <= time(record.get('recorded_at')) <= time(now()), 'Invalid approval chronology.')
        require(type(record.get('imported')) is bool, 'Host must declare whether the receipt was imported.')
        if record['action'] == 'approved':
            satisfied.add(record['scope'])
        records.append({**{k: record[k] for k in ('receipt_ref', 'scope', 'action', 'occurred_at', 'recorded_at', 'imported')},
                        'verification': 'host_verified'})
    missing = sorted(set(required_scopes) - satisfied)
    return {'status': 'not_required' if not required_scopes else 'missing' if missing else 'verified',
            'required_scopes': sorted(set(required_scopes)), 'missing_scopes': missing, 'records': records,
            'guidance': GUIDANCE, 'enforcement_owner': 'Calling host; independent of forecast readiness.'}
