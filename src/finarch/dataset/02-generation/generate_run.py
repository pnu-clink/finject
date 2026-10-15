"""Generate seven variants from human-approved inputs with bounded feedback rounds."""
from importlib import import_module
g01_perturbation = import_module("finarch.dataset.02-generation.01-perturbation.stage")
g02_generate_text = import_module("finarch.dataset.02-generation.02-generate-text.stage")
g03_verification = import_module("finarch.dataset.02-generation.03-validation.stage")
g04_exception_handler = import_module("finarch.dataset.02-generation.04-exception-handler.stage")
g05_human_review = import_module("finarch.dataset.02-generation.05-human-review.stage")
import argparse
from concurrent.futures import Future
from threading import RLock
completed = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['completed']).completed
limit = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['limit']).limit
record_queue = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['record_queue']).record_queue
from copy import deepcopy
import hashlib
import json
from pathlib import Path

require_generation_inputs = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['require_generation_inputs']).require_generation_inputs
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
generation_sample = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['generation_sample']).generation_sample
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepStopped = __import__('finarch.dataset.90-operations.staging', fromlist=['StepStopped']).StepStopped
measure = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['measure']).measure
TYPES = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['TYPES']).TYPES
build = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['build']).build
source_request = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['source_request']).source_request
check_response = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['check_response']).check_response
from finarch.dataset.shared.review.dtt_audit import audit_one, observation_hash
use_feedback = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['use_feedback']).use_feedback
from finarch.shared.providers.cli import call, prepare_instruction


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def expand(indices):
    indices=set(indices)
    if indices & {0,1}:indices.update((0,1,2,3))
    return sorted(indices)


def invoke(ctx,config,stage,role,payload):
    def handler(value,*,response_schema):
        return call(config,role,value,save=lambda name,data:ctx.save(stage+'/02-LLM-call/'+name,data))
    return ctx.invoke(stage,'01-request',role,payload,local=handler)


def process(bundle,round_dir,name,index,config,approved,latest,value_ready=None):
    folder,axis,label=TYPES[index]
    prior=latest.get(index,{})
    recovery=prior.get('recovery',{})
    directory=Path(round_dir)/'.feedback-input'/name/folder
    if recovery.get('feedback_ref'):
        load = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['load']).load
        ref=recovery['feedback_ref']
        load(ref,case=name,target_round=Path(round_dir).name)
        write(directory/ref['target_role']/'feedback.json',{'feedback_refs':[ref]})
    with use_feedback(directory,case=name,target_round=Path(round_dir).name):
        result=_process_attempt(bundle,round_dir,name,index,config,approved,latest,value_ready)
    if result['status']!='PASS' and result.get('disposition')!='COEFFICIENT_POLICY_BLOCKED':
        root=Path(bundle)/result['path']
        ctx=RunContext.resume(root,{},name)
        with ctx.trace.activate():
            try:
                result['recovery']=g04_exception_handler.run(ctx,config,result,name)
                result['retryable']=result['recovery']['retryable']
            except Exception as error:
                result['recovery']={'retryable':False,'handler_error':str(error)}
                result['retryable']=False
                ctx.save('04-exception-handler/handler-failure.json',result['recovery'])
            record_recovery(ctx, result)
    return result


def record_recovery(ctx, result):
    """Preserve the attempt before atomically refreshing its representative state."""
    original = ctx.root / '04-exception-handler/pre-feedback-run.json'
    if not original.exists():
        ctx.save('04-exception-handler/pre-feedback-run.json', read(ctx.root / 'run.json'))
    write(ctx.root / 'run.json', result)
    ctx.trace.artifact('run.json', result)


def restore_saved_result(path):
    """Reuse completed diagnosis after an interrupted representative-state update."""
    result = read(path)
    if result.get('status') == 'FAIL' and not result.get('recovery'):
        retry = path.parent / '04-exception-handler/03-retry.json'
        failed = path.parent / '04-exception-handler/handler-failure.json'
        if retry.exists() or failed.exists():
            recovery = read(retry if retry.exists() else failed)
            result.update(recovery=recovery, retryable=recovery.get('retryable', False))
            ctx = RunContext.resume(path.parent, {}, path.parent.parent.name)
            record_recovery(ctx, result)
    return result


def _process_attempt(bundle,round_dir,name,index,config,approved,latest,value_ready=None):
    folder,axis,label=TYPES[index];root=round_dir/name/folder
    ctx=RunContext(root,{},name)
    ctx.trace.emit(phase='START', status='RUNNING', stage='generation', reason='Variant attempt started')
    source=bundle/approved[name]['case_path'];sample,reference_repair=generation_sample(source)
    program=read(source/'03-calculation/02-prepare-code/03-program.json');graph=read(source/'04-graph/04-save-graph/01-graph.json')
    result={'label':label,'axis':axis,'status':'RUNNING','path':str(root.relative_to(bundle)),'round':round_dir.name,'restart':'01-perturbation'}
    with ctx.trace.activate():
        ctx.save('approved-input.json',approved[name])
        if reference_repair:ctx.save('reference-metadata-handoff.json',reference_repair)
        ctx.save_text('README.md',Path(__file__).with_name('generation-variant-readme.md').read_text())
        try:
            runtime_settings=config if isinstance(config,dict) else read(config)
            planning_latest=latest
            if runtime_settings.get('perturbation_policy') and index==1 and value_ready is not None:
                planning_latest={**latest,0:value_ready.result()}
            plan=g01_perturbation.run(ctx,sample,program,graph,index,planning_latest,build,policy=runtime_settings.get('ea_recovery_policy'),perturbation_policy=runtime_settings.get('perturbation_policy'))
            result.update(plan=plan,restart='02-generate-text')
            prior = latest.get(index, {})
            same_relation_plan = index != 4 or digest(prior.get('plan', {})) == digest(plan)
            if same_relation_plan and prior.get('recovery', {}).get('target_step') == '03-validation' and all(key in prior for key in ('generation_request','generation_response','observation','patches')):
                import shutil
                shutil.copytree(bundle/prior['path']/'02-generate-text', root/'02-generate-text')
                request,response,observation,patches = [deepcopy(prior[key]) for key in ('generation_request','generation_response','observation','patches')]
                result.update(generation_request=request,generation_response=response,observation=observation,patches=patches)
                ctx.save('02-generate-text/reuse.json', {'source':prior['path'],'reason':'FEEDBACK_TARGETS_VERIFICATION'})
                if index == 0 and value_ready is not None and not value_ready.done(): value_ready.set_result(deepcopy(result))
            else:
                request,response,observation,patches=g02_generate_text.run(ctx,config,bundle,root,name,index,axis,sample,plan,latest,result,value_ready,invoke,digest,check_response)
            result['restart'] = '03-validation' 
            g03_verification.run(ctx,config,sample,plan,request,response,observation,patches,axis,label,index,latest,result,digest,audit_one)
        except (Exception,) as error:
            reason=error.result.reason if isinstance(error,StepStopped) else type(error).__name__+': '+str(error)
            result.update(status='FAIL',reason=reason)
            if any(code in reason for code in ('NO_ADMISSIBLE_COEFFICIENT','COEFFICIENT_BINDING','COEFFICIENT_PARENT','PERTURBATION_POLICY')):
                result.update(retryable=False,disposition='COEFFICIENT_POLICY_BLOCKED')
            if index==0 and value_ready is not None and not value_ready.done():
                value_ready.set_result(deepcopy(result))
            if any(code in reason for code in ('EA_VALUE_PRESENT_IN_QUESTION','MISSING_SECOND_EA_INPUT')):
                result.update(retryable=False,disposition='REQUIRES_PLAN_REVIEW')
            ctx.save(result['restart']+'/failure.json',{'status':'FAIL','reason':reason})
        ctx.save('run.json',result)
    return result


def feedback_one(round_dir,item,config):
    if item.get('recovery'):
        return
    axis=item['axis'];name=item['case'];label=item['label']
    folder=next(folder for folder,a,l in TYPES if a==axis and l==label)
    directory=round_dir/name/folder/'feedback'
    result_path=directory/'02-result.json'
    evidence={'case':name,'label':label,'reason':item.get('reason',''),
              'response':{'generated':item.get('generation_response'),'audit':item.get('audit',{})},
              'request':item.get('generation_request',item.get('plan',{}).get('request',{}))}
    identity=digest(evidence)
    path=directory/'02-generation.02-generate-text.realization'/f'{axis.lower()}.json'
    if result_path.exists():
        saved=read(result_path)
        if saved.get('evidence_sha256')!=identity:raise ValueError('CASE_FEEDBACK_EVIDENCE_CHANGED')
        write(path,saved);return
    if (directory/'01-LLM-build-feedback').exists():
        archive=directory.with_name('feedback-interrupted-'+str(len(list(directory.parent.glob('feedback-interrupted-*')))+1))
        directory.rename(archive)
    instructions,_=prepare_instruction('02-generation.02-generate-text.realization',{'axis':axis})
    payload={'axis':axis,'target_role':'02-generation.02-generate-text.realization','feedback_scope':'single_case_variant',
             'common_and_type_instructions':instructions,'previous_guidance':'','failures':[evidence]}
    call_dir=directory/'build-attempt'
    if call_dir.exists():
        archive=directory/('build-interrupted-'+str(len(list(directory.glob('build-interrupted-*')))+1))
        call_dir.rename(archive)
    ctx=RunContext(call_dir,{},name)
    with ctx.trace.activate():
        ctx.save('00-evidence.json',evidence)
        write(directory/'00-evidence.json',evidence)
        value=invoke(ctx,config,'01-LLM-build-feedback','02-generation.feedback.case-feedback',payload)
        merged={**value,'axis':axis,'target_role':'02-generation.02-generate-text.realization','version':1,
                'case':name,'label':label,'evidence_round':round_dir.name,'evidence_sha256':identity}
        ctx.save('02-result.json',merged);write(result_path,merged);write(path,merged)
        ctx.save_text('FEEDBACK.md','Read 00-evidence.json, the schema-bound call, then 02-result.json. This feedback is only for this case and variant. The next retry records its source and hash in feedback/01-applied.json.\n')


def run_round(bundle, round_dir, name, indices, config, approved, latest, *, resume=False, on_result=None):
    """One case: independent variants first, then dependent source variants."""
    indices=expand(indices); snapshot=deepcopy(latest); results={}
    value_ready=Future()
    if 0 not in indices:value_ready.set_result(snapshot.get(0,{}))
    def variant(index):
        stored=round_dir/name/TYPES[index][0]/'run.json'
        try:
            result=restore_saved_result(stored) if resume and stored.exists() else process(bundle,round_dir,name,index,config,approved,snapshot,value_ready if index in (0,1) else None)
            return result
        finally:
            if index==0 and not value_ready.done():value_ready.set_result(locals().get('result',{}))
    load_run = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['load_run']).load_run
    variant_workers=load_run('generation',read(config).get('hyperparameter_path'))['variant_concurrency']
    for phase in ([i for i in indices if i not in (2,3)],[i for i in indices if i in (2,3)]):
        for index,result in completed(phase,variant,variant_workers):
            results[index]=result
            if on_result:on_result(index,result)
        snapshot.update(deepcopy(results))
    return results


def run(bundle, name, *, round_name='01-round', indices=None, start_stage=None, stop_after=None, only_stage=None, approved=None):
    GENERATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['GENERATION']).GENERATION
    select = __import__('finarch.dataset.90-operations.stage_range', fromlist=['select']).select
    selected=select(GENERATION,start_stage,stop_after,only_stage)
    return execute(bundle,round_name,[name],list(range(7)) if indices is None else indices,selected,approved=approved)

GENERATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['GENERATION']).GENERATION
begin = __import__('finarch.dataset.90-operations.stage_range', fromlist=['begin']).begin
finish = __import__('finarch.dataset.90-operations.stage_range', fromlist=['finish']).finish
require = __import__('finarch.dataset.90-operations.stage_range', fromlist=['require']).require

def execute(bundle, round_name, names, indices, selected, *, approved=None):
    driver=import_module('finarch.dataset.02-generation.generate_run')
    bundle=Path(bundle).resolve()
    approved=deepcopy(approved) if approved is not None else require_generation_inputs(bundle, persist=False)
    if Path(round_name).name!=round_name or not round_name.endswith('-round') or not round_name[:-6].isdigit():raise ValueError('INVALID_ROUND')
    names=names or list(approved)
    if len(set(names))!=len(names) or any(n not in approved for n in names):raise ValueError('INVALID_CASE_SELECTION')
    round_dir=bundle/'02-generation'/round_name;results=[]
    runtime_config=round_dir/names[0]/'runtime-config.json'
    bind = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['bind']).bind
    settings=bind(read(bundle/'config.json'),bundle);settings['run_phase']='generation'
    if settings.get('profiles_path'):settings['profiles_path']=str((bundle/settings['profiles_path']).resolve())
    write(runtime_config,settings)
    for name in names:
        source=bundle/approved[name]['case_path']
        values=require(source,['data.json','03-calculation/02-prepare-code/03-program.json','04-graph/04-save-graph/01-graph.json'])
        sample,reference_repair=generation_sample(source);program=values['03-calculation/02-prepare-code/03-program.json'];graph=values['04-graph/04-save-graph/01-graph.json']
        latest={i:read(round_dir/name/folder/'run.json') for i,(folder,_,_) in enumerate(driver.TYPES) if (round_dir/name/folder/'run.json').exists()}
        latest={i:v for i,v in latest.items() if v.get('status')!='STALE'}
        for index in sorted(indices):
            folder,axis,label=driver.TYPES[index];root=round_dir/name/folder
            previous=latest.get(index,{})
            if selected[0]!='01-perturbation' and not previous.get('plan'):raise ValueError('PREREQUISITE_MISSING: plan '+name+'/'+folder)
            if '02-generate-text' in selected and index in (1,2,3):
                dependency=1 if index==3 else 0
                if not latest.get(dependency,{}).get('observation'):raise ValueError('VALUE_DEPENDENCY_REQUIRED:'+driver.TYPES[dependency][0])
            if selected[0] in ('03-validation','05-human-review'):
                for key in ('generation_request','generation_response','observation','patches'):
                    if key not in previous:raise ValueError('PREREQUISITE_MISSING:'+key)
                expected=read(root/'approved-input.json')
                if expected!=approved[name]:raise ValueError('APPROVED_INPUT_CHANGED')
            if selected[0]=='05-human-review' and 'audit' not in previous:raise ValueError('VALIDATION_REQUIRED')
            ctx=begin(root,GENERATION,selected,name)
            result=deepcopy(previous) if selected[0]!='01-perturbation' else {}
            for key in ('audit','reason'):result.pop(key,None) if GENERATION.index(selected[0])<=2 else None
            result.update(label=label,axis=axis,path=str(root.relative_to(bundle)),round=round_name,status='RUNNING')
            with ctx.trace.activate():
                if not (root/'approved-input.json').exists():ctx.save('approved-input.json',approved[name])
                if reference_repair:ctx.save('reference-metadata-handoff.json',reference_repair)
                try:
                    plan=result.get('plan')
                    for stage in selected:
                        result['restart']=stage
                        if stage=='01-perturbation':
                            plan=g01_perturbation.run(ctx,sample,program,graph,index,latest if settings.get('perturbation_policy') else {},driver.build,policy=settings.get('ea_recovery_policy'),perturbation_policy=settings.get('perturbation_policy'));result['plan']=plan
                        elif stage=='02-generate-text':
                            g02_generate_text.run(ctx,runtime_config,bundle,root,name,index,axis,sample,plan,latest,result,None,driver.invoke,driver.digest,driver.check_response)
                        elif stage=='03-validation':
                            g03_verification.run(ctx,runtime_config,sample,plan,result['generation_request'],result['generation_response'],result['observation'],result['patches'],axis,label,index,latest,result,driver.digest,driver.audit_one)
                            if result['status']!='PASS':break
                        else:g05_human_review.run(bundle,result)
                    if result['status']=='RUNNING':result.update(status='PAUSED',reason='REQUESTED_STAGE_BOUNDARY')
                    elif selected[-1]=='03-validation' and result['status']=='PASS':result['reason']='VALIDATION_COMPLETED'
                except Exception as error:
                    result.update(status='FAIL',reason=str(error))
                    if any(code in str(error) for code in ('NO_ADMISSIBLE_COEFFICIENT','COEFFICIENT_BINDING','COEFFICIENT_PARENT','PERTURBATION_POLICY')):
                        result.update(retryable=False,disposition='COEFFICIENT_POLICY_BLOCKED')
                if result.get('status') == 'FAIL' and result.get('disposition')!='COEFFICIENT_POLICY_BLOCKED':
                    try:
                        result['recovery'] = g04_exception_handler.run(ctx, runtime_config, result, name)
                        result['retryable'] = result['recovery']['retryable']
                    except Exception as handler_error:
                        result['recovery'] = {'retryable': False, 'handler_error': str(handler_error)}
                        result['retryable'] = False
                        ctx.save('04-exception-handler/handler-failure.json', result['recovery'])
                finish(ctx,result,selected)
            latest[index]=result;results.append(result)
            # Dependent variants cannot retain a current verdict after value text changes.
            if index in (0,1) and GENERATION.index(selected[0])<=1:
                for dependent in ((1,2,3) if index==0 else (3,)):
                    if dependent in latest:
                        item=latest.pop(dependent);path=bundle/item['path']/'run.json'
                        write(path.with_name('superseded-by-value-change.json'),item)
                        write(path,{**item,'status':'STALE','reason':'VALUE_DEPENDENCY_CHANGED'})
    # Saved per-variant records are authoritative in the viewer; summaries must not
    # continue claiming an older completed batch after an explicit stage edit.
    write(round_dir/name/'stage-summary.json',{'status':'PAUSED','selected_stages':list(selected),'results':results,'reason':'EXPLICIT_STAGE_EXECUTION'})
    return {'run':str(bundle),'status':'FAIL' if any(r['status']=='FAIL' for r in results) else 'PAUSED','results':results}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Execute one generation case')
    parser.add_argument('--run',required=True);parser.add_argument('--case',required=True)
    parser.add_argument('--round',default='01-round')
    parser.add_argument('--start-stage');parser.add_argument('--stop-after');parser.add_argument('--only-stage')
    args=parser.parse_args()
    print(json.dumps(run(args.run,args.case,round_name=args.round,start_stage=args.start_stage,stop_after=args.stop_after,only_stage=args.only_stage)))
