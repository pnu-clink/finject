"""Recheck actual typed-prompt run artifacts without model calls or new verdicts."""
import argparse
import json
from pathlib import Path

read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
digest = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['digest']).digest
from finarch.dataset.shared.review.dtt_audit import prepare, evaluate_saved
candidate_current = __import__('finarch.dataset.02-generation.05-human-review.human_review', fromlist=['candidate_current']).candidate_current
report = __import__('finarch.dataset.02-generation.02-generate-text.prompt_rerun', fromlist=['report']).report


def verify(root):
    root=Path(root).resolve();state=read(root/'production-progress.json')
    assert state['status']=='COMPLETED', 'RUN_NOT_FINISHED'
    result=report(root,state)
    assert result['original_inputs_unchanged']
    assert result['prompt_snapshots_match_actual_calls']
    assert not (root/'test-0008/05-text').exists()
    assert len(state['cases'])==10
    calls=[];checks=[]
    for case in sorted(root.glob('test-*')):
        if case.name=='test-0008':continue
        for p in sorted(case.glob('05-text/**/01-input.json')):
            req=read(p);selection=req['prompt_selection'];role=req['role'];where=p.parent
            assert role in ('02-generation.02-generate-text.realization','shared.01-02.02-03.review-and-validation'), 'UNPLANNED_ROLE'
            assert len(selection['parts'])==2
            request=read(where.parent/'01-input.json')
            assert request['axis']==selection['axis']
            assert req['prompt']==selection['instruction']+'\nInput:\n'+json.dumps(request,ensure_ascii=False)
            assert (req['model'],req['effort'])==(('gpt-5.6-luna','none') if role=='shared.01-02.02-03.review-and-validation' else ('gpt-5.3-codex-spark','low'))
            definition=read(where/'01-input/response-schema.json');schema_check=read(where/'03-result/schema-check.json')
            assert req['response_schema']==definition['schema']
            process=read(where/'02-raw-response/cli-execution.json');assert process['state']=='EXITED'
            if process['exit_code']==0:
                assert schema_check['status']=='PASS'
                assert schema_check['schema_sha256']==definition['sha256']
                assert (where/'02-raw-response.json').is_file()
            else:
                assert schema_check['status']!='PASS'
                assert (where/'03-result/failure.json').is_file()
                assert not (where.parent/'04-final-observation.json').exists(), 'FAILED_CALL_PROMOTED'
            calls.append({'case':case.name,'path':str(where.relative_to(root)),'role':role,'axis':request['axis'],
                          'prompt_sha256':selection['sha256'],'response_schema_sha256':definition['sha256'],
                          'raw_response_sha256':digest(where/'02-raw-response.json') if (where/'02-raw-response.json').exists() else None,
                          'process_exit_code':process['exit_code'],'elapsed_seconds':process['elapsed_seconds']})
        for p in sorted(case.glob('05-text/*/latest-audit.json')):
            label=p.parent.name;stage=read(p)['stage'];where=case/stage
            req,binding=prepare(case,label);saved=read(where/'01-input.json');audit=read(where/'03-result.json')
            assert req==saved
            for key in ('stage16_ref','observation_sha256','plan_sha256'):assert audit[key]==binding[key]
            raw=read(where/'audit/02-raw-response.json')
            if isinstance(raw,dict) and set(raw)=={'text'}:raw=json.loads(raw['text'])
            checked=evaluate_saved(req,raw,audit)
            assert checked['status']==audit['status'] and checked['findings']==audit['findings']
            checks.append({'case':case.name,'label':label,'status':audit['status'],'saved_response_replay':'PASS'})
        for item in read(case/'06-human-review/03-result.json'):
            assert item['human_decision']=='PENDING'
            if item.get('stage16_ref') or item['variant']=='ANSWER':
                assert candidate_current(case,item)
            else:
                assert item['status']=='NOT_EVALUATED', 'UNGENERATED_ITEM_PROMOTED'
    assert len(calls)==sum(result['call_count'].values())
    out={'status':'PASS','verification_scope':'saved provenance, schema, patch replay, audit aggregation and review hashes; not semantic truth',
         'model_calls_during_verification':0,'actual_call_count':len(calls),'audit_replays':checks,'calls':calls,
         'original_inputs_unchanged':True,'excluded_case_not_called':True,'stage18_not_called':True}
    (root/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ('status','actual_call_count','model_calls_during_verification')},ensure_ascii=False))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);verify(p.parse_args().root)
