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
        results.append({'label':label,'status':report['status'],'observed_state':report.get('observed_state','v3 세 가지 판단'),
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
    ctx.save_text('05-text/STAGE17-README.md',f'''# 17번 완성 문장 의미 검사 — 첫 문항

이번 범위: **{summary['status']}**. 원본 1개와 생성 본문 7개의 최신 판정입니다. 역산·우회·EA 답 비유일성, 18번 독립 답변, 사람 승인은 미실행입니다.

|대상|최신 판정|관찰한 상태|실행 기록|
|---|---|---|---|
{rows}

실제 Luna/low 호출은 총 **{len(calls)}회**입니다. 최초 10회, 문제를 보완한 뒤 4회, 기간 검사 사례 재확인 1회입니다. 실제 본문 감사 10회와 개발용 오류 사례 감사 5회이며 고유 본문 수와 호출 횟수를 구분합니다. 토큰 사용량은 `stage17-verification.json`의 `actual_usage`, 비용은 확인되지 않아 미확인입니다.

첫 시도에서 인용문 변형·적용 항목 오류, EA 허용 삭제 범위 오해, 출처 배정 오류 미탐지가 나왔습니다. 허용 편집 범위와 값별 출처 배정을 명시하고 해당 사례를 재확인했습니다. 기간 오류 예시는 편집 로그도 변형된 본문과 일치시켜 다시 검사했습니다. 이전 원응답과 실패 기록은 삭제하지 않았습니다. 이 개발 사례를 반복 확인한 결과를 일반 정확도로 보고하지 않습니다.

읽는 순서:
1. `stage17-verification.json`: 최신 판정, 모든 시도, 사용량, 보류 범위.
2. 유형별 `latest-audit.json` → 해당 `audits/v*/README.md`: 실제 요청·스키마·원응답·판정·인용.
3. `stage17-v1/review.json`, `stage17-v2/review.json`, `stage17-v3/review.json`: 최초 결과와 보완 흐름.
4. `stage17-local-checks.json`: 로컬 검사 결과. 오류 사례는 `stage17-v*/counterexamples/`이며 데이터 후보가 아닙니다.

`plan-binding.json`은 현재 계획 해시와 감사 당시 계획 해시를 다시 대조한 Python 기록입니다. 본문·질문·계획이 달라지면 뷰어는 예전 PASS를 현재 판정으로 표시하지 않습니다. 문제 루트 `events.jsonl`에 파일·호출 로그가 있습니다.

뷰어: 실행 `first-10-pot-validated-v3` → `test-0001` → 유형 선택 → **5 문장과 답변** 하단의 **17번 완성 문장 의미 검사**. 항목별 이유와 실제 본문 인용을 확인하고, 아래 LLM 디버그에서 당시 프롬프트·응답 스키마·원응답을 확인합니다. `stage17-ui-review.json`에 실제 화면 확인 기록을 남깁니다.

통과는 범위를 제한한 단일 모델의 제작 검사 결과입니다. IC-SOURCE의 출처 선호에 의한 RESOLVED는 따로 기록하며, EA의 MISSING_TARGET_EVIDENCE는 선택 수치가 없다는 뜻입니다. 전체 복원 불가나 논문 타당성, 사람 승인으로 확대하지 않습니다.
''')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('attempt_history','current_results')},ensure_ascii=False))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',type=Path,required=True)
    verify(parser.parse_args().case)
