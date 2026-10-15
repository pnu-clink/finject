"""Compare frozen experiments and report cached usage without any model calls."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
from finarch.paths import SOURCE

call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text


def build(root, reference):
    root, reference = Path(root), Path(reference)
    pipeline.verify(root)
    pipeline.verify(reference)
    model = read(root / 'config.json')['models'][0]
    key = model['key']
    if model['transport'] != 'codex_cli' or model['model'] != 'gpt-5.6-luna':
        raise ValueError('LUNA_CLI_AUDIT_REQUIRED')
    if read(root / 'state.json')['status'] != 'CACHE_POLICY_BLOCKED' or list((root / key).rglob('started.json')):
        raise ValueError('EXPECTED_BLOCKED_RUN_WITHOUT_MODEL_ATTEMPTS')
    previous = rows(reference / key / '01-requests/manifest.jsonl')
    current = rows(root / key / '01-requests/manifest.jsonl')
    if not previous or len(previous) != len(current):
        raise ValueError('REFERENCE_REQUEST_COUNT_MISMATCH')
    def content(request):
        return {k: v for k, v in request.items() if k not in ('cache_policy', 'trial_id')}
    same_requests = [content(r) for r in previous] == [content(r) for r in current]
    relative_files = ('01-input/public.jsonl', '01-input/private.jsonl', '00-definition/common.md',
                      '00-definition/p0-standard.md', '00-definition/p1-abstention-aware.md',
                      '00-definition/response.schema.json')
    equality = {p: {'reference_sha256': file_hash(reference / p), 'current_sha256': file_hash(root / p)}
                for p in relative_files}
    if not same_requests or any(v['reference_sha256'] != v['current_sha256'] for v in equality.values()):
        raise ValueError('RERUN_INPUT_OR_CONDITION_CHANGED')
    counts = defaultdict(Counter)
    for request in previous:
        attempts = call_layout.result_paths(reference / key, request)
        if not attempts:
            raise ValueError('REFERENCE_RESPONSE_MISSING')
        usage = read(attempts[-1]).get('usage') or {}
        count = counts[request['reasoning']]
        count['requests'] += 1
        count['requests_with_cache_hits'] += int(usage.get('cached_input_tokens', 0) > 0)
        count['requests_missing_cache_counter'] += int('cached_input_tokens' not in usage)
        count['requests_missing_cache_write_counter'] += int('cache_write_input_tokens' not in usage)
        for field in ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens'):
            count[field] += usage.get(field, 0)
    plan = read(root / 'plan.json')['models'][0]
    estimated_input = plan['input_token_estimate']
    alternative = {'status': 'PROPOSAL_NOT_EXECUTED', 'model': model['model'], 'requests': len(current),
                   'transport': 'OPENAI_RESPONSES_API', 'billing_mode': 'PAID_API',
                   'subscription_cli_is_not_this_transport': True,
                   'adapter_status': 'NOT_IMPLEMENTED_FOR_EXPERIMENTS',
                   'cache_read_write_control': {'prompt_cache_options': {'mode': 'explicit'}, 'breakpoints': []},
                   'price_source': 'https://developers.openai.com/api/docs/models/gpt-5.6-luna',
                   'uncached_input_usd_per_million': 0.2, 'output_usd_per_million': 1.2,
                   'input_tokens_estimated': estimated_input, 'input_estimate_method': plan['estimate_method'],
                   'output_tokens_assumed_per_request_including_reasoning': 1000,
                   'estimated_usd': round((estimated_input * .2 + len(current) * 1000 * 1.2) / 1e6, 6),
                   'is_cost_cap': False, 'new_model_calls': 0}
    report = {'created_at': now(), 'reference_run': reference.name, 'run_id': root.name,
              'request_contents_and_order_equal_excluding_local_policy_and_id': same_requests,
              'file_comparison': equality, 'previous_usage_by_reasoning': dict(counts),
              'cache_counter_fields': {'read': 'cached_input_tokens', 'write': 'cache_write_input_tokens'},
              'previous_outputs_reused': 0, 'new_model_calls': 0,
              'current_status': read(root / 'state.json')['status'], 'api_alternative': alternative}
    write(root / 'cache-audit.json', report)
    write(root / 'api-alternative-plan.json', alternative)
    table = '\n'.join(f"|{mode}|{s['requests']:,}|{s['requests_with_cache_hits']:,}|{s['input_tokens']:,}|{s['cached_input_tokens']:,}|{s['cache_write_input_tokens']:,}|{s['requests_missing_cache_write_counter']:,}|{s['reasoning_output_tokens']:,}|"
                      for mode, s in sorted(counts.items()))
    template = (SOURCE / 'experiments/templates/cache-audit-readme-template.md').read_text()
    correction_note = ('2026-09-20 정정: 이전 보고서는 Anthropic의 필드명 `cache_creation_input_tokens`를 Codex에도 잘못 적용해 쓰기 항목이 없다고 표시했습니다. '
                       '실제 Codex 필드명으로 다시 집계했습니다. 이전 보고서와 정정 내역은 `cache-review/superseded/`, `cache-review/correction.json`에 보존합니다.'
                       if (root / 'cache-review/correction.json').exists() else '')
    write_text(root / 'CACHE-AUDIT.md', template.format(run_id=root.name, reference_run=reference.name,
               usage_table=table, requests=len(current), cost=f"{alternative['estimated_usd']:.2f}",
               input_estimate=f'{estimated_input:,}', correction_note=correction_note))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--reference', required=True)
    args = parser.parse_args()
    report = build(args.run, args.reference)
    print({'run': report['run_id'], 'status': report['current_status'], 'new_model_calls': 0})
