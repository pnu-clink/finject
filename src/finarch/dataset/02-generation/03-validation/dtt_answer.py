"""R18: independent individual answers to saved, audited final observations."""
import argparse
import hashlib
import json
from pathlib import Path
import re

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepStopped = __import__('finarch.dataset.90-operations.staging', fromlist=['StepStopped']).StepStopped
from finarch.dataset.shared.review.dtt_audit import prepare as prepare_audit, read, evaluate_saved, observation_hash
from finarch.shared.providers.cli import call, read_settings
from finarch.dataset.schemas.registry import describe
from finarch.dataset.schemas.validation import validate, parse_json_object


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(case, label):
    """R18.1: private gate first; project a fresh C/Q-only model input afterward."""
    current, binding = prepare_audit(case, label)
    pointer = read(case/f'05-text/{label}/latest-audit.json')
    stage = pointer['stage']
    path = (case/stage).resolve()
    if not path.is_relative_to((case/f'05-text/{label}/audits').resolve()):
        raise ValueError('AUDIT_PATH_OUTSIDE_VARIANT')
    report = read(path/'03-result.json')
    request = read(path/'01-input.json')
    for key in ('context', 'question', 'original_context', 'axis', 'edits'):
        if request[key] != current[key]:
            raise ValueError('AUDIT_TEXT_CHANGED')
    for key in ('stage16_ref', 'observation_sha256', 'plan_sha256'):
        if report[key] != binding[key]:
            raise ValueError('AUDIT_BINDING_CHANGED')
    snapshot = report.get('plan_snapshot')
    if snapshot is None and (path/'plan-binding.json').exists():
        snapshot = read(path/'plan-binding.json').get('plan_snapshot')
    if label != 'ANSWER' and snapshot != binding.get('plan_snapshot'):
        raise ValueError('AUDIT_PLAN_CHANGED')
    raw = parse_json_object(read(path/'audit/02-raw-response.json')['text'])
    if read(path/'audit/03-result/schema-check.json')['status'] != 'PASS':
        raise ValueError('AUDIT_SCHEMA_NOT_PASSED')
    checked = evaluate_saved(request, raw, report)
    if report['status'] != 'PASS' or checked['status'] != 'PASS':
        raise ValueError('STAGE17_NOT_PASSED')
    if any(checked.get(k) != report.get(k) for k in ('findings', 'observed_state')):
        raise ValueError('AUDIT_RAW_REPORT_MISMATCH')
    observation = {k:current[k] for k in ('context', 'question')}
    validate('dtt.answer.request', observation)
    binding.update(audit_ref=stage, audit_sha256=file_hash(path/'03-result.json'),
                   audit_raw_sha256=file_hash(path/'audit/02-raw-response.json'),
                   checks=binding['checks']+['current_audit_PASS', 'audit_raw_rechecked', 'CQ_only_projection'])
    return observation, binding


README = '# R18 independent answer — {label}\n\nCall/response status: **{status}**. Passing response-format checks does not establish answer correctness.\nThe model received only the final context/question, shared answer instructions, and response schema. Calls are independent CLI requests with no shared previous response and no automatic retry.\n\nReading order:\n1. `01-input.json`: actual context and question. `01-input/check.json` contains internal checks that were not sent to the model.\n2. `answer/01-input.json`: actual prompt, model, and transmitted response schema.\n3. `answer/02-raw-response.json`, `answer/03-result/schema-check.json`: raw response and Python validation against the same definition.\n4. `independent-answer.json`: actual answer or failure reason, linked to the latest context and audit.\n5. `review-bundle.json`: material pending human review. Response-behavior review is shown only when a separate `behavior-review.json` exists.\n\nThe time in `answer/02-raw-response/cli-execution.json` covers the entire CLI process, not pure model inference. Actual usage is in `answer/03-result/usage.json`; sequential execution events are in `events.jsonl` at the case root. A failure before dispatch has no call artifacts. Missing raw responses are not fabricated.\nIn the viewer, inspect section 5 (Text and answers), below R17. Inverse/bypass recovery and human approval remain pending.\n'

FAMILY_README = "# R18 independent-answer run\n\nRead `plan.json` → each type's `answer_ref/README.md` → `review.json`. The planned {count} entries were handled as individual requests; actual status and call records in `review.json` are authoritative.\n`config.json` is the configuration copy for this run. No automatic retry or batch call is used. Blocked inputs and failed requests remain in the review bundle. A passing response does not establish semantic correctness or human approval.\nThe viewer displays actual independent answers at the bottom of section 5 and calls, responses, and timing in the log popup. Consult separate records for behavior/evidence review. Inverse/bypass recovery remains pending by user decision.\n"


def publish(ctx, label, stage, report):
    relative = f'05-text/{label}/latest-answer.json'
    pointer = ctx.root/relative
    value = {'stage':stage, 'observation_sha256':report.get('observation_sha256'),
             'audit_ref':report.get('audit_ref')}
    if pointer.exists():
        ctx.save(stage+'/previous-latest-answer.json', read(pointer))
        temp = pointer.with_suffix('.tmp')
        with temp.open('x') as stream:json.dump(value, stream)
        temp.replace(pointer)
        ctx.trace.artifact(relative)
    else:
        ctx.save(relative, value)


def answer_one(ctx, config, label, stage):
    # R18.2: gate failures and transport/schema failures all leave a review bundle.
    with ctx.trace.activate(), ctx.trace.span('dtt.independent_answer', stage=stage, step='R18', role='python'):
        binding = {}
        report = {'status':'FAIL', 'response':None, 'failure_phase':'input_gate',
                  'human_decision':'PENDING', 'behavior_status':'NOT_REVIEWED',
                  'recovery_review':'DEFERRED_BY_USER', 'model':read_settings(config,'dtt.answer')['model']}
        try:
            observation, binding = prepare(ctx.root, label)
            ctx.save(stage+'/01-input/check.json', {'status':'PASS', **binding})
            ctx.save(stage+'/01-input.json', observation)
            report['failure_phase'] = 'request_or_response'
            def handler(payload, *, response_schema):
                validate('dtt.answer.request', payload)
                if response_schema != describe('dtt.answer.response')['schema']:
                    raise ValueError('ANSWER_SCHEMA_CHANGED')
                return call(config, 'dtt.answer', payload, save=lambda n,v:ctx.save(stage+'/answer/'+n,v))
            response = ctx.invoke(stage, 'T04-blind-response', 'dtt.answer', observation, local=handler)
            # Recheck after the call: a concurrently changed text must not inherit this answer.
            _, latest_binding = prepare(ctx.root, label)
            if latest_binding != binding:
                raise ValueError('INPUT_CHANGED_DURING_ANSWER')
            report.update(status='RECEIVED', response=response, failure_phase=None)
        except (StepStopped, ValueError, TypeError, KeyError, OSError) as error:
            reason = error.result.reason if isinstance(error,StepStopped) else str(error)
            report['reason'] = reason
            if not (ctx.root/stage/'01-input/check.json').exists():
                ctx.save(stage+'/01-input/check.json', {'status':'FAIL', 'reason':reason})
            ctx.save(stage+'/03-result/failure.json', {'status':'FAIL','reason':reason,'phase':report['failure_phase']})
        report.update(binding, answer_ref=stage)
        ctx.save(stage+'/independent-answer.json', report)
        ctx.save(stage+'/review-bundle.json', {'label':label, 'answer_ref':stage,
                 'stage16_ref':binding.get('stage16_ref'), 'audit_ref':binding.get('audit_ref'),
                 'response_status':report['status'], 'human_decision':'PENDING',
                 'behavior_review':'NOT_REVIEWED', 'recovery_review':'DEFERRED_BY_USER'})
        ctx.save_text(stage+'/README.md', README.format(label=label,status=report['status']))
        publish(ctx,label,stage,report)
        ctx.trace.update(status='PASS' if report['status']=='RECEIVED' else 'FAIL',
                         reason='Response received, not a correctness verdict' if report['status']=='RECEIVED' else report['reason'])
    return report


def record_review(case_dir, label, review):
    """Record an explicit agent review; do not invent an automatic semantic score."""
    case=Path(case_dir).resolve()
    observation,binding=prepare(case,label)
    stage=read(case/f'05-text/{label}/latest-answer.json')['stage']
    path=(case/stage).resolve()
    if not path.is_relative_to((case/f'05-text/{label}/answers').resolve()):
        raise ValueError('ANSWER_PATH_OUTSIDE_VARIANT')
    report=read(path/'independent-answer.json')
    if report['status']!='RECEIVED' or any(report.get(k)!=binding.get(k) for k in
        ('observation_sha256','audit_ref','audit_sha256','audit_raw_sha256','plan_sha256')):
        raise ValueError('ANSWER_NOT_CURRENT')
    behaviors={'SINGLE_NUMBER_ASSERTION','ABSTENTION','CONDITIONAL_ANSWERS','UNCOMMITTED'}
    if review.get('behavior') not in behaviors:raise ValueError('UNKNOWN_RESPONSE_BEHAVIOR')
    for key in ('behavior_label','reason','reviewer_note'):
        if not isinstance(review.get(key),str) or not review[key].strip():raise ValueError('INCOMPLETE_REVIEW')
    source={'context':observation['context'],'response':report['response']['text']}
    if not review.get('evidence'):raise ValueError('REVIEW_EVIDENCE_REQUIRED')
    for e in review['evidence']:
        if e.get('field') not in source or not e.get('quote') or e['quote'] not in source[e['field']]:
            raise ValueError('REVIEW_QUOTE_NOT_FOUND')
    value={**review,'response':report['response'],'observation_sha256':binding['observation_sha256'],
           'answer_sha256':file_hash(path/'independent-answer.json'),'reviewer_kind':'AGENT_REVIEW',
           'human_decision':'PENDING','recovery_review':'DEFERRED_BY_USER'}
    ctx=RunContext.resume(case,{},case.name)
    with ctx.trace.activate(),ctx.trace.span('dtt.answer_evidence_review',stage=stage,step='R18.4',role='agent-review-record'):
        ctx.save(stage+'/behavior-review.json',value)
        ctx.trace.update(status='RECORDED',reason='Agent review notes with exact quotations; no automatic approval')
    return value


def run(case_dir, config, revision='v1', labels=None):
    case=Path(case_dir).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',revision):raise ValueError('INVALID_ANSWER_REVISION')
    all_labels=['ANSWER']+[v['label'] for v in read(case/'04-perturbation/05-list-candidates/03-result.json')]
    labels=all_labels if labels is None else labels
    if not labels or len(labels)!=len(set(labels)) or any(l not in all_labels for l in labels):
        raise ValueError('INVALID_ANSWER_LABELS')
    family=f'05-text/stage18-{revision}'
    stages={label:f'05-text/{label}/answers/{revision}' for label in labels}
    if any((case/p).exists() for p in [family,*stages.values()]):raise ValueError('ANSWER_OUTPUT_ALREADY_EXISTS')
    settings=read_settings(config,'dtt.answer')
    ctx=RunContext.resume(case,{},case.name)
    ctx.save(family+'/config.json',read(config))
    ctx.save(family+'/plan.json',{'labels':labels,'model':settings['model'],'effort':settings['effort'],
             'maximum_calls':len(labels),'automatic_retries':0,'input_fields':['context','question'],
             'estimated_cost':None,'cost_status':'CLI billing rate unavailable; actual usage is recorded',
             'stop_after':18,'recovery_review':'DEFERRED_BY_USER'})
    results=[]
    for label in labels:
        report=answer_one(ctx,config,label,stages[label])
        result={k:report[k] for k in ('status','answer_ref')};result['label']=label
        results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    usage=[{'stage':stage,'usage':read(case/stage/'answer/03-result/usage.json')}
           for stage in stages.values() if (case/stage/'answer/03-result/usage.json').exists()]
    summary={'results':results,'usage':usage,'pipeline_status':'COMPLETED',
             'human_decision':'PENDING','recovery_review':'DEFERRED_BY_USER'}
    ctx.save(family+'/review.json',summary)
    ctx.save_text(family+'/README.md',FAMILY_README.format(count=len(labels)))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--revision',default='v1');parser.add_argument('--label',action='append')
    args=parser.parse_args();run(args.case,args.config,args.revision,args.label)
