"""Four sequential registered audit calls plus the existing local EA gate. No alternate transport."""
import argparse
from datetime import datetime, timezone
from importlib import import_module
import json
from pathlib import Path
import re
import shutil
InputSnapshot = __import__('finarch.dataset.03-release.response_screen', fromlist=['InputSnapshot']).InputSnapshot
PROJECT = __import__('finarch.dataset.03-release.response_screen', fromlist=['PROJECT']).PROJECT
from finarch.shared.providers.cli import read_settings
from finarch.dataset.shared.review.dtt_audit import audit_one
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext

ROLE='shared.01-02.02-03.review-and-validation'
IDS=('test-0026/06-ea-earlier-input','test-0074/06-ea-earlier-input','test-0001/03-ic-source-type-1','test-0001/04-ic-source-type-2')



def link_artifacts(records,snapshot):
    names={'wire':'03-validation/audit/01-input.json','raw':'03-validation/audit/02-raw-response/api-execution.json',
           'schema':'03-validation/audit/01-input/response-schema.json','schema_check':'03-validation/audit/03-result/schema-check.json',
           'usage':'03-validation/audit/03-result/usage.json','audit':'03-validation/03-result.json',
           'gate':'03-validation/05-recovery-screen.json','result':'result.json'}
    for record in records:
        record['artifacts']={}
        for key,relative in names.items():
            path=PROJECT/record['path']/relative
            if path.is_file():
                snapshot.capture(path);record['artifacts'][key]=snapshot.ref(path)


def run(output):
    output=Path(output).resolve();output.relative_to(PROJECT);output.mkdir(parents=True,exist_ok=False)
    snapshot=InputSnapshot(PROJECT);records=[]
    def save(name,value):
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    def event(phase,**extra):
        row={'time':datetime.now(timezone.utc).isoformat(),'phase':phase,'workflow':'quality_api_check',**extra}
        with (output/'events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    quality_path=PROJECT/'reports/run/20260916-quality-v1/quality_scope.json'
    quality={r['id']:r for r in snapshot.capture(quality_path)['records']}
    config=snapshot.capture(PROJECT/'config/llm-test-luna-low-api.json')
    original_profile=PROJECT/'config/codex-profiles.toml';profile=snapshot.capture(original_profile,parse=False).decode()
    stanza=re.search(r'(?ms)^\[profiles\.luna-low-api\]\n.*?(?=^\[|\Z)',profile)
    if stanza is None:raise ValueError('PROFILE_MISSING')
    bounded=stanza.group().replace('max_output_tokens = 32768','max_output_tokens = 8192').replace('total_token_budget = 500000','total_token_budget = 32768')
    profile=profile[:stanza.start()]+bounded+profile[stanza.end():]
    (output/'test-profiles.toml').write_text(profile)
    config.update(execution_enabled=True,profiles_path=str(output/'test-profiles.toml'),ea_recovery_policy={'enabled':True},use_model_selection=False)
    save('test-config.json',config);config_path=output/'test-config.json'
    settings=read_settings(config_path,ROLE)
    if (settings['model'],settings['effort'],settings['provider'],settings['profile']['transport'],settings['profile']['max_output_tokens'],settings['profile']['total_token_budget'])!=('gpt-6-luna','low','openai','api',8192,32768):raise ValueError('TEST_WIRE_PROFILE_MISMATCH')
    price=PROJECT/'src/finarch/shared/run_logging/api-pricing-snapshot.json';snapshot.capture(price);shutil.copyfile(price,output/'pricing-snapshot.json')
    rates=json.loads(price.read_text())['models'][settings['model']]
    token_bound=6*((32768-8192)*rates['input_per_million']+8192*rates['output_per_million'])/1000000
    save('call-plan.json',{'ids':IDS,'planned_generation_calls':4,'maximum_authorized_generation_calls':6,'automatic_retries':0,
         'model':settings['model'],'effort':'low','max_output_tokens':8192,'total_token_budget':32768,
         'snapshot_usd_per_million':{'input':rates['input_per_million'],'output':rates['output_per_million']},'conservative_six_call_token_cost_bound_usd':token_bound,
         'authorized_cost_cap_usd':0.50,'token_count_requests':'One provider input-token-count request before each generation; tracked separately.',
         'route':'g03_verification.run -> audit_one -> registered cli.call -> complete_api'})
    verify=import_module('finarch.dataset.02-generation.03-validation.stage');driver=import_module('finarch.dataset.02-generation.generate_run')
    event('START',planned_generation_calls=4,automatic_retries=0,model=settings['model'],effort='low')
    for identifier in IDS:
        row=quality[identifier];ref=row['references']['generation'];path=PROJECT/ref['path'];saved=snapshot.capture(path)
        if snapshot.ref(path)!=ref:raise ValueError('GENERATION_INPUT_HASH_CHANGED')
        case,variant=identifier.split('/');index=int(variant[:2])-1
        folder=output/(case+'-'+variant[:2]);ctx=RunContext(folder,{},case)
        ctx.save('source-generation.json',saved);ctx.save('source-reference.json',ref)
        result={'id':identifier,'axis':saved['axis'],'status':'RUNNING'}
        event('CALL_START',id=identifier,ordinal=len(records)+1)
        try:
            verify.run(ctx,config_path,{'context':saved['plan']['request']['context'],'question':saved['plan']['request']['question']},
                saved['plan'],saved['generation_request'],saved['generation_response'],saved['observation'],saved['patches'],saved['axis'],saved['label'],index,{},result,driver.digest,audit_one)
        except Exception as error:
            result.update(status='FAIL',failure_type=type(error).__name__,reason=str(error))
            # Preserve the existing local gate even when the audit transport raises.
            verify.gg04_screen_recovery(ctx,config_path,saved['plan'],saved['observation'],saved['axis'],result)
        audit_root=folder/'03-validation/audit'
        wire_path=audit_root/'01-input.json'
        wire=json.loads(wire_path.read_text()) if wire_path.exists() else None
        draft_path=audit_root/'01-input/request-draft.json'
        if wire is None and draft_path.exists():wire=json.loads(draft_path.read_text())
        wire_ok=bool(wire and wire['request']['model']==settings['model'] and wire['request']['reasoning']['effort']=='low' and wire['automatic_retries']==0 and wire['request']['text']['format']['schema'])
        if wire and not wire_ok:raise ValueError('ACTUAL_WIRE_MISMATCH')
        usage_path=audit_root/'03-result/usage.json';usage=json.loads(usage_path.read_text()) if usage_path.exists() else None
        api_started=(audit_root/'01-input/api-start.json').exists()
        response_path=audit_root/'02-raw-response/api-execution.json'
        record={'id':identifier,'audit_status':result.get('audit',{}).get('status','NOT_COMPLETED'),'combined_status':result['status'],
             'reason':result.get('reason'),'failure_type':result.get('failure_type'),'recovery_status':result.get('recovery_screen',{}).get('status'),
             'wire_luna_low_verified':wire_ok,'generation_request_started':api_started,'raw_response_saved':response_path.exists(),
             'usage':usage,'path':folder.relative_to(PROJECT).as_posix(),'source':ref}
        if saved['axis']=='EA' and (record['recovery_status']!='RECOVERABLE' or record['combined_status']!='FAIL'):
            raise ValueError('KNOWN_EA_COUNTEREXAMPLE_NOT_BLOCKED')
        ctx.save('result.json',result);records.append(record);save('partial-results.json',records)
        event('CALL_END',id=identifier,generation_request_started=api_started,raw_response_saved=response_path.exists(),audit_status=record['audit_status'],combined_status=record['combined_status'],reason=record['reason'])
    link_artifacts(records,snapshot)
    snapshot.verify()
    cost=sum((r['usage'] or {}).get('estimated_cost') or 0 for r in records)
    summary={'records':len(records),'generation_requests':sum(r['generation_request_started'] for r in records),
        'raw_responses':sum(r['raw_response_saved'] for r in records),'wire_verified':sum(r['wire_luna_low_verified'] for r in records),
        'audit_pass':sum(r['audit_status']=='PASS' for r in records),'ea_counterexamples_blocked':sum(r['recovery_status']=='RECOVERABLE' and r['combined_status']=='FAIL' for r in records),
        'estimated_cost_usd':cost,'automatic_retries':0,'semantic_generalization':'NOT_EVALUATED'}
    report={'schema_version':'quality-api-check-v1','run_id':output.name,'model':settings['model'],'effort':settings['effort'],'summary':summary,'records':records,'references':list(snapshot.references.values()),
            'limitations':['Four saved examples, not full dataset semantic validity or Qwen baseline.',
             'Audit three-axis findings and bounded EA gate are separate. Known EA witnesses must block even audit PASS.',
             'Costs use the preserved repository price snapshot, not a billing statement. Input-token-count requests are separate from generation calls.']}
    save('quality-api-check.json',report);save('summary.json',{'workflow':'quality_api_check','status':'COMPLETED' if summary['raw_responses']==4 else 'BLOCKED_OR_PARTIAL',**summary})
    save('manifest.json',{'snapshot_status':'UNCHANGED','inputs':list(snapshot.references.values()),'missing':sorted(snapshot.missing)})
    (output/'README.md').write_text(Path(__file__).with_name('quality-api-check-readme-template.md').read_text().format(run_id=output.name,summary=json.dumps(summary,ensure_ascii=False,indent=2)))
    event('END',**summary);return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
