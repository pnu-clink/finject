"""Collect validated response reviews; never infer verdicts from pattern notes."""
from collections import Counter, defaultdict
from importlib import import_module
from hashlib import sha256

store = import_module('finarch.experiments.90-operations.storage')
contracts = import_module('finarch.experiments.02-analysis.contracts')
FIELDS = ('abstention_reason_validity', 'decision_grounding')
RECHECK_STATUSES = frozenset(('NOT_REVIEWED', 'REVIEW_FAILED'))


def recheck_trials(requests, backend, folder):
    """Select failed/missing judge calls only when their targets can be reviewed."""
    selected = set()
    for req in requests:
        if 'response_assessments' not in req.get('response_schema', {}).get('properties', {}):
            return None  # Frozen V1 requests retain their original call-based gate.
        result = backend.latest(folder, req)
        if result and result.get('status') == 'VALID':
            continue
        if any(row['variant'] != 'ORIGINAL' and contracts.review_status(row, req) == 'COMPLETED'
               for row in req['input']['responses']):
            selected.add(req['trial_id'])
    return selected


def gate(summary):
    """Unreviewed/failed reviews block A03; unavailable targets remain limitations."""
    counts = summary['overall']['review_status']
    return {'blocked': any(counts.get(k, 0) for k in RECHECK_STATUSES),
            'recheck_required': sum(counts.get(k, 0) for k in RECHECK_STATUSES),
            'review_status': counts,
            'nonblocking_statuses': ['NOT_REVIEWABLE', 'SOURCE_MISSING']}


def apply_gate(state, summary):
    if summary is None or state['status'] == 'PAUSED_BY_USER':
        return state
    review_gate = gate(summary)
    return {**state, 'model_call_status': state.get('model_call_status', state['status']),
            'status': 'BLOCKED' if review_gate['blocked'] else 'COLLECTED',
            'reason': 'REVIEW_RETRY_REQUIRED' if review_gate['blocked'] else None,
            'review_gate': review_gate}


def outcome(assessment, response):
    """Return True/False only for resolved reviews of the applicable decision."""
    if assessment['review_status'] != 'COMPLETED':
        return None
    verdicts = [assessment['decision_grounding']['verdict']]
    if response.get('answer') is None:
        verdicts.append(assessment['abstention_reason_validity']['verdict'])
    if 'UNSUPPORTED' in verdicts:
        return False
    return True if all(v == 'SUPPORTED' for v in verdicts) else None


def collect(root, requests, backend):
    """Preserve one row per planned variant, including failed/pending judge calls."""
    if not any('response_assessments' in req['response_schema']['properties'] for req in requests):
        return None
    folder = root / '02_analysis/02_comparison'
    records, seen = [], set()
    for req in requests:
        result = backend.latest(folder, req)
        supported = 'response_assessments' in req['response_schema']['properties']
        valid = supported and result and result['status'] == 'VALID'
        if valid:
            errors = contracts.validate_response(result['response'], req)
            if errors:
                raise ValueError('SAVED_ASSESSMENT_VALIDATION_CHANGED:' + str(errors))
        assessments = {a['response_id']: a for a in result['response']['response_assessments']} if valid else {}
        for row in req['input']['responses']:
            if row['variant'] == 'ORIGINAL':
                continue
            response_id = row['response_id']
            if response_id in seen:
                raise ValueError('DUPLICATE_ASSESSMENT_RESPONSE:' + response_id)
            seen.add(response_id)
            status = result['status'] if result else 'NOT_RUN'
            assessment = assessments.get(response_id)
            if assessment is None:
                material_status = contracts.review_status(row, req)
                if material_status == 'NOT_REVIEWABLE':
                    review_status = material_status
                    reason = 'Target response is not structurally valid; target status: ' + row['status']
                elif material_status == 'SOURCE_MISSING':
                    review_status = material_status
                    reason = 'Question or context is absent from the frozen public input.'
                else:
                    review_status = 'REVIEW_FAILED' if supported and result and status != 'VALID' else 'NOT_REVIEWED'
                    reason = 'No validated response assessment is available; judge call status: ' + status
                assessment = {'response_id': response_id,
                    'review_status': review_status,
                    **{field: {'verdict': None, 'reason': reason, 'citations': []} for field in FIELDS}}
            record = {**assessment, 'assessment_id': req['trial_id'] + ':' + response_id,
                'rubric_version': 'ResponseGroundingV1' if supported else None,
                'trial_id': req['trial_id'], 'request_sha256': store.digest(req),
                'prompt_sha256': sha256(req['prompt'].encode()).hexdigest(), 'schema_sha256': store.digest(req['response_schema']),
                'input_sha256': store.digest(req['input']),
                **{field: row[field] for field in ('case', 'item_id', 'variant', 'model', 'prompt_condition', 'reasoning')},
                'response_status': row['status'], 'judge_call_status': status,
                'adaptation_success': outcome(assessment, row.get('response') or {})}
            records.append(record)
    groups = defaultdict(list)
    for record in records:
        groups[tuple(record[k] for k in ('model', 'variant', 'prompt_condition', 'reasoning'))].append(record)

    def counts(rows):
        return {'planned': len(rows), 'review_status': dict(Counter(r['review_status'] for r in rows)),
            'adaptation_outcome': dict(Counter('SUCCESS' if r['adaptation_success'] is True else
                'FAILURE' if r['adaptation_success'] is False else 'UNDETERMINED_OR_UNREVIEWED' for r in rows)),
            **{field: dict(Counter(r[field]['verdict'] or 'UNREVIEWED' for r in rows)) for field in FIELDS}}

    summary = {'rubric_version': 'ResponseGroundingV1', 'denominator': 'All planned non-ORIGINAL responses',
        'overall': counts(records), 'groups': [dict(zip(('model', 'variant', 'prompt_condition', 'reasoning'), key))
            | counts(rows) for key, rows in sorted(groups.items())],
        'boundary': 'LLM judgments with structural and citation validation; not human-verified gold or original correctness.'}
    store.write_rows(folder / 'response-assessments.jsonl', records)
    summary['response_assessments_sha256'] = store.file_hash(folder / 'response-assessments.jsonl')
    summary['review_gate'] = gate(summary)
    store.write(folder / 'response-assessment-summary.json', summary)
    store.write(folder / 'response-assessment-coverage.json', {'planned': len(records),
        'review_status': summary['overall']['review_status'],
        'response_ids_by_status': {status: [r['response_id'] for r in records if r['review_status'] == status]
            for status in sorted({r['review_status'] for r in records})},
        'response_assessments_sha256': summary['response_assessments_sha256']})
    return summary
