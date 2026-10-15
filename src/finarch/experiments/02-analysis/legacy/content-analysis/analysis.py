"""Reproducible post-run diagnostics from preserved responses; no model calls."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath

read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_rows = __import__('finarch.experiments.90-operations.storage', fromlist=['write_rows']).write_rows
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
VARIANT_NAMES = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['VARIANT_NAMES']).VARIANT_NAMES
VARIANT_ORDER = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['VARIANT_ORDER']).VARIANT_ORDER

MARKER = re.compile(r'cannot (?:be |reliably |uniquely )?(?:determine|calculate|answer)|insufficient|not enough|underdetermined|unable to|cannot provide', re.I)


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, data):
    return ['|' + '|'.join(headers) + '|', '|' + '|'.join('---' for _ in headers) + '|'] + [
        '|' + '|'.join(cell(v) for v in row) + '|' for row in data] + ['']


def main(root):
    root = Path(root).resolve()
    summary = read(root / 'summary.json')
    if summary['status'] != 'FINISHED':
        raise ValueError('COLLECTION_NOT_FINISHED')
    public = {x['item_id']: x for x in rows(root / '01-input/public.jsonl')}
    private = {x['item_id']: x for x in rows(root / '01-input/private.jsonl')}
    output = root / 'analysis'
    output.mkdir(exist_ok=True)
    models, diagnostics = {}, []
    for model in summary['models']:
        name = model['model']
        entries = rows(root / name / '03-results/results.jsonl')
        assert len(entries) == 3000 and len({x['trial_id'] for x in entries}) == 3000
        models[name] = entries
        failure_lines = [f'# {name} 실패 응답 전수 기록', '',
            '원문 질문·컨텍스트·반환 답변·검사 사유를 보존한 분석용 사본입니다. 형식 오류는 오답 판정이 아닙니다. 진단 태그는 중복될 수 있습니다.', '']
        for row in entries:
            result = read(root / row['result_path'])
            response = result.get('response')
            answer = response.get('answer') if isinstance(response, dict) else None
            tags = set()
            if row['status'] == 'OUTPUT_TRUNCATED':
                tags.add('OUTPUT_TRUNCATED')
            if isinstance(response, dict):
                if 'answer' not in response:
                    tags.add('ANSWER_MISSING')
                elif answer is None:
                    tags.add('ANSWER_NULL')
                elif type(answer) in (int, float):
                    tags.add('ANSWER_NUMERIC_NOT_STRING')
                for err in result.get('schema_errors', []):
                    tags.add('SCHEMA_' + str(err['rule']).upper())
            elif row['status'] == 'INVALID_RESPONSE':
                tags.add('JSON_PARSE_OR_TOP_LEVEL_TYPE')
            checks = row.get('checks', {})
            comparison = checks.get('numeric_comparison')
            if row['experiment'] == 1 and row['status'] == 'VALID':
                if comparison:
                    tags.add('NUMERIC_MATCH' if comparison['matches'] else 'NUMERIC_MISMATCH')
                else:
                    tags.add('BASELINE_NOT_NUMERICALLY_EVALUATED')
                    if len(checks.get('numeric_tokens', [])) > 1:
                        tags.add('MULTIPLE_NUMERIC_TOKENS')
            if checks.get('all_quotes_present') is False:
                tags.add('QUOTE_NOT_EXACT_SUBSTRING')
            if row['status'] == 'VALID' and not response.get('evidence'):
                tags.add('EMPTY_EVIDENCE')
            fulltext = json.dumps(response, ensure_ascii=False) if response is not None else ''
            extended = bool(MARKER.search(fulltext))
            diag = {k: row[k] for k in ('trial_id', 'item_id', 'case', 'experiment', 'variant', 'prompt_condition', 'reasoning', 'status', 'result_path')}
            diag.update(model=name, tags=sorted(tags), strict_answer_marker=bool(checks.get('abstention_marker_detected')),
                        response_text_marker=extended, answer_type=type(answer).__name__,
                        numeric_comparison=comparison, schema_errors=result.get('schema_errors', []),
                        finish_reason=result.get('finish_reason'), usage=result.get('usage'),
                        semantic_assessment='NOT_SCORED')
            diagnostics.append(diag)
            if row['status'] != 'VALID':
                rawtext = None
                if response is None:
                    raw = read((root / row['result_path']).parent / 'raw-response.json', {})
                    rawtext = ''.join(p.get('text', '') for c in raw.get('response', {}).get('candidates', [])
                                      for p in c.get('content', {}).get('parts', []) if not p.get('thought'))
                failure_lines += [f"## {row['trial_id']}", '',
                    f"{row['case']} / {row['variant']} / {row['prompt_condition']} / {row['reasoning']} / {row['status']}", '',
                    '진단: ' + ', '.join(sorted(tags)), '',
                    f"[호출 JSON](../{row['call_path']}) · [원응답](../{PurePosixPath(row['result_path']).parent}/raw-response.json)", '',
                    '**질문 및 컨텍스트**', '', '```json', json.dumps(public[row['item_id']], ensure_ascii=False, indent=2), '```', '',
                    '**반환 응답**', '', '```json', json.dumps(response, ensure_ascii=False, indent=2) if response is not None else (rawtext or '(본문 없음)'), '```', '',
                    '**검사 사유**', '', '```json', json.dumps(diag['schema_errors'], ensure_ascii=False, indent=2), '```', '']
        write_text(output / f'{name}-failures.md', '\n'.join(failure_lines))
    write_rows(output / 'response-diagnostics.jsonl', diagnostics)
    ds = {m: [d for d in diagnostics if d['model'] == m] for m in models}
    lines = ['# 실험 1·2 응답 및 실패 분석', '', f"실행: {root.name} · 분석 갱신: {now()}", '',
        '**6,000건 수집 완료. API 요청 실패 0건. 형식 오류 488건과 출력 잘림 37건은 계산 오답과 구분합니다.**', '',
        '7종 모두 PASS인 후보 1,080개 중 앞 100개를 사용했습니다. 원문 100개 × 2조건 = 200건, 변형 700개 × 4조건 = 2,800건으로 모델당 3,000건입니다. 조건·입력은 두 모델 간 동일합니다. 재호출 없이 저장된 6,000개 응답 전부를 검사했습니다. 의미 정답률·유보 정확도는 이 보고서에서 확정하지 않습니다.', '',
        '## 1. 수집·형식·비용', '']
    lines += table(['모델','요청','형식 통과','형식 오류','출력 잘림','형식 통과율','입력 토큰','출력+추론 토큰','추정 USD'],
        [[m['model'],m['planned'],m['statuses'].get('VALID',0),m['statuses'].get('INVALID_RESPONSE',0),m['statuses'].get('OUTPUT_TRUNCATED',0),
          f"{m['statuses'].get('VALID',0)/m['planned']:.2%}",m['input_tokens'],m['output_tokens_including_thinking'],f"{m['paid_batch_usage_cost_estimate_usd']:.6f}"] for m in summary['models']])
    lines += ['비용은 반환 사용량 × 모델별 Batch 단가입니다. 실제 청구서는 조회하지 않았습니다. 입력은 Flash $0.15 / Lite $0.05, 출력·추론은 Flash $1.25 / Lite $0.20(각 백만 토큰당)입니다. 모든 요청은 유료 Batch 경로이며, 과거 무료·Claude 실행의 비용을 합치지 않았습니다.', '',
        '## 2. 실패 원인 전수 분류', '',
        '아래 태그는 중복될 수 있으므로 합산하면 실패 응답 수가 되지 않습니다. 숫자 답변·null·누락 여부는 실제 파싱 결과에서 확인했습니다. 스키마가 요청에 포함되었는데도 해당 형식을 어긴 응답이 반환되었습니다. 제공자 내부에서 왜 강제되지 않았는지는 이 자료로 확인할 수 없습니다.', '']
    tag_order = ['ANSWER_NUMERIC_NOT_STRING','ANSWER_NULL','ANSWER_MISSING','SCHEMA_TYPE','SCHEMA_REQUIRED','SCHEMA_ADDITIONALPROPERTIES','JSON_PARSE_OR_TOP_LEVEL_TYPE','OUTPUT_TRUNCATED']
    explanations = ['answer가 숫자: 문자열 계약 위반','answer가 null: 문자열 계약 위반','answer 필드 자체가 없음','필드 타입 위반','필수 필드 누락','허용하지 않은 필드 추가','JSON 파싱 또는 최상위 타입 문제','MAX_TOKENS로 출력 잘림']
    lines += table(['원인',*models], [[desc,*[sum(tag in d['tags'] and d['status']!='VALID' for d in ds[m]) for m in models]] for tag,desc in zip(tag_order,explanations)])
    lines += ['### 조건별 실패 집중도', '']
    lines += table(['모델','프롬프트','추론','요청','형식 오류','출력 잘림','null 답변'],
        [[m,p,t,len(z),sum(d['status']=='INVALID_RESPONSE' for d in z),sum(d['status']=='OUTPUT_TRUNCATED' for d in z),sum('ANSWER_NULL' in d['tags'] for d in z)]
         for m in models for p in ['P0','P1'] for t in ['off','on'] if (z:=[d for d in ds[m] if d['prompt_condition']==p and d['reasoning']==t])])
    lines += ['P0에는 실험 1의 100건이 추가되어 각 800건, P1은 각 700건입니다. 분모가 다른 행의 실패 개수만 비교하지 않아야 합니다.', '',
              '## 3. 실험 1: 숫자 비교와 채점기 한계', '',
              '기존 추출기가 `-$35`를 `35`로 읽는 오류를 수정했습니다. 원응답은 변경하지 않았고 수정 전 집계는 analysis/before-currency-sign-fix에 보존했습니다. 아래는 수정 후 값입니다. 숫자가 하나만 추출되는 유효 응답만 비교하며, 단위·배율·답의 의미는 별도입니다.', '']
    lines += table(['모델','추론','전체','형식 통과','숫자 비교 가능','숫자 일치','숫자 불일치','유효하지만 미평가'],
        [[m,t,len(z),sum(d['status']=='VALID' for d in z),sum(d['numeric_comparison'] is not None for d in z),sum('NUMERIC_MATCH' in d['tags'] for d in z),sum('NUMERIC_MISMATCH' in d['tags'] for d in z),sum('BASELINE_NOT_NUMERICALLY_EVALUATED' in d['tags'] for d in z)]
         for m in models for t in ['off','on'] if (z:=[d for d in ds[m] if d['experiment']==1 and d['reasoning']==t])])
    lines += ['예를 들어 답이 “2011년의 합계는 $86 million”이면 연도와 금액 두 숫자가 추출되어 미평가됩니다. 그러므로 Flash의 숫자 일치가 낮다는 사실만으로 Lite보다 풀이력이 낮다고 결론낼 수 없습니다.', '',
              '### 두 모델 모두 숫자 비교가 가능한 동일 문항', '']
    names=list(models)
    pair_data=[]
    for t in ['off','on']:
        maps=[{d['case']:d for d in ds[m] if d['experiment']==1 and d['reasoning']==t and d['numeric_comparison'] is not None} for m in names]
        ids=set(maps[0])&set(maps[1]);counts=Counter((maps[0][i]['numeric_comparison']['matches'],maps[1][i]['numeric_comparison']['matches']) for i in ids)
        pair_data.append([t,len(ids),counts[True,True],counts[True,False],counts[False,True],counts[False,False]])
    lines += table(['추론','공통 비교 문항','둘 다 숫자 일치','Flash만 일치','Lite만 일치','둘 다 불일치'],pair_data)
    lines += ['## 4. 실험 2: 유보 표현과 형식 실패의 관계', '',
        '각 행의 분모는 동일하게 100건입니다. 엄격 탐지는 형식 통과 응답의 answer 필드만 검사합니다. 확장 탐지는 형식 실패도 포함하여 파싱된 전체 응답 문자열에서 같은 정규식 표현을 찾습니다. 확장 탐지는 explanation·인용문에도 반응하므로 유보 정확도나 최종 유보 건수로 사용하면 안 됩니다. null만으로도 유보라고 단정하지 않습니다.', '']
    variant_rows=[]
    for v in list(VARIANT_ORDER)[1:]:
        for p in ['P0','P1']:
            for t in ['off','on']:
                values=[VARIANT_NAMES[v],p+'/'+t]
                for m in models:
                    z=[x for x in ds[m] if x['variant']==v and x['prompt_condition']==p and x['reasoning']==t]
                    values += [sum(d['status']=='VALID' for d in z),sum(d['strict_answer_marker'] for d in z),sum(d['response_text_marker'] for d in z),sum('ANSWER_NULL' in d['tags'] for d in z)]
                variant_rows.append(values)
    lines += table(['유형','조건',*sum(([m+' 유효',m+' 엄격 탐지',m+' 전체문자열 탐지',m+' null'] for m in models),[])],variant_rows)
    lines += ['### 프롬프트 변경 시 동일 문항의 엄격 탐지 변화', '',
              '실험 2에서 P0와 P1 모두 형식 통과한 문항만 연결했습니다. 여전히 표현 탐지이며 의미 판정은 아닙니다.', '']
    pair=[]
    for m in models:
        for t in ['off','on']:
            maps=[{(d['case'],d['variant']):d for d in ds[m] if d['experiment']==2 and d['reasoning']==t and d['prompt_condition']==p and d['status']=='VALID'} for p in ['P0','P1']]
            ids=set(maps[0])&set(maps[1]);c=Counter((maps[0][i]['strict_answer_marker'],maps[1][i]['strict_answer_marker']) for i in ids)
            pair.append([m,t,len(ids),c[False,True],c[True,False],c[True,True],c[False,False]])
    lines += table(['모델','추론','공통 유효','P1에서 새 탐지','P1에서 사라짐','둘 다 탐지','둘 다 없음'],pair)
    lines += ['## 5. 근거 인용·입력 동질성', '']
    lines += table(['모델','유효 응답','근거 빈 배열','인용문 하나 이상 불일치'],[[m,len(z),sum('EMPTY_EVIDENCE' in d['tags'] for d in z),sum('QUOTE_NOT_EXACT_SUBSTRING' in d['tags'] for d in z)] for m in models if (z:=[d for d in ds[m] if d['status']=='VALID'])])
    lines += ['인용문 불일치는 문맥에 문자열 그대로 없다는 뜻이며 곧바로 환각을 의미하지 않습니다. 반대로 정확한 인용문도 계산·논리를 보장하지 않습니다.', '',
        '변형 700개 중 350개(원문 50개)에 대해 제작 기준 Q/C와 실험 1 원문 Q/C가 문자열 수준에서 다릅니다. test-0006은 앞 문장의 대소문자·공백·구두점 정리 차이가 확인됩니다. 모든 50개가 의미상 동등하다고 판정한 것은 아닙니다. 두 모델 사이에는 동일 입력을 사용했지만, 실험 1→2 변화에는 변형 이외의 본문 정리 효과가 섞일 수 있습니다.', '',
        'IC-source 200개는 각각 대응하는 IC-value 부모가 하나씩 기록되어 있습니다. 현재 표의 before/after는 연결된 value 부모 위치입니다. 원래 A/B는 출처를 부여한 주장 구분이며 그 ID를 보존합니다. 위치와 출처 효과를 동일하게 해석하지 않습니다. 모든 변형의 자동 PASS는 최종 텍스트 검사 통과이며 의미적 비정답 가능성/답변 불가능성의 완전한 증명이 아닙니다.', '',
        '## 6. 원응답 사례와 조치', '',
        '[사례별 검토](CASE-STUDIES.md)를 읽으십시오. 실패 전체는 아래 모델별 문서에 보존했습니다.', '',
        *[f'- [{m} 실패 전수 기록](analysis/{m}-failures.md)' for m in models], '',
        '1. 채점기 통화기호 앞 음수 부호 누락: 수정·재집계 완료. 원응답 및 이전 결과 보존.',
        '2. 문자열 대신 숫자, null, 필수 필드 누락: 반환 형식 문제와 내용 문제를 분리. 원응답을 자동으로 정상 응답으로 바꾸지 않음.',
        '3. 다중 숫자 답변: 연도·중간값·최종값을 구분하는 후속 추출 개선이 필요. 이번에는 미평가 유지.',
        '4. 출력 잘림 37건: 최종 답이 완성되지 않았으므로 오답/유보로 강제 판정하지 않음. 재호출하지 않음.',
        '5. 유보 표현: 설명에만 유보가 있거나 null을 반환한 사례 때문에 기존 answer-only 탐지가 누락. 확장 관찰치를 함께 제공하지만 정확도로 사용하지 않음.',
        '6. 의미 평가와 입력 동질성: 50개 원문 차이와 실제 답변 가능 여부를 검토하기 전 강한 모델 우열·유보 성공률 주장은 보류.', '',
        '## 재현 및 범위', '',
        '`PYTHONPATH=src .venv/bin/python -m finarch.experiments.02-analysis.legacy.content-analysis.analysis --run reports/experiments-run/20260920-exp-003`', '',
        '이 분석 프로그램은 API를 호출하지 않습니다. 진단 6,000행과 실패 전수 기록을 생성합니다. 대표 사례의 내용 검토는 CASE-STUDIES.md에 별도 기록하며, 전수 의미 채점을 수행했다고 주장하지 않습니다. 루브릭 작업은 계속 중단 상태입니다.', '']
    build_cases = __import__('finarch.experiments.02-analysis.legacy.content-analysis.case_studies', fromlist=['build']).build
    build_cases(root)
    write_text(root / 'ANALYSIS.md', '\n'.join(lines))
    write_text(output / 'README.md', '# 분석 산출물 안내\n\n1. ../ANALYSIS.md: 집계·비교·해석 범위.\n2. ../CASE-STUDIES.md: 근거를 대조한 대표 응답 사례.\n3. 모델명-failures.md: 실패 응답 전수와 실제 Q/C·응답·검사 사유.\n4. response-diagnostics.jsonl: 6,000개 응답의 재현 가능한 진단.\n5. before-currency-sign-fix/: 숫자 추출 수정 전 집계.\n\nanalysis.py가 집계와 안내 문서를 생성합니다. HTML은 생성하지 않습니다.\n')
    event(root,'RESPONSE_ANALYSIS_COMPLETED',responses=len(diagnostics),failures=sum(d['status']!='VALID' for d in diagnostics),new_model_calls=0)
    print(json.dumps({'responses':len(diagnostics),'failures':sum(d['status']!='VALID' for d in diagnostics)}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    main(parser.parse_args().run)
