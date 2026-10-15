run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
"""Analyze magnitude-format runs using saved outputs; no evaluator model calls."""
import json
import math
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from finarch.paths import SOURCE

read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_rows = __import__('finarch.experiments.90-operations.storage', fromlist=['write_rows']).write_rows
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
VARIANT_NAMES = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['VARIANT_NAMES']).VARIANT_NAMES
VARIANT_ORDER = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['VARIANT_ORDER']).VARIANT_ORDER
table = __import__('finarch.experiments.02-analysis.legacy.content-analysis.analysis', fromlist=['table']).table
answer_contract = __import__('finarch.experiments.01-evaluation.02-request.answer_contract', fromlist=['*'])


def precision_conflict(request):
    """Recognize explicit literal rounding instructions without inferring intent."""
    question = request['input']['question'].lower()
    words = {word: i for i, word in enumerate(('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'))}
    hints = set()
    if 'nearest integer' in question:
        hints.add(0)
    for token in re.findall(r'\b(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten) decimal places?\b', question):
        hints.add(int(token) if token.isdigit() else words[token])
    supplied = request['input'].get('answer_format', {}).get('decimal_places')
    if hints and hints != {supplied}:
        return {'question_decimal_places': sorted(hints), 'supplied_decimal_places': supplied,
                'policy': 'OBSERVATION_ONLY_NO_REQUEST_OR_SCORE_CHANGE'}
    return None


def response_diagnostics(row, result, reference):
    """Keep diagnostic observations separate from the frozen scoring decision."""
    response = result.get('response')
    observations = []
    for error in result.get('schema_errors', []):
        message = error.get('message', '')
        if message == 'Abstention requires a null answer.':
            observations.append('ABSTAINED_WITH_NUMERIC_ANSWER')
        elif message == 'Abstention requires a null sign.':
            observations.append('ABSTAINED_WITH_BOOLEAN_SIGN')
        elif 'exactly' in message and 'decimal places' in message:
            observations.append('DECIMAL_PLACES_MISMATCH')
        else:
            observations.append('OTHER_SCHEMA_ERROR')
    relaxed = None
    if isinstance(response, dict):
        if response.get('status') == 'abstained':
            observations.append('RAW_STATUS_ABSTAINED')
        meta = response.get('answer_meta', {})
        answer = response.get('answer')
        predicted = None
        if ('status' not in response and 'answer_meta' in response
                and type(answer) in (int, float) and (type(answer) is int or math.isfinite(answer))):
            predicted = Decimal(str(answer))
        elif (response.get('status') == 'answered' and isinstance(answer, str)
              and re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', answer)
              and type(meta.get('negative')) is bool):
            predicted = Decimal(answer) * (-1 if meta['negative'] else 1)
        if row['experiment'] == 1 and predicted is not None:
            gold = Decimal(reference['reference_answer'])
            if row['status'] != 'VALID':
                relaxed = {'computed': str(predicted), 'gold': str(gold), 'matches': predicted == gold,
                           'policy': 'DIAGNOSTIC_ONLY_IGNORE_REPRESENTATION_PRECISION', 'changes_score': False}
                if predicted == gold:
                    observations.append('INVALID_FORMAT_BUT_EQUAL_NUMERIC_VALUE')
            elif predicted != gold:
                observations.append('SIGN_ONLY_DIFFERENCE' if abs(predicted) == abs(gold) else 'MAGNITUDE_DIFFERENCE')
    return sorted(set(observations)), relaxed


def build(root):
    root = Path(root)
    summary = read(run_layout.validation(root) / 'summary.json')
    private = {x['item_id']: x for x in rows(run_layout.inputs(root) / 'private.jsonl')}
    public = {x['item_id']: x for x in rows(run_layout.inputs(root) / 'public.jsonl')}
    output = run_layout.diagnostics(root)
    output.mkdir(parents=True, exist_ok=True)
    diagnostics = []
    lines = ['# 숫자·부호·배율 응답 분석', '', f"실행 {root.name} · 상태 {summary['status']} · 갱신 {now()}", '',
             '이 분석은 저장된 응답·Python 검사·원문 숫자 정답을 사용합니다. 형식 오류, 숫자 불일치, 유보 선언과 의미 미평가를 구별합니다. 추가 평가 모델은 호출하지 않습니다.', '']
    for model in summary['models']:
        key = model['model']
        entries = rows(run_layout.validation(root, key) / 'results.jsonl')
        requests = {x['trial_id']: x for x in rows(run_layout.requests(root, key))}
        v5 = all(x['response_schema'].get('title') in answer_contract.STRUCTURAL_TITLES for x in requests.values())
        failure_lines = [f'# {key} 실패·불일치·원본 유보 응답', '',
                         '숫자 불일치의 계산 원인과 정답·단위 해석의 타당성을 자동으로 확정하지 않습니다. 실제 질문·응답·검사 사유를 아래에서 대조하십시오.', '']
        local = []
        error_messages = Counter()
        for row in entries:
            result = read(root / row['result_path']) if row.get('result_path') else {}
            checks, response = row.get('checks', {}), result.get('response')
            if run_layout.ordered(root) and row['status'] == 'VALID':
                screen = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['screen']).screen
                checks = screen(response, public[row['item_id']], private[row['item_id']])
                row = {**row, 'checks': checks}
            tags = []
            comparison = checks.get('numeric_comparison')
            if row['status'] != 'VALID':
                tags.append(row['status'])
            if comparison:
                tags.append('NUMERIC_MATCH' if comparison['matches'] else 'NUMERIC_MISMATCH')
            if checks.get('declared_abstention'):
                tags.append('DECLARED_ABSTENTION')
            if checks.get('numeric_answer_present') is False:
                tags.append('NUMERIC_ANSWER_ABSENT')
            if row['experiment'] == 1 and not comparison:
                tags.append('BASELINE_NOT_NUMERICALLY_EVALUATED')
            if checks.get('all_quotes_present') is False:
                tags.append('QUOTE_NOT_EXACT_SUBSTRING')
            for error in result.get('schema_errors', []):
                tags.append('SCHEMA_' + str(error['rule']).upper())
            if isinstance(response, dict) and not response.get('evidence'):
                tags.append('EMPTY_EVIDENCE')
            observations, relaxed = response_diagnostics(row, result, private[row['item_id']]['reference'])
            tags.extend(observations)
            conflict = precision_conflict(requests[row['trial_id']])
            if conflict:
                tags.append('QUESTION_METADATA_PRECISION_CONFLICT')
            error_messages.update(error['message'] for error in result.get('schema_errors', []))
            diag = {k: row[k] for k in ('case', 'variant', 'experiment', 'prompt_condition', 'reasoning', 'trial_id', 'status', 'call_path')}
            diag.update(model=key, checks=checks, tags=sorted(set(tags)), numeric_comparison=comparison,
                        diagnostic_numeric_comparison=relaxed, raw_status=response.get('status') if isinstance(response, dict) else None,
                        precision_conflict=conflict,
                        schema_errors=result.get('schema_errors'), usage=result.get('usage'), semantic_assessment='NOT_SCORED')
            local.append(diag)
            if row['status'] not in ('VALID', 'NOT_RUN') or 'NUMERIC_MISMATCH' in tags or (row['experiment'] == 1 and 'DECLARED_ABSTENTION' in tags):
                failure_lines += [f"## {row['case']} · {VARIANT_NAMES.get(row['variant'],row['variant'])} · {row['prompt_condition']}/{row['reasoning']}", '',
                    f"상태: {row['status']} · 분류: {', '.join(tags)}", '',
                    f"[요청·응답 JSON]({'../../' if run_layout.ordered(root) else '../'}{row['call_path']})" if row.get('call_path') else '저장된 호출 없음', '',
                    '**질문:** ' + public[row['item_id']]['question'], '',
                    '**실제 전달 본문:** ' + public[row['item_id']]['context'], '',
                    '**원문 숫자 정답:** ' + str(private[row['item_id']]['reference']['reference_answer']) + ' (변형의 의미 정답으로 사용하지 않음)', '',
                    '```json', json.dumps({'response': response, 'schema_errors': result.get('schema_errors'), 'comparison': comparison, 'diagnostic_comparison_only': relaxed, 'error': result.get('error')}, ensure_ascii=False, indent=2), '```', '']
        diagnostics.extend(local)
        write_text(output / f'{key}-failures.md', '\n'.join(failure_lines))
        lines += [f'## {key}', '', f"계획 {model['planned']}건 · 시도 {model['attempts']}회 · 상태 {model['statuses']}", '',
                  f"입력 토큰 {model['input_tokens']:,}, 캐시 입력 {model['cache_read_tokens']:,}, 출력 토큰 {model['output_tokens_including_thinking']:,}입니다. 호출 경로는 `{model['transport']}`이며 Codex 구독 사용량과 유료 API 비용을 구분합니다.", '', '### 원본 문제', '']
        data = []
        for prompt, reasoning in sorted({(x['prompt_condition'], x['reasoning']) for x in local if x['experiment'] == 1}):
            subset = [x for x in local if x['experiment'] == 1 and x['prompt_condition'] == prompt and x['reasoning'] == reasoning]
            compared = [x for x in subset if x['numeric_comparison'] is not None]
            matched = sum(x['numeric_comparison']['matches'] for x in compared)
            data.append([run_layout.prompt_label(prompt), reasoning, len(subset), sum(x['status'] == 'VALID' for x in subset), len(compared), matched,
                         sum(not x['numeric_comparison']['matches'] for x in compared),
                         '미평가' if v5 else sum('DECLARED_ABSTENTION' in x['tags'] for x in subset),
                         f'{matched / len(subset):.1%}' if subset else '—',
                         f'{matched / len(compared):.1%}' if compared else '—'])
        lines += table(['풀이 조건', '추론 조건', '계획', '형식 통과', '숫자 비교', '숫자 일치', '숫자 불일치', '유효 유보', '계획 대비 일치', '비교 가능 응답 내 일치'], data)
        lines += ['계획 대비 일치는 미평가·형식 실패를 포함한 고정 분모입니다. 비교 가능 응답 내 비율은 조건부 관찰값이며 전체 정답률로 사용하지 않습니다.', '']
        lines += ['### 변형 문제', '']
        groups = []
        for variant in list(VARIANT_ORDER)[1:]:
            for prompt in sorted({x['prompt_condition'] for x in local}):
                for reasoning in sorted({x['reasoning'] for x in local}):
                    subset = [x for x in local if x['variant'] == variant and x['prompt_condition'] == prompt and x['reasoning'] == reasoning]
                    groups.append([VARIANT_NAMES[variant], run_layout.prompt_label(prompt), reasoning, len(subset),
                                   sum(x['status'] == 'VALID' for x in subset),
                                   '미평가' if v5 else sum('DECLARED_ABSTENTION' in x['tags'] for x in subset),
                                   '해당 없음' if v5 else sum('RAW_STATUS_ABSTAINED' in x['tags'] and x['status'] != 'VALID' for x in subset)])
        lines += table(['유형', '프롬프트', '추론 조건', '계획', '형식 통과', '유효 유보', '유보라 적었으나 형식 실패'], groups)
        lines += ['### 실패와 검사 관찰값', '']
        counts = Counter(tag for x in local for tag in x['tags'])
        lines += table(['분류', '건수'], sorted(counts.items()))
        lines += ['한 응답에 여러 태그가 붙을 수 있습니다. `RAW_STATUS_ABSTAINED`는 형식 실패까지 포함한 원응답 관찰값이며 유효 유보에 더하지 않습니다. `INVALID_FORMAT_BUT_EQUAL_NUMERIC_VALUE`는 자리수 형식을 무시했을 때 숫자만 같은 진단 결과로, 원래 실패 판정을 바꾸지 않습니다.', '']
        lines += table(['실제 검사 실패 사유', '발생 횟수'], error_messages.most_common())
        conflicts = [x for x in local if x['precision_conflict']]
        conflict_cases = {x['case']: x for x in conflicts if x['experiment'] == 1}
        lines += ['### 질문과 소수 자릿수 메타정보의 충돌', '',
                  f"명시적 자릿수 문구와 전달 메타정보가 다른 원문은 {len(conflict_cases)}개이며, 해당 요청은 {len(conflicts)}건(원본 {sum(x['experiment'] == 1 for x in conflicts)}건, 변형 {sum(x['experiment'] == 2 for x in conflicts)}건)입니다. 원문 정답에 남은 소수 자릿수와 질문이 요구한 표기 자릿수는 서로 다른 개념입니다. 아래는 실제 전달된 요청의 관찰값이며 자동 보정이나 점수 변경을 하지 않았습니다.", '']
        lines += table(['원문', '질문 자릿수', '전달 메타정보 자릿수'],
                       [[case, x['precision_conflict']['question_decimal_places'], x['precision_conflict']['supplied_decimal_places']]
                        for case, x in sorted(conflict_cases.items())])
        write_rows(output / f'{key}-precision-conflicts.jsonl', conflicts)
        samples = rows(run_layout.execution(root, key) / 'resources.jsonl')
        if samples:
            resource = {'samples': len(samples), 'maximum_active': max(s['active'] for s in samples),
                        'maximum_limit': max(s['concurrency_limit'] for s in samples),
                        'maximum_cpu_percent': max(s['cpu_percent'] for s in samples),
                        'maximum_memory_percent': max(s['memory_percent'] for s in samples),
                        'minimum_available_memory_gb': min(s['available_memory_bytes'] for s in samples) / 1024 ** 3,
                        'memory_blocked_samples': sum(s['memory_blocked'] for s in samples)}
            write(output / f'{key}-resources.json', resource)
            lines += ['### 자원 사용', '', '```json', json.dumps(resource, indent=2), '```', '']
        lines += [f'[실패·숫자 불일치 상세]({key}-failures.md)' if run_layout.ordered(root) else f'[실패·숫자 불일치 상세](analysis/{key}-failures.md)', '']
    lines += ['## 해석 범위', '',
              'V5 이후(V7 포함)의 숫자 일치는 answer 숫자 자체를 원문 정답과 직접 비교합니다. 과거 V3·V4만 당시 계약대로 별도 부호를 적용합니다. 배율은 다시 곱하지 않습니다. 계산 과정·통화·단위 의미 전체의 정답률을 확정한 것은 아닙니다.',
              'V3·V4의 status=abstained와 V7의 classification은 모델이 반환한 선언입니다. NUMERIC_ANSWER_ABSENT는 숫자 답 없음만 기록하며, 이 숫자 검사에서 유보의 적절성을 확정하지 않습니다. 의미 판정과 미평가 여부는 A01 내용 검토와 A02 비교 결과에서 확인합니다. 형식 실패와 원본 유보를 계산 오답으로 합치지 않습니다.',
              'Luna의 none/medium과 Gemini의 thinking budget off/on은 제어 방식이 다릅니다. CLI에서 API로 전환하면 기본 지시문·전송 방식도 달라집니다. 이전 실행과의 차이를 캐시 또는 응답 형식 변경 하나만의 효과로 단정할 수 없습니다.', '']
    write_rows(output / 'response-diagnostics.jsonl', diagnostics)
    write_text((run_layout.diagnostics(root) / 'numeric-analysis.md') if run_layout.ordered(root) else root / 'ANALYSIS.md', '\n'.join(lines))
    if run_layout.ordered(root):
        render = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_review', fromlist=['render_readme']).render_readme
        render(root)
    else:
        write_text(output / 'README.md', (SOURCE / 'experiments/templates/numeric-analysis-readme-template.md').read_text())
    event(root, 'NUMERIC_ANALYSIS_COMPLETED', records=len(diagnostics), new_model_calls=0)
