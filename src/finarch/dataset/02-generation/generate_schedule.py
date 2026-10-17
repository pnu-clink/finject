scheduler_owned = __import__('finarch.dataset.90-operations.schedule_lock', fromlist=['scheduler_owned']).scheduler_owned
schedule_lock = __import__('finarch.dataset.90-operations.schedule_lock', fromlist=['schedule_lock']).schedule_lock
"""Generate seven variants from human-approved inputs with bounded feedback rounds."""
import argparse
from concurrent.futures import Future
from queue import SimpleQueue, Empty
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


from importlib import import_module
_driver=import_module('finarch.dataset.02-generation.generate_run')
process=_driver.process
feedback_one=_driver.feedback_one
schedule_cases = __import__('finarch.dataset.90-operations.adaptive_schedule', fromlist=['run']).run
load_schedule = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['load']).load
schedule_for_config = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['for_config']).for_config

def feedback(bundle,round_dir,failures,config):
    items=[item for item in failures if item['restart']=='02-generate-text' and item.get('retryable',True)]
    keys=[(item['case'],item['label']) for item in items]
    if len(keys)!=len(set(keys)):raise ValueError('DUPLICATE_CASE_FEEDBACK')
    workers=schedule_for_config('feedback',config)['initial_concurrency']
    for _,_result in completed(items,lambda item: feedback_one(round_dir,item,config),workers):
        pass


@scheduler_owned
def run(bundle, maximum_rounds=None, resume=False):
    bundle=Path(bundle).resolve()
    if maximum_rounds is None:maximum_rounds=schedule_for_config('generation',bundle/'config.json')['max_rounds']
    if type(maximum_rounds) is not int or not 1<=maximum_rounds<=3:raise ValueError('INVALID_ROUND_LIMIT')
    bind = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['bind']).bind
    settings=bind(read(bundle/'config.json'),bundle,resume=resume)
    approved=require_generation_inputs(bundle, persist=True)
    if not approved:raise ValueError('NO_APPROVED_INPUTS')
    generation=bundle/'02-generation'
    existing=sorted(generation.glob('0[123]-round'))
    if existing and not resume:raise ValueError('GENERATION_ALREADY_STARTED')
    if resume and not existing:raise ValueError('EXISTING_GENERATION_REQUIRED')
    if resume and (generation/'timing.json').exists() and read(generation/'timing.json').get('status')=='COMPLETED':raise ValueError('GENERATION_ALREADY_COMPLETED')
    config=generation/'runtime-config.json'
    settings['run_phase']='generation'
    if settings.get('profiles_path'):settings['profiles_path']=str((bundle/settings['profiles_path']).resolve())
    write(config,settings)
    latest={name:{} for name in approved};pending={name:list(range(7)) for name in approved};history=[]
    generation.mkdir(exist_ok=True)
    (generation/'README.md').write_text(Path(__file__).with_name('generation-variant-readme.md').read_text())
    first_round=1;resume_feedback=None
    if resume:
        first_round=int(existing[-1].name[:2])
        for directory in existing:
            for name in approved:
                for index,(folder,_,_) in enumerate(TYPES):
                    record=directory/name/folder/'run.json'
                    if record.exists():latest[name][index]=read(record)
            verdict=directory/'final-validator.json'
            if verdict.exists():
                v=read(verdict);history.append({k:v[k] for k in ('round','decision','failure_count')})
        finished=(existing[-1]/'final-validator.json').exists()
        if finished:
            previous=existing[-1]/'final-validator.json'
            if read(previous)['decision']=='RETRY':
                resume_feedback=existing[-1];first_round+=1
            else:first_round=maximum_rounds+1
        elif first_round>1:previous=existing[-2]/'final-validator.json'
        else:previous=None
        if previous is not None:
            failures=read(previous)['failures']
            pending={name:[i for i,(_,_,label) in enumerate(TYPES) if any(f['case']==name and f['label']==label and f.get('retryable',True) for f in failures)] for name in approved}
            pending={name:items for name,items in pending.items() if items}
        archive=generation/'interrupted-attempts'/f'resume-{len(list((generation/"interrupted-attempts").glob("resume-*")))+1:02d}'
        archive.mkdir(parents=True)
        for name in approved:
            for folder,_,_ in TYPES:
                candidate=existing[-1]/name/folder
                if candidate.exists() and not (candidate/'run.json').exists():
                    target=archive/name/folder;target.parent.mkdir(parents=True,exist_ok=True);candidate.rename(target)
        for path in (generation/'timing.json',existing[-1]/'timing.json'):
            if path.exists():
                target=archive/path.relative_to(generation);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
        for candidate in (existing[-1]/'feedback').glob('*'):
            if candidate.is_dir() and not (candidate/'02-result.json').exists():
                target=archive/'feedback'/candidate.name;target.parent.mkdir(parents=True,exist_ok=True);candidate.rename(target)
        write(archive/'resume.json',{'round':first_round,'completed_variants_reused':True,'incomplete_variants_archived':True,'final_response_may_be_absent_for_cancelled_calls':True})
        (archive/'README.md').write_text('The unfinished type and time record at the time of the interruption. The completed type is kept in the original array, and only the unfinished one is reset to a new call. The canceled call may not have a final response.\n')
    with measure(generation,'generation'):
        if resume_feedback is not None:
            feedback(bundle,resume_feedback,read(resume_feedback/'final-validator.json')['failures'],config)
        for number in range(first_round,maximum_rounds+1):
            if require_generation_inputs(bundle)!=approved:raise ValueError('APPROVED_INPUTS_CHANGED')
            round_dir=generation/f'{number:02d}-round';round_dir.mkdir(exist_ok=resume and number==first_round)
            with measure(round_dir,'round'):
                state={'status':'RUNNING','cases':{}}
                events=SimpleQueue()
                def flush_results():
                    while True:
                        try:name,index,result=events.get_nowait()
                        except Empty:break
                        latest[name][index]=result
                        state["cases"].setdefault(name,{})[result["label"]]={k:result.get(k, "") for k in ("status","reason","path")}
                    write(round_dir/"progress.json",state)
                def monitor(value):
                    flush_results()
                    record_queue(round_dir/"queue.json",value)
                scheduling=schedule_for_config('generation',config)
                write(round_dir/'schedule-settings.json',scheduling)
                def run_case_variants(name):
                    def on_result(index,result):
                        events.put((name,index,result))
                    return _driver.run_round(bundle,round_dir,name,pending[name],config,approved,latest[name],
                        resume=resume and number==first_round,on_result=on_result)
                for name,result in schedule_cases(list(pending),run_case_variants,settings=scheduling,
                        monitor=monitor):
                    if isinstance(result,dict) and result.get('status')=='FAIL':raise RuntimeError(result['reason'])
                failures=[{'case':name,**item} for name,items in latest.items() for item in items.values() if item['status']!='PASS']
                retryable=[item for item in failures if item.get('retryable',True)]
                decision='PASS' if not failures else 'RETRY' if retryable and number<maximum_rounds else 'LIMIT_REACHED' if retryable else 'REQUIRES_PLAN_REVIEW'
                verdict={'round':number,'decision':decision,'failure_count':len(failures),'failures':failures}
                write(round_dir/'final-validator.json',verdict);history.append({'round':number,'decision':decision,'failure_count':len(failures)})
                state['status']='FINISHED';write(round_dir/'progress.json',state)
                write(generation/'summary.json',{'status':decision,'rounds':history,'latest':latest})
                if decision!='RETRY':break
                feedback(bundle,round_dir,failures,config)
                pending={name:[i for i,item in items.items() if item['status']!='PASS' and item.get('retryable',True)] for name,items in latest.items()}
                pending={name:items for name,items in pending.items() if items}
        for name,items in latest.items():
            for item in items.values():
                __import__('finarch.dataset.02-generation.05-human-review.stage',fromlist=['collect']).collect(bundle,item)
    result={'status':history[-1]['decision'] if history else 'NO_APPROVED_INPUTS','rounds':history,'latest':latest}
    write(generation/'summary.json',result)
    from finarch.dataset.viewer.reports.completion_report import build as build_completion_report
    from finarch.dataset.viewer.reports.phase_report import publish
    publish(bundle, 'generation')
    build_completion_report(bundle)
    # Archive after the entire scheduler and review-material collection finish.
    consolidate = import_module('finarch.dataset.03-release.publication.consolidate')
    result['generated_dataset'] = {key: value for key, value in consolidate.publish(bundle).items()
                                  if key in ('output', 'counts', 'annotation_state', 'changed')}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True);parser.add_argument('--maximum-rounds',type=int,default=None)
    parser.add_argument('--analysis-job', help='Interpret a confirmed failure snapshot without rerunning production')
    parser.add_argument('--retry-job')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--start-stage');parser.add_argument('--stop-after');parser.add_argument('--only-stage')
    parser.add_argument('--cases',nargs='+');parser.add_argument('--types',nargs='+',choices=[t[0] for t in TYPES])
    parser.add_argument('--round',default='01-round');parser.add_argument('--plan-only',action='store_true')
    args=parser.parse_args()
    if args.analysis_job:
        if not args.run:parser.error('--run is required with --analysis-job')
        if args.retry_job:parser.error('--analysis-job and --retry-job are exclusive')
        execute = __import__('finarch.dataset.90-operations.failure_analysis', fromlist=['execute']).execute
        print(json.dumps(execute(args.run,args.analysis_job,'generation')),flush=True)
        raise SystemExit(0)
    if args.retry_job:
        execute = __import__('finarch.dataset.90-operations.failed_recheck', fromlist=['execute']).execute
        print(json.dumps(execute(args.run,args.retry_job,'generation')))
        raise SystemExit(0)
    if args.start_stage or args.stop_after or args.only_stage:
        if args.resume:parser.error('--resume cannot be combined with explicit stages')
        GENERATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['GENERATION']).GENERATION
        select = __import__('finarch.dataset.90-operations.stage_range', fromlist=['select']).select
        selected=select(GENERATION,args.start_stage,args.stop_after,args.only_stage)
        indices=[i for i,t in enumerate(TYPES) if not args.types or t[0] in args.types]
        if args.plan_only:result={'selected_stages':selected,'cases':args.cases,'types':[TYPES[i][0] for i in indices],'round':args.round,'model_calls_started':0}
        else:
            with schedule_lock(args.run):
                approved=require_generation_inputs(Path(args.run), persist=True)
                names=args.cases or list(approved)
                if len(names)!=len(set(names)) or any(n not in approved for n in names):raise ValueError('INVALID_CASE_SELECTION')
                config=read(Path(args.run)/'config.json')
                results=[]
                for name,item in schedule_cases(names,lambda name:_driver.run(args.run,name,round_name=args.round,indices=indices,start_stage=selected[0],stop_after=selected[-1],approved=approved),
                        settings=schedule_for_config('generation',Path(args.run)/'config.json'),
                        monitor=lambda value:record_queue(Path(args.run)/'02-generation/queue.json',value)):
                    results.append({'case':name,**item})
                result={'status':'PAUSED','results':results}
                write(Path(args.run)/'02-generation/selected-summary.json',result)


    else:
        if args.cases or args.types or args.plan_only:parser.error('Stage options required for selective execution')
        result=run(args.run,args.maximum_rounds,args.resume)
    print(json.dumps(result))
