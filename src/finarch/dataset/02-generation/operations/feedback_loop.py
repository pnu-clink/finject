"""Bounded three-round production feedback with immutable per-call evidence."""
import hashlib
import json
import shutil
from pathlib import Path
Journal = __import__('finarch.shared.run_logging.logging', fromlist=['Journal']).Journal
RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
realize = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['run']).run
from finarch.dataset.shared.review.dtt_audit import run as audit
build = __import__('finarch.dataset.02-generation.05-human-review.human_review', fromlist=['build']).build
use_feedback = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['use_feedback']).use_feedback
from finarch.shared.providers.cli import call, prepare_instruction


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temp.replace(path)


def failures(case):
    generation_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['generation_root']).generation_root
    audit_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['audit_root']).audit_root
    candidate_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['candidate_root']).candidate_root
    variants={v['label']:v['axis'] for v in read(case/'04-perturbation/05-list-candidates/03-result.json')}
    revision=case.parent.name
    results=[]
    for label,axis in {'ANSWER':'ANSWER',**variants}.items():
        generated=case/generation_root(label)/revision
        failed=read(generated/'03-result/failure.json') if (generated/'03-result/failure.json').exists() else None
        # Ordered artifacts expose logical paths through resolve_read.
        resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read
        fp=resolve_read(generated/'03-result/failure.json')
        if fp.is_file():failed=read(fp)
        ap=resolve_read(case/audit_root(label)/revision/'03-result.json')
        if not ap.is_file():
            pointer=resolve_read(case/candidate_root(label)/'latest-audit.json')
            if pointer.is_file():ap=resolve_read(case/read(pointer)['stage']/'03-result.json')
        report=read(ap) if ap.is_file() else None
        if not report and not failed:
            failed={'reason':'No completed semantic audit is available for this candidate.'}
        if failed or (report and report['status']!='PASS'):
            role='shared.01-02.02-03.review-and-validation' if label=='ANSWER' else '02-generation.02-generate-text.realization'
            stage=generated if failed else case/audit_root(label)/revision
            def optional(relative):
                p=resolve_read(stage/relative)
                return read(p) if p.is_file() else {}
            results.append({'case':case.name,'label':label,'axis':axis,'target_role':role,
                'reason':str((failed or report).get('reason','Validation failed')),
                'request':optional('01-input.json'),'response':failed or report,
                'restart':'02-audit-meaning' if role=='shared.01-02.02-03.review-and-validation' else '01-generate-text'})
    return results


def decide(items, round_number):
    return {'decision':'PASS' if not items else ('RETRY' if round_number<3 else 'LIMIT_REACHED'),
            'round':round_number,'maximum_rounds':3,'failures':items,
            'human_decision':'PENDING'}


def expand_dependencies(labels, variants):
    labels=set(labels)
    if labels & {'IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER'}:
        labels.update({'IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER'})
        labels.update(v['label'] for v in variants if v['axis']=='IC_SOURCE')
    return labels


def inherit_case(previous, target):
    """Only same-run continuation; snapshots are explicitly marked, never new calls."""
    if previous.parent.parent.resolve()!=target.parent.parent.resolve():
        raise ValueError('CROSS_RUN_INHERITANCE_FORBIDDEN')
    shutil.copytree(previous,target,ignore=shutil.ignore_patterns('events.jsonl','log','06-human-review'))
    hashes={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in target.rglob('*') if p.is_file()}
    save(target/'inherited-inputs.json',{'source_round':previous.parent.name,
        'source_case':str(previous),'scope':'same-run frozen inputs and successful dependencies',
        'new_model_calls':0,'files_sha256':hashes})
    journal=Journal(target,target.name)
    journal.emit(phase='INHERITED',function='feedback.inherit_case',kind='python',
                 detail={'source':str(previous),'new_model_calls':0},stage='00-data-preparation')


def build_feedback(root, round_dir, items, config):
    groups={}
    allowed_roles=read(config).get('feedback_target_roles') if Path(config).is_file() else None
    for item in items:
        if allowed_roles is not None and item['target_role'] not in allowed_roles:
            RunLogs.for_case(round_dir).write('detail.log','feedback.keep_fixed_instructions',
                stage='05-text/04-LLM-build-feedback',value={'role':item['target_role'],'axis':item['axis'],
                    'case':item['case'],'reason':'Retry with unchanged instructions under the experiment contract'})
            continue
        groups.setdefault((item['target_role'],item['axis']),[]).append(item)
    for (role,axis),group in groups.items():
        path=root/'feedback'/role/ (axis.lower()+'.json')
        old=json.loads(path.read_text()) if path.exists() else {}
        stage=round_dir/'05-text/04-LLM-build-feedback'/axis.lower()/role
        ctx=RunContext(stage,{},'feedback-'+axis.lower())
        instructions,_=prepare_instruction(role,{'axis':axis})
        payload={'axis':axis,'target_role':role,'common_and_type_instructions':instructions,
                 'previous_guidance':old.get('guidance',''),
                 'failures':[{k:v for k,v in item.items() if k in ('case','label','reason','request','response')} for item in group]}
        with ctx.trace.activate(),ctx.trace.span('feedback.build',kind='llm',axis=axis,stage='.'):
            ctx.save('01-input.json',payload)
            result=call(config,'02-generation.feedback.case-feedback',payload,save=lambda n,v:ctx.save('03-LLM-call/'+n,v))
            if result.status!='PASS':
                ctx.save('03-result.json',{'status':'FAIL','reason':result.reason})
                raise ValueError('FEEDBACK_GENERATION_FAILED: '+result.reason)
            value={'axis':axis,'target_role':role,'version':old.get('version',0)+1,
                **result.data,'evidence_round':round_dir.name,
                'evidence':[{'case':i['case'],'label':i['label'],'reason':i['reason']} for i in group]}
            ctx.save('03-result.json',value)
            save(path,value)
            ctx.save_text('README.md','# Feedback creation\n\nRead input, schema-bound LLM request/raw response, then result. The result replaces the cumulative supplement outside round folders. Prior call snapshots remain unchanged.\n')


def retry_round(previous, current, items, config, feedback):
    cases={}
    for item in items:cases.setdefault(item['case'],[]).append(item)
    state={'status':'RUNNING','cases':{name:{'status':'PENDING'} for name in cases}}
    from threading import RLock
    lock=RLock()
    def save_progress():
        with lock:save(current/'production-progress.json',state)
    def process(pair):
        name,errors=pair
        case=current/name;inherit_case(previous/name,case)
        variants=read(case/'04-perturbation/05-list-candidates/03-result.json')
        labels=expand_dependencies([e['label'] for e in errors],variants)
        generate=labels-{'ANSWER'}
        row=state['cases'][name]={'status':'GENERATING','retry_labels':sorted(labels)}
        save_progress()
        try:
            with use_feedback(feedback):
                generated=realize(case,config,revision=current.name,selected_labels=sorted(generate)) if generate else {'results':[],'prerequisite_audit':{}}
                eligible=[v['label'] for v in generated['results'] if v['status']=='PASS' and v['label'] not in generated['prerequisite_audit']]
                if 'ANSWER' in labels:eligible.insert(0,'ANSWER')
                checked=audit(case,config,revision=current.name,labels=eligible,prerequisite_report=generated['prerequisite_audit']) if eligible else {'results':[]}
            row.update(status='CHECKED',generation=generated,audit=checked)
        except Exception as error:
            row.update(status='ERROR',reason=type(error).__name__+': '+str(error))
        save_progress()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=(read(config).get('case_workers',1) if Path(config).is_file() else 1)) as pool:
        list(pool.map(process,cases.items()))
    state['status']='FINISHED';save_progress()
    return state


def finish_rounds(root, first, config, maximum_rounds=3):
    begin_timing = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['begin']).begin
    end_timing = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['end']).end
    current=first;history=[];latest={name:first/name for name in read(first/'production-progress.json')['cases']}
    try:
        for number in range(1,maximum_rounds+1):
            items=[]
            progress=read(current/'production-progress.json')
            for name,row in progress['cases'].items():
                latest[name]=current/name
                if row['status']=='ERROR':
                    items.append({'case':name,'label':'PIPELINE','reason':row['reason'],'restart':'manual'})
                else:items.extend(failures(current/name))
            decision=decide(items,number)
            decision['maximum_rounds']=maximum_rounds
            if number>=maximum_rounds and items:decision['decision']='LIMIT_REACHED'
            if any(i['restart']=='manual' for i in items):decision['decision']='BLOCKED'
            upstream=read(first/'graph-next-stage.json') if (first/'graph-next-stage.json').exists() else {}
            decision['upstream_exclusions']=upstream.get('excluded',[])+upstream.get('blocked',[])
            if not progress['cases'] and decision['upstream_exclusions']:decision['decision']='BLOCKED'
            path=current/'05-text/03-final-validator/03-result.json';save(path,decision)
            logs=RunLogs.for_case(current/'batch');logs.write('pipeline.log','feedback.final_validator',value=decision,phase='END',stage='05-text/03-final-validator')
            history.append({'round':current.name,'decision':decision['decision'],'failure_count':len(items)})
            save(root/'loop-summary.json',{'status':'RUNNING','rounds':history,'maximum_rounds':maximum_rounds})
            if decision['decision']!='RETRY':
                end_timing(current)
                break
            build_feedback(root,current,items,config)
            end_timing(current)
            next_dir=root/f'{number+1:02d}-round';next_dir.mkdir()
            begin_timing(next_dir,'round')
            retry_round(current,next_dir,items,config,root/'feedback')
            (next_dir/'README.md').write_text(Path(__file__).with_name('feedback-readme.md').read_text())
            current=next_dir
        reviews={}
        for name,case in latest.items():
            try:reviews[name]=build(case,revision='final-'+case.parent.name)
            except Exception as error:reviews[name]={'status':'FAIL','reason':str(error)}
        result={'status':history[-1]['decision'],'rounds':history,'maximum_rounds':maximum_rounds,
                'review':reviews,'latest_cases':{k:str(v.relative_to(root)) for k,v in latest.items()}}
        for case in latest.values():
            write_index = __import__('finarch.dataset.90-operations.numbered_layout', fromlist=['write_index']).write_index
            write_index(case,finalize=True)
        result['upstream_exclusions']=decision['upstream_exclusions']
        if result['status']=='PASS' and result['upstream_exclusions']:result['status']='PASS_WITH_EXCLUSIONS'
        save(root/'loop-summary.json',result)
        return result
    except Exception as error:
        end_timing(current,'ERROR',type(error).__name__+': '+str(error))
        save(root/'loop-summary.json',{'status':'BLOCKED','rounds':history,'reason':type(error).__name__+': '+str(error)})
        raise
