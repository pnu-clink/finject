"""Audit completed Luna API artifacts and render an offline run summary."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
table = __import__('finarch.experiments.02-analysis.legacy.content-analysis.analysis', fromlist=['table']).table
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
validate_cache_body = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['validate_cache_body']).validate_cache_body


def build(root):
    root = Path(root).resolve()
    pipeline.verify(root)
    config, summary = read(root / 'config.json'), read(root / 'summary.json')
    if summary['status'] != 'FINISHED':
        raise ValueError('COMPLETED_COLLECTION_REQUIRED')
    model = next(m for m in config['models'] if m['transport'] == 'openai_responses')
    key = model['key']
    requests = rows(root / key / '01-requests/manifest.jsonl')
    result_rows = rows(root / key / '03-results/results.jsonl')
    diagnostics = rows(root / 'analysis/response-diagnostics.jsonl')
    model_summary = next(m for m in summary['models'] if m['model'] == key)
    pairs, condition_usage, hashes = defaultdict(dict), defaultdict(Counter), {}
    issues = []
    request_map = {r['trial_id']: r for r in requests}
    all_results = []
    for row in result_rows:
        path = root / row['result_path']
        result = read(path)
        request = request_map[row['trial_id']]
        body = read(path.parent / 'provider-request.json')
        raw = read(path.parent / 'raw-response.json')
        validate_cache_body(body)
        check = cache_policy.usage_check(model['transport'], raw.get('usage'))
        if check['status'] != 'VERIFIED_ZERO' or raw.get('usage') != result.get('usage'):
            issues.append({'trial_id': row['trial_id'], 'error': 'CACHE_USAGE_NOT_VERIFIED'})
        if (raw.get('model') != model['model'] or raw.get('status') != 'completed'
                or raw.get('prompt_cache_options', {}).get('mode') != 'explicit'):
            issues.append({'trial_id': row['trial_id'], 'error': 'RETURNED_MODEL_STATUS_OR_CACHE_MODE_MISMATCH'})
        if body['instructions'] != request['prompt'] or body['reasoning']['effort'] != request['reasoning_effort']:
            issues.append({'trial_id': row['trial_id'], 'error': 'FROZEN_PROMPT_OR_REASONING_MISMATCH'})
        if (json.loads(body['input'][0]['content'][0]['text']) != request['input']
                or body['text']['format']['schema'] != {k: v for k, v in request['response_schema'].items() if k not in ('$schema', 'title')}):
            issues.append({'trial_id': row['trial_id'], 'error': 'FROZEN_INPUT_OR_SCHEMA_MISMATCH'})
        raw_text = ''.join(part.get('text', '') for item in raw.get('output', []) if item.get('type') == 'message'
                           for part in item.get('content', []) if part.get('type') == 'output_text')
        if json.loads(raw_text) != result.get('response'):
            issues.append({'trial_id': row['trial_id'], 'error': 'RAW_RESPONSE_DIFFERS_FROM_SAVED_RESULT'})
        usage = result['usage']
        counter = condition_usage[row['reasoning']]
        for name in ('input_tokens', 'output_tokens'):
            counter[name] += usage[name]
        counter['reasoning_tokens'] += usage['output_tokens_details']['reasoning_tokens']
        counter['requests'] += 1
        counter['cost_usd'] += result['token_cost_estimate_usd']
        pairs[(row['case'], row['variant'], row['prompt_condition'])][row['reasoning']] = {
            'response': result.get('response'), 'status': row['status'], 'experiment': row['experiment'],
            'call_path': row['call_path'], 'usage': usage}
        hashes[row['trial_id']] = {'provider_request_sha256': file_hash(path.parent / 'provider-request.json'),
                                   'raw_response_sha256': file_hash(path.parent / 'raw-response.json')}
        all_results.append(result)
    if len(result_rows) != len(requests) or any(len(p) != 2 for p in pairs.values()):
        raise ValueError('INCOMPLETE_CONDITIONS')
    pair_stats = []
    for experiment in (1, 2):
        selected = [p for p in pairs.values() if p['off']['experiment'] == experiment]
        same_response = [p for p in selected if p['off']['response'] == p['on']['response']]
        same_explanation = [p for p in selected if p['off']['response']['explanation'] == p['on']['response']['explanation']]
        pair_stats.append({'experiment': experiment, 'pairs': len(selected),
                           'identical_response_json': len(same_response), 'identical_explanation': len(same_explanation)})
    failures = [d for d in diagnostics if d['status'] == 'INVALID_RESPONSE']
    abstention_errors = [d for d in failures if 'ABSTAINED_WITH_NUMERIC_ANSWER' in d['tags']]
    precision_errors = [d for d in failures if 'DECIMAL_PLACES_MISMATCH' in d['tags']]
    zero_placeholders = []
    for d in abstention_errors:
        response = pairs[(d['case'], d['variant'], d['prompt_condition'])][d['reasoning']]['response']
        if response['answer'] is not None and float(response['answer']) == 0:
            zero_placeholders.append(d)
    events = rows(root / 'events.jsonl')
    waves = [r for r in events if r['event'] == 'WAVE_START']
    baseline = []
    for mode in ('off', 'on'):
        ds = [d for d in diagnostics if d['experiment'] == 1 and d['reasoning'] == mode]
        baseline.append([mode, len(ds), sum(d['status'] == 'VALID' for d in ds),
                         sum('NUMERIC_MATCH' in d['tags'] for d in ds),
                         sum('NUMERIC_MISMATCH' in d['tags'] for d in ds),
                         sum(d['status'] == 'INVALID_RESPONSE' for d in ds),
                         sum('DECLARED_ABSTENTION' in d['tags'] for d in ds)])
    verification = {'checked_at': now(), 'run_id': root.name, 'status': 'PASS' if not issues else 'FAIL',
                    'issues': issues, 'frozen_manifest_verified': True, 'requests': len(requests),
                    'responses': len(result_rows), 'attempts': model_summary['attempts'],
                    'cache_read_tokens': model_summary['cache_read_tokens'],
                    'cache_write_tokens': model_summary['cache_creation_tokens'],
                    'raw_usage_verified_zero': len(result_rows) - len({i['trial_id'] for i in issues}),
                    'returned_model_counts': dict(Counter(r['model_version'] for r in all_results)),
                    'service_tier_counts': dict(Counter(r['service_tier'] for r in all_results)),
                    'wave_sizes': [w['requests'] for w in waves], 'configured_concurrency': config['schedule']['concurrency'],
                    'usage_by_reasoning': dict(condition_usage), 'pair_comparison': pair_stats,
                    'format_failures': len(failures), 'abstention_field_failures': len(abstention_errors),
                    'zero_placeholders_among_abstention_field_failures': len(zero_placeholders),
                    'precision_failures': len(precision_errors), 'baseline': baseline,
                    'first_call_at': min(r['started_at'] for r in all_results),
                    'last_response_at': max(r['ended_at'] for r in all_results),
                    'new_model_calls_for_this_audit': 0, 'semantic_evaluation': 'NOT_SCORED'}
    folder = root / 'api-verification'
    write(folder / 'verification.json', verification)
    write(folder / 'raw-hashes.json', hashes)
    write(folder / 'test-0006.json', pairs.get(('test-0006', 'ORIGINAL', 'P0')))
    write(folder / 'identical-original-example.json', next((p for p in pairs.values()
          if p['off']['experiment'] == 1 and p['off']['response'] == p['on']['response']), None))
    baseline_table = '\n'.join(table(['추론', '계획', '형식 통과', '숫자 일치', '숫자 불일치', '형식 실패', '형식 통과 유보'], baseline))
    usage_table = '\n'.join(table(['추론', '요청', '입력 토큰', '출력 토큰', '그중 reasoning', '비용 추정 USD'],
        [[mode, u['requests'], u['input_tokens'], u['output_tokens'], u['reasoning_tokens'], f"{u['cost_usd']:.6f}"]
         for mode, u in sorted(condition_usage.items())]))
    pair_table = '\n'.join(table(['실험', 'off/on 비교 쌍', 'JSON 전체 동일', 'explanation 동일'],
        [[p['experiment'], p['pairs'], p['identical_response_json'], p['identical_explanation']] for p in pair_stats]))
    values = {'run_id': root.name, 'checked_at': verification['checked_at'], 'status': verification['status'],
              'requests': len(requests), 'attempts': model_summary['attempts'], 'valid': model_summary['statuses'].get('VALID', 0),
              'failed': len(failures), 'cost': f"{model_summary['paid_api_usage_cost_estimate_usd']:.7f}",
              'baseline_table': baseline_table, 'usage_table': usage_table, 'pair_table': pair_table,
              'abstention_failures': len(abstention_errors), 'precision_failures': len(precision_errors),
              'zero_placeholders': len(zero_placeholders), 'first_call': verification['first_call_at'],
              'last_response': verification['last_response_at'], 'concurrency': config['schedule']['concurrency']}
    template = Path(__file__).with_name('luna-api-summary-template.md').read_text()
    write_text(root / 'RUN-SUMMARY.md', template.format(**values))
    readme = Path(__file__).with_name('luna-api-verification-readme-template.md').read_text()
    write_text(folder / 'README.md', readme.format(**values))
    event(root, 'LUNA_API_RAW_AUDIT_COMPLETED', status=verification['status'], responses=len(result_rows), new_model_calls=0)
    return verification


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    result = build(args.run)
    print({'run_id': result['run_id'], 'status': result['status'], 'responses': result['responses'], 'new_model_calls': 0})
