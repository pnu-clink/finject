"""Summarize saved GPU evaluation evidence without new model calls."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import importlib
import json
import math
from pathlib import Path
import statistics
from string import Template

store = importlib.import_module('finarch.experiments.90-operations.storage')
layout = importlib.import_module('finarch.experiments.90-operations.run_layout')


def table(headers, rows):
    return '\n'.join(['|' + '|'.join(headers) + '|', '|' + '|'.join('---' for _ in headers) + '|',
                      *('|' + '|'.join(str(x).replace('|', '/') for x in row) + '|' for row in rows)])


def percent(value, total):
    return f'{100 * value / total:.2f}%' if total else '미평가'


def duration(seconds):
    return f'{int(seconds // 3600)}시간 {int(seconds % 3600 // 60)}분 {int(seconds % 60)}초'


def timing(latencies):
    if not latencies:
        return None
    values = sorted(latencies)
    return {'count': len(values), 'sum_seconds': sum(values), 'mean_seconds': statistics.mean(values),
            'median_seconds': statistics.median(values), 'p95_seconds': values[math.ceil(.95 * len(values)) - 1],
            'max_seconds': values[-1]}


def summarize(root, source_stage=None):
    store.verify(root)
    model, = store.configuration(root)['models']
    validated = store.rows(layout.validation(root, model['key']) / 'results.jsonl')
    numeric = {row['trial_id']: row for row in store.rows(layout.validation(root) / 'numeric-comparisons.jsonl')}
    by_id = {row['trial_id']: row for row in validated}
    source = Path(source_stage).resolve() if source_stage else root
    evidence = source / 'remote-evidence'
    remote = store.read(evidence / 'state.json') if source_stage else store.read(root / 'remote-state.json')
    if len(by_id) != remote['total'] or len(numeric) != len(by_id):
        raise ValueError('SUMMARY_COVERAGE_MISMATCH')
    conditions, types, failures = defaultdict(Counter), defaultdict(Counter), []
    failure_reasons, classifications, usage = Counter(), defaultdict(Counter), Counter()
    metadata_discrepancies = Counter()
    latency, seen = defaultdict(list), set()
    with (source / 'collection/responses.jsonl').open() as stream:
        for line in stream:
            row = json.loads(line)
            trial = row['trial_id']
            if trial not in by_id or trial in seen:
                raise ValueError('COLLECTION_TRIAL_MISMATCH')
            seen.add(trial)
            local = by_id[trial]
            condition = (row['prompt_condition'], row['reasoning'])
            group = conditions[condition]
            variant = types[(row['variant'], *condition)]
            for target in (group, variant):
                target['planned'] += 1
                target[local['status']] += 1
                target['remote_schema_valid'] += int(row['format_check']['status'] == 'VALID')
            elapsed = row['delivery']['elapsed_seconds']
            latency[condition].append(elapsed)
            raw_usage = row['response']['usage']
            raw_finish = row['response']['choices'][0]['finish_reason']
            for key, value in (('usage', raw_usage), ('finish_reason', raw_finish)):
                metadata_discrepancies[key] += int(row['delivery'].get(key) != value)
            usage['input_tokens'] += raw_usage['prompt_tokens']
            usage['output_tokens_including_reasoning'] += raw_usage['completion_tokens']
            reason_tokens = (raw_usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
            if type(reason_tokens) is int:
                usage['reported_reasoning_tokens'] += reason_tokens
                usage['records_with_reasoning_usage'] += 1
            usage['records_without_cached_token_usage'] += int(row['delivery'].get('reported_cached_tokens') is None)
            if row['experiment'] == 1:
                group['original_planned'] += 1
                check = numeric[trial]['numeric_comparison']
                group['original_compared'] += int(check is not None)
                group['original_numeric_match'] += int(bool(check and check['matches']))
                if local['status'] == 'VALID':
                    group['original_null'] += int(local['response']['answer'] is None)
            if local['status'] == 'VALID':
                value = local['response'].get('classification')
                classifications[condition]['null' if value is None else value] += 1
                variant['answer_null_valid'] += int(local['response']['answer'] is None)
            else:
                details = {'trial_id': trial, 'case': row['case'], 'variant': row['variant'],
                           'prompt_condition': condition[0], 'reasoning': condition[1],
                           'status': local['status'], 'remote_schema_status': row['format_check']['status'],
                           'finish_reason': raw_finish,
                           'schema_errors': local.get('schema_errors', []),
                           'call_path': local['call_path'], 'raw_response_path': row['raw_response_path']}
                if local['status'] == 'OUTPUT_TRUNCATED':
                    failure_reasons['output_token_limit'] += 1
                else:
                    for error in details['schema_errors']:
                        failure_reasons['/'.join(map(str, error['path'])) + ': ' + error['message']] += 1
                failures.append(details)
    if seen != set(by_id):
        raise ValueError('COLLECTION_INCOMPLETE')
    all_latency = [x for values in latency.values() for x in values]
    conditions_out = [{'prompt': key[0], 'reasoning': key[1], **dict(value),
                       'latency': timing(latency[key]), 'classifications_valid_only': dict(classifications[key])}
                      for key, value in sorted(conditions.items())]
    runtime = store.read(layout.preparation(root) / 'a100-runtime.json') if source_stage else store.read(evidence / 'a100-runtime.json')
    cache = store.read(layout.preparation(root) / 'cache-audit.json') if source_stage else {name: store.read(evidence / ('cache-' + name + '.json')) for name in ('initial', 'final')}
    summary = {'run': root.name, 'model': model['model'], 'created_at': store.now(),
               'responses': len(validated), 'originals': 1080, 'variants': 7560,
               'statuses': dict(Counter(row['status'] for row in validated)),
               'remote_schema_statuses': store.read(evidence / 'collection-index.json')['format_status'],
               'conditions': conditions_out, 'type_conditions': [
                   {'variant': key[0], 'prompt': key[1], 'reasoning': key[2], **dict(value)}
                   for key, value in sorted(types.items())],
               'failure_rule_counts': dict(failure_reasons), 'usage': dict(usage), 'runtime': runtime,
               'remote_delivery_metadata_discrepancies': dict(metadata_discrepancies),
               'timing': {'evaluation_wall_seconds': remote['elapsed_seconds'],
                          'started_at': datetime.fromtimestamp(remote['started_at']).astimezone().isoformat() if remote.get('started_at') is not None else None,
                          'finished_at': remote['at'], 'throughput_requests_per_second': len(validated) / remote['elapsed_seconds'],
                          'request_latency': timing(all_latency),
                          'allocated_gpu_hours_during_evaluation': 4 * remote['elapsed_seconds'] / 3600,
                          'internal_provider_wait_and_inference_separated': False},
               'cache': {'engine_snapshots': cache, 'per_request_tokens': 'UNKNOWN_NOT_ZERO'},
               'cost': {'incremental_external_api_usd': 0, 'gpu_infrastructure_usd': None},
               'semantic_assessment': 'NOT_REVIEWED', 'analysis_status': 'NOT_STARTED', 'new_model_calls': 0,
               'recovery': store.read(root / 'recovery-receipt.json')}
    store.write(root / 'recovered-summary.json', summary)
    store.write_rows(layout.validation(root) / 'failure-details.jsonl', failures)
    condition_table = table(
        ['풀이 방식', '추론', '응답', '원격 스키마 통과', '로컬 전체 계약 통과', '잘림', '원본 숫자 일치/계획', '원본 숫자 일치/비교'],
        [(layout.prompt_label(row['prompt']), row['reasoning'].upper(), row['planned'], row['remote_schema_valid'],
          f"{row.get('VALID', 0)} ({percent(row.get('VALID', 0), row['planned'])})", row.get('OUTPUT_TRUNCATED', 0),
          f"{row['original_numeric_match']}/{row['original_planned']} ({percent(row['original_numeric_match'], row['original_planned'])})",
          f"{row['original_numeric_match']}/{row['original_compared']} ({percent(row['original_numeric_match'], row['original_compared'])})")
         for row in conditions_out])
    classification_table = table(['조건', '유효 응답의 classification 분포'], [
        (layout.prompt_label(row['prompt']) + '/' + row['reasoning'].upper(),
         ', '.join(f'{key}: {value}' for key, value in row['classifications_valid_only'].items())) for row in conditions_out])
    ordered_conditions = sorted(conditions)
    type_table = table(['입력 유형', *[layout.prompt_label(p) + '/' + r.upper() for p, r in ordered_conditions]], [
        (name, *[f"{types[(name, p, r)]['VALID']}/{types[(name, p, r)]['planned']} "
                 f"({percent(types[(name, p, r)]['VALID'], types[(name, p, r)]['planned'])})"
                 for p, r in ordered_conditions]) for name in sorted({key[0] for key in types})])
    null_table = table(['입력 유형', *[layout.prompt_label(p) + '/' + r.upper() for p, r in ordered_conditions]], [
        (name, *[f"{types[(name, p, r)]['answer_null_valid']}/{types[(name, p, r)]['VALID']} "
                 f"({percent(types[(name, p, r)]['answer_null_valid'], types[(name, p, r)]['VALID'])})"
                 for p, r in ordered_conditions]) for name in sorted({key[0] for key in types})])
    failure_table = table(['실패 규칙', '발생 수'], failure_reasons.most_common())
    latency_table = table(['조건', '평균', '중앙값', '95백분위', '최대'], [
        (layout.prompt_label(row['prompt']) + '/' + row['reasoning'].upper(),
         *[f"{row['latency'][key]:.2f}초" for key in ('mean_seconds', 'median_seconds', 'p95_seconds', 'max_seconds')])
        for row in conditions_out])
    template = Template((store.PROJECT / 'src/finarch/experiments/templates/a100-recovered-results.md').read_text())
    store.write_text(root / 'RESULTS.md', template.substitute(
        model=model['model'], run=root.name, responses=len(validated),
        valid=summary['statuses'].get('VALID', 0), valid_rate=percent(summary['statuses'].get('VALID', 0), len(validated)),
        conditions=condition_table, types=type_table, null_answers=null_table,
        classifications=classification_table, failures=failure_table,
        latency=latency_table, wall=duration(remote['elapsed_seconds']),
        gpu_hours=f"{summary['timing']['allocated_gpu_hours_during_evaluation']:.2f}",
        throughput=f"{summary['timing']['throughput_requests_per_second']:.3f}"))
    store.event(root, 'A100_RECOVERED_SUMMARY_SAVED', responses=len(validated), statuses=summary['statuses'], model_calls=0)
    store.verify(root)
    return summary


def render_index(values, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    store.write(output / 'comparison.json', {'runs': values, 'model_calls': 0})
    comparison = table(['모델', '수집', '원격 스키마 통과', '로컬 전체 계약 통과', '잘림', '평가 경과', '건당 평균 응답 시간'], [
        (row['model'], row['responses'], row['remote_schema_statuses'].get('VALID', 0),
         f"{row['statuses'].get('VALID', 0)} ({percent(row['statuses'].get('VALID', 0), row['responses'])})",
         row['statuses'].get('OUTPUT_TRUNCATED', 0), duration(row['timing']['evaluation_wall_seconds']),
         f"{row['timing']['request_latency']['mean_seconds']:.2f}초") for row in values])
    links = '\n'.join(f"- [{row['model']} 결과](../../experiments-run/{row['run']}/RESULTS.md) · "
                      f"[뷰어](http://127.0.0.1:8894/?run={row['run']}&tab=overview)" for row in values)
    template = Template((store.PROJECT / 'src/finarch/experiments/templates/a100-recovery-index.md').read_text())
    store.write_text(output / 'README.md', template.substitute(comparison=comparison, links=links))
    print(comparison)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, default=Path('reports/run/20260930-a100-recovery'))
    args = parser.parse_args()
    render_index([summarize(path.resolve()) for path in args.runs], args.output)


if __name__ == '__main__':
    main()
