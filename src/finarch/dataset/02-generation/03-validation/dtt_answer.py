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


README = '''# 18번 독립 답변 — {label}

호출/응답 상태: **{status}**. 응답 형식 통과는 답의 정확성 판정이 아닙니다.
모델에는 최종 본문·질문과 공통 답변 안내·응답 스키마만 전달했습니다.
이전 응답을 공유하지 않는 개별 CLI 요청이며 자동 재시도는 없습니다.

읽는 순서:
1. `01-input.json`: 실제 본문과 질문. `01-input/check.json`은 모델에게 보내지 않은 내부 검사 기록입니다.
2. `answer/01-input.json`: 실제 프롬프트·모델·전달 응답 스키마.
3. `answer/02-raw-response.json`, `answer/03-result/schema-check.json`: 원응답과 동일 정의의 Python 검사.
4. `independent-answer.json`: 실제 답변 또는 실패 사유, 최신 본문·감사 연결.
5. `review-bundle.json`: 사람 검토 대기 자료. 응답 행동 검토는 별도 `behavior-review.json`이 있을 때만 표시합니다.

`answer/02-raw-response/cli-execution.json`의 시간은 CLI 전체 처리 시간이며 순수 모델 추론 시간으로 해석하지 않습니다.
`answer/03-result/usage.json`에 실제 사용량, 문항 루트 `events.jsonl`에 순차 실행 기록이 있습니다.
호출 전 실패하면 호출 관련 파일이 없고, 원응답이 없으면 만들어 채우지 않습니다.
뷰어 5번 문장과 답변의 17번 아래에서 확인합니다. 역산·우회와 사람 승인은 보류입니다.
'''

FAMILY_README = '''# 18번 독립 답변 실행

`plan.json` → 유형별 `answer_ref/README.md` → `review.json` 순서로 읽습니다.
예정 {count}개를 개별 요청으로 처리했습니다. `review.json`의 실제 상태와 호출 기록이 기준입니다.
`config.json`은 이 실행만 허용하는 설정의 사본입니다. 자동 재시도와 묶음 호출은 없습니다.
입력 차단·요청 실패도 검토 묶음에 남깁니다. 통과 응답을 의미 정답이나 사람 승인으로 바꾸지 않습니다.
뷰어 5번 하단에 실제 독립 답변을, 로그 팝업에 호출·응답·시간을 표시합니다.
행동/근거 검토는 별도 기록을 확인해야 하며, 역산·우회는 사용자 결정으로 보류입니다.
'''


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
