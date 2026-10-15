"""Observe two independent collections with identical provider request bodies."""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['ROOT']).ROOT
read_rows = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['read_rows']).read_rows
sha = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['sha']).sha
table = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['table']).table


def signature(row):
    """RR01: Distinguish missing responses, explicit null, and signed scaled values."""
    response = row.get('response')
    if not isinstance(response, dict) or 'answer' not in response:
        return None
    value = response['answer']
    if value is None:
        return ('NULL',)
    if type(value) not in (int, float):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    coefficient = '0' if number == 0 else str(number.normalize())
    return ('NUMERIC', coefficient, response.get('answer_meta', {}).get('scale'))


def compare(left, right, same_payload, same_model):
    """RR02: Compare observed answers only when request and model labels match."""
    a, b = signature(left), signature(right)
    eligible = same_payload and same_model
    observed = eligible and a is not None and b is not None
    both_numeric = observed and a[0] == b[0] == 'NUMERIC'
    pair = {k: left[k] for k in ('case', 'variant', 'prompt_condition', 'reasoning')}
    pair.update(left_trial_id=left['trial_id'], right_trial_id=right['trial_id'],
                same_provider_payload=same_payload, same_reported_model_label=same_model,
                eligible=eligible, answers_observed=observed,
                left_signature=a, right_signature=b,
                same_presence=(a[0] == b[0]) if observed else None,
                same_answer_and_scale=(a == b) if observed else None,
                both_numeric=both_numeric,
                same_numeric_and_scale=(a == b) if both_numeric else None,
                left_valid=left['saved_status'] == 'VALID', right_valid=right['saved_status'] == 'VALID',
                same_evidence=(left['response'].get('evidence') == right['response'].get('evidence')) if observed else None,
                left_original_outcome=left['original_outcome'], right_original_outcome=right['original_outcome'],
                left_result_path=left['result_path'], right_result_path=right['result_path'])
    return pair


def summarize(pairs):
    observed = [p for p in pairs if p['answers_observed']]
    numeric = [p for p in observed if p['both_numeric']]
    eligible = [p for p in pairs if p['eligible']]
    return {'planned_pairs': len(pairs), 'eligible_pairs': len(eligible),
            'answer_observed_pairs': len(observed), 'answer_unassessed_pairs': len(pairs)-len(observed),
            'same_presence': sum(p['same_presence'] is True for p in observed),
            'same_answer_and_scale': sum(p['same_answer_and_scale'] is True for p in observed),
            'changed_answer_or_scale': sum(p['same_answer_and_scale'] is False for p in observed),
            'numeric_to_null': sum(p['left_signature'][0] == 'NUMERIC' and p['right_signature'][0] == 'NULL' for p in observed),
            'null_to_numeric': sum(p['left_signature'][0] == 'NULL' and p['right_signature'][0] == 'NUMERIC' for p in observed),
            'both_numeric_pairs': len(numeric), 'same_numeric_and_scale': sum(p['same_numeric_and_scale'] for p in numeric),
            'same_evidence_array': sum(p['same_evidence'] is True for p in observed),
            'both_valid': sum(p['left_valid'] and p['right_valid'] for p in eligible),
            'valid_to_invalid': sum(p['left_valid'] and not p['right_valid'] for p in eligible),
            'invalid_to_valid': sum(not p['left_valid'] and p['right_valid'] for p in eligible),
            'stable_original_numeric_mismatch': sum(p['variant'] == 'ORIGINAL' and p['same_answer_and_scale'] is True
                and p['left_original_outcome'] == p['right_original_outcome'] == 'NUMERIC_MISMATCH' for p in observed)}


def build(first, second, output):
    """RR03–05: Verify saved payloads, preserve sources, and write paired evidence."""
    first, second, output = Path(first).resolve(), Path(second).resolve(), Path(output).resolve()
    if output in (first, second) or first in output.parents or second in output.parents:
        raise ValueError('OUTPUT_MUST_NOT_REPLACE_INPUT_ANALYSIS')
    key = lambda row: tuple(row[k] for k in ('case', 'variant', 'prompt_condition', 'reasoning'))
    datasets = [read_rows(folder/'rows.jsonl') for folder in (first, second)]
    maps = [{key(row): row for row in data} for data in datasets]
    if any(len(data) != len(mapping) for data, mapping in zip(datasets, maps)) or set(maps[0]) != set(maps[1]):
        raise ValueError('EXACT_UNIQUE_CONDITION_COVERAGE_REQUIRED')
    hashes = {str((folder/'rows.jsonl').relative_to(ROOT)): sha(folder/'rows.jsonl') for folder in (first, second)}
    pairs, model_labels = [], Counter()
    for condition in sorted(maps[0]):
        left, right = maps[0][condition], maps[1][condition]
        bodies, models = [], []
        for row in (left, right):
            if not row.get('result_path'):
                bodies.append(None); models.append(None); continue
            result_file = ROOT/row['result_path']
            body_file = result_file.with_name('provider-request-wire.json')
            if not body_file.is_file():
                bodies.append(None); models.append(None); continue
            for path in (result_file, body_file):
                hashes[str(path.relative_to(ROOT))] = sha(path)
            result = json.loads(result_file.read_text())
            bodies.append(body_file.read_bytes())
            models.append(result.get('model_version'))
            model_labels[str(result.get('model_version'))] += 1
        same_body = all(isinstance(body, bytes) for body in bodies) and bodies[0] == bodies[1]
        same_model = all(isinstance(model, str) and model for model in models) and models[0] == models[1]
        pairs.append(compare(left, right, same_body, same_model))
    groups, conditions, cases = defaultdict(list), defaultdict(list), defaultdict(list)
    for pair in pairs:
        groups[(pair['variant'], pair['prompt_condition'], pair['reasoning'])].append(pair)
        scope = 'ORIGINAL' if pair['variant'] == 'ORIGINAL' else 'VARIANTS'
        conditions[(scope, pair['prompt_condition'], pair['reasoning'])].append(pair)
        cases[pair['case']].append(pair)
    report = {'kind': 'TWO_COLLECTION_IDENTICAL_REQUEST_OBSERVATIONS', 'created_at': datetime.now(timezone.utc).isoformat(),
              'first_run': datasets[0][0]['run_id'], 'second_run': datasets[1][0]['run_id'],
              'independent_originals': len({p['case'] for p in pairs}), 'collections': 2,
              'overall': summarize(pairs), 'model_label_counts': dict(model_labels),
              'groups': [{**dict(zip(('variant','prompt_condition','reasoning'), group)), **summarize(items)}
                         for group, items in sorted(groups.items())],
              'by_scope_prompt_reasoning': [{**dict(zip(('scope','prompt_condition','reasoning'), group)), **summarize(items)}
                         for group, items in sorted(conditions.items())],
              'by_original_case': [{'case': case, **summarize(items),
                    'variant_p0': summarize([p for p in items if p['variant'] != 'ORIGINAL' and p['prompt_condition'] == 'P0']),
                    'variant_p1': summarize([p for p in items if p['variant'] != 'ORIGINAL' and p['prompt_condition'] == 'P1'])}
                    for case, items in sorted(cases.items())],
              'limitations': ['Two independent calls per condition, not a reliability estimate over many repetitions.',
                             'A matching provider model label does not identify immutable backend weights.',
                             'Signed numeric coefficient plus scale equality is not semantic correctness.',
                             'Variants and conditions share 100 original-case clusters.',
                             'Exact evidence-array equality is not equality of supporting meaning.'],
              'new_model_calls': 0, 'semantic_scoring': 'NOT_PERFORMED'}
    if not all(sha(ROOT/path) == digest for path, digest in hashes.items()):
        raise ValueError('SOURCE_CHANGED_DURING_REPEAT_ANALYSIS')
    output.mkdir(parents=True, exist_ok=True)
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    (output/'pairs.jsonl').write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in pairs))
    (output/'verification.json').write_text(json.dumps({'source_files':len(hashes),'source_sha256':hashes,
        'all_source_hashes_unchanged':True,'analyzer_sha256':sha(Path(__file__)),
        'viewer_verified':False,'user_review_completed':False,'new_model_calls':0},indent=2)+'\n')
    total = report['overall']
    lines = ['# 같은 조건으로 두 번 호출한 응답 비교', '',
        f"`{report['first_run']}` → `{report['second_run']}` · 원문 {report['independent_originals']}개 · 계획 {total['planned_pairs']:,}쌍.", '',
        '실제 전송한 provider 요청 JSON 바이트와 제공자가 반환한 모델 이름이 같은 쌍만 비교했습니다. 키 순서도 전송 바이트 비교에 포함됩니다. 모델 이름이 같아도 내부 가중치 revision까지 같음을 증명하지는 않습니다. 응답을 재사용하지 않은 두 수집 결과의 관찰이며, 정답률과 별도로 읽습니다.', '',
        table(['관찰','쌍수'],[(k,total[k]) for k in ('planned_pairs','eligible_pairs','answer_observed_pairs','answer_unassessed_pairs','same_presence','same_answer_and_scale','changed_answer_or_scale','numeric_to_null','null_to_numeric','both_numeric_pairs','same_numeric_and_scale','both_valid','valid_to_invalid','invalid_to_valid','stable_original_numeric_mismatch')]), '',
        '같은 답은 signed 숫자와 scale이 모두 같거나 양쪽 모두 명시적 null인 경우입니다. 미수집·읽을 수 없는 답은 같은 null로 세지 않습니다. `stable_original_numeric_mismatch`는 두 번 모두 같은 숫자를 냈지만 저장된 원문 참조 숫자와 불일치한 경우로, 안정성과 정답이 다른 속성임을 보여줍니다.', '',
        table(['범위','P','추론','계획쌍','관측쌍','숫자·단위/빈값 동일','값·단위/빈값 변화','숫자→null','null→숫자'],
              [[g['scope'],g['prompt_condition'],g['reasoning'],g['planned_pairs'],g['answer_observed_pairs'],g['same_answer_and_scale'],g['changed_answer_or_scale'],g['numeric_to_null'],g['null_to_numeric']] for g in report['by_scope_prompt_reasoning']]), '',
        table(['유형','P','추론','계획쌍','관측쌍','숫자·단위/빈값 동일','값·단위/빈값 변화','양쪽 숫자','그중 값·단위 동일'],
              [[g['variant'],g['prompt_condition'],g['reasoning'],g['planned_pairs'],g['answer_observed_pairs'],g['same_answer_and_scale'],g['changed_answer_or_scale'],g['both_numeric_pairs'],g['same_numeric_and_scale']] for g in report['groups']]), '',
        '두 번의 관찰로 장기간 신뢰도나 모집단의 반복 분산을 확정하지 않습니다. 이 100원문은 개발 집단이고, 같은 원문의 변형·조건들은 독립 표본이 아닙니다. 설명·근거가 의미상 같거나 올바른지는 별도 미평가입니다.', '',
        '## 변화가 많은 원문 묶음', '',
        '관측된 값·단위 또는 숫자 유무 변화가 많은 10원문을 사후에 골라 보여줍니다. 전체 100원문의 분모·변화는 summary.json의 by_original_case에 있습니다. 순위는 문제의 정답 난도나 새로운 의미 오류 점수가 아닙니다.', '',
        table(['원문','관측/계획','전체 답 변화','변형 P0 변화/관측','변형 P1 변화/관측','숫자→null','null→숫자'],
              [[g['case'],f"{g['answer_observed_pairs']}/{g['planned_pairs']}",g['changed_answer_or_scale'],
                f"{g['variant_p0']['changed_answer_or_scale']}/{g['variant_p0']['answer_observed_pairs']}",
                f"{g['variant_p1']['changed_answer_or_scale']}/{g['variant_p1']['answer_observed_pairs']}",g['numeric_to_null'],g['null_to_numeric']]
               for g in sorted(report['by_original_case'], key=lambda g:(-g['changed_answer_or_scale'],g['case']))[:10]]), '']
    (output/'analysis.md').write_text('\n'.join(lines))
    template = ROOT/'src/finarch/documentation/templates/experiment-repeat-analysis.md'
    text = template.read_text().replace('{{first_run}}', report['first_run']).replace('{{second_run}}',report['second_run'])
    (output/'README.md').write_text(text)
    with (output/'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'at':report['created_at'],'event':'IDENTICAL_REQUEST_REPEAT_REVIEW_COMPLETED',
                                 'pairs':len(pairs),'new_model_calls':0})+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = build(args.first, args.second, args.output)
    print(json.dumps(result['overall']))
