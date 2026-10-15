"""Run a disjoint batch with explicitly delegated Preparation approval."""
import argparse
import json
import threading
from datetime import datetime
from pathlib import Path
PreparedInputs = __import__('finarch.dataset.90-operations.staging', fromlist=['PreparedInputs']).PreparedInputs
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
record_decision = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['record_decision']).record_decision
evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
measure = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['measure']).measure
allocate_run = __import__('finarch.dataset.90-operations.run_identity', fromlist=['allocate_run']).allocate_run
preparation_results = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['preparation_results']).preparation_results
plan = __import__('finarch.dataset.01-preparation.prepare_schedule', fromlist=['plan']).plan
run_case = __import__('finarch.dataset.01-preparation.preparation_pipeline', fromlist=['run_case']).run_case
generate = __import__('finarch.dataset.02-generation.generate_schedule', fromlist=['run']).run
from finarch.dataset.viewer.reports.generation_report import build as report

QUOTAS={'finance-easy':9,'finance-medium':6,'finance-hard':3,'tatqa-dev':12}


def select(input_path,exclude_path):
    source=PreparedInputs(Path(input_path));excluded=PreparedInputs(Path(exclude_path))
    old_ids={s['raw_id'] for s in excluded.samples.values()}
    old_texts={(s['context'],s['question']) for s in excluded.samples.values()}
    names=[];counts={k:0 for k in QUOTAS}
    for name,s in source.samples.items():
        category=source.providers[s['raw_id']]['source']
        if s['raw_id'] in old_ids or (s['context'],s['question']) in old_texts:continue
        if counts[category]<QUOTAS[category]:names.append(name);counts[category]+=1
    if counts!=QUOTAS:raise ValueError('INSUFFICIENT_DISJOINT_INPUTS')
    return source,names,{'source_counts':counts,'excluded_raw_ids':sorted(old_ids),'selected':[{'id':n,'raw_id':source.samples[n]['raw_id']} for n in names],'overlap_with_previous_ten':0}


def run(input_path,exclude_path,config,all_inputs=False,hyperparameters=None):
    load = __import__('finarch.dataset.02-generation.01-perturbation.hyperparameters', fromlist=['load']).load
    profile_snapshot = __import__('finarch.dataset.02-generation.01-perturbation.hyperparameters', fromlist=['profile_snapshot']).profile_snapshot
    controls=load(hyperparameters) if hyperparameters else None
    if controls:
        input_path=controls["dataset"]["input_path"];all_inputs=True
    if all_inputs:
        inputs=PreparedInputs(Path(input_path));names=list(inputs.samples)
        from collections import Counter
        selection={'source_counts':dict(Counter(inputs.providers[s['raw_id']]['source'] for s in inputs.samples.values())),
                   'selected':[{'id':n,'raw_id':inputs.samples[n]['raw_id']} for n in names],
                   'selection_mode':'all supplied prepared inputs; no historical overlap exclusion'}
    else:
        inputs,names,selection=select(input_path,exclude_path)
    _,settings,profiles,estimate=plan(input_path,config,names)
    prep_rounds=controls['preparation']['max_rounds'] if controls else 1
    gen_rounds=controls['generation']['max_rounds'] if controls else 3
    if controls and len(names)!=controls['dataset']['count']:
        raise ValueError('HYPERPARAMETER_INPUT_COUNT_MISMATCH')
    settings['preparation_revision_attempts']=0 if controls else 1
    if controls:
        settings['parallelism']={stage:controls[stage]['concurrency'] for stage in ('preparation','generation')}
    snapshot=profile_snapshot(profiles,controls) if controls else profiles.read_text()
    estimate.update(parallelism=settings['parallelism'],revision_attempts=settings['preparation_revision_attempts'],
        preparation_maximum_rounds=prep_rounds,
        maximum_model_calls=len(names)*(4+6*(prep_rounds-1)) if controls else len(names)*6,
        stop_after='generation_before_final_human_review',generation_maximum_rounds=gen_rounds,
        generation_maximum_calls=len(names)*7*2*gen_rounds+4*(gen_rounds-1))
    bundle=allocate_run('reports/run');(bundle/'01-preparation').mkdir()
    profile=bundle/'model-profiles.toml';profile.write_text(snapshot);settings['profiles_path']=str(profile.resolve())
    if controls:
        write(bundle/'hyperparameter.json',controls)
        from finarch.shared.providers.profiles import selected_profile
        estimate['roles']={role:{k:selected_profile(profile,role)[k] for k in ('provider','model','effort','id')} for role in estimate['roles']}
    write(bundle/'config.json',settings);write(bundle/'plan.json',estimate)
    write(bundle/'selection-evidence.json',selection)
    write(bundle/'input-selection.json',{'cases':names,'input_path':str(inputs.path)})
    write(bundle/'delegation.json',{'scope':'Preparation approval after verified automatic checks; no final Generation human review.','source':'Explicit user confirmation in this task on 2026-09-10','original_audit_rounds':1,'failed_preparation':'Exclude with saved reason; do not treat as approved.'})
    (bundle/'README.md').write_text(Path(__file__).with_name('new-batch-readme.md').read_text().replace('# 새 30건 실행',f'# 새 {len(names)}건 실행').replace('이전 10건과 원천 ID 및 Q/C가 겹치지 않는 30건입니다. 기존 100건 입력에서 원문만 선정하며 이전 코드·생성문·판정은 사용하지 않습니다. 문항 번호는 입력 묶음의 ID를 유지합니다.', '입력 선정 방식과 출처별 수는 selection-evidence.json을 따릅니다. 이전 코드·생성문·판정은 재사용하지 않으며 문항 번호는 입력 묶음 ID를 유지합니다.'))
    state={'run':bundle.name,'status':'RUNNING','phase':'PREPARATION','planned_cases':len(names),'processed_cases':0,'current_case':None};stop=threading.Event()
    def save():
        value={**state,'heartbeat_at':datetime.now().astimezone().isoformat()}
        if state['phase']=='GENERATION':
            paths=sorted((bundle/'02-generation').glob('0*-round/progress.json'))
            if paths:
                p=read(paths[-1]);value.update(round=paths[-1].parent.name,completed_types_this_round=sum(len(v) for v in p['cases'].values()))
        write(bundle/'execution-progress.json',value)
    def heartbeat():
        while not stop.wait(3):save()
    save();thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    print('RUN '+str(bundle.resolve()),flush=True)
    try:
        with measure(bundle,'batch'):
            with measure(bundle/'01-preparation','preparation'):
                results=[]
                for name,value in preparation_results(bundle,inputs,names,bundle/'config.json',run_case):
                    state['current_case']=name
                    results.append(value)
                    state['processed_cases']=len(results)
                    case=bundle/'01-preparation'/name
                    if value['status']=='PASS':
                        record_decision(case,'APPROVED','user (delegated automatic checks)','Approved under the user instruction to proceed after successful Preparation checks.',{k:True for k in ('02-review-and-correct','03-calculation','04-graph')})
                    else:record_decision(case,'REJECTED','user (delegated automatic checks)',value.get('reason') or 'Preparation checks did not pass.')
                    print(name,value['status'],value.get('reason'),flush=True)
                write(bundle/'01-preparation/rounds/01-round.json',{'round':1,'results':results})
                completed = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['completed']).completed
                limit = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['limit']).limit
                repair_case = __import__('finarch.dataset.01-preparation.repair_failed_preparation', fromlist=['repair_case']).repair_case
                current={r['input_id']:r for r in results}
                for round_number in range(2,prep_rounds+1):
                    failed=[name for name,r in current.items() if r['status']=='FAIL']
                    if not failed:break
                    history=bundle/'01-preparation/repair-history'/f'{round_number-1:02d}-round'
                    history.mkdir(parents=True,exist_ok=False)
                    state.update(phase='PREPARATION_REPAIR',round=round_number,processed_cases=0)
                    repaired=[]
                    for name,value in completed(failed,lambda name:repair_case(bundle,name,history,attempt=round_number-1),limit(settings,'preparation')):
                        current[name]=value;repaired.append(value)
                        state.update(current_case=name,processed_cases=len(repaired))
                        write(bundle/'01-preparation/rounds'/f'{round_number:02d}-round.json',{'round':round_number,'results':repaired})
                        print(name,'repair',round_number,value['status'],value.get('reason'),flush=True)
                write(bundle/'01-preparation/summary.json',{'planned':len(names),'processed':len(names),'results':[current[n] for n in names]})
                gate=evaluate(bundle);write(bundle/'summary.json',gate)
            state.update(phase='GENERATION',current_case=None)
            if gate['approved']:
                result=generate(bundle,gen_rounds);final=report(bundle)
                state.update(status='COMPLETED',phase='READY_FOR_FINAL_REVIEW',final_status=result['status'],passed_types=sum(r['status']=='PASS' for r in final['rows']),failed_types=sum(r['status']!='PASS' for r in final['rows']))
            else:state.update(status='COMPLETED',phase='NO_ELIGIBLE_INPUTS')
    except Exception as error:
        state.update(status='ERROR',reason=type(error).__name__+': '+str(error));raise
    finally:
        stop.set();thread.join();save()
    from finarch.dataset.viewer.reports.timing_report import build as timing_report
    timing_report(bundle)
    print(json.dumps(state),flush=True)
    return bundle

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',default='data/prepared/first-100/input.json');p.add_argument('--exclude',default='data/prepared/first-10/input.json');p.add_argument('--config',default='config/llm.json');p.add_argument('--all-inputs',action='store_true');p.add_argument('--hyperparameters');a=p.parse_args();run(a.input,a.exclude,a.config,a.all_inputs,a.hyperparameters)
