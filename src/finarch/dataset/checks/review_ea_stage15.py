variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""EA15: audit saved deletion plans; inverse/semantic certification stays deferred."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
from importlib import import_module
import io
import json
from pathlib import Path
import unittest

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
build = __import__('finarch.dataset.02-generation.01-perturbation.ea_plan', fromlist=['build']).build
from finarch.dataset.shared.calculation.python_graph import load_graph
compose_ea = __import__('finarch.dataset.02-generation.02-generate-text.text_preview', fromlist=['compose_ea']).compose_ea


NUMBER = import_module('finarch.dataset.00-input.content').NUMBER
SCOPE = '첫 문항의 관측 입력 삭제·보존·오류 구분; 역산 및 최종 문장 의미 검사는 제외'
DEFERRED = ['T097의 단위 환산·관계 기반 복원 조사', 'T098 복원 경로 삭제 집합',
            'T100 답 유일성·상쇄·우회', 'T101 서로 다른 답의 보완 사례', 'T104의 역산·우회']
FOLLOW_UP = ['16·17: 실제 LLM 문장 생성·응답 스키마·최종 본문 및 의미 검사',
             '24: public/private 동결·분리 검사']


def occurrences(text, value):
    """Decimal digit notation only; no unit conversion or inferred relationships."""
    target = Decimal(str(value).replace(',', ''))
    return [{'span': [m.start(), m.end()], 'text': m.group()} for m in NUMBER.finditer(text)
            if not m.group().endswith('%') and Decimal(m.group().replace(',', '')) == target]


def inspect(sample, program, plan, binding, graph, preview, original):
    key = plan['fact_id']; fact = program['facts'][key]
    replay, inputs, _ = build({**program, 'context': sample['context']}, key)
    draft = compose_ea(sample, plan, program)
    contexts = {'original': sample['context'], 'question': sample['question'],
                'draft': preview['preview_context']}
    target_matches = {k: occurrences(v, fact['value']) for k, v in contexts.items()}
    gold_matches = {k: occurrences(v, sample['reference_answer']) for k, v in contexts.items()}
    first_reads = list(dict.fromkeys(n['fact_id'] for n in original['nodes'] if n['kind'] == 'fact'))
    structure = lambda g: [(n['id'], n['kind'], n['inputs'], n.get('code_line')) for n in g['nodes']]
    checks = {
        'observed_input_selected': key in first_reads,
        'source_span_matches': fact['span'] == plan['deletion']['span'] and
            sample['context'][slice(*fact['span'])] == fact['text'] == plan['deletion']['before'],
        'one_direct_target_occurrence': [m['span'] for m in target_matches['original']] == [fact['span']],
        'no_target_in_draft_or_question': not target_matches['draft'] and not target_matches['question'],
        'no_direct_gold_in_context_or_question': not any(gold_matches.values()),
        'graph_replay_matches': replay == graph == plan['graphs']['EA'],
        'same_nodes_and_edges': structure(graph) == structure(original) and graph['edges'] == original['edges'],
        'same_code_and_remaining_inputs': inputs == binding and binding['code'] == program['code'],
        'only_selected_fact_missing': binding['missing_facts'] == [key] and
            set(binding['facts']) == set(program['facts']) - {key},
        'preview_replay_matches': all(draft[k] == preview[k] for k in
            ('original_context', 'preview_context', 'question', 'intermediate', 'rewritten_sentence',
             'preserved_evidence', 'python', 'graph_binding', 'calculation_result')) and
            [{k: p[k] for k in ('start', 'end', 'before', 'text', 'element_ids')} for p in draft['patches']] ==
            [{k: p[k] for k in ('start', 'end', 'before', 'text', 'element_ids')} for p in preview['patches']],
        'same_question_and_code': preview['question'] == sample['question'] and preview['python']['code'] == program['code'],
        'remaining_amounts_preserved': all(preview['preview_context'][slice(*v['span'])] == v['text']
            for v in preview['preserved_evidence'].values()) and
            set(preview['preserved_evidence']) == set(program['facts']) - {key},
        'tag_only_in_private_intermediate': preview['intermediate']['context'].count(preview['intermediate']['tag']) == 1
            and '[EA_DELETE:' not in preview['preview_context'],
        'no_numeric_ea_answer': plan['result'] == preview['calculation_result'] == {'answer': None, 'missing_facts': [key]},
        'no_stale_missing_or_blocked_values': all(not any(k in n for k in ('value', 'computed'))
            for n in graph['nodes'] if n['evaluation']['state'] != 'KNOWN'),
        'semantic_and_recovery_not_claimed': plan['semantic_status'] == preview['semantic_status'] == 'NOT_EVALUATED'
            and plan['recovery_review'] == 'SKIPPED_BY_USER' and preview['final_text_status'] == 'NOT_RUN',
    }
    return {'checks': checks, 'direct_occurrences': {'target': target_matches, 'original_gold': gold_matches},
            'selection': {'kind': 'observed_input', 'fact_id': key, 'original_value': fact['value'],
                          'input_order': first_reads.index(key) + 1, 'input_order_base': 1,
                          'order_basis': 'first fact read in Python code', 'target_span': fact['span']},
            'node_states': dict(Counter(n['evaluation']['state'] for n in graph['nodes']))}


def review(case_dir, labels):
    # [EA15.1] Reuse eligibility and graph checks; excluded gold cases cannot pass.
    case = Path(case_dir).resolve()
    for label in labels:
        if Path(label).name != label or label in ('.', '..'):
            raise ValueError('INVALID_LABEL')
        if (case / '04-perturbation/variants' / label / 'stage15-review.json').exists():
            raise ValueError('REVIEW_ALREADY_EXISTS')
    ctx = RunContext.resume(case, {}, case.name)
    with ctx.trace.activate(), ctx.trace.span('review_ea_stage15', stage='03-graph', step='EA15', role='python') as outcome:
        original = load_graph(case)
        read = lambda p: json.loads((case / p).read_text())
        sample = read('00-data-preparation/01-select-input/01-input.json'); program = read('02-calculation/02-prepare-code/03-program.json')
        stream = io.StringIO()
        suite = unittest.defaultTestLoader.loadTestsFromNames([
            'finarch.dataset.checks.test_ea_plan', 'finarch.dataset.checks.test_ea_stage15'])
        tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        results = []
        for label in labels:
            base = variant_root(label)
            plan = read(base + '/plan.json')
            report = inspect(sample, program, plan, read(base + '/calculation-input.json'),
                             read(base + '/graph.json'), read(base + '/05-text-input-preview.json'), original)
            hashes = {p: hashlib.sha256((case / p).read_bytes()).hexdigest()
                      for p in plan['preserved_inputs_sha256']}
            report['checks'].update(original_files_preserved=hashes == plan['preserved_inputs_sha256'],
                                    error_and_residue_regressions_passed=tests.wasSuccessful())
            status = 'PASS' if all(report['checks'].values()) else 'FAIL'
            report.update(status=status, scope=SCOPE, case_id=case.name, variant=label,
                          checklist_status='COMPLETE_CURRENT_SCOPE' if status == 'PASS' else 'NOT_COMPLETE',
                          completed_items=['T096', 'T097 직접 기재', 'T099', 'T102 기술 오류', 'T103 원본 보관', 'T104 직접 잔존']
                              if status == 'PASS' else [], deferred=DEFERRED, follow_up=FOLLOW_UP,
                          scan_scope='숫자로 직접 적힌 동일 값과 쉼표 표기만 검사; 문자 수사·단위 환산·관계 추론 미검사',
                          preserved_inputs_sha256=hashes, tests={'run': tests.testsRun, 'passed': tests.wasSuccessful()},
                          semantic_status='NOT_EVALUATED', model_calls=0)
            # [EA15.2] Append a new audit and generated guide; never rewrite original evidence.
            ctx.save(base + '/04-deletion-check.json', report)
            ctx.save_text(base + '/STAGE15-TESTS.txt', stream.getvalue())
            rows = '\n'.join(f'| {name} | {"PASS" if passed else "FAIL"} |' for name, passed in report['checks'].items())
            ctx.save_text(base + '/STAGE15-README.md', f'''# 15번 EA · 이번 범위 검사

판정: **{status}**. {SCOPE}입니다. 대상: {key_label(report)}.

읽는 순서: stage15-review.json → STAGE15-TESTS.txt → plan.json → calculation-input.json → graph.json → text-preview-v2.json.
stage15-review.json은 직접 숫자 기재 위치, 원본 해시, 삭제 입력 순서, 그래프 재생성과 보존 검사를 저장합니다.
STAGE15-TESTS.txt는 이번에 실행한 {tests.testsRun}개 로컬 검사의 원출력입니다. 원본·기존 checklist-review.json은 과거 기록으로 보존합니다.

| 검사 | 결과 |
|---|---|
{rows}

완료는 첫 문항의 지정 입력 삭제·보존·기술 오류 검사 범위입니다. 순서는 원문 입력을 Python 코드에서 처음 읽는 순서이며 파생 중간값의 삭제가 아닙니다.
숫자로 직접 적힌 동일 값만 조사합니다. 문자 수사·단위 환산·관계 추론으로 복원되지 않는다는 증명은 아닙니다.
보류: {' / '.join(DEFERRED)}.
후속: {' / '.join(FOLLOW_UP)}.
EA 숫자 답은 null, 의미 판정은 NOT_EVALUATED를 유지합니다. 추가 LLM 호출은 0회입니다.

공통 viewer에서 이 실행 → {case.name} → EA의 해당 삭제 입력 → 4 그래프 변경을 선택하면 이번 검사 요약과 상세 기록을 확인합니다. 5 문장과 답변에서 삭제 태그와 수정 문장을 확인하고, 8 전체 기록에서 원파일을 읽습니다.
이 README는 검사 함수의 템플릿에서 생성합니다. events.jsonl의 EA15에는 시작·산출물·종료가 남습니다. 자동 재시도는 없으며 실패면 원인을 고친 뒤 별도 기록으로 재검사합니다.
''')
            results.append(report)
        failed = [r['variant'] for r in results if r['status'] != 'PASS']
        outcome.update(status='FAIL' if failed else 'PASS', reason='EA15_CURRENT_SCOPE_AUDIT', failed=failed)
        if failed:
            raise ValueError('EA15_CHECK_FAILED:' + ','.join(failed))
        return [{'variant': r['variant'], 'status': r['status'], 'checks': len(r['checks']), 'tests': r['tests']} for r in results]


def key_label(report):
    item = report['selection']
    return f"{item['fact_id']} ({item['original_value']}, 입력 순서 {item['input_order']})"


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case_dir'); parser.add_argument('labels', nargs='+')
    args = parser.parse_args()
    print(json.dumps(review(args.case_dir, args.labels), ensure_ascii=False))
