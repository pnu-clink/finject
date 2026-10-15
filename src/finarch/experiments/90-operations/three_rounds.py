"""Resume the authorized native-Batch study without choosing unreviewed changes."""
import argparse
from collections import Counter
import json
from pathlib import Path
from finarch.experiments import assets

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
semantic = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_review', fromlist=['*'])
CAMPAIGN = '20260927-luna-three-rounds'
REPORT = store.PROJECT / 'reports/run' / CAMPAIGN
BEGIN, END = '<!-- LUNA-THREE-ROUNDS:BEGIN -->', '<!-- LUNA-THREE-ROUNDS:END -->'
VARIANT_ORDER = ('ORIGINAL', 'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')


def runs():
    found = []
    for path in (store.PROJECT / 'reports/experiments-run').glob('*/config.json'):
        config = store.read(path)
        if config.get('improvement', {}).get('campaign') == CAMPAIGN:
            found.append((config['improvement']['round'], path.parent, config))
    found.sort()
    if len({r[0] for r in found}) != len(found):
        raise ValueError('DUPLICATE_CAMPAIGN_ROUND')
    return found


def costs(root):
    summary = store.read(root / 'summary.json', {})
    models = summary.get('models', [])
    solver = sum(m.get('paid_batch_usage_cost_estimate_usd') or 0 for m in models)
    analysis = sum(store.read(p).get('token_cost_estimate_usd') or 0 for p in (root / semantic.ROOT).rglob('state.json'))
    missing = sum(m.get('attempts_without_usage') or 0 for m in models)
    missing += sum(store.read(p).get('requests_without_known_cost') or 0 for p in (root / semantic.ROOT).rglob('state.json'))
    return {'solver': solver, 'analysis': analysis, 'total': solver + analysis, 'unknown_cost_records': missing}


def repeat_controls(first, second):
    """Describe unchanged-request variation separately from prompt revisions."""
    model_a = store.read(first / 'config.json')['models'][0]['key']
    model_b = store.read(second / 'config.json')['models'][0]['key']
    identity = lambda r: (r['case'], r['variant'], r['prompt_condition'], r['reasoning'])
    requests = [{identity(r): r for r in store.rows(root / key / '01-requests/manifest.jsonl')} for root, key in ((first, model_a), (second, model_b))]
    results = [{identity(r): r for r in store.rows(root / key / '03-results/results.jsonl')} for root, key in ((first, model_a), (second, model_b))]
    groups = {}
    for key in sorted(set(requests[0]) & set(requests[1])):
        group = groups.setdefault(key[2], Counter())
        a, b = requests[0][key], requests[1][key]
        identical = all(a.get(field) == b.get(field) for field in ('model', 'input', 'prompt', 'response_schema', 'reasoning_effort', 'max_output_tokens'))
        group['same_request' if identical else 'changed_request'] += 1
        ra, rb = results[0].get(key), results[1].get(key)
        if not identical:
            continue
        if not ra or not rb or ra['status'] != 'VALID' or rb['status'] != 'VALID':
            group['unassessed'] += 1
            continue
        group['comparable'] += 1
        aa, ab = ra['response']['answer'], rb['response']['answer']
        group['number_null_transition'] += (aa is None) != (ab is None)
        group['answer_changed'] += aa != ab
    return groups


def round_pairs(first, second):
    """Compare only jointly assessed responses; retain all planned pairs."""
    folders = [Path(root) / '02_analysis/02_comparison/rows.jsonl' for root in (first, second)]
    if not all(folder.exists() for folder in folders):
        return []
    rows = [{**row, 'round': label} for label, folder in zip(('previous', 'next'), folders) for row in store.rows(folder)]
    return [{**semantic.paired([r for r in rows if r['prompt_condition'] == prompt and r['reasoning'] == reasoning], 'round', 'previous', 'next'),
             'prompt': prompt, 'reasoning': reasoning} for prompt in ('P0', 'P1') for reasoning in ('off', 'on')]


def write_report():
    REPORT.mkdir(parents=True, exist_ok=True)
    cohort = runs()
    cost_lines, sections, paper_lines, outcome_lines = [], [], [], []
    reviewed_rounds = 0
    total_costs = Counter()
    for number, root, config in cohort:
        state, summary = store.read(root / 'state.json'), store.read(root / 'summary.json')
        analyzed = store.read(root / '02_analysis/02_comparison/summary.json')
        model = summary['models'][0]
        cost = costs(root)
        total_costs.update(cost)
        reviews = [event for event in store.rows(root / 'events.jsonl') if event.get('event') == 'STUDY_CRITICAL_REVIEW']
        reviewed_rounds += bool(analyzed and reviews)
        status = '비판적 검토·논문 반영' if analyzed and reviews else '내용 분석 집계됨 · 비판적 검토 대기' if analyzed else '분석 진행 중' if state['status'] == 'FINISHED' else state['status']
        cost_lines.append(f"|{number}차 · {root.name}|{status}|${cost['solver']:.6f}|${cost['analysis']:.6f}|${cost['total']:.6f}|{cost['unknown_cost_records']}|")
        sections.extend([f'## {number}차 · {root.name}', '',
            f'[뷰어에서 보기](http://127.0.0.1:8894/?run={root.name}&tab=analysis) · [실제 요청·응답](../../experiments-run/{root.name}/README.md)', '',
            f"- 상태: {state['status']}; 형식 {model.get('statuses', {})}; 캐시 {model.get('cache_verification', {}).get('status', '미확인')}.",
            f"- 프롬프트: {config['improvement'].get('prompt_revision', '미기록')}; 출력 상한 {config['max_output_tokens']}토큰.", ''])
        note = config['improvement'].get('review_of_previous_round')
        if note:
            sections += ['### 앞 차수 검토와 이번 변경', '', note, '']
        groups = [g for g in model.get('groups', []) if g['experiment'] == 1]
        originals_by_reasoning = {g['reasoning']: g for g in groups}
        original_digest = ' · '.join(f"{reasoning.upper()} {originals_by_reasoning[reasoning].get('numeric_matches', 0)}/100"
            if originals_by_reasoning.get(reasoning, {}).get('numeric_compared') else f'{reasoning.upper()} 미평가' for reasoning in ('off', 'on'))
        variant_digest = []
        for prompt in ('P0', 'P1'):
            for reasoning in ('off', 'on'):
                cells = [c for c in analyzed.get('matrix', []) if c['variant'] != 'ORIGINAL' and c['prompt'] == prompt and c['reasoning'] == reasoning] if analyzed else []
                variant_digest.append(f"{sum(c['appropriate'] for c in cells)}/{sum(c['assessed'] for c in cells)}" if cells else '분석 중')
        mode_digest = f"{analyzed['overall'].get('p1_mode_answer_mismatches', 0)}/{analyzed['overall'].get('p1_mode_answer_checked', 0)}" if analyzed else '집계 대기'
        outcome_lines.append(f"|[{number}차](http://127.0.0.1:8894/?run={root.name}&tab=analysis)|{original_digest}|" + '|'.join(variant_digest) + f'|{mode_digest}|')
        sections += ['|원본 조건|숫자 일치 / 계획|숫자 비교 가능|숫자 답 없음|', '|---|---:|---:|---:|']
        for g in groups:
            observed = g.get('numeric_compared', 0) + g.get('numeric_answers_absent', 0)
            match = f"{g.get('numeric_matches', 0)} / {g['planned']}" if observed else f"미평가 / {g['planned']}"
            sections.append(f"|P0 · {g['reasoning']}|{match}|{g.get('numeric_compared', 0)}|{g.get('numeric_answers_absent', 0)}|")
        sections.append('')
        if number > 1:
            sections += [f"- 입력 답변 가능성은 {cohort[0][1].name}의 같은 800문항 판정·실패 기록을 공통으로 사용합니다. 추가 입력 판정 호출·비용은 0입니다."]
        stage_states = [(str(p.parent.relative_to(root / semantic.ROOT)), store.read(p)) for p in sorted((root / semantic.ROOT).rglob('state.json'))]
        sections += [f"- 분석 {name}: {s['status']} · {s.get('statuses', s.get('request_counts', {}))}" for name, s in stage_states]
        sections.append('')
        if analyzed:
            a = analyzed['overall']
            bounds = ' ~ '.join(f'{100 * b:.1f}%' for b in a['planned_worst_best_bounds'])
            sections += [f"내용 판단 가능 {a['assessed']}/{a['planned']}, 타당한 대응 {a['appropriate']}/{a['assessed']}, 미평가·미해결 {a['unassessed']}, 재검토 불일치 {a['audit_disagreements']}입니다. 전체 계획 분모에서 미확정 응답을 모두 부적절/적절로 둘 때의 범위는 {bounds}입니다. 이 범위도 유효한 분석 판정이 맞다는 조건에 의존합니다.", '',
                '|유형|지시|추론|형식 통과 / 계획|타당 / 판정 가능|미평가|', '|---|---|---|---:|---:|---:|']
            for c in sorted(analyzed['matrix'], key=lambda c: (VARIANT_ORDER.index(c['variant']), c['prompt'], c['reasoning'])):
                sections.append(f"|{c['variant']}|{c['prompt']}|{c['reasoning']}|{c['format_valid']}/{c['planned']}|{c['appropriate']}/{c['assessed']}|{c['unassessed']}|")
            sections += ['', f"재검토된 {a['audit_reviewed']}응답 중 적절/부적절/미해결의 큰 판단이 달라진 것은 {a['audit_appropriateness_disagreements']}개입니다. 오류 종류나 계산·근거·일관성만 달라져도 포함하는 엄격한 불일치는 {a['audit_disagreements']}개이며 모두 기본 집계에서 미해결로 보존합니다. 표본은 판정별로 골랐으므로 이 비율을 전체 오류율로 해석하지 않습니다.", '']
            sections += ['', '|대응 비교|공동 판정 가능 / 계획 짝|개선 0→1|악화 1→0|타당률 차이|', '|---|---:|---:|---:|---:|']
            for p in analyzed['paired']:
                difference = '미평가' if p['difference'] is None else f"{100 * p['difference']:+.1f}%p"
                sections.append(f"|{p['left']}→{p['right']} · {' '.join(p.get('fixed_conditions', {}).values())}|{p['assessed_pairs']}/{p['planned_pairs']}|{p['transitions'].get('0->1', 0)}|{p['transitions'].get('1->0', 0)}|{difference}|")
            sections += ['', '|P1 추론 조건|분류 일치 / 입력 판정 가능|선언: 답 / 조건부 / 유보|선언·숫자/null 모순 / 검사|선언·관찰 행동 불일치 / 검토|', '|---|---:|---:|---:|---:|']
            for reasoning in ('off', 'on'):
                cells = [c for c in analyzed['matrix'] if c['prompt'] == 'P1' and c['reasoning'] == reasoning]
                modes = ' / '.join(str(sum(c.get('p1_stated_modes', {}).get(mode, 0) for c in cells)) for mode in ('ANSWER', 'CONDITIONAL', 'ABSTAIN'))
                contradiction = f"{sum(c.get('p1_mode_answer_mismatches', 0) for c in cells)} / {sum(c.get('p1_mode_answer_checked', 0) for c in cells)}"
                behavior = f"{sum(c.get('p1_mode_behavior_mismatches', 0) for c in cells)} / {sum(c.get('p1_mode_behavior_compared', 0) for c in cells)}"
                sections.append(f"|{reasoning}|{sum(c['p1_classification_matches'] for c in cells)} / {sum(c['p1_classification_compared'] for c in cells)}|{modes}|{contradiction}|{behavior}|")
            sections += ['', '선언·숫자/null 모순은 ANSWER인데 null 또는 CONDITIONAL/ABSTAIN인데 숫자인 경우의 로컬 검사입니다. 선언·관찰 행동 불일치는 분석 LLM이 읽은 행동과 선언이 다른 경우로, 분석자의 오류 가능성도 포함합니다. 이 진단을 추가했다고 기존 형식·의미 점수를 소급 변경하지 않습니다.']
            sections += ['', '|P1 추론|조건부 선언 / 요청|분석자가 관찰한 조건부 / 검토|그중 타당한 조건부|', '|---|---:|---:|---:|']
            for reasoning in ('off', 'on'):
                cells = [c for c in analyzed['matrix'] if c['prompt'] == 'P1' and c['reasoning'] == reasoning]
                mode = lambda field: sum(c.get(field, {}).get('CONDITIONAL', 0) for c in cells)
                sections.append(f"|{reasoning}|{mode('p1_stated_modes')} / {sum(c['p1_planned'] for c in cells)}|{mode('observed_behaviors')} / {sum(c.get('p1_mode_behavior_compared', 0) for c in cells)}|{mode('appropriate_behaviors')}|")
            sections += ['', '조건부라고 선언한 수와 분석자가 설명에서 관찰한 행동을 구분합니다. 타당한 조건부는 미해결·재검토 불일치를 제외한 잠정 판정이며, 조건별 결과 자체의 개수나 완전히 객관적인 정보량 지표가 아닙니다. 분류 문구가 행동 판정에 영향을 주었을 가능성도 남깁니다.']
            sections += ['', '### 비판적 해석과 다음 차수 결정', '',
                f"원본 정오와 변형 대응의 역전 사례 {analyzed['counterexample_count']}개를 `02_analysis/02_comparison/counterexamples.jsonl`에 연결했습니다. 원문 숫자 일치가 변형의 타당성을 보장하지 않는지, 원문 숫자는 틀려도 변형의 충돌·결측에는 타당하게 대응하는지 양쪽 사례를 확인합니다.", '',
                '분석 LLM의 판단은 잠정값입니다. 동일 Luna 계열의 공유 오류, 판정 가능 응답만의 선택 편향, 입력 판정 오류와 재검토 불일치를 함께 검토해야 합니다. null 증가 자체를 개선으로 해석하지 않습니다.', '']
            if reviews:
                sections += [reviews[-1]['report_ko'], '']
            paper_lines.append(f"|{number}차|{root.name}|{model['statuses'].get('VALID', 0)}/3000|{a['assessed']}/3000|{a['appropriate']}/{a['assessed']}|{a['unassessed']}|${cost['total']:.6f}|")
    cost_lines.append(f"|합계|수집된 사용량 기준|${total_costs['solver']:.6f}|${total_costs['analysis']:.6f}|${total_costs['total']:.6f}|{total_costs['unknown_cost_records']}|")
    if len(cohort) > 1:
        comparisons = list(zip(cohort, cohort[1:]))
        if len(cohort) == 3:
            comparisons.append((cohort[0], cohort[2]))
        sections += ['## 차수 사이 같은 요청의 변동', '', 'P1 지시를 바꾼 요청의 차이는 개선 실험입니다. 실제 payload가 같은 요청만 따로 확인하여 숫자/null 전환과 답의 변동을 기록합니다. 같은 모델 이름이 제공자의 고정된 내부 버전까지 보장하지는 않습니다.', '',
            '|비교|조건|동일 요청|변경 요청|양쪽 형식 통과|숫자/null 전환|답 값 변경|미평가|', '|---|---|---:|---:|---:|---:|---:|---:|']
        for a, b in comparisons:
            for prompt, counts in repeat_controls(a[1], b[1]).items():
                sections.append(f"|{a[0]}→{b[0]}차|{prompt}|{counts['same_request']}|{counts['changed_request']}|{counts['comparable']}|{counts['number_null_transition']}|{counts['answer_changed']}|{counts['unassessed']}|")
        sections.append('')
        sections += ['### 차수 사이 내용 판정의 대응 비교', '', '두 차수에서 모두 판정 가능한 동일 응답 조건만 비교합니다. P0는 원본을 포함한 800짝/추론 조건, P1은 변형 700짝/추론 조건이므로 두 줄의 분모를 같다고 보지 않습니다. 누락 짝과 P0의 자연 변동도 함께 확인하며 P1 변화 전체를 지시 개선의 인과 효과로 해석하지 않습니다.', '',
            '|비교|조건|공동 판정 가능 / 계획 짝|개선 0→1|악화 1→0|타당률 차이|', '|---|---|---:|---:|---:|---:|']
        for a, b in comparisons:
            for p in round_pairs(a[1], b[1]):
                difference = '미평가' if p['difference'] is None else f"{100 * p['difference']:+.1f}%p"
                sections.append(f"|{a[0]}→{b[0]}차|{p['prompt']} · {p['reasoning']}|{p['assessed_pairs']}/{p['planned_pairs']}|{p['transitions'].get('0->1', 0)}|{p['transitions'].get('1->0', 0)}|{difference}|")
        sections.append('')
    template = (store.PROJECT / 'src/finarch/experiments/templates/three-rounds-report.md').read_text()
    completion = '3차 풀이·분석·비판적 검토·논문 반영 완료. 미평가·미해결 응답은 아래 분모에 보존합니다.' if reviewed_rounds == 3 else f'진행 중 · 비판적 검토·논문 반영 {reviewed_rounds}/3차'
    if any(event.get('event') == 'USER_REVIEW_RESET' for event in store.rows(REPORT / 'events.jsonl')):
        completion = '진행 방식 수정 · 기존 API 분석·개선 결론 보류. 1차 원응답을 Codex에서 직접 재검토하며 개선안은 사용자와 합의합니다. 아래 2·3차 및 API 분석 수치는 이전 실행 이력입니다.'
    delivery = [event for event in store.rows(REPORT / 'events.jsonl') if event.get('event') == 'STUDY_DELIVERY_VERIFIED']
    verification = delivery[-1]['report_ko'] if delivery else '실제 화면과 최종 무결성 확인 전입니다.'
    text = template.replace('{{updated}}', store.now()).replace('{{completion}}', completion).replace('{{verification}}', verification).replace('{{costs}}', '\n'.join(cost_lines)).replace('{{outcomes}}', '\n'.join(outcome_lines)).replace('{{rounds}}', '\n'.join(sections))
    store.write_text(REPORT / 'README.md', text)
    return paper_lines


def update_paper():
    """Replace only the explicitly marked development-study block."""
    if any(event.get('event') == 'USER_REVIEW_RESET' for event in store.rows(REPORT / 'events.jsonl')):
        write_report()
        return False
    paper = store.PROJECT / 'reports/run/20260924-paper-draft/PAPER-KO.md'
    text = paper.read_text()
    rows = write_report()
    if not rows:
        return False
    findings = []
    for number, root, _ in runs():
        reviews = [event for event in store.rows(root / 'events.jsonl') if event.get('event') == 'STUDY_CRITICAL_REVIEW']
        if reviews and reviews[-1].get('paper_ko'):
            findings.extend([f'#### {number}차의 관찰과 해석 한계', '', reviews[-1]['paper_ko'], ''])
    block = '\n'.join([BEGIN, '### 8.1 동일 100원문에 대한 3차 개발 실험', '',
        '동일한 원문 100개와 7종 변형 700개를 유지하며 GPT-6-Luna를 OpenAI Batch API로 실행하였다. 원본은 P0×Reasoning OFF/ON, 변형은 P0/P1×Reasoning OFF/ON으로 차수당 3,000개 응답을 계획하였다. 추론 설정은 none/medium, 캐시는 명시 모드에서 breakpoint 없이 비활성화하였다. 변경된 프롬프트와 미변경 조건은 차수별 요청 manifest에 동결하였다.', '',
        '대상은 20260917-002/results의 순서에서 원문 준비와 일곱 변형의 자동 검사를 모두 통과한 첫 100원문이다. 선택 과정에서 원문 준비 미통과 20개, 변형 세트 미완성 159개를 건너뛰었다. 무작위 표본이 아니며, 선택된 원본 100개의 사람 판단 기록은 PENDING이다. 따라서 제작 완료 조건에 따른 선택 편향과 사람 미승인 상태를 보존하고 전체 데이터셋으로 일반화하지 않는다.', '',
        '입력의 답변 가능성은 풀이 응답·제작 유형·gold를 보지 않는 분석 LLM으로 먼저 검토하고, 같은 판단을 차수 간 공통 기준으로 사용하였다. 이후 모델·조건 식별자를 가린 응답을 계산·근거·일관성·행동·분류 준수로 나누어 검토하였다. P1의 분류 문구 등 응답 내용으로 조건을 추측할 수 있으므로 완전한 조건 은폐는 아니다. 첫 판정별 최대 8개 응답을 다시 검토하며 불일치는 미해결로 보존하였다. 이 재검토는 전체 평가 오류율의 무작위 추정이 아니며 같은 입력 판정을 참조하므로 입력 판정과 공유하는 오류를 배제하지 못한다.', '',
        '|차수|실행 기록|형식 통과|내용 판정 가능|타당 / 판정 가능|미평가·미해결|풀이+분석 추정 USD|', '|---|---|---:|---:|---:|---:|---:|', *rows, '',
        *findings,
        '위 의미 판정은 같은 Luna 계열의 분석 결과로서 독립 gold나 사람 최종 검증을 뜻하지 않는다. 원문별 일곱 변형의 의존성을 보존해 대응 비교하며, 형식 실패·잘림·분석 실패·미해결의 분모를 보존한다. 원본 P1 정상 대조군은 이번 범위에 없어 정상 문제에서 P1의 과도한 유보를 일반화할 수 없다. 동일 자료를 보며 고친 차수 간 변화는 탐색적 개발 결과이며 독립 확인으로 사용하지 않는다. 반복 변동은 요청 payload가 실제로 같은 조건만 별도로 보고하며, 변경한 P1의 개선과 구별한다. RQ2의 제작 기준 방식 비교도 이 실험으로 검증되지 않는다.', '',
        '[차수별 조건·판정·반례·비용 기록](../20260927-luna-three-rounds/README.md)', END])
    block = block.replace('P0', 'Unguided Solving').replace('P1', 'Criteria-Guided Solving')
    if BEGIN in text:
        before, rest = text.split(BEGIN, 1)
        _, after = rest.split(END, 1)
        revised = before + block + after
    else:
        marker = '## 8. 실험 결과\n'
        if marker not in text:
            raise ValueError('PAPER_RESULTS_SECTION_NOT_FOUND')
        revised = text.replace(marker, marker + '\n' + block + '\n', 1)
    revised = revised.replace('실험 결과와 결론은 공란입니다.', '8.1절에는 실제 수집된 개발 실험과 잠정 분석을 기록합니다. 최종 확인 실험과 결론은 아직 완성되지 않았습니다.')
    revised = revised.replace('아래는 2026-09-26에 확인한 현행 작업 파일의 내용이며, 최종 실험에 사용한 버전은 해당 실행의 동결 파일·해시와 대조하여 확정한다.',
        '아래 영문은 2026-09-27 1차 개발 실험에 동결한 지시이다. 2·3차의 변경은 8.1절과 각 차수의 동결 파일·해시로 추적하며, 작업 파일의 최신 내용으로 과거 지시를 덮어쓰지 않는다.')
    revised = revised.replace('현행 Criteria-Guided Solving에서 조건부 설명은 단일 답을 유보하면서 제공할 수 있는 설명 방식이다. 별도 분류 라벨을 출력하는 필드는 없으며, 구분은 `answer`와 `explanation`의 내용에 나타난다. 조건부 설명의 기준에 해당하면 유보 이유와 함께 조건별 결과를 제시한다.',
        '입력 분류는 ANSWERABLE / CONFLICT / INSUFFICIENT_EVIDENCE / UNRESOLVED이며 응답 방식은 ANSWER / CONDITIONAL / ABSTAIN이다. 별도 JSON 필드를 추가하지 않고 `explanation`을 `Classification: <CLASS>; Response: <MODE>.`로 시작한다. 따라서 null 여부만으로 분류를 추정하지 않고 실제 선언과 이유를 함께 확인한다. Unguided Solving에는 이 분류 지시를 넣지 않는다.')
    revised = revised.replace('P0에는 이 분류 지시를 넣지 않는다.', 'Unguided Solving에는 이 분류 지시를 넣지 않는다.')
    first = runs()[0][1]
    start, end = '### A.3 Criteria-Guided Solving 조건 지시 원문', '### A.4 두 조건에 공통으로 적용하는 지시 원문'
    if start in revised and end in revised:
        before, rest = revised.split(start, 1)
        _, after = rest.split(end, 1)
        links = ' · '.join(f"[{number}차 분류 기준 지시](../../experiments-run/{root.name}/00-definition/p1-abstention-aware.md)" for number, root, _ in runs())
        revised = before + start + '\n\n입력 분류 기준과 응답 방식을 구분한 1차 지시 원문이다.\n\n' + links + '\n\n```text\n' + (first / '00-definition/p1-abstention-aware.md').read_text().rstrip() + '\n```\n\n' + end + after
    common_start, common_end = '### A.4 두 조건에 공통으로 적용하는 지시 원문', '### A.5 공통 응답 구조'
    if common_start in revised and common_end in revised:
        before, rest = revised.split(common_start, 1)
        _, after = rest.split(common_end, 1)
        revised = before + common_start + '\n\n공통 지시의 필드 설명 순서와 응답 schema의 키 순서는 별개이며, precision은 public 입력의 `answer_format.decimal_places`에서 제공한다. 다음은 1차에 동결한 공통 지시이다.\n\n```text\n' + (first / '00-definition/common.md').read_text().rstrip() + '\n```\n\n' + common_end + after
    if revised != text:
        old_hash = store.file_hash(paper)
        store.write_text(paper, revised)
        store.event(REPORT, 'PAPER_UPDATED', source=str(paper.relative_to(store.PROJECT)), before_sha256=old_hash, after_sha256=store.file_hash(paper), completed_analysis_rounds=len(rows))
    source_file = paper.parent / 'sources.json'
    sources = store.read(source_file, {})
    evidence_files = [{'path': str(p.relative_to(store.PROJECT)), 'sha256': store.file_hash(p)}
        for _, root, _ in runs() for p in [root / 'manifest.json', root / 'summary.json',
            root / '02_analysis/02_comparison/summary.json', root / '02_analysis/02_comparison/rows.jsonl', root / 'events.jsonl'] if p.exists()]
    if sources.get('development_study', {}).get('files') != evidence_files:
        sources['development_study'] = {'campaign': CAMPAIGN, 'updated_at': store.now(), 'status': 'EXPLORATORY_NOT_CONFIRMATORY',
            'files': evidence_files}
        store.write(source_file, sources)
    return True


def tick():
    """Advance completed stages; stop at the scientific-review decision boundary."""
    if any(event.get('event') == 'USER_REVIEW_RESET' for event in store.rows(REPORT / 'events.jsonl')):
        return {'status': 'CODEX_REVIEW_AND_USER_DISCUSSION_REQUIRED', 'api_calls': 0,
                'next': 'Review round-one solver outputs in this Codex conversation. Agree improvements with the user before another experiment.'}
    cohort = runs()
    if not cohort:
        raise ValueError('FIRST_ROUND_NOT_PREPARED')
    number, root, config = cohort[-1]
    first = cohort[0][1]
    pipeline.run(root)
    state = store.read(root / 'state.json')
    if state['status'] != 'FINISHED':
        write_report()
        return {'round': number, 'run': root.name, 'status': state['status']}
    stage = semantic.run_stage(first, semantic.prepare_input(first))
    if stage['status'] != 'COLLECTED':
        write_report()
        return {'round': number, 'status': 'INPUT_REVIEW_PENDING', 'stage': stage}
    recovery = semantic.recover_stage(first, first / semantic.ROOT / '01-LLM-input')
    if recovery['status'] != 'COLLECTED':
        write_report()
        return {'round': number, 'status': 'INPUT_REVIEW_RECOVERY_PENDING', 'stage': recovery}
    for audit in (False, True):
        folder = semantic.prepare_response(root, first, audit=audit)
        stage = semantic.run_stage(root, folder)
        if stage['status'] != 'COLLECTED':
            write_report()
            return {'round': number, 'status': 'AUDIT_PENDING' if audit else 'RESPONSE_REVIEW_PENDING', 'stage': stage}
        recovery = semantic.recover_stage(root, folder)
        if recovery['status'] != 'COLLECTED':
            write_report()
            return {'round': number, 'status': 'REVIEW_RECOVERY_PENDING', 'stage': recovery}
    semantic.build(root, first)
    update_paper()
    write_report()
    return {'round': number, 'run': root.name, 'status': 'CRITICAL_REVIEW_REQUIRED',
            'next': 'Read judgments, audit disagreements and counterexamples. Record specific evidence and changes before preparing the next round.'}


def prepare_next(config_path):
    """Enforce review and paper completion before another 3,000 solver calls."""
    cohort = runs()
    number, previous, _ = cohort[-1]
    if number >= 3:
        raise ValueError('AUTHORIZED_THREE_ROUNDS_ALREADY_PREPARED')
    config = store.read(config_path)['experiments']
    improvement = config.get('improvement', {})
    if improvement.get('campaign') != CAMPAIGN or improvement.get('round') != number + 1 or improvement.get('previous_run') != previous.name:
        raise ValueError('NEXT_ROUND_IDENTITY_MISMATCH')
    if not (previous / '02_analysis/02_comparison/summary.json').exists():
        raise ValueError('PREVIOUS_ANALYSIS_REQUIRED')
    reviews = [e for e in store.rows(previous / 'events.jsonl') if e.get('event') == 'STUDY_CRITICAL_REVIEW']
    if not reviews or not reviews[-1].get('report_ko') or not reviews[-1].get('paper_ko'):
        raise ValueError('PREVIOUS_CRITICAL_REVIEW_REQUIRED')
    if not update_paper():
        raise ValueError('PREVIOUS_PAPER_UPDATE_REQUIRED')
    first = cohort[0][1]
    if (store.PROJECT / config['dataset'].get('reuse_input_run', '')).resolve() != first:
        raise ValueError('FIRST_COHORT_REUSE_REQUIRED')
    if config.get('definition_source_run'):
        raise ValueError('NEXT_ROUND_MUST_FREEZE_REVIEWED_WORKING_PROMPTS')
    frozen = pipeline.run_layout.definition(first)
    controls = [(assets.prompt_path('solver_common'), frozen / 'common.md'),
                (assets.prompt_path('solver_unguided'), pipeline.run_layout.prompt_file(frozen, 'P0'))]
    for current, previous_control in controls:
        if store.file_hash(current) != store.file_hash(previous_control):
            raise ValueError('UNCHANGED_CONTROL_PROMPT_REQUIRED:' + current.name)
    new = pipeline.prepare(config_path)
    for name in ('public.jsonl', 'private.jsonl'):
        if store.file_hash(new / '01-input' / name) != store.file_hash(first / '01-input' / name):
            raise ValueError('COHORT_BYTES_CHANGED:' + name)
    store.event(new, 'PREVIOUS_ROUND_REVIEW_APPLIED', previous_run=previous.name, previous_review_time=reviews[-1]['time'],
        unchanged_controls=[current.name for current, _ in controls], paired_cohort_source=first.name)
    write_report()
    return new


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['tick', 'report', 'paper', 'prepare-next'])
    parser.add_argument('--config', default=str(store.PROJECT / 'config/experiments-luna-improvement.json'))
    args = parser.parse_args()
    if args.action == 'prepare-next':
        with store.locked(REPORT / '.study.lock'):
            print(prepare_next(args.config))
    elif args.action == 'tick':
        REPORT.mkdir(parents=True, exist_ok=True)
        with store.locked(REPORT / '.study.lock'):
            try:
                print(json.dumps(tick()))
            except Exception as error:
                store.event(REPORT, 'STUDY_ADVANCE_FAILED', error_type=type(error).__name__, error=str(error))
                write_report()
                raise
    elif args.action == 'paper':
        print(json.dumps({'paper_updated': update_paper()}))
    else:
        write_report()
        print(REPORT / 'README.md')
