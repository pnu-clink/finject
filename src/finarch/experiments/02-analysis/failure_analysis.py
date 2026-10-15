"""A04: expose recorded review limitations and target output without modifying it."""
from importlib import import_module
import json
from pathlib import Path

reviews = import_module('finarch.experiments.02-analysis.02-comparison.response_assessments')
results = import_module('finarch.experiments.02-analysis.01-results.results')
store = reviews.store


def build(root, requests, backend):
    root = Path(root)
    comparison = root / '02_analysis/02_comparison'
    summary = store.read(comparison / 'response-assessment-summary.json')
    if summary is None:
        return None  # Legacy runs have no exhaustive review coverage.
    assessments = store.rows(comparison / 'response-assessments.jsonl')
    if store.file_hash(comparison / 'response-assessments.jsonl') != summary['response_assessments_sha256']:
        raise ValueError('FAILURE_ANALYSIS_ASSESSMENTS_CHANGED')
    failed = {row['response_id']: row for row in assessments if row['review_status'] != 'COMPLETED'}
    validation = {}
    for path in sorted((root / '01_evaluation/04_validation').glob('*/results.jsonl')):
        for row in store.rows(path):
            response_id = path.parent.name + ':' + row['trial_id']
            if response_id in failed:
                validation[response_id] = {k: row.get(k) for k in ('schema_errors', 'error', 'result_path')}
    records = []
    for req in requests:
        for row in req['input']['responses']:
            assessment = failed.get(row['response_id'])
            if assessment is None:
                continue
            judge = backend.latest(comparison, req) or {}
            records.append({**assessment,
                'recheck_required': assessment['review_status'] in reviews.RECHECK_STATUSES,
                'public_input': req['input']['inputs'].get(row['item_id'], {}).get('public', {}),
                'target_response': row.get('response'), 'target_tags': row.get('tags', []),
                'target_validation': validation.get(row['response_id'], {}),
                'judge_error': judge.get('error'), 'judge_validation_errors': judge.get('schema_errors', []),
                'source_request': '02_analysis/02_comparison/manifest.jsonl',
                'target_output_ownership': 'Evaluation target model; preserved, not corrected by Analysis.'})
    folder = root / '02_analysis/04_failure_analysis'
    # Small pages keep both live and offline viewer reads below their file-size limit.
    pages, batch, size = [], [], 0
    for record in records:
        record_size = len(json.dumps(record, ensure_ascii=False).encode())
        if batch and (len(batch) >= 50 or size + record_size > 1024 * 1024):
            pages.append(batch)
            batch, size = [], 0
        batch.append(record)
        size += record_size
    if batch:
        pages.append(batch)
    index = []
    for number, page in enumerate(pages, 1):
        relative = f'02_analysis/04_failure_analysis/page-{number:04d}/summary.json'
        store.write(root / relative, {'run': root.name, 'records': page})
        for row in page:
            index.append({**{k: row[k] for k in ('response_id', 'case', 'variant', 'model',
                'prompt_condition', 'reasoning', 'review_status', 'recheck_required')}, 'page': relative})
    value = {'schema_version': 1, 'run': root.name, 'status': 'COLLECTED', 'processor': 'PYTHON',
        'planned': summary['overall']['planned'], 'review_gate': reviews.gate(summary),
        'records': index, 'record_count': len(records), 'new_model_calls': 0,
        'response_assessments_sha256': summary['response_assessments_sha256'],
        'boundary': 'Review limitations and recorded errors, not a correction or a new semantic judgment.'}
    store.write(folder / 'summary.json', value)
    store.write(folder / 'state.json', {k: value[k] for k in ('status', 'record_count', 'new_model_calls', 'review_gate')})
    results.render(root, '04_failure_analysis', count=len(records))
    store.event(root, 'ANALYSIS_FAILURE_DETAILS_COLLECTED', stage='A04', records=len(records),
                recheck_required=value['review_gate']['recheck_required'], new_model_calls=0)
    return value
