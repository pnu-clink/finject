"""Verify saved Stage17 evidence and generate its review guide; no LLM calls."""
import argparse
from collections import Counter
import json
from pathlib import Path

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
from finarch.dataset.shared.review.dtt_audit import prepare, evaluate_saved, read


def verify(case):
    case=Path(case).resolve();ctx=RunContext.resume(case,{},case.name)
    labels=['ANSWER']+[v['label'] for v in read(case/'04-perturbation/05-list-candidates/03-result.json')]
    results=[]
    for label in labels:
        request,binding=prepare(case,label)
        stage=read(case/f'05-text/{label}/latest-audit.json')['stage']
        assert stage.startswith(f'05-text/{label}/03-audit-meaning/') and '..' not in stage
        path=case/stage;report=read(path/'03-result.json');saved=read(path/'01-input.json')
        assert all(saved[k]==request[k] for k in ('original_context','context','question','axis'))
        assert all(report[k]==binding[k] for k in ('stage16_ref','plan_sha256','observation_sha256'))
        provider=path/'audit';definition=read(provider/'01-input/response-schema.json')
        schema_check=read(provider/'03-result/schema-check.json');sent=read(provider/'01-input.json')
        assert schema_check['status']=='PASS' and schema_check['schema_sha256']==definition['sha256']
        assert sent['response_schema']==definition['schema']
        evaluated=evaluate_saved(saved,json.loads(read(provider/'02-raw-response.json')['text']),report)
        assert evaluated['status']==report['status']
        assert report['stage18']=='NOT_RUN' and report['recovery_review']=='DEFERRED_BY_USER'
        if label!='ANSWER' and not (path/'plan-binding.json').exists():
            ctx.save(stage+'/plan-binding.json',{'plan_sha256':binding['plan_sha256'],
                'plan_snapshot':binding['plan_snapshot'],
                'basis':'Current plan hash equals the saved Stage16 and audit plan hashes; no model call.'})
        results.append({'label':label,'status':report['status'],'observed_state':report.get('observed_state','v3 \uc138 \uac00\uc9c0 \ud310\ub2e8'),
                        'audit_ref':stage,'stage16_ref':binding['stage16_ref'],
                        'observation_sha256':binding['observation_sha256'],
                        'checks':binding['checks']+['saved_response_schema_match','versioned_response_replay']})
    calls=sorted([*case.glob('05-text/*/03-audit-meaning/v*/audit/03-result/usage.json'),
                  *case.glob('05-text/stage17-v*/counterexamples/*/audit/03-result/usage.json')])
    usage=Counter();history=[]
    for path in calls:
        raw=read(path);usage.update({k:v for k,v in raw['reported_usage'].items() if isinstance(v,int)})
        stage=path.parent.parent;report=read(stage/'03-result.json')
        history.append({'audit_ref':str(stage.relative_to(case)),'status':report['status'],
                        'reason':report.get('reason',report.get('state_reason')),
                        'not_a_dataset_candidate':bool(report.get('not_a_dataset_candidate'))})
    qa=[]
    for name in ('wrong-period','wrong-source-side'):
        versions=sorted(case.glob(f'05-text/stage17-v*/counterexamples/{name}/03-result.json'),
                        key=lambda p:int(p.parents[2].name.split('-v')[-1]))
        report=read(versions[-1]);criterion='scope' if name=='wrong-period' else 'source_assignment'
        caught=report['status']=='FAIL' and any(f['criterion']==criterion and f['judgment']=='FAIL' for f in report['findings'])
        qa.append({'case':name,'caught':caught,'audit_ref':str(versions[-1].parent.relative_to(case))})
    assert not list(case.glob('05-text/**/T04-blind-response/01-input.json'))
    summary={'scope':'first case, original + seven variants; FINAL_TEXT_ONLY',
             'status':'PASS' if all(x['status']=='PASS' for x in results) and all(x['caught'] for x in qa) else 'INCOMPLETE',
             'current_results':results,'counterexamples':qa,'call_count':len(calls),'actual_usage':dict(usage),
             'estimated_cost':None,'actual_billed_cost':None,'cost_status':'CLI price unavailable',
             'attempt_history':history,'stage16_text_unchanged':True,'stage18':'NOT_RUN',
             'human_decision':'PENDING','recovery_review':'DEFERRED_BY_USER',
             'general_auditor_accuracy':'NOT_EVALUATED; development cases were reused after fixes'}
    ctx.save('05-text/stage17-verification.json',summary)
    rows='\n'.join(f"|{r['label']}|{r['status']}|{r['observed_state']}|[{r['audit_ref'].split('/')[-1]}]({r['audit_ref'][6:]}/README.md)|" for r in results)
    ctx.save_text('05-text/STAGE17-README.md',f'''# 17\ubc88 \uc644\uc131 \ubb38\uc7a5 \uc758\ubbf8 \uac80\uc0ac — \uccab \ubb38\ud56d

\uc774\ubc88 \ubc94\uc704: **{summary['status']}**. \uc6d0\ubcf8 1\uac1c\uc640 \uc0dd\uc131 \ubcf8\ubb38 7\uac1c\uc758 \ucd5c\uc2e0 \ud310\uc815\uc785\ub2c8\ub2e4. \uc5ed\uc0b0·\uc6b0\ud68c·EA \ub2f5 \ube44\uc720\uc77c\uc131, 18\ubc88 \ub3c5\ub9bd \ub2f5\ubcc0, \uc0ac\ub78c \uc2b9\uc778\uc740 \ubbf8\uc2e4\ud589\uc785\ub2c8\ub2e4.

|\ub300\uc0c1|\ucd5c\uc2e0 \ud310\uc815|\uad00\ucc30\ud55c \uc0c1\ud0dc|\uc2e4\ud589 \uae30\ub85d|
|---|---|---|---|
{rows}

\uc2e4\uc81c Luna/low \ud638\ucd9c\uc740 \ucd1d **{len(calls)}\ud68c**\uc785\ub2c8\ub2e4. \ucd5c\ucd08 10\ud68c, \ubb38\uc81c\ub97c \ubcf4\uc644\ud55c \ub4a4 4\ud68c, \uae30\uac04 \uac80\uc0ac \uc0ac\ub840 \uc7ac\ud655\uc778 1\ud68c\uc785\ub2c8\ub2e4. \uc2e4\uc81c \ubcf8\ubb38 \uac10\uc0ac 10\ud68c\uc640 \uac1c\ubc1c\uc6a9 \uc624\ub958 \uc0ac\ub840 \uac10\uc0ac 5\ud68c\uc774\uba70 \uace0\uc720 \ubcf8\ubb38 \uc218\uc640 \ud638\ucd9c \ud69f\uc218\ub97c \uad6c\ubd84\ud569\ub2c8\ub2e4. \ud1a0\ud070 \uc0ac\uc6a9\ub7c9\uc740 `stage17-verification.json`\uc758 `actual_usage`, \ube44\uc6a9\uc740 \ud655\uc778\ub418\uc9c0 \uc54a\uc544 \ubbf8\ud655\uc778\uc785\ub2c8\ub2e4.

\uccab \uc2dc\ub3c4\uc5d0\uc11c \uc778\uc6a9\ubb38 \ubcc0\ud615·\uc801\uc6a9 \ud56d\ubaa9 \uc624\ub958, EA \ud5c8\uc6a9 \uc0ad\uc81c \ubc94\uc704 \uc624\ud574, \ucd9c\ucc98 \ubc30\uc815 \uc624\ub958 \ubbf8\ud0d0\uc9c0\uac00 \ub098\uc654\uc2b5\ub2c8\ub2e4. \ud5c8\uc6a9 \ud3b8\uc9d1 \ubc94\uc704\uc640 \uac12\ubcc4 \ucd9c\ucc98 \ubc30\uc815\uc744 \uba85\uc2dc\ud558\uace0 \ud574\ub2f9 \uc0ac\ub840\ub97c \uc7ac\ud655\uc778\ud588\uc2b5\ub2c8\ub2e4. \uae30\uac04 \uc624\ub958 \uc608\uc2dc\ub294 \ud3b8\uc9d1 \ub85c\uadf8\ub3c4 \ubcc0\ud615\ub41c \ubcf8\ubb38\uacfc \uc77c\uce58\uc2dc\ucf1c \ub2e4\uc2dc \uac80\uc0ac\ud588\uc2b5\ub2c8\ub2e4. \uc774\uc804 \uc6d0\uc751\ub2f5\uacfc \uc2e4\ud328 \uae30\ub85d\uc740 \uc0ad\uc81c\ud558\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4. \uc774 \uac1c\ubc1c \uc0ac\ub840\ub97c \ubc18\ubcf5 \ud655\uc778\ud55c \uacb0\uacfc\ub97c \uc77c\ubc18 \uc815\ud655\ub3c4\ub85c \ubcf4\uace0\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.

\uc77d\ub294 \uc21c\uc11c:
1. `stage17-verification.json`: \ucd5c\uc2e0 \ud310\uc815, \ubaa8\ub4e0 \uc2dc\ub3c4, \uc0ac\uc6a9\ub7c9, \ubcf4\ub958 \ubc94\uc704.
2. \uc720\ud615\ubcc4 `latest-audit.json` → \ud574\ub2f9 `audits/v*/README.md`: \uc2e4\uc81c \uc694\uccad·\uc2a4\ud0a4\ub9c8·\uc6d0\uc751\ub2f5·\ud310\uc815·\uc778\uc6a9.
3. `stage17-v1/review.json`, `stage17-v2/review.json`, `stage17-v3/review.json`: \ucd5c\ucd08 \uacb0\uacfc\uc640 \ubcf4\uc644 \ud750\ub984.
4. `stage17-local-checks.json`: \ub85c\uceec \uac80\uc0ac \uacb0\uacfc. \uc624\ub958 \uc0ac\ub840\ub294 `stage17-v*/counterexamples/`\uc774\uba70 \ub370\uc774\ud130 \ud6c4\ubcf4\uac00 \uc544\ub2d9\ub2c8\ub2e4.

`plan-binding.json`\uc740 \ud604\uc7ac \uacc4\ud68d \ud574\uc2dc\uc640 \uac10\uc0ac \ub2f9\uc2dc \uacc4\ud68d \ud574\uc2dc\ub97c \ub2e4\uc2dc \ub300\uc870\ud55c Python \uae30\ub85d\uc785\ub2c8\ub2e4. \ubcf8\ubb38·\uc9c8\ubb38·\uacc4\ud68d\uc774 \ub2ec\ub77c\uc9c0\uba74 \ubdf0\uc5b4\ub294 \uc608\uc804 PASS\ub97c \ud604\uc7ac \ud310\uc815\uc73c\ub85c \ud45c\uc2dc\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4. \ubb38\uc81c \ub8e8\ud2b8 `events.jsonl`\uc5d0 \ud30c\uc77c·\ud638\ucd9c \ub85c\uadf8\uac00 \uc788\uc2b5\ub2c8\ub2e4.

\ubdf0\uc5b4: \uc2e4\ud589 `first-10-pot-validated-v3` → `test-0001` → \uc720\ud615 \uc120\ud0dd → **5 \ubb38\uc7a5\uacfc \ub2f5\ubcc0** \ud558\ub2e8\uc758 **17\ubc88 \uc644\uc131 \ubb38\uc7a5 \uc758\ubbf8 \uac80\uc0ac**. \ud56d\ubaa9\ubcc4 \uc774\uc720\uc640 \uc2e4\uc81c \ubcf8\ubb38 \uc778\uc6a9\uc744 \ud655\uc778\ud558\uace0, \uc544\ub798 LLM \ub514\ubc84\uadf8\uc5d0\uc11c \ub2f9\uc2dc \ud504\ub86c\ud504\ud2b8·\uc751\ub2f5 \uc2a4\ud0a4\ub9c8·\uc6d0\uc751\ub2f5\uc744 \ud655\uc778\ud569\ub2c8\ub2e4. `stage17-ui-review.json`\uc5d0 \uc2e4\uc81c \ud654\uba74 \ud655\uc778 \uae30\ub85d\uc744 \ub0a8\uae41\ub2c8\ub2e4.

\ud1b5\uacfc\ub294 \ubc94\uc704\ub97c \uc81c\ud55c\ud55c \ub2e8\uc77c \ubaa8\ub378\uc758 \uc81c\uc791 \uac80\uc0ac \uacb0\uacfc\uc785\ub2c8\ub2e4. IC-SOURCE\uc758 \ucd9c\ucc98 \uc120\ud638\uc5d0 \uc758\ud55c RESOLVED\ub294 \ub530\ub85c \uae30\ub85d\ud558\uba70, EA\uc758 MISSING_TARGET_EVIDENCE\ub294 \uc120\ud0dd \uc218\uce58\uac00 \uc5c6\ub2e4\ub294 \ub73b\uc785\ub2c8\ub2e4. \uc804\uccb4 \ubcf5\uc6d0 \ubd88\uac00\ub098 \ub17c\ubb38 \ud0c0\ub2f9\uc131, \uc0ac\ub78c \uc2b9\uc778\uc73c\ub85c \ud655\ub300\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.
''')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('attempt_history','current_results')},ensure_ascii=False))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',type=Path,required=True)
    verify(parser.parse_args().case)
