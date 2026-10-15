"""Compare any two saved LLM step directories without new model calls."""
import argparse
import difflib
import json
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write


def optional(path):
    return read(path) if path.exists() else None


def capture(step):
    step = Path(step).resolve()
    request = read(step / '03-LLM-call/01-input.json')
    model = read(step / '03-LLM-call/01-input/model-request.json')
    schema = read(step / '01-input/response-schema.json')
    if not schema.get('schema'):
        raise ValueError('Saved response schema is missing or empty')
    result = optional(step / '03-result.json')
    return dict(path=str(step), model=request.get('model'), effort=request.get('effort'),
                fresh_session=request.get('fresh_session'), prompt=request['prompt'],
                schema=schema['schema'], schema_version=schema.get('version'),
                input=model['input'], response=result.get('data') if result else None,
                result=result, usage=optional(step / '03-LLM-call/03-result/usage.json'))


def changes(before, after, path='$'):
    """Retain nested changes, including required fields, types and list values."""
    if isinstance(before, dict) and isinstance(after, dict):
        rows = []
        for key in sorted(before.keys() | after.keys()):
            child = path + '/' + key.replace('~', '~0').replace('/', '~1')
            if key not in before:
                rows.append(dict(path=child, kind='added', after=after[key]))
            elif key not in after:
                rows.append(dict(path=child, kind='removed', before=before[key]))
            else:
                rows.extend(changes(before[key], after[key], child))
        return rows
    if type(before) is not type(after) or before != after:
        return [dict(path=path, kind='changed', before=before, after=after)]
    return []


def build(output, before_step, after_step, validation=None, local_repair=None):
    output = Path(output).resolve()
    before, after = capture(before_step), capture(after_step)
    old, new = before['prompt'].splitlines(), after['prompt'].splitlines()
    removed, added = [], []
    for op, i, j, k, l in difflib.SequenceMatcher(a=old, b=new).get_opcodes():
        if op in ('replace', 'delete'): removed.extend(old[i:j])
        if op in ('replace', 'insert'): added.extend(new[k:l])
    schema_diff = changes(before['schema'], after['schema'])
    input_diff = changes(before['input'], after['input'])
    response_diff = changes(before['response'], after['response'])
    report = dict(title=output.name + ' · LLM 요청 변경 전후', before=before, after=after,
        same_input=not input_diff, input_changes=input_diff, response_changes=response_diff,
        prompt_changes=dict(removed=removed, added=added, diff='\n'.join(difflib.unified_diff(old,new,fromfile='Before',tofile='After',lineterm=''))),
        schema_changes=dict(old_fields=list(before['schema'].get('properties',{})), new_fields=list(after['schema'].get('properties',{})), changes=schema_diff),
        validation=read(Path(validation)) if validation else None,
        local_repair=read(Path(local_repair)) if local_repair else None,
        record_paths=dict(validation=str(validation) if validation else None, local_repair=str(local_repair) if local_repair else None),
        attempt_note='저장된 두 호출만 비교합니다. 입력 동일성은 정답 미전달 또는 의미 정답을 증명하지 않습니다. 첨부하지 않은 검증·보정 기록은 미제공으로 표시합니다.')
    report['summary'] = [
        dict(item='모델 / 추론 설정',before=str(before['model'])+' / '+str(before['effort']),after=str(after['model'])+' / '+str(after['effort'])),
        dict(item='전송 입력',before='저장된 입력',after='동일' if not input_diff else f'{len(input_diff)}개 경로 변경'),
        dict(item='프롬프트',before=f'{len(removed)}줄 제거·교체',after=f'{len(added)}줄 추가·교체'),
        dict(item='응답 스키마',before=str(before['schema_version']),after=f"{after['schema_version']} · {len(schema_diff)}개 경로 변경"),
        dict(item='모델 응답',before='기록 있음' if before['response'] is not None else '응답 데이터 없음',after=f'{len(response_diff)}개 경로 변경' if after['response'] is not None else '응답 데이터 없음'),
        dict(item='검증·로컬 보정',before='원응답 보존',after=f"검증 {'첨부' if validation else '미제공'} / 보정 {'첨부' if local_repair else '미제공'}")]
    output.mkdir(parents=True,exist_ok=True)
    write(output/'request-change-report.json',report)
    sections=[('입력 변경',input_diff),('스키마 변경',schema_diff),('응답 변경',response_diff),('검증 기록',report['validation']),('로컬 보정 기록',report['local_repair'])]
    lines=['# '+report['title'],'',report['attempt_note'],'','## 프롬프트 변경','```diff',report['prompt_changes']['diff'],'```']
    for title,value in sections:
        lines += ['', '## '+title,'```json',json.dumps(value,ensure_ascii=False,indent=2),'```']
    lines += ['', '이전 호출: '+before['path'],'이후 호출: '+after['path']]
    (output/'REQUEST-CHANGE-REPORT.md').write_text('\n'.join(lines)+'\n')
    template=Path(__file__).with_name('request-change-readme.md')
    (output/'REQUEST-CHANGE-README.md').write_text(template.read_text())
    from datetime import datetime, timezone
    with (output/'request-change-events.jsonl').open('a') as log:
        log.write(json.dumps(dict(timestamp=datetime.now(timezone.utc).isoformat(), event='report_written', before=before['path'], after=after['path'], artifact='request-change-report.json'))+'\n')
    return report

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output');parser.add_argument('--before',required=True);parser.add_argument('--after',required=True)
    parser.add_argument('--validation');parser.add_argument('--local-repair')
    args=parser.parse_args()
    result=build(args.output,args.before,args.after,args.validation,args.local_repair)
    print(json.dumps({'title':result['title'],'same_input':result['same_input']},ensure_ascii=False))
