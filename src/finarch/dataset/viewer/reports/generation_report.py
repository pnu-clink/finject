"""Report completed generation from saved evidence, including interrupted calls."""
import argparse
from datetime import datetime
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
TYPES = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['TYPES']).TYPES


def build(bundle):
    bundle=Path(bundle).resolve();root=bundle/'02-generation'
    summary=read(root/'summary.json');timing=read(root/'timing.json')
    if summary['status'] not in ('PASS','LIMIT_REACHED','REQUIRES_PLAN_REVIEW','REQUIRES_REVIEW') or timing.get('status')!='COMPLETED':
        raise ValueError('GENERATION_NOT_FINISHED')
    gate=evaluate(bundle,persist=False)
    if not gate['allow_generation']:raise ValueError('APPROVED_INPUTS_CHANGED')
    expected=set(gate['approved']);latest=summary['latest']
    if set(latest)!=expected:raise ValueError('CASE_COVERAGE_MISMATCH')
    rows=[]
    for name,variants in latest.items():
        if set(map(int,variants))!=set(range(len(TYPES))):raise ValueError('TYPE_COVERAGE_MISMATCH')
        for index,item in variants.items():
            path=bundle/item['path'];stored=read(path/'run.json')
            if stored['status']!=item['status']:raise ValueError('RESULT_STATUS_MISMATCH')
            human=read(path/('05-human-review' if (path/'05-human-review/01-result.json').exists() else '04-human-review')/'01-result.json')
            if human['automatic_status']!=item['status']:raise ValueError('HUMAN_MATERIAL_STATUS_MISMATCH')
            if (path/'04-human-review/decision.json').exists():raise ValueError('FINAL_HUMAN_DECISION_PRESENT')
            rows.append({'case':name,'type':TYPES[int(index)][2],'status':item['status'],'reason':item.get('reason',''),'origin':item['path']})
    calls=[]
    for start in root.rglob('cli-start.json'):
        call=start.parent.parent;execution=call/'02-raw-response/cli-execution.json';profile=start.parent/'cli-profile.json'
        data=read(execution) if execution.exists() else {};model=read(profile) if profile.exists() else {}
        calls.append({'path':str(call.relative_to(bundle)),'provider':model.get('provider'),'model':model.get('model'),'effort':model.get('effort'),'completed':execution.exists(),'exit_code':data.get('exit_code'),'elapsed_seconds':data.get('elapsed_seconds'),'interrupted_archive':'interrupted-attempts' in call.parts})
    starts=[timing['started_at']]
    for p in (root/'interrupted-attempts').glob('*/timing.json'):starts.append(read(p)['started_at'])
    first=min(starts,key=datetime.fromisoformat)
    elapsed=(datetime.fromisoformat(timing['ended_at'])-datetime.fromisoformat(first)).total_seconds()
    totals={label:dict(pass_count=sum(r['type']==label and r['status']=='PASS' for r in rows),fail_count=sum(r['type']==label and r['status']!='PASS' for r in rows)) for _,_,label in TYPES}
    report={'status':summary['status'],'approved_cases':sorted(expected),'excluded_cases':gate['rejected'],'rounds':summary['rounds'],'rows':rows,'type_totals':totals,'calls':calls,'call_count':len(calls),'completed_call_count':sum(c['completed'] for c in calls),'llm_elapsed_seconds_sum':sum(c['elapsed_seconds'] or 0 for c in calls),'generation_wall_seconds_including_restart':elapsed,'first_started_at':first,'ended_at':timing['ended_at'],'final_human_review_performed':False}
    write(root/'result-report.json',report)
    lines=['# Generation 최종 결과','',f"승인 {len(expected)}문항 · 제외 {len(gate['rejected'])}문항 · {len(rows)}개 유형 결과. 최종 사람 판정은 수행하지 않았습니다.",'','|유형|통과|실패|','|---|---:|---:|']
    lines += [f"|{label}|{n['pass_count']}|{n['fail_count']}|" for label,n in totals.items()]
    lines+=['','## 차수별 결과','']+[f"- {r['round']}차: 실패 {r['failure_count']}건 · {r['decision']}" for r in summary['rounds']]
    lines+=['','## 시간과 호출','',f"전체 Generation {elapsed:.1f}초(중단·재개 구간 포함). 완료된 LLM 호출 시간 합계 {report['llm_elapsed_seconds_sum']:.1f}초. 호출 시작 {len(calls)}건, 종료 기록 {report['completed_call_count']}건. 미종료 호출은 성공으로 집계하지 않습니다.",'','## 최종 실패','']
    lines += [f"- {r['case']} / {r['type']}: {r['reason']} ([원기록]({Path(r['origin']).relative_to('02-generation')}/run.json))" for r in rows if r['status']!='PASS'] or ['없음.']
    lines+=['','`result-report.json`은 유형별 집계·호출·각 결과의 원래 차수를 포함합니다. `summary.json`은 최종 누적 결과, 각 차수의 `final-validator.json`은 당시 실패 목록입니다. 원응답은 해당 유형의 단계 폴더에 있고, 중단된 미완료 자료는 `interrupted-attempts`에 보존됩니다.']
    lines+=['','실행 중 수정·재개 내역은 [README](README.md)를 확인하십시오. 실제 적용된 생성 지침은 호출별 저장 프롬프트를 기준으로 확인하며, 이 누적 통과 결과를 한 번의 생성 성공률로 해석하지 않습니다.']
    (root/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    report=build(parser.parse_args().run);print({k:report[k] for k in ('status','call_count','type_totals')})
