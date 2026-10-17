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


README = '''# Type by type prompt for actual re-enactment {name}

State of play: {status}The old one. 10In the case, test-0008The equation keeps the equation of the equation unchanged.
The basic POT calculation graphs and transformation plans {source}The hash reuses the same copy.
16And the phrase "B" 17The bar-meaning check calls up to the first case. The old generated case judgment doesn't copy.

In order of reading:
1. plan.json / config.json: object; maximum call number; model; referral setting; directional hash.
2. Production-progress.json: Progress by case; failure; Ready for review: number.
3. Each case 05-text/stage16-typed-v1/review.json: Created results and causes of failure.
4. Each case 05-text/stage17-typed-v1/review.json: Three judgments from the tests.
5. PRODUCTION-RESULTS.json: total estimate; nearby; actual call time; usage.
6. Each case 06-human-review/01-collect-results/typed-v1: Human review data. Judgment is pending.

Every call is realized or audited. 01-input.json(real prompt and type; file hash ),
01-input/response-schema.json, 02-raw-response.json, 03-result/schema-check.json, 03-result/usage.json is read.
events.jsonl is a timeline log recorded during this run. The old POT call connects to replay-source.json.
copied-inputs.json is a reuse file list, source, and not a new model call.

Common viewer: http://127.0.0.1:8893/?run={name}&case=test-0002&tab=dtt
Real time log: http://127.0.0.1:8893/live?run={name}
5The generated and verified 6I see it in the order of the person's judgement.18There is no automatic approval.
The cost is CLI, the uncertain sum of the call time, which separates the actual total visit and time.
This README automatically generates from the prompt_rerun.py template.
'''


def guide(root, state):
    table='\n'.join(f"|{name}|{row['status']}|{row.get('ready','—')} / {row.get('total','—')}|{row.get('reason','')}|"
                    for name,row in state['cases'].items())
    (root/'README.md').write_text(README.format(name=root.name, source=state['source'], status=state['status'])+
        '\n## The current state of each case\n\nReady for review: / the target is the target\n|---|---|---|---|\n'+table+'\n')


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
