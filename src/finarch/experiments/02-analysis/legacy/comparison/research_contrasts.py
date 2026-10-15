"""Calculate descriptive paired contrasts from saved response observations."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

NAMES = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['NAMES']).NAMES
VARIANTS = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['VARIANTS']).VARIANTS
read_rows = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['read_rows']).read_rows
sha = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['sha']).sha


def build(source, output):
    source, output = Path(source), Path(output)
    rows = read_rows(source / 'rows.jsonl')
    selected = [row for row in rows if row['variant'] != 'ORIGINAL']
    keyed = {(r['case'], r['variant'], r['prompt_condition'], r['reasoning']): r for r in selected}
    if len(keyed) != len(selected):
        raise ValueError('DUPLICATE_CONDITION_KEY')
    cases = sorted({r['case'] for r in selected})
    contrasts, pairs = [], []
    for variant in VARIANTS[1:]:
        for reasoning in ('off', 'on'):
            changes = []
            for case in cases:
                p0 = keyed.get((case, variant, 'P0', reasoning))
                p1 = keyed.get((case, variant, 'P1', reasoning))
                if not p0 or not p1:
                    raise ValueError('PAIRED_CONDITION_MISSING')
                if p0['qc_sha256'] != p1['qc_sha256'] or p0['schema_sha256'] != p1['schema_sha256']:
                    raise ValueError('UNMATCHED_INPUT_OR_SCHEMA')
                observed = all(isinstance(p['response'], dict) and 'answer' in p['response']
                               and type(p['answer_is_null']) is bool for p in (p0, p1))
                row = {'case': case, 'variant': variant, 'reasoning': reasoning,
                       'observed': observed, 'p0_trial': p0['trial_id'], 'p1_trial': p1['trial_id'],
                       'p0_null': p0['answer_is_null'] if observed else None,
                       'p1_null': p1['answer_is_null'] if observed else None,
                       'p0_numeric': p0['signed_numeric_field'] is not None if observed else None,
                       'p1_numeric': p1['signed_numeric_field'] is not None if observed else None,
                       'delta': int(p1['answer_is_null']) - int(p0['answer_is_null']) if observed else None}
                pairs.append(row)
                changes.append(row)
            seen = [c for c in changes if c['observed']]
            n = len(changes)
            contrasts.append({'variant': variant, 'reasoning': reasoning, 'planned_pairs': n,
                'observed_pairs': len(seen), 'missing_pairs': n-len(seen),
                'p0_null': sum(c['p0_null'] for c in seen), 'p1_null': sum(c['p1_null'] for c in seen),
                'numeric_to_null': sum(c['p0_numeric'] and c['p1_null'] for c in seen),
                'null_to_numeric': sum(c['p0_null'] and c['p1_numeric'] for c in seen),
                'null_change_percentage_points': 100*sum(c['delta'] for c in seen)/n if len(seen)==n else None})
    per_case = defaultdict(dict)
    for p in pairs:
        per_case[(p['case'], p['variant'])][p['reasoning']] = p['delta']
    interactions = []
    for variant in VARIANTS[1:]:
        values = [v['on']-v['off'] for (case, kind),v in per_case.items()
                  if kind == variant and v.get('on') is not None and v.get('off') is not None]
        interactions.append({'variant': variant, 'originals': len(cases), 'observed_originals': len(values),
            'instruction_by_reasoning_null_interaction_pp': 100*sum(values)/len(cases) if len(values)==len(cases) else None})
    report = {'kind': 'DESCRIPTIVE_PAIRED_CONTRASTS', 'source_run': rows[0]['run_id'],
              'source_sha256': sha(source / 'rows.jsonl'), 'new_model_calls': 0,
              'source_contracts': dict(Counter(row.get('schema_title') or 'UNKNOWN' for row in rows)),
              'analysis_unit': 'ORIGINAL_CASE_CLUSTER_WITH_SEVEN_RELATED_VARIANTS',
              'interpretation': 'Null-field behavior under changed conditions; not semantic abstention accuracy or repeated-condition stability.',
              'planned_originals': len(cases), 'planned_variant_pairs_per_reasoning': len(cases)*7,
              'contrasts': contrasts, 'interactions': interactions,
              'hypothesis_test': 'NOT_PERFORMED_EXPLORATORY_NONRANDOM_DEVELOPMENT_COHORT'}
    output.mkdir(parents=True,exist_ok=True)
    (output/'contrasts.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'paired-observations.jsonl').write_text(''.join(json.dumps(p)+'\n' for p in pairs))
    contracts = ', '.join(f'`{title}` {count}건' for title, count in sorted(report['source_contracts'].items()))
    lines=['# 저장된 Luna 응답의 프롬프트·추론 조건 비교','',
           f"실행 `{report['source_run']}` · 원문 {report['planned_originals']}개 · 응답 형식 {contracts}. 실제 입력 rows.jsonl에 기록된 실행과 형식입니다. 이 분석은 새 모델 호출이나 의미 정답 채점을 수행하지 않습니다.",
           '', '## 안내 효과가 추론 설정에 따라 달라지는가', '',
           '같은 원문·변형·추론 조건에서 P0와 P1을 연결했습니다. 숫자 필드가 null로 바뀌는 차이를 관찰하며, 적절한 유보인지 채점하지 않습니다. 형식 실패 응답도 원래 분모에 포함합니다. 양쪽 answer가 관측된 쌍과 미관측 쌍을 JSON에 나누어 기록하며, 해당 유형·추론의 계획쌍이 모두 관측되지 않으면 변화율은 0이 아닌 미평가로 남깁니다.', '',
           '|유형|추론|쌍|P0 null|P1 null|숫자→null|null→숫자|P1−P0 변화(%p)|',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for c in contrasts:
        delta=c['null_change_percentage_points']
        lines.append(f"|{NAMES[c['variant']]}|{c['reasoning']}|{c['planned_pairs']}|{c['p0_null']}|{c['p1_null']}|{c['numeric_to_null']}|{c['null_to_numeric']}|{delta:.1f}|" if delta is not None else f"|{NAMES[c['variant']]}|{c['reasoning']}|{c['planned_pairs']}|—|—|—|—|미평가|")
    lines += ['', '|유형|원문 수|안내 효과의 on−off 차이(%p)|','|---|---:|---:|']
    for i in interactions:
        v=i['instruction_by_reasoning_null_interaction_pp']
        lines.append(f"|{NAMES[i['variant']]}|{i['originals']}|{v:.1f}|" if v is not None else f"|{NAMES[i['variant']]}|{i['originals']}|미평가|")
    lines += ['', '### 해석과 다음 조치', '',
      f"- **수정 채택:** 안내 효과를 추론 조건별로 따로 보고, 두 효과의 차이도 제시합니다. 위 차이는 이 {len(cases)}원문에서의 기술 통계이며 모집단 인과 효과나 통계적 유의성을 확정하지 않습니다.",
      '- **채택:** VALUE/SOURCE/RELATION과 EA를 분리합니다. 충돌에 대한 응답 변화와 필수 정보 삭제에 대한 변화가 같은 방향·크기인지 확인합니다.',
      '- **보류:** null 증가를 사용자 의도 대응 향상으로 주장하는 것. 정상 문제 P1 대조와 삭제 정보의 실제 복원 가능성 검토가 필요합니다.',
      f"- **기각:** 7종 변형과 조건별 응답을 독립 원문으로 세어 표본 수를 부풀리는 것. 분석·향후 불확실성 계산의 묶음은 원문 {len(cases)}개입니다.",
      '', '## 논문에 넣을 표와 남은 검증', '',
      '|표 또는 그림|현재 확보한 내용|추가로 필요한 내용|', '|---|---|---|',
      '|응답 계약 실패 유형|각 실행 당시 계약의 관찰을 별도 형식 분석에서 확인|다른 계약끼리는 공통 관찰과 계약에만 있는 실패를 분리|',
      '|안내 × 추론 × 변형 종류|위 대응표와 원문별 전환 기록|실행 간 비교는 같은 입력의 공통 관측쌍으로 제한; 정상 P1 추가 대조는 별도 설계|',
      '|출처 부착 전후|이 null 비교표에는 별도 부모 연결 검증이 없음|형식 분석의 source-links와 질문의 출처 조건을 함께 확인|',
      '|동일 조건 안정성|이 단일 수집의 P0/P1 비교에는 포함되지 않음|두 수집의 실제 요청 바이트·모델 이름을 맞춘 별도 반복 분석을 확인|',
      '|금융 모델 대 기반 모델|A100의 실행 가능 여부와 시간 자료|금융 모델 응답이 있어야 직접 쌍 비교 가능|',
      '', '원문 P1 대조 추가는 과도한 유보를 확인할 후보이고, 같은 조건 반복은 변동을 확인할 후보입니다. 이 분석에 이미 포함된 것처럼 취급하지 않으며 새 호출은 별도 준비·호출량·비용 기록이 필요합니다.',
      '', '## 일반화와 개발 편향', '',
      f'이 비교의 {len(cases)}원문은 무작위 모집단 표본으로 간주하지 않습니다. 같은 표본의 결과를 보고 지시문·응답 형식을 수정한 뒤 다시 측정한 경우, 실행 간 차이는 개발 자료에서의 관찰입니다. 지시문·형식·반올림 정책을 함께 바꾸었다면 어느 하나의 효과로 분리하지 않습니다. 논문의 최종 확인 실험은 기준을 고정한 뒤 아직 읽지 않은 집단으로 분리해야 합니다. 지금 선택한 사례나 지표를 사전등록 지표로 소급 표현하지 않습니다.', '']
    (output/'analysis.md').write_text('\n'.join(lines))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=build(args.source,args.output)
    print(json.dumps({'originals':result['planned_originals'],'paired_rows':sum(x['planned_pairs'] for x in result['contrasts']),'new_model_calls':0}))
