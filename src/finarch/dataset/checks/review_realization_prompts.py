"""Export current prompt previews from saved requests; never call a model."""
import argparse
import json
from pathlib import Path
FILES = __import__('finarch.dataset.02-generation.02-generate-text.realization_prompts', fromlist=['FILES']).FILES
describe_prompt = __import__('finarch.dataset.02-generation.02-generate-text.realization_prompts', fromlist=['describe_prompt']).describe_prompt
from finarch.dataset.shared.review.audit_prompts import FILES as AUDIT_FILES, describe_prompt as describe_audit_prompt
from finarch.shared.providers.cli import prepare_instruction
from finarch.dataset.schemas.registry import describe
from finarch.dataset.schemas.validation import validate

README = '''# {title} · 호출 전 확인

상태: PREVIEW_ONLY. 실제 모델 호출 0회. 기존 본문·요청·판정 변경 없음.

읽는 순서:
1. `summary.json`: 유형 파일·해시 및 확인한 조건 목록.
2. `prompt-previews/`: 현재 지침과 저장된 문제 입력을 결합한 전송 **예정** 전문, 응답 스키마.
3. `checks.log`: 로컬 선택·CLI 경계·기존 편집·뷰어 검사 기록.

뷰어: http://127.0.0.1:8893/?run={run}&case={case}&tab=dtt
유형 선택 → 5번 → `{button}`에서 현재 지침을 읽습니다.
사용한 프롬프트·입력 팝업은 기존 수정문이나 판정의 과거 기록입니다.
현재 파일을 수정하면 현재 지침 팝업은 바뀌지만 이 미리보기 사본의 해시는 그대로입니다.

형식과 연결 검사만 수행했습니다. 새 지침의 실제 생성 품질·비용·시간은 미평가입니다.
모델·추론 설정·자동 재시도·원문 편집 범위는 이번 변경으로 바꾸지 않았습니다.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--role', choices=('02-generation.02-generate-text.realization','shared.01-02.02-03.review-and-validation'), default='02-generation.02-generate-text.realization')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    target = args.output/'prompt-previews'; target.mkdir()
    rows = []
    audit = args.role == 'shared.01-02.02-03.review-and-validation'
    files, selector = (AUDIT_FILES, describe_audit_prompt) if audit else (FILES, describe_prompt)
    pattern = '*/latest-audit.json' if audit else '*/latest-realization.json'
    for pointer in sorted((args.case/'05-text').glob(pattern)):
        stage = json.loads(pointer.read_text())['stage']
        source = args.case/stage/'01-input.json'
        request = json.loads(source.read_text())
        validate(args.role+'.request', request)
        instruction, definition = prepare_instruction(args.role, request)
        preview = {'status':'PREVIEW_ONLY', 'model_calls':0, 'source_request':str(source),
                   'prompt':instruction+'\nInput:\n'+json.dumps(request, ensure_ascii=False),
                   'prompt_selection':definition, 'response_schema':describe(args.role+'.response')}
        (target/(pointer.parent.name+'.json')).write_text(json.dumps(preview, ensure_ascii=False, indent=2)+'\n')
        rows.append({'label':pointer.parent.name, 'axis':request['axis'],
                     'slots':len(request['intent'].get('authorized_edit_slots',[])) if audit else len(request['edit_slots']),
                     'prompt_sha256':definition['sha256'], 'status':'INPUT_VALID_PREVIEW_ONLY'})
    summary = {'status':'PREVIEW_ONLY', 'model_calls':0, 'cases':rows,
               'role':args.role, 'types':[selector(axis) for axis in files]}
    (args.output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    (args.output/'README.md').write_text(README.format(run=args.case.parent.name, case=args.case.name,
        title='17번 유형별 검증 지침' if audit else '16번 유형별 문장 생성 지침',
        button='현재 유형 검증 지침 보기 · 미호출' if audit else '현재 유형 지침 보기 · 미호출'))
    print(json.dumps({'status':'PREVIEW_ONLY', 'conditions':len(rows), 'types':len(files), 'model_calls':0}))


if __name__ == '__main__': main()
