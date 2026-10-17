"""Read the latest successful realization and replay checks without any model call."""
import argparse
from pathlib import Path
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
check_response = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['check_response']).check_response
digest = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['digest']).digest
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
from finarch.dataset.schemas.validation import validate, parse_json_object
from finarch.dataset.schemas.registry import describe

README = '''# 16The first case

The current results: **{passed}/{total} Pass the conditioned editing check**Call the real CLI. {calls}Chapter two.
Model: gpt-5.3-codex-spark / low. {input_tokens:,} Tokens, output {output_tokens:,} tokens
(cache input) {cached_tokens:,} Include) overpayment of uncertain amounts 0It doesn't show up as.

In order of reading:
1. `STAGE16-REVIEW.json`The current success rate: 7items and re-exams, source code, hashing, whole use.
2. `stage16/plan.json`, `stage16/review.json`The first: 6Turn and fail causes.
3. `stage16-v2/review.json`: Prompt value after modification 1Rescue and recovery 2Additional generated rounds.
4. By type `latest-realization.json`If this is a directory, if not a type folder, `README.md`.
5. The folder is the same as the folder. `realize/01-input.json`(Real prompt response scheme)
   `02-raw-response.json`(Raw response) `03-result/schema-check.json`, `03-result/validation.json`,
   `03-result/patches.json`, `04-final-observation.json`(C/Q) I read it in order.

|Type|Current results are in the folder|
|---|---|
{rows}

IC-VALUE is the same generated phrase in Python, and the additional call to the back condition is 0calls.
So the source A/B also fixes the value phrase. ` totaling 80,000` Or
` reaching 45,000`The tag, the replacement number, the end guide are not in the finished text.

Exposure to the Python variable of the first value phrase, the default default default of the source B response,
I've identified and corrected a mark assembly error that follows the axis gap in the source preview.
The initial raw response results are saved and the current success revision is selected as the viewer text.

Common log: the root of the case `events.jsonl`, each call to the folder `03-result/usage.json`and `02-raw-response/cli-execution.json`.
Viewer: http://127.0.0.1:8893/?run={run}&case={case}&tab=dtt
The type button **5 The phrases and answers**In the actual sentence, check the two sets of LLM debugging transmissions and transmissions below.

17The meaning of the word18The test is a misreading of the terms of the agreement and the terms of a sentence editing agreement.
It doesn't make a meaningful guarantee of collision/response inflation. 9I didn't create a new case.
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
