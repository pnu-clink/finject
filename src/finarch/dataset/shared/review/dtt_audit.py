resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read
candidate_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['candidate_root']).candidate_root
generation_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['generation_root']).generation_root
audit_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['audit_root']).audit_root
"""R17: scoped final-text audit of saved Stage16 outputs, without Stage18 calls."""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepStopped = __import__('finarch.dataset.90-operations.staging', fromlist=['StepStopped']).StepStopped
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
digest = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['digest']).digest
checked_plan = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['checked_plan']).checked_plan
check_response = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['check_response']).check_response
make_request = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['make_request']).make_request
numbers = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['numbers']).numbers
from finarch.dataset.shared.calculation.python_graph import load_graph
from finarch.shared.providers.cli import call, read_settings
from finarch.dataset.schemas.registry import describe, canonical
from finarch.dataset.schemas.validation import validate


def observation_hash(observation):
    return hashlib.sha256(canonical(observation)).hexdigest()


def latest_stage(case, label):
    base=candidate_root(label)
    pointer=case/base/'latest-realization.json'
    stage=read(pointer)['stage'] if pointer.exists() else generation_root(label)+'/attempt-001'
    path=(case/stage).resolve()
    if not path.is_relative_to((case/generation_root(label)).resolve()):
        raise ValueError('REALIZATION_PATH_OUTSIDE_VARIANT')
    return stage


def prepare(case, label):
    """R17.1: rebind current text to the protected plan and original facts."""
    sample=read(case/'00-data-preparation/01-select-input/01-input.json'); program=read(case/'02-calculation/02-prepare-code/03-program.json')
    graph=load_graph(case)  # Reject original gold-mismatch cases before any audit.
    original={k:sample[k] for k in ('context','question')}
    if label=='ANSWER':
        request={'original_context':sample['context'],**original,'axis':'ANSWER',
                 'intent':{'preserve_original':True},'edits':[], 'recovery_review':'DEFERRED_BY_USER'}
        validate('shared.01-02.02-03.review-and-validation.request',request)
        return request,{'stage16_ref':None,'observation_sha256':observation_hash(original),
                        'plan_sha256':None,'checks':['original_pot_eligible','original_CQ_unchanged']}
    variants={v['label']:v for v in read(case/'04-perturbation/05-list-candidates/03-result.json')}
    variant=variants[label];plan=variant['plan'];base=checked_plan(case,variant)
    stage=latest_stage(case,label); path=case/stage
    final=read(path/'04-final-observation.json'); meta=read(path/'03-result/metadata.json')
    if meta['stage16_status']!='PASS' or read(path/'03-result/validation.json')['status']!='PASS':
        raise ValueError('STAGE16_NOT_PASSED')
    expected_hash=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
    if meta['plan_sha256']!=expected_hash:
        raise ValueError('CURRENT_PLAN_CHANGED')
    saved_request=read(path/'01-input.json');patches=read(path/'03-result/patches.json')
    response={'patches':[{k:p[k] for k in ('start','end','before','text','element_ids')} for p in patches]}
    # Regenerate the authorized slots instead of trusting the saved request alone.
    rebuilt=make_request(case,variant,sample,program,graph)
    if saved_request!=rebuilt:
        raise ValueError('REALIZATION_REQUEST_PLAN_MISMATCH')
    applied,enriched=check_response(rebuilt,response)
    if applied!=final or enriched!=patches:
        raise ValueError('FINAL_TEXT_PATCH_MISMATCH')
    axis=variant['axis']
    intent={'preserve_question':True, 'preserve_other_evidence':True,
            'authorized_edit_slots':rebuilt['edit_slots']}
    if axis in ('IC_VALUE','IC_SOURCE'):
        key=base['fact_id'];intent.update(target=key,target_original=program['facts'][key],
            value_pair=base['value_pair'],perturb_position=plan.get('perturb_position','after'),
            source_condition=plan.get('source_condition'),sources=plan.get('sources',[]))
        if axis=='IC_SOURCE':
            intent['base_variant']=plan.get('base_variant','IC_VALUE_01_BEFORE')
            intent['perturb_position']='after' if intent['base_variant']=='IC_VALUE_01_AFTER' else 'before'
            intent['source_assignment_by_value']=[
                {'side':side,'value':base['value_pair'][i],
                 'source':next((s for s in plan['sources'] if s['side']==side),None)}
                for i,side in enumerate(('A','B'))]
    elif axis=='IC_RELATION':
        intent.update(relation=plan['relation']['properties'],scope=plan['scope'],preserve_original_values=True)
    else:
        intent.update(target=plan['fact_id'],deletion=plan['deletion'],
                      scope='Remove the selected source input value; do not delete an intermediate computed sum.')
        missing=program['facts'][plan['fact_id']]['value']
        if not (case/'04-perturbation/00-receive-input/01-input.json').exists() and numbers(final['context']+' '+final['question'])[Decimal(missing.replace(',',''))]:
            raise ValueError('DELETED_VALUE_STILL_PRESENT')
    request={'original_context':rebuilt['context'] if axis=='IC_SOURCE' else sample['context'],**final,'axis':axis,'intent':intent,
             'edits':response['patches'],'recovery_review':'DEFERRED_BY_USER'}
    validate('shared.01-02.02-03.review-and-validation.request',request)
    return request,{'stage16_ref':stage,'observation_sha256':observation_hash(final),
                    'plan_sha256':meta['plan_sha256'],'plan_snapshot':deepcopy(plan), 'checks':['original_pot_eligible', 'current_plan_binding',
                    'authorized_edit_replay','question_unchanged','unchanged_regions_preserved','numeric_contract']}


class AuditResponseError(ValueError):
    def __init__(self,issues):
        self.issues=issues
        super().__init__(issues[0]['code'])


def evaluate_legacy(request,response):
    """R17.3: exact cited-text grounding and deterministic aggregation, not truth proof."""
    validate('shared.01-02.02-03.review-and-validation.request',request);validate('shared.01-02.02-03.review-and-validation.response.v2',response)
    applicable={c:True for c in ('preservation','planned_change','scope','unplanned_content','readability')}
    applicable.update(source_assignment=request['axis']=='IC_SOURCE',
                      explicit_resolution=request['axis'].startswith('IC_'),ea_consistency=request['axis']=='EA')
    issues=[]
    def issue(code,criterion,**details):issues.append({'code':code,'criterion':criterion,**details})
    def evidence(items,criterion,require_final=True):
        if not items:issue('AUDIT_EVIDENCE_MISSING',criterion)
        if require_final and not any(e['field'] in ('context','question') for e in items):
            issue('FINAL_TEXT_EVIDENCE_REQUIRED',criterion)
        for e in items:
            if e['quote'] not in request[e['field']]:issue('AUDIT_QUOTE_NOT_IN_TEXT',criterion,**e)
    for f in response['findings']:
        expected=applicable[f['criterion']]
        if (f['judgment']=='NOT_APPLICABLE')==expected:
            issue('AUDIT_APPLICABILITY_MISMATCH',f['criterion'],judgment=f['judgment'],applicable=expected)
        if expected:evidence(f['evidence'],f['criterion'])
        elif f['evidence']:evidence(f['evidence'],f['criterion'],False)
    evidence(response['state_evidence'],'observed_state')
    if issues:raise AuditResponseError(issues)
    states=[f['judgment'] for f in response['findings'] if applicable[f['criterion']]]
    status='FAIL' if 'FAIL' in states else 'NOT_EVALUATED' if 'UNKNOWN' in states else 'PASS'
    allowed={'ANSWER':{'ANSWERABLE'},'IC_VALUE':{'CONFLICT'},'IC_RELATION':{'CONFLICT'},
             'IC_SOURCE':{'CONFLICT','RESOLVED'},'EA':{'MISSING_TARGET_EVIDENCE'}}[request['axis']]
    if response['observed_state'] in ('MIXED','UNKNOWN') and status=='PASS':status='NOT_EVALUATED'
    elif response['observed_state'] not in allowed and status=='PASS':status='FAIL'
    return {'status':status,'scope':'FINAL_TEXT_ONLY','observed_state':response['observed_state'],
            'state_reason':response['state_reason'],'state_evidence':response['state_evidence'],
            'findings':response['findings'],'recovery_review':'DEFERRED_BY_USER',
            'full_EA_verdict':'NOT_EVALUATED' if request['axis']=='EA' else 'NOT_APPLICABLE',
            'stage18':'NOT_RUN','human_decision':'PENDING',
            'limitation':'Single-model text audit; quoted evidence is checked, semantic truth is not proven.'}


def evaluate(request, response):
    """R17.3: three semantic judgments; no quote or independent state gate."""
    validate('shared.01-02.02-03.review-and-validation.request', request)
    validate('shared.01-02.02-03.review-and-validation.response', response)
    findings = response['findings']
    judgments = [item['judgment'] for item in findings]
    status = 'FAIL' if 'FAIL' in judgments else 'NOT_EVALUATED' if 'UNKNOWN' in judgments else 'PASS'
    reasons = '; '.join(f"{f['criterion']}: {f['reason']}" for f in findings if f['judgment'] != 'PASS')
    return {'audit_version': 3, 'status': status, 'scope': 'FINAL_TEXT_ONLY',
            'findings': findings, 'reason': reasons,
            'recovery_review': 'DEFERRED_BY_USER',
            'full_EA_verdict': 'NOT_EVALUATED' if request['axis'] == 'EA' else 'NOT_APPLICABLE',
            'stage18': 'NOT_RUN', 'human_decision': 'PENDING',
            'limitation': 'Single-model semantic audit; not a proof of unanswerability or human approval.'}


def evaluate_saved(request, response, report):
    """Recheck old records with their old rules; never convert them to v3 PASS."""
    version = report.get('audit_version', 2)
    if version == 2:
        return evaluate_legacy(request, response)
    if version == 3:
        return evaluate(request, response)
    raise ValueError('UNSUPPORTED_AUDIT_VERSION')


README='''# 17번 완성 문장 의미 검사 — {label}

이번 범위 상태: **{status}**. 입력된 최종 문장에 대한 단일 모델의 감사이며 역산·우회는 보류입니다. EA는 삭제 사실까지만 검사하며 전체 답변 불가능을 확정하지 않습니다. 18번 호출·사람 승인은 하지 않았습니다.

읽는 순서:
1. `01-input/check.json` → `01-input.json`: 최신 생성 본문·계획 연결과 실제 감사 입력.
2. `audit/01-input.json`: 프롬프트·모델·전송 응답 스키마.
3. `audit/02-raw-response.json` → `audit/03-result/schema-check.json`: 실제 원응답과 동일 스키마 검사.
4. `03-result.json`: 세 가지 판정·실패/보류 이유·audit_version=3. 실패 시 `03-result/failure.json`.

문항 루트 `events.jsonl`에 실행/파일 로그, `audit/03-result/usage.json`에 사용량이 있습니다.
뷰어에서 해당 유형의 5번 문장과 답변 하단에 **17번 의미 검사**가 표시됩니다. 예전 본문에 대한 결과는 최신 본문의 판정으로 사용하지 않습니다.
'''


def audit_event_reason(report):
    """R17: failed criteria explain rejection; observed state alone does not."""
    if report['status']=='FAIL':
        return report.get('reason') or '; '.join(
            f"{item['criterion']}: {item['reason']}" for item in report.get('findings',[])
            if item.get('judgment')=='FAIL') or 'Failure reason not recorded'
    return report.get('reason') or report.get('state_reason','')


def audit_one(ctx,config,request,binding,stage,label):
    with ctx.trace.activate(),ctx.trace.span('dtt.final_text_audit',stage=stage,step='',role='python'):
        ctx.save(stage+'/01-input.json',request);ctx.save(stage+'/01-input/check.json',{'status':'PASS',**binding})
        try:
            def handler(payload,*,response_schema):
                if response_schema!=describe('shared.01-02.02-03.review-and-validation.response')['schema']:raise ValueError('AUDIT_SCHEMA_CHANGED')
                return call(config,'shared.01-02.02-03.review-and-validation',payload,save=lambda n,v:ctx.save(stage+'/audit/'+n,v))
            response=ctx.invoke(stage,'03-LLM-call','shared.01-02.02-03.review-and-validation',request,local=handler)
            report=evaluate(request,response)
        except (StepStopped,ValueError,TypeError,KeyError) as error:
            reason=error.result.reason if isinstance(error,StepStopped) else str(error)
            ctx.save(stage+'/03-result/failure.json',{'status':'FAIL','reason':reason,'stage18':'NOT_RUN'})
            report={'audit_version':3,'status':'FAIL','scope':'FINAL_TEXT_ONLY','reason':reason,
                    'findings':[],'failure_kind':'AUDIT_RESPONSE_INVALID','semantic_status':'NOT_EVALUATED',
                    'response_errors':getattr(error,'issues',[]),
                    'recovery_review':'DEFERRED_BY_USER','stage18':'NOT_RUN','human_decision':'PENDING'}
        settings=read_settings(config,'shared.01-02.02-03.review-and-validation')
        report.update(binding,audit_ref=stage,model=settings['model'],effort=settings['effort'])
        ctx.save(stage+'/03-result.json',report)
        ctx.save_text(stage+'/README.md',README.format(label=label,status=report['status']))
        ctx.trace.update(status=report['status'],reason=audit_event_reason(report))
    return report


def publish(ctx,label,stage,report):
    pointer=ctx.root/candidate_root(label)/'latest-audit.json'
    value={'stage':stage,'stage16_ref':report['stage16_ref'],'observation_sha256':report['observation_sha256']}
    if pointer.exists():
        ctx.save(stage+'/previous-latest-audit.json',read(pointer))
        temp=pointer.with_suffix('.tmp')
        with temp.open('x') as stream:json.dump(value,stream)
        temp.replace(pointer);ctx.trace.artifact(str(pointer.relative_to(ctx.root)))
    else:ctx.save(str(pointer.relative_to(ctx.root)),value)


def adversarial_requests(requests):
    """Two bounded meaning errors; not production candidates or a quality benchmark."""
    examples=[]
    value=deepcopy(requests['IC_VALUE_01_BEFORE'][0])
    text=value['edits'][0]['text']; wrong=text.replace('past quarter','next quarter')
    if wrong==text:raise ValueError('COUNTEREXAMPLE_PERIOD_PHRASE_NOT_FOUND')
    value['context']=value['context'].replace(text,wrong,1)
    value['edits'][0]['text']=wrong  # Actual edit log follows text; intent keeps the original period.
    examples.append(('wrong-period',value,['planned_change']))
    source=deepcopy(requests['IC_SOURCE_A_ONLY'][0]);other=requests['IC_SOURCE_B_ONLY'][0]
    source['context']=other['context'];source['edits']=other['edits']
    examples.append(('wrong-source-side',source,['planned_change']))
    return examples


def run(case_dir,config,revision='v1',include_counterexamples=False,labels=None,prerequisite_report=None):
    case=Path(case_dir).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',revision):raise ValueError('INVALID_AUDIT_REVISION')
    all_labels=['ANSWER']+[v['label'] for v in read(case/'04-perturbation/05-list-candidates/03-result.json')]
    labels=all_labels if labels is None else labels
    if not labels or any(label not in all_labels for label in labels):raise ValueError('UNKNOWN_AUDIT_LABEL')
    if len(labels)!=len(set(labels)):raise ValueError('DUPLICATE_AUDIT_LABEL')
    requests={label:prepare(case,label) for label in labels}
    stages={label:audit_root(label)+'/'+revision for label in labels}
    family='05-text/02-audit-meaning/00-run-summary/'+revision
    for p in [family,*stages.values()]:
        if (case/p).exists():raise ValueError('AUDIT_OUTPUT_ALREADY_EXISTS')
    if include_counterexamples:
        fixtures={label:requests.get(label) or prepare(case,label) for label in
                  ('IC_VALUE_01_BEFORE','IC_SOURCE_A_ONLY','IC_SOURCE_B_ONLY')}
        examples=adversarial_requests(fixtures)
    else:examples=[]
    ctx=RunContext.resume(case,{},case.name);settings=read_settings(config,'shared.01-02.02-03.review-and-validation')
    ctx.save(family+'/config.json',read(config))
    ctx.save(family+'/plan.json',{'labels':labels,'model':settings['model'],'effort':settings['effort'],
              'maximum_calls':len(labels)+len(examples),'automatic_retries':0,'estimated_cost':None,
              'cost_status':'CLI billing price unavailable; record actual usage',
              'recovery_review':'DEFERRED_BY_USER','stop_after':17})
    results=[]
    for label in labels:
        report=audit_one(ctx,config,*requests[label],stages[label],label)
        publish(ctx,label,stages[label],report)
        results.append({'label':label,'status':report['status'],'audit_version':report['audit_version'],'audit_ref':stages[label]})
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    if prerequisite_report:
        reports=({'IC_VALUE_01_BEFORE':prerequisite_report} if 'audit_ref' in prerequisite_report else prerequisite_report)
        for label,prior in reports.items():
            stages[label]=prior['audit_ref']
            results.insert(0,{'label':label,'status':prior['status'],
                             'audit_version':prior['audit_version'],'audit_ref':prior['audit_ref'],
                             'performed_before_source_generation':True})
    checks=[]
    for name,request,criteria in examples:
        stage=family+'/counterexamples/'+name
        binding={'stage16_ref':None,'observation_sha256':observation_hash({k:request[k] for k in ('context','question')}),
                 'plan_sha256':None,'checks':['deliberately_mutated_LOCAL_QA_ONLY'], 'not_a_dataset_candidate':True}
        report=audit_one(ctx,config,request,binding,stage,name)
        caught=report['status']=='FAIL' and any(f['criterion'] in criteria and f['judgment']=='FAIL' for f in report['findings'])
        checks.append({'case':name,'caught':caught,'audit_ref':stage,'not_a_dataset_candidate':True})
        print(json.dumps(checks[-1]),flush=True)
    usage=[{'stage':p,'usage':read(case/p/'audit/03-result/usage.json')} for p in list(stages.values())+
           [family+'/counterexamples/'+n for n,_,_ in examples] if resolve_read(case/p/'audit/03-result/usage.json').exists()]
    summary={'results':results,'counterexamples':checks,'usage':usage,
             'pipeline_status':'COMPLETED','scope':'FINAL_TEXT_ONLY','stage18':'NOT_RUN','recovery_review':'DEFERRED_BY_USER'}
    ctx.save(family+'/review.json',summary)
    ctx.save_text(family+'/README.md','# 17번 실행 안내\n\n`plan.json` → 유형별 `audit_ref/README.md` → `review.json` 순서로 읽습니다.\n'
        '본문은 수정하지 않습니다. 통과·실패·판정 불가를 그대로 보관하며, 검사 사례는 데이터 후보에 등록하지 않습니다.\n'
        '5번 문장과 답변 하단에서 세 가지 판정·실패/보류 이유·전송/수신 기록을 확인합니다. 역산·18번·사람 승인은 미실행입니다.\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--revision',default='v1');parser.add_argument('--counterexamples',action='store_true')
    parser.add_argument('--label',action='append',help='Audit only these saved variants; repeat to select several.')
    args=parser.parse_args();run(args.case,args.config,args.revision,args.counterexamples,args.label)
