"""Run source preparation for a selected batch, ending at human review."""
import argparse
import json
from pathlib import Path

measure = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['measure']).measure
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
allocate_run = __import__('finarch.dataset.90-operations.run_identity', fromlist=['allocate_run']).allocate_run
PreparedInputs = __import__('finarch.dataset.90-operations.staging', fromlist=['PreparedInputs']).PreparedInputs
prepare_batch = __import__('finarch.dataset.01-preparation.preparation_pipeline', fromlist=['prepare_batch']).prepare_batch
from finarch.shared.providers.profiles import selected_profile


def plan(input_path, config, cases=None):
    inputs = PreparedInputs(Path(input_path))
    names = list(cases) if cases else list(inputs.samples)
    if not names or len(names) != len(set(names)) or any(name not in inputs.samples for name in names):
        raise ValueError('INVALID_PREPARATION_SELECTION')
    from finarch.shared.providers.roles import normalize_config
    settings = normalize_config(json.loads(Path(config).read_text()))
    for_config = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['for_config']).for_config
    load_run = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['load_run']).load_run
    scheduling=for_config('preparation',config)
    settings['run_phase']='preparation'
    settings['parallelism']={stage:for_config(stage,config)['initial_concurrency'] for stage in ('preparation','generation')}
    settings['preparation_revision_attempts']=load_run('preparation',settings.get('hyperparameter_path'))['revision_attempts']
    maximum = settings.get('preparation_revision_attempts', 0)
    if type(maximum) is not int or not 0 <= maximum <= 3:
        raise ValueError('INVALID_PREPARATION_REVISION_LIMIT')
    profiles = (Path(config).resolve().parent / settings.get('profiles_path', 'codex-profiles.toml')).resolve()
    roles = {}
    for role in ('01-preparation.05-verification.semantic', 'shared.01-06.02-04.exception-handler', 'shared.01-02.02-03.review-and-validation', '01-preparation.02-review-and-correct.revision', '01-preparation.03-calculation.pot', '01-preparation.03-calculation.review-answer-evidence'):
        if settings.get('use_model_selection'):
            profile = selected_profile(profiles, role, phase="preparation")
            roles[role] = {key: profile[key] for key in ('provider', 'model', 'effort', 'id')}
        else:
            roles[role] = {'provider': settings['provider'], **settings['roles'][role]}
    estimate = {'parallelism': settings['parallelism'], 'cases': names, 'case_count': len(names), 'roles': roles,
                'revision_attempts': maximum,
                'maximum_model_calls': len(names) * scheduling['max_rounds'] * 4,
                'max_rounds': scheduling['max_rounds'],
                'maximum_handler_calls': len(names) * scheduling['max_rounds'],
                'cost': None, 'cost_note': 'Billing price unavailable; record actual usage.',
                'schedule':scheduling,
                'stop_after': 'preparation_human_review', 'generation_started': False}
    return inputs, settings, profiles, estimate


def run(input_path, config, cases=None, runs_root='reports/run'):
    PREPARATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['PREPARATION']).PREPARATION
    return run_selected(input_path,config,cases,PREPARATION,runs_root=runs_root)


def run_selected(input_path, config, cases, selected, bundle=None, plan_only=False, runs_root="reports/run", *, resume=False):
    read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
    explicit_cases=bool(cases)
    if resume and not bundle:raise ValueError('RESUME_REQUIRES_RUN')
    if bundle:
        bundle=Path(bundle).resolve()
        stored=read(bundle/'input-selection.json')
        input_path=input_path or stored['input_path']
        config=str(bundle/'config.json')
        cases=cases or stored['cases']
        if resume and not explicit_cases:
            state_path=bundle/'01-preparation/schedule-state.json'
            if state_path.exists():
                state=read(state_path)
                pending=set(state['pending_ids']+state['running_ids'])
                cases=[n for n in cases if n in pending]
            else:
                cases=[n for n in cases if not (bundle/'01-preparation'/n/'run.json').exists()
                       or read(bundle/'01-preparation'/n/'run.json').get('status') not in ('PASS','FAIL','ERROR')]
            if not cases:
                return {'run':str(bundle),'status':'NO_UNFINISHED_CASES','scheduled_cases':[],'model_calls':0}
    inputs,settings,profiles,estimate=plan(input_path,config,cases)
    estimate.update(selected_stages=list(selected),stop_after=selected[-1])
    if plan_only:return estimate
    if bundle is None:
        if selected[0]!='01-source':raise ValueError('EXISTING_RUN_REQUIRED_FOR_MIDDLE_STAGE')
        bundle=allocate_run(runs_root)
    schedule_lock = __import__('finarch.dataset.90-operations.schedule_lock', fromlist=['schedule_lock']).schedule_lock
    with schedule_lock(bundle):
        # Preserve the scheduler's phase and resolved settings for actual calls.
        settings['profiles_path']=str(profiles)
        runtime_config=bundle/'01-preparation/runtime-config.json'
        write(runtime_config,settings)
        config=str(runtime_config)
        if not (bundle/'config.json').exists():
            settings['profiles_path']=str(profiles)
            write(bundle/'config.json',settings)
            write(bundle/'input-selection.json',{'cases':estimate['cases'],'input_path':str(Path(input_path).resolve())})
            config=bundle/'config.json'
        print(json.dumps(estimate),flush=True)
        schedule_cases = __import__('finarch.dataset.90-operations.adaptive_schedule', fromlist=['run']).run
        record_queue=__import__('finarch.dataset.02-generation.operations.parallel_scheduler',fromlist=['record_queue']).record_queue
        CaseQueue = __import__('finarch.dataset.01-preparation.prepare_queue', fromlist=['CaseQueue']).CaseQueue
        queue=CaseQueue(bundle,inputs,estimate['cases'],selected,resume=resume,explicit=explicit_cases)
        estimate['scheduled_cases']=queue.targets
        write(bundle/'plan.json',estimate)
        (bundle/'README.md').write_text(Path(__file__).with_name('preparation-batch-readme.md').read_text())
        for_config = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['for_config']).for_config
        scheduling=for_config('preparation',config)
        write(bundle/'schedule-settings.json',scheduling)
        def monitor(value):
            queue.observe(value.get('active_cases',[]))
            record_queue(bundle/'01-preparation/queue.json',value)
        try:
            with measure(bundle,'preparation'):
                for name,result in schedule_cases(queue.targets,lambda name:run_case_rounds(inputs,name,bundle/'01-preparation'/name,config,selected,scheduling),
                        settings=scheduling,monitor=monitor):
                    if result.get('worker_exception'):
                        result.update(input_id=name,status='ERROR')
                        write(bundle/'01-preparation'/name/'run.json',result)
                    queue.complete(name)
                    write(bundle/'01-preparation/summary.json',queue.summary())
        except BaseException:
            queue.close(interrupted=True)
            write(bundle/'01-preparation/summary.json',queue.summary())
            raise
        queue.close()
        summary=queue.summary()
        write(bundle/'01-preparation'/'summary.json',summary)
        evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
        evaluate(bundle, persist=True)
        from finarch.dataset.viewer.reports.phase_report import publish
        publish(bundle, 'preparation')
        from finarch.dataset.viewer.reports.timing_report import build as timing_report
        timing_report(bundle)
        return {'run':str(bundle),**summary}


def run_case_rounds(inputs, name, root, config, selected, scheduling):
    """Each immutable attempt lives in case/NN-round; root stores only indexes."""
    import shutil
    from hashlib import sha256
    from importlib import import_module
    PREPARATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['PREPARATION']).PREPARATION
    load_feedback = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['load']).load
    runner = import_module('finarch.dataset.01-preparation.prepare_run').run
    use_feedback = import_module('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context').use_feedback
    maximum=scheduling['max_rounds']
    if type(maximum) is not int or maximum<1:raise ValueError('INVALID_MAX_ROUNDS')
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    history=[];previous=None;target=None;reference=None
    for number in range(1,maximum+1):
        round_name=f'{number:02d}-round';round_root=root/round_name
        round_root.mkdir(exist_ok=False)
        directory=round_root/'00-round-input/feedback'
        seed={'case':name,'round':round_name,'reuse_before':target,'artifacts':[]}
        if previous:
            for step in PREPARATION[:PREPARATION.index(target)]:
                if (previous/step).is_dir():shutil.copytree(previous/step,round_root/step)
            if PREPARATION.index(target)>=2:
                for filename in ('data.json','reference-data.json','data-comparison.json'):
                    if (previous/filename).is_file():shutil.copy2(previous/filename,round_root/filename)
            for dest in sorted(round_root.rglob('*')):
                if not dest.is_file():continue
                relative=dest.relative_to(round_root);source=previous/relative
                digest=sha256(source.read_bytes()).hexdigest()
                if sha256(dest.read_bytes()).hexdigest()!=digest:raise ValueError('REUSED_ARTIFACT_HASH_MISMATCH')
                seed['artifacts'].append({'status':'REUSED','source':str(source.resolve()),'path':str(relative),'sha256':digest})
            load_feedback(reference,case=name,target_round=round_name)
            write(directory/reference['target_role']/'answer.json',{'feedback_refs':[reference]})
        write(round_root/'00-round-input/seed.json',seed)
        write(root/'run.json',{'input_id':name,'status':'RUNNING','layout':'preparation-generation-v2',
                              'active_round':round_name,'rounds':history,'human_decision':'PENDING'})
        with use_feedback(directory,case=name,target_round=round_name):
            result=runner(inputs,name,round_root,config,start_stage=selected[0],stop_after=selected[-1],
                          round_number=number,reuse_before=target)
        recovery=result.get('recovery',{})
        should_retry=result['status']=='FAIL' and recovery.get('retryable')
        if should_retry and recovery.get('target_step') not in selected:
            should_retry=False;recovery.update(retryable=False,reason='OUTSIDE_REQUESTED_STAGE_BOUNDARY')
        if should_retry and number==maximum:result['retry_limit_reached']=True;should_retry=False
        if not should_retry and result['status']=='FAIL':_record_unresolved(round_root,result)
        write(round_root/'run.json',result)
        history.append({'round':round_name,'status':result['status'],'stopped_at':result.get('stopped_at'),
                        'path':f'{round_name}/run.json','reused_steps':result.get('reused_steps',[])})
        result={**result,'layout':'preparation-generation-v2','active_round':round_name,'rounds':list(history)}
        write(root/'run.json',result)
        (root/'README.md').write_text(Path(__file__).with_name('preparation-case-rounds-readme.md').read_text())
        if not should_retry:return result
        previous=round_root;target=recovery['target_step'];reference=recovery['feedback_ref']
    return result


def _record_unresolved(root, result):
    result['human_decision'] = 'PENDING'
    write(root/'07-human-review/01-collect-review-package/01-result.json', dict(result))
    write(root/'07-human-review/review-note.json',
          {'status': 'UNRESOLVED', 'reason': 'Automatic processing ended without approval.'})

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input')
    parser.add_argument('--analysis-job', help='Interpret a confirmed failure snapshot without rerunning production')
    parser.add_argument('--retry-job', help='Resume the snapshotted failed targets in this run')
    parser.add_argument('--run', help='Existing run for a selected stage range')
    parser.add_argument('--resume',action='store_true',help='Queue unfinished case IDs and restart them from source')
    parser.add_argument('--start-stage')
    parser.add_argument('--stop-after')
    parser.add_argument('--only-stage')
    parser.add_argument('--config', default='config/llm.json')
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--cases-file',help='JSON array of case IDs to register for a fresh per-case restart')
    parser.add_argument('--plan-only', action='store_true')
    args = parser.parse_args()
    if args.cases_file:
        if args.cases:parser.error('--cases and --cases-file are exclusive')
        args.cases=json.loads(Path(args.cases_file).read_text())
        if not isinstance(args.cases,list) or not args.cases or any(not isinstance(n,str) for n in args.cases):
            parser.error('--cases-file must contain a nonempty JSON array of case IDs')
    if args.resume and (not args.run or args.retry_job or args.analysis_job):
        parser.error('--resume requires --run and cannot be combined with analysis/recheck jobs')
    if args.analysis_job:
        if not args.run:parser.error('--run is required with --analysis-job')
        if args.retry_job:parser.error('--analysis-job and --retry-job are exclusive')
        execute = __import__('finarch.dataset.90-operations.failure_analysis', fromlist=['execute']).execute
        print(json.dumps(execute(args.run,args.analysis_job,'preparation')),flush=True)
        return
    if args.retry_job:
        if not args.run:parser.error('--run is required with --retry-job')
        execute = __import__('finarch.dataset.90-operations.failed_recheck', fromlist=['execute']).execute
        print(json.dumps(execute(args.run,args.retry_job,'preparation')),flush=True)
        return
    if args.run or args.start_stage or args.stop_after or args.only_stage:
        PREPARATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['PREPARATION']).PREPARATION
        select = __import__('finarch.dataset.90-operations.stage_range', fromlist=['select']).select
        selected=select(PREPARATION,args.start_stage,args.stop_after,args.only_stage)
        if args.resume and not any((args.start_stage,args.stop_after,args.only_stage)):
            state_path=Path(args.run)/'01-preparation/schedule-state.json'
            if state_path.exists():selected=tuple(json.loads(state_path.read_text())['selected_stages'])
        result=run_selected(args.input,args.config,args.cases,selected,args.run,args.plan_only,resume=args.resume)
    else:
        if not args.input:parser.error('--input is required')
        result = plan(args.input, args.config, args.cases)[3] if args.plan_only else run(args.input, args.config, args.cases)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
