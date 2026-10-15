variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""Save an explicitly editorial preview for the verified first service-fee case."""
import json
import hashlib
from pathlib import Path
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
apply_patches = __import__('finarch.dataset.90-operations.staging', fromlist=['apply_patches']).apply_patches


def compose_relation(sample, plan, original_graph, programs):
    # [TP02] docs/02-architecture.md#TP02 — show the saved relation draft, not a generated response.
    raise ValueError('MANUAL_TEXT_PREVIEW_REMOVED: use an actual LLM response')


RELATION_PREVIEW_README = '''# IC-RELATION 문장 편집 미리보기

읽는 순서: 활성 후보의 plan-v2.json(없으면 plan.json) → text-preview-v2.json → B/program.json과 B/graph.json.

text-preview-v2.json은 저장된 관계 문장을 지정 위치에 삽입한 검토용 사본입니다. 원문·질문·관측 금액은 보존하며, 추가 구간과 코드·그래프 연결을 기록합니다. 원본 A와 관계 적용 B만 비교합니다.

공통 viewer에서 이 실행과 문항 → IC-RELATION → 5 문장과 답변을 선택합니다. 원본식·관계 적용식 바로 아래의 원문/미리보기 비교에서 추가 문장은 초록색입니다. 조건부 계산값은 별도 모델의 응답이 아닙니다.

관계와 문장 초안은 에이전트가 작성했습니다. 추가 문장 생성용 LLM 호출은 없으며, 16번 최종 문장 생성과 17번 의미 검사는 미실행입니다. 전체 작업이 LLM을 사용하지 않았다는 뜻이 아닙니다. events.jsonl에 TP02 처리와 산출물 기록이 남습니다.
'''


def save_relation(case_dir, label='IC_RELATION_01'):
    case = Path(case_dir); root = f'{variant_root(label)}'
    ctx = RunContext.resume(case, {}, case.name)
    with ctx.trace.activate(), ctx.trace.span('text_preview.relation', stage='03-graph', step='TP02') as outcome:
        variants = json.loads((case/'04-perturbation/05-list-candidates/03-result.json').read_text())
        plan = next(v['plan'] for v in variants if v['label'] == label)
        for name, expected in plan['preserved_inputs_sha256'].items():
            if hashlib.sha256((case/name).read_bytes()).hexdigest() != expected:
                raise ValueError('RELATION_PREVIEW_INPUT_CHANGED:' + name)
        sample = json.loads((case/'00-data-preparation/01-select-input/01-input.json').read_text())
        graph = json.loads((case/'03-graph/04-save-graph/01-graph.json').read_text())
        programs = {key: json.loads((case/path).read_text())['code'] for key, path in
                    [('A', '02-calculation/02-prepare-code/03-program.json'), ('B', root+'/B/program.json')]}
        preview = compose_relation(sample, plan, graph, programs)
        ctx.save(root+'/05-text-input-preview.json', preview)
        ctx.save_text(root+'/05-text-input-preview.md', RELATION_PREVIEW_README)
        outcome.update(status='PASS', reason='RELATION_EDITORIAL_PREVIEW_SAVED')
        return preview


def compose(payload):
    # [TP01] docs/02-architecture.md#TP01 — preview only, never a model result.
    raise ValueError('MANUAL_TEXT_PREVIEW_REMOVED: use an actual LLM response')


def target_ids(payload):
    return payload['graph_binding']['original_node_ids']


def compose_ea(sample, plan, program):
    raise ValueError('MANUAL_TEXT_PREVIEW_REMOVED: use an actual LLM response')


def save_ea(case_dir, label='EA_01'):
    case = Path(case_dir); root = f'{variant_root(label)}'
    if Path(label).name != label or label in ('.', '..'):
        raise ValueError('INVALID_LABEL')
    ctx = RunContext.resume(case, {}, case.name)
    with ctx.trace.activate(), ctx.trace.span('text_preview.ea', stage='03-graph', step='TP03') as outcome:
        plan = json.loads((case/root/'plan.json').read_text())
        for name, expected in plan['preserved_inputs_sha256'].items():
            if hashlib.sha256((case/name).read_bytes()).hexdigest() != expected:
                raise ValueError('EA_PREVIEW_INPUT_CHANGED:' + name)
        sample = json.loads((case/'00-data-preparation/01-select-input/01-input.json').read_text())
        program = json.loads((case/'02-calculation/02-prepare-code/03-program.json').read_text())
        preview = compose_ea(sample, plan, program)
        ctx.save(root+'/05-text-input-preview.json', preview)
        ctx.save_text(root+'/context-tagged.txt', preview['intermediate']['context'])
        ctx.save_text(root+'/context-preview-v2.txt', preview['preview_context'])
        ctx.save_text(root+'/05-text-input-preview.md', '''# EA · 삭제 태그에서 자연스러운 문장으로

읽는 순서: plan.json → text-preview-v2.json → context-tagged.txt → context-preview-v2.txt.
plan.json에 지정한 입력 금액 위치만 제작용 삭제 태그로 바꾼 중간 본문을 저장합니다. 다음 수정본 초안은 대상 수익 항목을 남기고 금액을 소개하는 표현과 숫자만 제거한 사본입니다. 태그·삭제 안내를 수정본 본문에 넣지 않습니다. 원본 파일은 보존했습니다. 다른 세 금액·질문·계산식은 그대로이며 삭제 위치와 그래프 연결은 text-preview-v2.json에 있습니다. 첫 문항의 서비스 수수료 80,000 삭제와 판매 수수료 45,000 삭제를 지원하며, 파생 중간합을 지우는 방식이 아닙니다.

공통 뷰어에서 이 실행 → test-0001 → EA → 5 문장과 답변을 선택합니다. 원문 전체 → 태그가 있는 전체 본문 → 다듬은 문장 하나를 세로로 쌓아 비교합니다. 2번에서는 태그를 포함한 작업 문장 전체, 3번에서는 변경한 문장만 색으로 표시합니다. 변경 문장 복사는 3번의 문장만 복사합니다. 8 전체 기록에서도 파일을 읽을 수 있습니다.

에이전트가 지정한 첫 문항 편집을 Python으로 적용한 미리보기이며, 문장 생성용 추가 LLM 호출은 없습니다. 미리보기 파일 저장은 최종 본문 승인·의미 검사·독립 모델 답변 완료가 아닙니다. 결과의 근거 부족 표시는 현재 계산 경로의 상태입니다. 역산·우회 및 EA 의미 성립은 미평가로 유지합니다.

이 README는 저장 함수의 템플릿에서 자동 생성됩니다. 문제별 events.jsonl에 TP03의 시작·산출물·종료를 기록합니다. 앞선 그래프 안내의 '본문 삭제 미적용'은 원본 및 최종 산출물 기준이며, 이 사본에서만 삭제 편집을 적용했습니다.
''')
        outcome.update(status='PASS', reason='EA_DELETION_PREVIEW_SAVED_NOT_FINAL_TEXT')
        return preview


def save(case_dir,label):
    case=Path(case_dir);root=f'{variant_root(label)}'
    ctx=RunContext.resume(case,{},case.name)
    with ctx.trace.activate(),ctx.trace.span('text_preview.save',stage='03-graph',step='TP01-text-preview') as outcome:
        payload=json.loads((case/root/'realization-input.json').read_text())
        preview=compose(payload)
        ctx.save(root+'/05-text-input-preview.json',preview)
        ctx.save_text(root+'/05-text-input-preview.md','이 파일은 첫 수수료 문항의 편집 미리보기입니다. LLM이 생성한 최종 본문이나 모델 답변이 아닙니다. text-preview-v2.json에 값 주장·A 출처·B 출처 구간 및 삽입 위치·문구·원문·미리보기·그래프 연결을 보존합니다. 공통 뷰어 5번에서 비교합니다.\n')
        outcome.update(status='PASS',reason='EDITORIAL_PREVIEW_SAVED_NOT_FINAL_TEXT')
        return preview
