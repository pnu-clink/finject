"""PR01–04: new Stage16/17 run from immutable validated inputs and plans."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
digest = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['digest']).digest
make_request = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['make_request']).make_request
realize = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['run']).run
from finarch.dataset.shared.review.dtt_audit import run as audit
build = __import__('finarch.dataset.02-generation.05-human-review.human_review', fromlist=['build']).build
from finarch.dataset.shared.calculation.python_graph import load_graph
from finarch.shared.providers.cli import prepare_instruction, read_settings, inspect_runtime
describe_prompt = __import__('finarch.dataset.02-generation.02-generate-text.realization_prompts', fromlist=['describe_prompt']).describe_prompt
from finarch.dataset.shared.review.audit_prompts import describe_prompt as audit_prompt


def now():
    return datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds")


def write(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    tmp.replace(path)


README = '''# 유형별 프롬프트 실제 재실행 — {name}

상태: {status}. 기존 10문항 중 test-0008은 정답 불일치 제외를 유지합니다.
원문·POT·계산 그래프·변경 계획은 {source}의 해시가 같은 사본을 재사용합니다.
16번 문장과 17번 의미 검사는 첫 문항까지 새로 호출합니다. 예전 생성문·판정은 복사하지 않습니다.

읽는 순서:
1. plan.json / config.json: 대상·최대 호출 수·모델·추론 설정·지침 해시.
2. production-progress.json: 문항별 진행·실패·Ready for review: 개수.
3. 각 문항 05-text/stage16-typed-v1/review.json: 생성 결과와 실패 원인.
4. 각 문항 05-text/stage17-typed-v1/review.json: 세 판단 검사 결과.
5. PRODUCTION-RESULTS.json: 전체 집계·비교·실제 호출 시간·사용량.
6. 각 문항 06-human-review/01-collect-results/typed-v1: 사람 검토 자료. 판정은 PENDING입니다.

각 호출의 realize/ 또는 audit/에서 01-input.json(실제 프롬프트와 유형·파일 해시),
01-input/response-schema.json, 02-raw-response.json, 03-result/schema-check.json, 03-result/usage.json을 읽습니다.
events.jsonl은 이번 실행 중 기록한 시간순 로그입니다. 예전 POT 호출은 replay-source.json으로 연결합니다.
copied-inputs.json은 재사용 파일 목록·출처·해시이며, 재사용을 새 모델 호출로 세지 않습니다.

공통 뷰어: http://127.0.0.1:8893/?run={name}&case=test-0002&tab=dtt
실시간 로그: http://127.0.0.1:8893/live?run={name}
5번 생성·검증 → 6번 사람 판정 순서로 봅니다. 자동 재시도·역산·18번·자동 승인은 없습니다.
비용은 CLI 단가 미확인입니다. 호출 시간 합은 실제 전체 경과 시간과 구분합니다.
이 README는 prompt_rerun.py 템플릿에서 자동 생성합니다.
'''


def guide(root, state):
    table='\n'.join(f"|{name}|{row['status']}|{row.get('ready','—')} / {row.get('total','—')}|{row.get('reason','')}|"
                    for name,row in state['cases'].items())
    (root/'README.md').write_text(README.format(name=root.name, source=state['source'], status=state['status'])+
        '\n## 문항별 현재 상태\n\n|문항|상태|사람 Ready for review: / 대상|이유|\n|---|---|---|---|\n'+table+'\n')


def prepare(source, root):
    # PR01: verify first, preserve existing observations, start a fresh journal.
    raise ValueError('PAST_RUN_REUSE_REMOVED: use a fresh pipeline from prepared inputs')


def report(root, state):
    # PR04: count real CLI invocations, current candidates, failures and old comparisons.
    plan=read(root/'plan.json'); usage=Counter(); role_usage=defaultdict(Counter); times=Counter(); calls=Counter(); selections=[]; results=[]; missing_usage=[]
    for p in root.glob('test-*/05-text/**/03-result/usage.json'):
        u=read(p);req=read(p.with_name('01-input.json'));role=req['role']
        calls[role]+=u['cli_invocations']
        process=p.with_name('02-raw-response/cli-execution.json')
        if process.exists():times[role]+=read(process).get('elapsed_seconds',0)
        usage.update({k:v for k,v in (u.get('reported_usage') or {}).items() if isinstance(v,int)})
        role_usage[role].update({k:v for k,v in (u.get('reported_usage') or {}).items() if isinstance(v,int)})
        if u.get('reported_usage') is None:missing_usage.append(str(p.relative_to(root)))
        selections.append({'path':str(p.parent.relative_to(root)),'role':role,'model':req['model'],'effort':req['effort'],
                           'prompt_id':req['prompt_selection']['id'],'prompt_sha256':req['prompt_selection']['sha256']})
    for old in plan['baseline']:
        case=root/old['case'];label=old['label'];p=case/f'05-text/{label}/latest-audit.json'
        current=read(case/read(p)['stage']/'03-result.json') if p.exists() else {}
        failure=case/f'05-text/{label}/01-generate-text/typed-v1/03-result/failure.json'
        results.append({**old,'previous_status':old['status'],'status':current.get('status','NOT_EVALUATED'),
                        'reason':current.get('reason',read(failure)['reason'] if failure.exists() else 'NOT_RUN'),
                        'audit_ref':current.get('audit_ref')})
    unchanged=all(digest(Path(state['source'])/case.name/p)==h and digest(case/p)==h
                  for case in root.glob('test-*') for p,h in read(case/'copied-inputs.json')['sha256'].items())
    generated=[]
    for case in sorted(root.glob('test-*')):
        review=case/'05-text/stage16-typed-v1/review.json'
        if review.exists():generated.extend({'case':case.name,**row} for row in read(review)['results'])
    snapshots={(role,p['id']):p['sha256'] for role,parts in plan['prompts'].items() for p in parts}
    matched=all(snapshots.get((s['role'],s['prompt_id']))==s['prompt_sha256'] for s in selections)
    result={'state':state,'call_count':dict(calls),'cli_seconds_by_role':dict(times),'reported_usage':dict(usage),
            'reported_usage_by_role':{k:dict(v) for k,v in role_usage.items()},
            'results':results,'statuses':dict(Counter(x['status'] for x in results)),
            'original_inputs_unchanged':unchanged,'prompt_selections':selections,'actual_billed_cost':None,
            'generation_results':generated,'generation_statuses':dict(Counter(x['status'] for x in generated)),
            'prompt_snapshots_match_actual_calls':matched,
            'usage_records_complete':not missing_usage,'missing_usage_paths':missing_usage,
            'stage18':'NOT_RUN','human_decision':'PENDING'}
    write(root/'PRODUCTION-RESULTS.json',result)
    summary=read(root/'summary.json');summary.update(status=state['status'],processed=sum(x['status']!='PENDING' for x in state['cases'].values()),
        model_calls=sum(calls.values()),production_statuses=result['statuses'])
    write(root/'summary.json',summary);guide(root,state)
    return result


def run(root):
    root=Path(root).resolve();config=root/'config.json';state=read(root/'production-progress.json')
    if state['status']!='PREPARED':raise ValueError('RUN_ALREADY_STARTED')
    runtime=inspect_runtime('codex')
    if runtime['native_tool_enforcement']!='VERIFIED':raise ValueError('NATIVE_CONTROL_VERIFICATION_REQUIRED')
    for role in ('02-generation.02-generate-text.realization','shared.01-02.02-03.review-and-validation'):
        if read_settings(config,role)['model'] not in runtime['verified_models']:raise ValueError('MODEL_CONTROL_VERIFICATION_REQUIRED')
    def update(name=None,**values):
        (state['cases'][name] if name else state).update(values);state['updated_at']=now()
        write(root/'production-progress.json',state)
    update(status='RUNNING',started_at=now(),message='Generate with type-specific prompts, audit the results, and prepare human review materials.')
    try:
        for name in state['cases']:
            if name=='test-0008':continue
            case=root/name
            try:
                # PR02: individual generation calls, paired placements share one sentence.
                update(name,status='GENERATING',reason='Generating new text with type-specific instructions')
                made=realize(case,config,revision='typed-v1')
                labels=['ANSWER']+[r['label'] for r in made['results'] if r['status']=='PASS']
                update(name,status='AUDITING',generated=len(labels)-1,reason='Auditing the new text with Luna, reasoning none')
                # PR03: same schema, three judgments, no Stage18 or automatic approval.
                checked=audit(case,config,revision='typed-v1',labels=labels)
                review=build(case,revision='typed-v1')
                update(name,status='AWAITING_HUMAN',audited=len(checked['results']),ready=review['ready'],
                       total=review['total'],reason=f"Ready for review: {review['ready']}/{review['total']}; failures and unevaluated cases preserved separately")
            except Exception as error:
                update(name,status='ERROR',reason=f'{type(error).__name__}: {error}')
            report(root,state);print(name,state['cases'][name],flush=True)
        update(status='COMPLETED',finished_at=now(),message='Generation and auditing finished. Failures and unevaluated cases are preserved; human decisions are pending.')
    except BaseException:
        update(status='INTERRUPTED',finished_at=now(),message='Execution stopped. Saved raw responses and logs are preserved.')
        raise
    finally:
        out=report(root,state);print(json.dumps({k:out[k] for k in ('call_count','statuses','original_inputs_unchanged')},ensure_ascii=False),flush=True)
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source');parser.add_argument('--root',required=True);parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    if args.prepare_only:prepare(args.source,args.root)
    else:run(args.root)
