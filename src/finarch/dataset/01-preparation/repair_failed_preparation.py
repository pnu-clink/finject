"""Give previously failed Preparation cases one recorded repair opportunity."""
import argparse
import hashlib
import json
import shutil
import threading
from datetime import datetime
from pathlib import Path

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
record_decision = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['record_decision']).record_decision
evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
measure = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['measure']).measure
calculate = __import__('finarch.dataset.01-preparation.preparation_pipeline', fromlist=['calculate']).calculate
revise = __import__('finarch.dataset.01-preparation.02-review.revisions', fromlist=['revise']).revise
publish = __import__('finarch.dataset.01-preparation.01-source.working_data', fromlist=['publish']).publish
use_feedback = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['use_feedback']).use_feedback

GUIDANCE = '''This is one repair attempt after a saved Preparation failure. Solve from the supplied context and question; no reference answer is supplied. Correct the actual cause instead of forcing an answer. Copy numeric_index text and spans as unchanged pairs after checking the associated row, year, and entity. Preserve all causal dependencies: price comparisons, bounds and period selection must affect the computation. Do not remove a necessary input, insert a zero-multiplied dependency, or hard-code selected outcomes merely to pass graph checks. Prefer named straight-line assignments and explicitly unrolled computations when mathematically equivalent; do not use lists or loops merely for compactness. The graph supports arithmetic, round/int/float/abs/pow and math functions pow/sqrt/log/log10/exp/fabs/ceil/floor/erf. If source conventions are ambiguous, state that ambiguity in grounding rather than claiming it is specified. Keep all generated text in English.'''


def repair_case(bundle, name, history, attempt=1):
    case = bundle/'01-preparation'/name
    old = history/name
    if old.exists():
        raise ValueError('REPAIR_ALREADY_STARTED:'+name)
    before = read(case/'run.json')
    if before['status'] != 'FAIL':
        raise ValueError('ONLY_FAILED_PREPARATION_CAN_BE_REPAIRED')
    manifest = {str(p.relative_to(case)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in case.rglob('*') if p.is_file()}
    case.rename(old)
    ctx = RunContext(case, {}, case_id=name)
    report = {'input_id':name, 'status':'RUNNING', 'human_decision':'PENDING',
              'allow_next_stage':False, 'layout':'preparation-generation-v1',
              'repair_attempt':attempt, 'previous_failure':before.get('reason'),
              'previous_attempt':str(old.relative_to(bundle))}
    ctx.save_text('README.md', Path(__file__).with_name('preparation-readme.md').read_text())
    ctx.save('repair-provenance.json', {'previous_attempt':str(old.relative_to(bundle)),
             'original_files_sha256':manifest, 'repair_attempt':attempt,
             'authorization':'User-authorized bounded Preparation repair before Generation.'})
    with ctx.trace.activate():
        try:
            for relative in ('01-source/01-receive-input/01-input.json',
                             '01-source/02-record-source/01-provenance.json',
                             '01-source/03-compare-source/01-result.json'):
                ctx.save(relative, read(old/relative))
            original=read(old/'01-source/01-receive-input/01-input.json')
            resolve_review_path = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['resolve_review_path']).resolve_review_path
            accepted=resolve_review_path(old/'02-review-and-correct/accepted-audit.json')
            if accepted.exists():
                audit=read(accepted)
                sample=read(old/'02-review-and-correct/accepted-input.json')
                ctx.save('02-review-and-correct/reused-audit.json',
                         {'source':str(accepted.relative_to(bundle)), 'new_model_call':False,
                          'sha256':hashlib.sha256(accepted.read_bytes()).hexdigest()})
            else:
                audit_paths=sorted(resolve_review_path(old/'02-review-and-correct').glob('*-round/01-LLM-audit-original/03-result.json'))
                audit_path=audit_paths[-1]
                audit=read(audit_path)
                ctx.save('02-review-and-correct/01-round/01-LLM-audit-original/03-result.json',audit)
                audited_input=audit_path.parent/'01-input.json'
                sample=dict(original)
                if audited_input.exists():
                    request=read(audited_input)
                    sample.update({k:request[k] for k in ('context','question')})
                    ctx.save('02-review-and-correct/01-round/01-LLM-audit-original/01-input.json',request)
                sample,audit=revise(ctx,bundle/'config.json',sample,audit,1)
            if audit['status']!='PASS':
                raise ValueError('ORIGINAL_AUDIT_NOT_PASSED_AFTER_ONE_REPAIR')
            ctx.save('02-review-and-correct/accepted-input.json',sample)
            ctx.save('02-review-and-correct/accepted-audit.json',audit)
            publish(ctx,original,sample,audit)
            preparation_evidence = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.case_feedback', fromlist=['preparation_evidence']).preparation_evidence
            fingerprint = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.case_feedback', fromlist=['fingerprint']).fingerprint
            evidence=preparation_evidence(old,before)
            ctx.save('repair-guidance/00-evidence.json',evidence)
            guidance=GUIDANCE+'\n\nCase-specific repair evidence:\n'+json.dumps(evidence,ensure_ascii=False)
            ctx.save('repair-guidance/01-applied.json',{'case':name,'attempt':attempt,'evidence_sha256':fingerprint(evidence),'source':str(old.relative_to(bundle))})
            feedback=case/'repair-guidance'
            publish_feedback = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['publish']).publish
            target_round=f'{attempt+1:02d}-round'
            ref=publish_feedback(old/'06-exception-handler/feedback'/target_round/'feedback.json',
                case=name,variant='ANSWER',source_round=f'{attempt:02d}-round',target_round=target_round,
                target_role='01-preparation.03-calculation.pot',axis='ANSWER',guidance=guidance,
                source=case/'repair-guidance/00-evidence.json')
            write(feedback/'01-preparation.03-calculation.pot/answer.json',{'feedback_refs':[ref]})
            with use_feedback(feedback,case=name,target_round=target_round):
                calculate(ctx,bundle/'config.json',sample,report)
        except Exception as error:
            report.update(status='FAIL',reason=str(error))
        ctx.save('07-human-review/01-collect-results/01-result.json',report)
        ctx.save('run.json',report)
    passed=report['status']=='PASS'
    record_decision(case,'APPROVED' if passed else 'REJECTED',
                    'user (delegated automatic checks)',
                    'Approved after the authorized repair and successful checks.' if passed else report['reason'],
                    {k:True for k in ('02-review-and-correct','03-calculation','04-graph')} if passed else None)
    return report


def run(bundle):
    bundle=Path(bundle).resolve()
    history=bundle/'01-preparation/repair-history/01-original'
    history.mkdir(parents=True,exist_ok=False)
    summary=read(bundle/'01-preparation/summary.json')
    names=[r['input_id'] for r in summary['results'] if r['status']=='FAIL']
    if not names:raise ValueError('NO_FAILED_PREPARATION')
    for relative in ('config.json','execution-progress.json','01-preparation/summary.json',
                     '01-preparation/review-gate.json','01-preparation/failure-report.json',
                     '01-preparation/FAILURES.md','02-generation/approved-inputs.json','timing.json'):
        path=bundle/relative
        if path.exists():
            target=history/'batch'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
    settings=read(bundle/'config.json');settings['preparation_revision_attempts']=1
    write(bundle/'config.json',settings)
    (history.parent/'README.md').write_text(Path(__file__).with_name('preparation-repair-readme.md').read_text())
    write(history.parent/'plan.json',{'cases':names,'additional_repair_attempts':1,
          'models':'GPT Luna low for generation and validation','maximum_preparation_calls':39,
          'cost_amount':None,'generation':'Resume completed variants; process newly approved cases; at most three rounds; no final human decisions.'})
    state={'run':bundle.name,'status':'RUNNING','phase':'PREPARATION_REPAIR','planned_cases':len(names),'processed_cases':0}
    stop=threading.Event()
    def save():
        value={**state,'heartbeat_at':datetime.now().astimezone().isoformat()}
        if state['phase']=='GENERATION':
            paths=sorted((bundle/'02-generation').glob('0*-round/progress.json'))
            if paths:
                progress=read(paths[-1]);value.update(round=paths[-1].parent.name,
                    completed_types_this_round=sum(len(v) for v in progress['cases'].values()))
        write(bundle/'execution-progress.json',value)
    def heartbeat():
        while not stop.wait(3):save()
    save();thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    repaired=[]
    try:
        with measure(history.parent,'preparation-repair-and-generation'):
            completed = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['completed']).completed
            limit = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['limit']).limit
            record_queue = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['record_queue']).record_queue
            record_queue(bundle/'01-preparation/queue.json',{'queue':'preparation','phase':'repair','limit':limit(settings,'preparation'),'planned':len(names),'completed':0,'status':'RUNNING'})
            for name,value in completed(names,lambda name:repair_case(bundle,name,history),limit(bundle/'config.json','preparation')):
                state['current_case']=name
                repaired.append(value)
                state['processed_cases']=len(repaired)
                record_queue(bundle/'01-preparation/queue.json',{'queue':'preparation','phase':'repair','limit':limit(settings,'preparation'),'planned':len(names),'completed':len(repaired),'status':'COMPLETED' if len(repaired)==len(names) else 'RUNNING'})
                write(history.parent/'results.json',{'planned':len(names),'processed':len(repaired),'results':repaired})
                print(name,value['status'],value.get('reason'),flush=True)
            replacement={r['input_id']:r for r in repaired}
            summary['results']=[replacement.get(r['input_id'],r) for r in summary['results']]
            write(bundle/'01-preparation/summary.json',summary)
            write(bundle/'summary.json',evaluate(bundle))
            state.update(phase='GENERATION',current_case=None)
            generate = __import__('finarch.dataset.02-generation.generate_schedule', fromlist=['run']).run
            from finarch.dataset.viewer.reports.generation_report import build
            result=generate(bundle,3,resume=True)
            final=build(bundle)
            state.update(status='COMPLETED',phase='READY_FOR_FINAL_REVIEW',
                         final_status=result['status'],
                         passed_types=sum(r['status']=='PASS' for r in final['rows']),
                         failed_types=sum(r['status']!='PASS' for r in final['rows']))
    except BaseException as error:
        state.update(status='ERROR',reason=type(error).__name__+': '+str(error));raise
    finally:
        stop.set();thread.join();save()
    return repaired


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    args=parser.parse_args();run(args.run)
