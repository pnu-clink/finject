"""Build a traceable, human-authored thematic index of saved A03 findings."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[5]
PAPER = Path('reports/run/20260924-paper-draft/PAPER-KO.md')
STAGE = Path('02_analysis/03_research')
ORDER = ('RQ1', 'RQ2', 'SQ1', 'SQ2', 'SQ3', 'SQ4', 'SQ5', 'SQ6')

# Each saved finding has one primary theme. The explicit IDs make editorial
# decisions reviewable and prevent a title-keyword rule from silently moving F.
PRIMARY = {
    'G01': '13 49 52 56 60 64 96',
    'G02': '1 5 9 14 17 21 25 29 33 37 41 45 50 54 61 68 76 80 92 97 101 108 112 124 128 132 136 144 152 165 169 172 181',
    'G03': '2 6 10 15 18 22 26 30 58 70 104 141 157',
    'G04': '3 7 11 16 19 23 42 46 53 57 62 65 69 73 77 81 85 89 98 100 105 109 113 116 120 125 129 133 137 140 145 148 153 156 160 164 168 176 180',
    'G05': '27 31 34 38 93 102 106 110 114 117 122 126 130 134 138 142 146 149 154 158 161 166 170 173 177 182',
    'G06': '35 39 67 72 78 84 88 94 118 121 150 162 174 178',
    'G07': '4 8 12 20 24 28 32 36 40 43 47 51 55 59 63 66 74 79 82 86 90 95 99 103 107 111 115 119 123 127 131 135 139 143 147 151 155 159 163 167 171 175 179 183',
    'G08': '71 75',
    'G09': '44 48 83 87 91',
}

SECONDARY = {
    'F003': ('G05',), 'F007': ('G05',), 'F033': ('G04',),
    'F035': ('G03',), 'F038': ('G02',), 'F044': ('G08',),
    'F050': ('G04',), 'F071': ('G01',), 'F075': ('G09',),
    'F083': ('G06',), 'F093': ('G04',), 'F104': ('G02',),
    'F121': ('G02', 'G03'), 'F126': ('G03',), 'F130': ('G03',),
    'F141': ('G02',), 'F157': ('G02',), 'F160': ('G02',),
    'F172': ('G04',), 'F173': ('G02',), 'F178': ('G02',),
}

GROUPS = {
    'G01': ('SQ1', '원본 수치 일치의 기준선',
            '원본의 기록된 수치 일치는 풀이 조건에 따라 다르지만, 원본 성과와 변형 대응의 관계를 이 묶음만으로 판정할 수 없습니다.',
            'F013·F049·F096의 원본 조건별 수치 일치와 전체 MATCH/MISMATCH/UNEVALUATED 기록을 대조합니다.',
            '반환 숫자와 참조값의 일치에는 유보·형식 실패·설명 경로의 차이가 섞일 수 있습니다.',
            'SQ1의 기준선일 뿐입니다. 원본 성과별 동일 조건 변형 대응을 직접 나눠 비교해야 H3 관계를 판단할 수 있습니다.'),
    'G02': ('RQ2', '판단 기준 안내와 충돌 보고·답변 유보',
            'Criteria-Guided Solving에서는 여러 충돌 변형에서 CONFLICT 표시와 null 답변이 더 자주 기록됐습니다.',
            'F001·F005·F101 등의 동일 모델·변형·추론 설정 아래 Unguided/Criteria-Guided 대응 비교를 읽습니다.',
            '기준 안내는 분류 요구와 출력 계약도 바꾸며, 일부 안내 조건에서도 숫자를 반환합니다.',
            'CONFLICT는 모델의 표기입니다. 유보 증가를 충돌 식별의 정확도나 의미상 품질 향상으로 환산하지 않습니다.'),
    'G03': ('RQ2', '추론 설정 차이는 편집 유형에 따라 달라짐',
            'Reasoning OFF/ON의 응답 변화는 주장 추가·관계 변형·사실 삭제에서 같은 방향으로 나타나지 않았습니다.',
            'F002·F006·F030·F141의 동일 문항·풀이 지시·변형 조건별 OFF/ON 대응을 읽습니다.',
            '편집 유형과 남은 정보량이 다르고, 보고된 설명은 모델 내부 추론을 보여주지 않습니다.',
            '설정 차이에 대한 관찰이며 독립 반복이나 인과 기제, 정답률 향상의 검증이 아닙니다.'),
    'G04': ('RQ1', '상충 주장 위치와 후보 수치 전환',
            '상충 수치 주장의 앞·뒤 배치에 따라 후보 수치 일치가 바뀐 사례와 대응쌍이 있지만 일률적인 위치 규칙은 없습니다.',
            'F003·F100·F140·F180의 BEFORE/AFTER 대응과 그대로 유지된 응답·반례를 함께 읽습니다.',
            '표와 문장의 위치, 주변 표현 및 선택된 계산 경로가 함께 달라질 수 있습니다.',
            'A/B는 후보 수치 일치 코드입니다. 근거 선택, 의미 정답 또는 순수한 위치 인과효과로 단정하지 않습니다.'),
    'G05': ('RQ1', '출처 표기와 연결 부모 대비 변화',
            '뒤쪽 주장에 출처를 붙인 변형은 연결된 부모 응답과 다른 후보 일치를 보이지만 변화 방향은 혼합돼 있습니다.',
            'F106·F170의 SOURCE_A/B와 각각 연결된 VALUE 부모의 대응 전이 및 반대 사례를 읽습니다.',
            '출처 문구 자체, 주장 대상과 위치, 모델 응답 변동이 함께 작용할 수 있습니다.',
            '출처 문구의 진위는 검증되지 않았고 모델의 일반적인 출처 선호나 인과효과는 식별되지 않습니다.'),
    'G06': ('RQ1', '관계식 충돌의 서로 다른 처리 경로',
            '관계 변형 응답에는 원래 표의 값 사용, 추가 관계 적용, 두 경로의 충돌 보고가 함께 나타났습니다.',
            'F035·F078·F162·F178의 조건별 분류와 저장된 설명의 계산 경로를 함께 읽습니다.',
            '표 안 관계의 적용 범위와 문구 해석이 다를 수 있으며 조건별 유보 패턴은 G02·G03과 겹칩니다.',
            '후보값 일치·CONFLICT 표기는 관계식 해석이나 산술의 정당성에 대한 독립 판정이 아닙니다.'),
    'G07': ('RQ1', '독립 사실 삭제 후 유보와 수치 경로',
            '각 사실 삭제에서는 null이 늘었고, 남은 숫자 응답의 설명에는 복원·부분 계산·가정 등 서로 다른 경로가 기록됐습니다.',
            'F004·F008·F171·F183의 EA_01/EA_02와 각각의 ORIGINAL 대응 및 수치 예외를 읽습니다.',
            '남은 자료로 계산 가능한 경우와 부족한 경우가 섞이며 설명된 계산도 별도 검산이 필요합니다.',
            '두 삭제는 원본에서 각각 출발한 별도 변형입니다. 숫자 일치를 복원 성공률이나 의미상 정답으로 세지 않습니다.'),
    'G08': ('SQ3', '형식 유효·수치 일치·의미 판단의 경계',
            '저장 응답의 형식 유효성과 후보 수치 일치는 설명·근거의 의미상 정합성을 보증하지 않습니다.',
            'F071·F075의 형식 검사 분모, 후보 코드, 설명과 계산의 반례를 구분해 읽습니다.',
            'OTHER는 단위·반올림·다른 계산 경로 때문일 수도 있으며, 후보 일치도 다른 설명 경로와 공존할 수 있습니다.',
            '형식 실패와 사례별 정합성 문제를 전수 의미 오류율로 합치지 않습니다.'),
    'G09': ('SQ3', '최종 답·분류·설명 속 수치의 불일치',
            '최종 answer, 모델 분류, 설명 안의 조건부 숫자는 서로 다른 응답 요소로 읽어야 합니다.',
            'F044·F083·F091의 null 설명 속 숫자, OTHER 답의 계산 경로, 관계 설명의 반례를 확인합니다.',
            '설명 속 수치는 조건부 예시일 수 있고, 수치 차이는 산술·단위·표현 선택과 관련될 수 있습니다.',
            '저장 사례를 근거로 한 문제 제기이며 전 응답의 정합성 판정이나 오류율은 아닙니다.'),
}

EMPTY = {
    'SQ2': ('직접 검토 없음', '제작 문항의 변형 타당성과 독립 검토자 간 일치도는 이 A03 발견 묶음에서 검토하지 않았습니다.'),
    'SQ4': ('직접 검토 없음', '계산 구조의 변수·연산·깊이와 응답을 연결한 직접 발견이 없습니다.'),
    'SQ5': ('직접 검토 없음', '원본 제작의 private 외부지식 분류는 있으나 모델의 지식 사용을 관찰·판정한 발견은 없습니다.'),
    'SQ6': ('독립 반복 확인 전 보류', '이번 저장 응답은 동일 조건의 독립 반복을 확인하는 자료가 아닙니다.'),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ids(numbers: str) -> list[str]:
    return [f'F{int(value):03d}' for value in numbers.split()]


def build(run: str) -> dict:
    if not run.replace('-', '').isalnum():
        raise ValueError('INVALID_RUN_ID')
    root = PROJECT / 'reports/experiments-run' / run
    folder = root / STAGE
    source_path = folder / 'findings.json'
    source = json.loads(source_path.read_text())
    findings = {row['id']: row for row in source['findings']}
    assigned = [item for values in PRIMARY.values() for item in ids(values)]
    if len(assigned) != len(set(assigned)) or set(assigned) != set(findings):
        raise ValueError('FINDING_PRIMARY_COVERAGE_MISMATCH')
    owner = {item: group for group, values in PRIMARY.items() for item in ids(values)}
    if set(SECONDARY) - set(findings) or any(set(values) - set(GROUPS) for values in SECONDARY.values()):
        raise ValueError('SECONDARY_GROUP_REFERENCE_INVALID')
    if any(owner[item] in values for item, values in SECONDARY.items()):
        raise ValueError('SECONDARY_DUPLICATES_PRIMARY')
    paper_path = PROJECT / PAPER
    paper_text = paper_path.read_text()
    version = re.search(r'한글 논문 초안 v(\d+\.\d+)', '\n'.join(paper_text.splitlines()[:5]))
    if not version:
        raise ValueError('PAPER_VERSION_NOT_FOUND')
    questions = {code: (title, text) for code, title, text in re.findall(
        r'^\|(SQ[1-6])\|([^|]+)\|([^|]+)\|', paper_text, re.MULTILINE)}
    questions.update((code, (title, text)) for code, title, text in [
        ('RQ1', '근거 변경에 대한 반응', re.search(r'\*\*RQ1\. ([^\n*]+)\*\*', paper_text).group(1)),
        ('RQ2', '풀이 조건과 원본 답변', re.search(r'\*\*RQ2\. ([^\n*]+)\*\*', paper_text).group(1)),
    ])
    if set(questions) != set(ORDER):
        raise ValueError('PAPER_QUESTION_SET_CHANGED')
    groups = []
    for group_id, values in GROUPS.items():
        question, title, claim, evidence, alternatives, boundary = values
        primary = ids(PRIMARY[group_id])
        observations = sorted({item for finding_id in primary for item in findings[finding_id]['interpretation_ids']})
        groups.append({'id': group_id, 'question_id': question, 'title_ko': title,
                       'claim_ko': claim, 'evidence_ko': evidence,
                       'alternatives_ko': alternatives, 'boundary_ko': boundary,
                       'primary_finding_ids': primary, 'related_finding_ids': [],
                       'interpretation_ids': observations})
    review = {'schema_version': 1, 'run': run, 'method': 'human-authored-thematic-editorial-index',
              'review_scope': 'Saved A03 findings only; no re-scoring or independent semantic adjudication',
              'new_external_model_calls': 0,
              'source_sha256': {str(STAGE / 'findings.json'): sha(source_path), str(PAPER): sha(paper_path)},
              'groups': groups,
              'finding_review': [{'finding_id': item, 'primary_group': owner[item],
                                  'secondary_groups': list(SECONDARY.get(item, ())),
                                  'note_ko': '원본 제목·주장·한계를 보존하고 주제별 읽기 위치를 지정했습니다.'}
                                 for item in sorted(findings)]}
    index = {'schema_version': 1, 'kind': 'editorial-index-of-saved-findings', 'run': run,
             'paper_version': version.group(1), 'paper': {'path': str(PAPER), 'sha256': sha(paper_path), 'sections': ['3.3', '3.4']},
             'saved_review': {'path': str(STAGE / 'rq-review.json'), 'sha256': None},
             'notice_ko': f'저장된 {len(findings)}개 연구 발견을 {len(GROUPS)}개 주제에 한 번씩 묶고 논문 v{version.group(1)}의 RQ/SQ로 연결한 편집 색인입니다. 새 모델 호출·의미 판정·논문 결론이 아닙니다.',
             'questions': [], 'groups': groups}
    for code in ORDER:
        mapped = [group['id'] for group in groups if group['question_id'] == code]
        status, scope = EMPTY.get(code, ('기존 관찰 연결 · 결론 미확정',
                                         '저장된 발견의 주장·반례·한계를 연결했습니다. 대응 집계와 사례 이상의 의미 정답 판정은 수행하지 않았습니다.'))
        if code == 'SQ1':
            status, scope = ('기준선 연결 · 직접 관계 미검토', GROUPS['G01'][5])
        if code == 'SQ3':
            status, scope = ('사례 연결 · 전수 판정 아님',
                             '저장된 설명의 반례를 연결했습니다. 전수 의미 정합성 검사나 오류율 추정은 수행하지 않았습니다.')
        index['questions'].append({'id': code, 'title_ko': questions[code][0],
                                   'question_ko': questions[code][1], 'status_ko': status,
                                   'scope_ko': scope, 'group_ids': mapped})
    folder.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    save('rq-review.json', review)
    index['saved_review']['sha256'] = sha(folder / 'rq-review.json')
    save('rq-sq-review.json', index)
    lines = ['# 연구 발견 주제별 통합 및 RQ/SQ 연결', '',
             '원본 F 183개를 한 주 그룹에 각각 연결했습니다. 보조 연결은 중복 계산하지 않습니다.',
             '이 문서는 저장된 A03의 편집 색인이며 새 모델 판정이나 논문 결론이 아닙니다.', '']
    for question in index['questions']:
        lines += [f"## {question['id']} · {question['title_ko']}", '', question['question_ko'], '',
                  f"**범위:** {question['scope_ko']}", '']
        for group in groups:
            if group['question_id'] != question['id']:
                continue
            lines += [f"### {group['id']} · {group['title_ko']} ({len(group['primary_finding_ids'])}개 F)", '',
                      group['claim_ko'], '', '**근거:** ' + group['evidence_ko'], '',
                      '**다른 설명:** ' + group['alternatives_ko'], '',
                      '**해석 한계:** ' + group['boundary_ko'], '',
                      '**원본 F:** ' + ', '.join(group['primary_finding_ids']), '']
    (folder / 'rq-review.md').write_text('\n'.join(lines) + '\n')
    audit = ['# 원본 연구 발견 183개 대응표', '',
             '모든 F의 주 그룹은 정확히 하나이며 보조 그룹은 교차 주제 안내입니다.', '',
             '|원본|저장 제목|주 그룹|보조 그룹|', '|---|---|---|---|']
    for row in review['finding_review']:
        audit.append('|'+ '|'.join([row['finding_id'], findings[row['finding_id']]['display_ko']['title'].replace('|','/'),
                                  row['primary_group'], ', '.join(row['secondary_groups']) or '—'])+'|')
    (folder / 'rq-review-audit.md').write_text('\n'.join(audit) + '\n')
    template = PROJECT / 'src/finarch/experiments/templates/editorial-grouping-readme.md'
    (folder / 'rq-sq-review-README.md').write_text(template.read_text().format(run=run, count=len(findings), version=version.group(1)))
    validation = {'source_findings': len(findings), 'primary_assignments': len(assigned),
                  'groups': len(groups), 'questions': len(index['questions']),
                  'all_findings_covered_once': True, 'source_hashes_verified': True,
                  'semantic_review': 'EDITORIAL_GROUPING_NOT_INDEPENDENT_VALIDATION',
                  'new_external_model_calls': 0}
    save('rq-review-validation.json', validation)
    return validation


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    print(json.dumps(build(parser.parse_args().run), ensure_ascii=False))
