"""Stratify a completed experiment by frozen preparation provenance, without calls."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import islice
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[4]
SOURCE = Path('reports/run/20260917-002/results/00-input.json')
SOURCE_MANIFEST = Path('reports/run/20260917-002/results/manifest.json')
STAGE = Path('02_analysis/source-types')
KINDS = ('FinQA', 'TAT-QA', 'FinanceMath', 'FinanceReasoning')
VARIANTS = ('ORIGINAL', 'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER',
            'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')
CONDITIONS = (('unguided', 'off'), ('unguided', 'on'), ('guided', 'off'), ('guided', 'on'))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path):
    with path.open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def kind_of(provenance: dict) -> str:
    source_id = provenance['source_id']
    if source_id.startswith('CodeFinQA-'):
        return 'FinQA'
    if source_id.startswith('CodeTAT-QA-'):
        return 'TAT-QA'
    if source_id.startswith('FinanceMath-'):
        return 'FinanceMath'
    if source_id.startswith('FinanceReasoning-'):
        return 'FinanceReasoning'
    raise ValueError(f'Unrecognized source_id: {source_id}')


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def ratio(n: int, d: int) -> str:
    return f'{n}/{d} ({n / d * 100:.1f}%)' if d else '0/0'


def condition_name(prompt: str, reasoning: str) -> str:
    return f'{"Unguided Solving" if prompt == "unguided" else "Criteria-Guided Solving"} · Reasoning {reasoning.upper()}'


def metric(rows: list[dict]) -> dict:
    valid = [row for row in rows if row['status'] == 'VALID']
    answer = [row for row in valid if isinstance(row.get('response'), dict)]
    numeric = [row['case'] for row in answer if row['response'].get('answer') is not None]
    null = [row['case'] for row in answer if row['response'].get('answer') is None]
    failed = [row['case'] for row in rows if row['status'] != 'VALID']
    if len(answer) != len(valid) or len(numeric) + len(null) + len(failed) != len(rows):
        raise ValueError('Saved response cannot be assigned to numeric, null, or format failure.')
    return {
        'planned': len(rows), 'status': dict(sorted(Counter(row['status'] for row in rows).items())),
        'valid': len(valid),
        'numeric_answer': len(numeric), 'numeric_case_ids': sorted(numeric),
        'null_answer': len(null), 'null_case_ids': sorted(null),
        'format_failed_case_ids': sorted(failed),
        'classification': dict(sorted(Counter(str(row['response'].get('classification')) for row in answer).items())),
        'original_result': dict(sorted(Counter(row['original_result'] for row in rows if row['variant'] == 'ORIGINAL').items())),
    }


def render_review(name: str, result: dict, observations: list[dict], linked: dict) -> str:
    count = result['case_count']
    lines = [f'# exp-001-luna-{name} · 원천 유형별 검토', '',
             f'원본 {count}문항, 저장 응답 {result["response_count"]}건을 같은 완료 run에서 재집계했습니다. '
             '별도 실험·새 모델 호출·의미 정답 재판정이 아닙니다.', '',
             f'원천 ID 접두사 `{result["source_id_prefix"]}`를 사용했습니다. '
             f'상위 데이터셋 표기는 `{", ".join(result["dataset_labels"])}`입니다. '
             '이 이름은 FinanceReasoning 선별 집합 안의 원천 계보이며 독립 벤치마크 점수가 아닙니다.', '',
             '## 문항 구성과 검사', '',
             f'- 난도: {", ".join(f"{k} {v}" for k, v in result["levels"].items())}',
             f'- 원본 제작의 외부지식 사용 표기: 사용 {result["original_external_knowledge"]["true"]}건, '
             f'미사용 {result["original_external_knowledge"]["false"]}건. 이는 제작 과정의 private 기록이며 모델 답변의 지식 사용 여부가 아닙니다.',
             f'- 응답 형식 상태: {", ".join(f"{k} {v}" for k, v in result["response_status"].items())}. '
             '형식 유효는 의미 정답을 뜻하지 않습니다.', '',
             '## SQ1 · 원본 기록 숫자 일치', '',
             '|풀이 지시|추론 설정|MATCH|MISMATCH|미평가|', '|---|---|---:|---:|---:|']
    for prompt, reasoning in CONDITIONS:
        m = result['conditions']['ORIGINAL'][f'{prompt}/{reasoning}']['original_result']
        lines.append(f'|{"Unguided Solving" if prompt == "unguided" else "Criteria-Guided Solving"}|Reasoning {reasoning.upper()}|{m.get("MATCH", 0)}|{m.get("MISMATCH", 0)}|{m.get("UNEVALUATED", 0)}|')
    lines += ['', 'MATCH는 저장된 참조 숫자와의 일치입니다. 설명의 타당성·문항 의미 정답의 판정은 아닙니다.', '',
              '## RQ1 · 변형별 수치 응답과 유보', '',
              '각 칸의 분모는 해당 유형의 원본 문항 수입니다. `숫자 / null / 형식 미통과` 순서입니다.', '',
              '|변형|Unguided Solving · Reasoning ON|Criteria-Guided Solving · Reasoning ON|', '|---|---:|---:|']
    for variant in VARIANTS[1:]:
        cells = []
        for prompt in ('unguided', 'guided'):
            m = result['conditions'][variant][f'{prompt}/on']
            cells.append(f'{m["numeric_answer"]} / {m["null_answer"]} / {count-m["valid"]}')
        lines.append(f'|{variant}|{cells[0]}|{cells[1]}|')
    lines += ['', '## RQ2 · 지시와 추론 설정', '',
              '위 표는 동일 문항·변형의 풀이 지시 차이를 보여 줍니다. 아래 표는 원본의 OFF/ON도 포함합니다. '
              '네 설정은 독립 반복이 아니므로 설정 변경의 인과효과로 읽지 않습니다.', '',
              '|설정|원본 수치 응답|원본 null|원본 형식 미통과|', '|---|---:|---:|---:|']
    for prompt, reasoning in CONDITIONS:
        m = result['conditions']['ORIGINAL'][f'{prompt}/{reasoning}']
        lines.append(f'|{condition_name(prompt, reasoning)}|{m["numeric_answer"]}|{m["null_answer"]}|{count-m["valid"]}|')
    lines += ['', '### 모든 변형·설정의 응답 상태', '',
              '각 칸은 `숫자 / null / 형식 미통과`이며 분모는 매번 이 유형의 원본 문항 수입니다.', '',
              '|변형|Unguided · OFF|Unguided · ON|Criteria-Guided · OFF|Criteria-Guided · ON|',
              '|---|---:|---:|---:|---:|']
    for variant in VARIANTS:
        cells = []
        for prompt, reasoning in CONDITIONS:
            m = result['conditions'][variant][f'{prompt}/{reasoning}']
            cells.append(f'{m["numeric_answer"]} / {m["null_answer"]} / {count-m["valid"]}')
        lines.append('|'+ '|'.join([variant, *cells]) + '|')
    lines += ['', '## 문항별 관찰과 전체 A03의 연결', '',
              f'A02 저장 관찰 {len(observations)}개가 이 유형의 문항에 속합니다. 분류별 수는 '
              + ', '.join(f'{k} {v}' for k, v in result['a02_categories'].items()) + '입니다.',
              '기존 A03 주제의 연결 관찰 ID가 이 유형에 속하는 횟수는 다음과 같습니다. '
              '한 관찰이 여러 주제에 연결될 수 있고, 그룹의 전체 주장 자체를 이 유형에 대해 다시 검증한 수는 아닙니다.', '',
              '|RQ/SQ|전체 A03 주제|이 유형에 속한 연결 관찰 ID|', '|---|---|---:|']
    for group, info in linked.items():
        lines.append(f'|{info["question_id"]}|{group} · {info["title_ko"]}|{info["observation_count"]}|')
    lines += ['', '### A02 관찰 원문 예시', '',
              '각 분류에서 저장 순서의 첫 2개를 찾기 위한 예시로 제시합니다. 대표 표본이나 해당 유형의 전체 결론이 아닙니다.', '']
    categories = sorted({item['category'] for item in observations})
    for category in categories:
        lines += [f'#### {category}', '']
        for item in islice((item for item in observations if item['category'] == category), 2):
            ko = item.get('display') or item.get('display_ko') or {}
            lines += [f'- **{item["id"]} · {ko.get("title", item["title"])}**: '
                      f'{ko.get("observation", item["observation"])} '
                      f'한계: {ko.get("limitation", item["limitation"])}']
        lines.append('')
    lines += ['', '## 해석 범위', '',
              '- 유형별 문항 수·난도·제작 당시 외부지식 사용 표기가 서로 달라 유형 간 비율 차이는 인과 비교가 아닙니다.',
              '- 원본과 각 변형은 같은 원본 문항에서 출발했습니다. 응답 32개를 독립 문항 32개처럼 세지 않습니다.',
              '- 숫자 반환, null, 분류 표기, 인용된 설명은 별개의 관찰입니다. 후보 숫자 일치를 충돌 인식·근거 선택의 정답률로 바꾸지 않습니다.',
              '- SQ2·SQ4·SQ5·SQ6에 관한 직접 결론은 이번 유형별 재집계에서 새로 만들지 않았습니다.', '',
              '## 근거 읽기', '',
              '1. [README](README.md)에서 파일과 범위를 확인합니다.',
              '2. [summary.json](summary.json)의 모든 변형·네 설정별 분모와 형식 상태를 확인합니다.',
              '3. [cases.jsonl](cases.jsonl)에서 원천 ID·난도·문항별 A02 관찰 ID를 확인하고, '
              '[A02 원문](../../02_comparison/interpretations.jsonl)과 실험 뷰어의 같은 문항 응답으로 돌아갑니다.',
              '4. [전체 A03 주제 색인](../../03_research/rq-review.md)의 주장·반례·한계는 별도로 읽습니다.', '']
    return '\n'.join(lines)


def build(run: str) -> dict:
    if run != '20260928-exp-001-luna':
        raise ValueError('This review is bound to the frozen 20260928-exp-001-luna run.')
    root = PROJECT / 'reports/experiments-run' / run
    state = json.loads((root / 'state.json').read_text())
    if state['analysis']['status'] != 'COMPLETE' or state['full_pipeline']['status'] != 'COMPLETE':
        raise ValueError('Evaluation and analysis must be complete before this saved-result review.')
    source_path = PROJECT / SOURCE
    manifest = json.loads((PROJECT / SOURCE_MANIFEST).read_text())
    if digest(source_path) != manifest['files'][SOURCE.name]['sha256']:
        raise ValueError('Frozen source hash differs from its preparation manifest.')
    source = {row['id']: row['input']['provenance'] for row in json.loads(source_path.read_text())}
    private = list(jsonl(root / '00_input/private.jsonl'))
    originals = {row['case']: row for row in private if row['variant'] == 'ORIGINAL'}
    if len(originals) != 1080 or len(private) != 8640:
        raise ValueError('Frozen selection has unexpected size or duplicate originals.')
    if {Path(row['source']).resolve() for row in originals.values()} != {(PROJECT / SOURCE_MANIFEST).resolve()}:
        raise ValueError('Original private input points to another preparation manifest.')
    private_matrix = [(row['case'], row['variant']) for row in private]
    if len(set(private_matrix)) != len(private_matrix) or set(private_matrix) != {(case, variant) for case in originals for variant in VARIANTS}:
        raise ValueError('Frozen private input matrix is incomplete, duplicated, or unexpected.')
    cases = {}
    for case, row in originals.items():
        provenance = source.get(case)
        if not provenance:
            raise ValueError(f'Missing source provenance: {case}')
        cases[case] = {'case': case, 'source_type': kind_of(provenance),
                       'source_id': provenance['source_id'], 'dataset': provenance['dataset'],
                       'level': provenance['level'], 'original_external_knowledge': row['original_external_knowledge']}
    responses = list(jsonl(root / '02_analysis/01_results/responses.jsonl'))
    expected = {(case, variant, prompt, reasoning) for case in cases for variant in VARIANTS for prompt, reasoning in CONDITIONS}
    actual = [(row['case'], row['variant'], row['prompt_condition'], row['reasoning']) for row in responses]
    if len(actual) != 34560 or len(set(actual)) != len(actual) or set(actual) != expected:
        raise ValueError('Saved response matrix is incomplete, duplicated, or unexpected.')
    observations = list(jsonl(root / '02_analysis/02_comparison/interpretations.jsonl'))
    by_case = defaultdict(list)
    for item in observations:
        case = item['id'].rsplit('-O', 1)[0]
        if case not in cases:
            raise ValueError(f'A02 observation has no selected case: {item["id"]}')
        by_case[case].append(item)
    review = json.loads((root / '02_analysis/03_research/rq-review.json').read_text())
    out = root / STAGE
    out.mkdir(parents=True, exist_ok=True)
    index = {'schema_version': 1, 'run': run, 'method': 'saved-response-provenance-stratification',
             'new_external_model_calls': 0, 'source_hashes': {
                 str(SOURCE): digest(source_path), str(SOURCE_MANIFEST): digest(PROJECT / SOURCE_MANIFEST),
                 '00_input/private.jsonl': digest(root / '00_input/private.jsonl'),
                 '02_analysis/01_results/responses.jsonl': digest(root / '02_analysis/01_results/responses.jsonl'),
                 '02_analysis/02_comparison/interpretations.jsonl': digest(root / '02_analysis/02_comparison/interpretations.jsonl'),
                 '02_analysis/03_research/rq-review.json': digest(root / '02_analysis/03_research/rq-review.json')},
             'types': []}
    summaries = {}
    for name in KINDS:
        selected = sorted((case for case, info in cases.items() if info['source_type'] == name))
        rows = [row for row in responses if row['case'] in set(selected)]
        obs = [item for case in selected for item in by_case[case]]
        obs_ids = {item['id'] for item in obs}
        linked = {group['id']: {'question_id': group['question_id'], 'title_ko': group['title_ko'],
                                'observation_count': len(set(group['interpretation_ids']) & obs_ids)} for group in review['groups']}
        conditions = {variant: {f'{prompt}/{reasoning}': metric([row for row in rows if row['variant'] == variant and row['prompt_condition'] == prompt and row['reasoning'] == reasoning]) for prompt, reasoning in CONDITIONS} for variant in VARIANTS}
        result = {'source_type': name, 'case_count': len(selected), 'response_count': len(rows),
                  'case_ids': selected,
                  'source_id_prefix': {'FinQA': 'CodeFinQA-', 'TAT-QA': 'CodeTAT-QA-', 'FinanceMath': 'FinanceMath-', 'FinanceReasoning': 'FinanceReasoning-'}[name],
                  'dataset_labels': sorted({cases[case]['dataset'] for case in selected}),
                  'levels': dict(sorted(Counter(cases[case]['level'] for case in selected).items())),
                  'original_external_knowledge': {'true': sum(cases[case]['original_external_knowledge']['used'] is True for case in selected),
                                                  'false': sum(cases[case]['original_external_knowledge']['used'] is False for case in selected)},
                  'response_status': dict(sorted(Counter(row['status'] for row in rows).items())),
                  'a02_observation_count': len(obs), 'a02_categories': dict(sorted(Counter(item['category'] for item in obs).items())),
                  'a02_examples': {category: [
                      {'id': item['id'], 'title_ko': (item.get('display') or item['display_ko'])['title'],
                       'observation_ko': (item.get('display') or item['display_ko'])['observation'],
                       'limitation_ko': (item.get('display') or item['display_ko'])['limitation']}
                      for item in islice((item for item in obs if item['category'] == category), 2)]
                      for category in sorted({item['category'] for item in obs})},
                  'linked_a03_observations_by_group': linked, 'conditions': conditions}
        summaries[name] = result
        folder = out / f'exp-001-luna-{name}'
        folder.mkdir(exist_ok=True)
        save(folder / 'summary.json', result)
        (folder / 'cases.jsonl').write_text(''.join(json.dumps({**cases[case], 'a02_observation_ids': [item['id'] for item in by_case[case]]}, ensure_ascii=False) + '\n' for case in selected))
        (folder / 'review.md').write_text(render_review(name, result, obs, linked))
        readme = PROJECT / 'src/finarch/experiments/templates/source-type-review-readme.md'
        (folder / 'README.md').write_text(readme.read_text().format(run=run, name=name, count=len(selected)))
        index['types'].append({'source_type': name, 'case_count': len(selected), 'response_count': len(rows),
                               'observation_count': len(obs), 'folder': str(STAGE / folder.name),
                               'review_path': str(STAGE / folder.name / 'review.md')})
    if sum(item['case_count'] for item in index['types']) != 1080 or sum(item['response_count'] for item in index['types']) != 34560 or sum(item['observation_count'] for item in index['types']) != len(observations):
        raise ValueError('Source partitions do not cover all cases, responses, and observations.')
    save(out / 'source-type-index.json', index)
    overview = ['# exp-001-luna · 원천 유형 간 관찰 대조', '',
                '아래는 완료된 동일 run을 원천 계보로 나눈 기술 통계입니다. 유형 간 사례 구성·난도·원본 제작의 외부지식 사용 표기가 다릅니다. '
                '따라서 비율 차이는 모델 성능 우열이나 유형의 인과효과가 아닙니다.', '',
                '## 원본 문항과 숫자 일치', '',
                '|원천 유형|원본 문항|Criteria-Guided Solving · Reasoning ON 원본 MATCH|Unguided Solving · Reasoning ON 원본 MATCH|형식 미통과 응답|',
                '|---|---:|---:|---:|---:|']
    for name in KINDS:
        item = summaries[name]
        original = item['conditions']['ORIGINAL']
        bad = item['response_count'] - item['response_status'].get('VALID', 0)
        overview.append(f'|[{name}](exp-001-luna-{name}/review.md)|{item["case_count"]}|'
                        f'{ratio(original["guided/on"]["original_result"].get("MATCH", 0), item["case_count"])}|'
                        f'{ratio(original["unguided/on"]["original_result"].get("MATCH", 0), item["case_count"])}|{bad}|')
    overview += ['', '## 변형별 Criteria-Guided Solving · Reasoning ON 숫자 반환', '',
                 '분모는 각 유형의 원본 문항 수입니다. 숫자 반환은 후보 숫자 일치나 의미상 정답과 다릅니다.', '',
                 '|원천 유형|BEFORE|AFTER|SOURCE_A|SOURCE_B|RELATION|EA_01|EA_02|',
                 '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name in KINDS:
        item = summaries[name]
        cells = [ratio(item['conditions'][variant]['guided/on']['numeric_answer'], item['case_count']) for variant in VARIANTS[1:]]
        overview.append('|'+ '|'.join([name, *cells]) + '|')
    overview += ['', '## 읽을 때 주의할 점', '',
                 '- FinanceReasoning native 계보와 FinQA·TAT-QA embedded 계보는 원천 형식과 문항 구성이 다릅니다.',
                 '- EA는 원본에서 서로 독립적으로 사실 하나씩 삭제한 변형입니다. 남은 정보로 계산 가능한지 개별 문항을 확인해야 합니다.',
                 '- Guided 조건의 null 증가는 모델의 표시 행동입니다. 충돌 식별 정답률이나 지식 사용 여부가 아닙니다.',
                 '- 유형별 A02 사례와 한계는 각 보고서에서, 전체 A03 주제와 RQ/SQ 연결은 기존 연구 해석에서 읽습니다.', '']
    (out / 'overview.md').write_text('\n'.join(overview))
    template = PROJECT / 'src/finarch/experiments/templates/source-type-index-readme.md'
    (out / 'README.md').write_text(template.read_text().format(run=run))
    (out / 'build.log').write_text(json.dumps({'status': 'COMPLETE', 'case_count': 1080, 'response_count': 34560,
                                               'observation_count': len(observations), 'types': len(KINDS),
                                               'new_external_model_calls': 0}, ensure_ascii=False, indent=2) + '\n')
    return index


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    print(json.dumps(build(parser.parse_args().run)['types'], ensure_ascii=False))
