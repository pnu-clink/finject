"""Read the latest successful realization and replay checks without any model call."""
import argparse
from pathlib import Path
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
check_response = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['check_response']).check_response
digest = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['digest']).digest
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
from finarch.dataset.schemas.validation import validate, parse_json_object
from finarch.dataset.schemas.registry import describe

README = '''# 16번 실제 문장 생성 · 첫 문항

현재 결과: **{passed}/{total} 조건 편집 검사 통과**, 실제 CLI 호출 {calls}회.
모델: gpt-5.3-codex-spark / low. 입력 {input_tokens:,} 토큰, 출력 {output_tokens:,} 토큰
(캐시 입력 {cached_tokens:,} 포함). 과금액·단가 미확인으로 비용을 0으로 표시하지 않습니다.

읽는 순서:
1. `STAGE16-REVIEW.json`: 현재 성공 결과 7개와 재검사·원본 해시·전체 사용량.
2. `stage16/plan.json`, `stage16/review.json`: 최초 6회 호출과 실패 사유.
3. `stage16-v2/review.json`: 프롬프트 수정 후 값 1회·출처 2회 추가 생성.
4. 유형별 `latest-realization.json`이 있으면 가리키는 폴더, 없으면 유형 폴더의 `README.md`.
5. 해당 폴더의 `realize/01-input.json`(실제 프롬프트·응답 스키마),
   `02-raw-response.json`(원응답), `03-result/schema-check.json`, `03-result/validation.json`,
   `03-result/patches.json`, `04-final-observation.json`(C/Q만) 순서로 읽습니다.

|유형|현재 결과 폴더|
|---|---|
{rows}

IC-VALUE 앞/뒤는 동일 생성 문장을 Python으로 배치하며 뒤 조건의 추가 호출은 0회입니다.
출처 A/B도 그 값 문장을 고정합니다. EA는 수익 항목을 남기고 ` totaling 80,000` 또는
` reaching 45,000`만 제거합니다. 태그·대체 숫자·결측 안내문은 완성 본문에 없습니다.

최초 값 문장의 Python 변수명 노출, 출처 B 응답의 고정 접두문 누락,
출처 미리보기의 axis 누락에 따른 표시 조립 오류를 확인하고 수정했습니다.
초기 원응답·검사 결과는 보존하며 현재 성공 revision만 뷰어 본문으로 선택합니다.

공통 로그: 문항 루트 `events.jsonl`, 각 호출 폴더 `03-result/usage.json`과 `02-raw-response/cli-execution.json`.
뷰어: http://127.0.0.1:8893/?run={run}&case={case}&tab=dtt
문항 → 유형 버튼 → **5 문장과 답변**에서 실제 문장, 하단 LLM 디버그의 전송·수신 두 묶음을 확인합니다.

17번 의미 검사·18번 독립 답변·역산/우회는 미실행입니다. 이 검사는 문장 편집 계약과
저장 일치를 확인하며 충돌/답변 불가의 의미적 보장은 하지 않습니다. 다른 9문항을 새로 생성하지 않았습니다.
'''


def review(case):
    case=Path(case).resolve();variants=read(case/'04-perturbation/05-list-candidates/03-result.json');items=[];texts={}
    for v in variants:
        stage='05-text/'+v['label'];pointer=case/stage/'latest-realization.json'
        if pointer.exists():stage=read(pointer)['stage']
        p=case/stage;request=read(p/'01-input.json');applied=read(p/'03-result/patches.json')
        response={'patches':[{k:x[k] for k in ('start','end','before','text','element_ids')} for x in applied]}
        final,patches=check_response(request,response)
        metadata=read(p/'03-result/metadata.json');text=read(p/'03-result.json');texts[v['label']]=text
        call=case/metadata['realization_call_ref'];raw=parse_json_object(read(call/'02-raw-response.json')['text'])
        validate('dtt.realize.response',raw)
        saved_schema=read(call/'01-input/response-schema.json')
        checks={
            'replayed_context_equals_saved':final==read(p/'04-final-observation.json'),
            'original_question_preserved':final['question']==read(case/'00-data-preparation/01-select-input/01-input.json')['question'],
            'preview_equals_final':text['preview_context']==final['context'],
            'patches_equal':patches==applied,
            'response_schema_matches_sent':saved_schema['schema']==read(call/'01-input.json')['response_schema'],
            'response_schema_checked':read(call/'03-result/schema-check.json')=={'status':'PASS','schema_sha256':saved_schema['sha256']},
            'response_schema_current':saved_schema['sha256']==describe('dtt.realize.response')['sha256'],
            'no_semantic_promotion':metadata['semantic_status']=='NOT_EVALUATED',
            'no_independent_answer':metadata['independent_answer_status']=='NOT_RUN',
        }
        if text.get('model_calls')!=0:
            checks['applied_matches_model_response']=response==raw
        else:
            checks['pair_sentence_matches_model']=text['perturb_sentence']==raw['patches'][0]['text'].strip()
        items.append({'label':v['label'],'stage':stage,'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks})
    pairs={}
    for v in texts.values():
        if v.get('pair_id'):pairs.setdefault(v['pair_id'],[]).append(v)
    pair_checks=[len(v)==2 and {x['perturb_position'] for x in v}=={'before','after'} and
                 v[0]['perturb_sentence']==v[1]['perturb_sentence'] for v in pairs.values()]
    original=read(case/'05-text/stage16/review.json')['original_sha256']
    preserved=all(digest(case/p)==value for p,value in original.items())
    usages=[read(p) for p in (case/'05-text').rglob('03-result/usage.json')]
    totals={k:sum(u['reported_usage'].get(k,0) for u in usages) for k in
            ('input_tokens','output_tokens','cached_input_tokens')}
    result={'status':'PASS' if preserved and all(pair_checks) and all(x['status']=='PASS' for x in items) else 'FAIL',
            'variants':items,'pair_checks':pair_checks,'original_inputs_preserved':preserved,
            'cli_invocations':sum(x['cli_invocations'] for x in usages),'usage':totals,
            'estimated_cost':None,'actual_billed_cost':None,'cost_status':'CLI pricing unavailable',
            'stage17':'NOT_RUN','stage18':'NOT_RUN','inverse':'DEFERRED_BY_USER'}
    ctx=RunContext.resume(case,{},case.name)
    with ctx.trace.activate(),ctx.trace.span('review_dtt_stage16',stage='05-text',step='R16.5',role='python'):
        ctx.save('05-text/STAGE16-REVIEW.json',result)
        ctx.save_text('05-text/STAGE16-README.md',README.format(passed=sum(i['status']=='PASS' for i in items),total=len(items),
            calls=result['cli_invocations'],input_tokens=totals['input_tokens'],output_tokens=totals['output_tokens'],
            cached_tokens=totals['cached_input_tokens'],rows='\n'.join(f"|{i['label']}|`{i['stage']}`|" for i in items),
            run=case.parent.name,case=case.name))
        ctx.trace.update(status=result['status'],reason='Saved model responses, applied patches and latest contexts reconciled.')
    print(result['status'],len(items),'variants',result['cli_invocations'],'calls',totals)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',type=Path,required=True)
    raise SystemExit(0 if review(p.parse_args().case)['status']=='PASS' else 1)
