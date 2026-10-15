"""Read round evidence and publish a reusable run completion report."""
import argparse
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
from finarch.dataset.viewer.summary_reader import read_status_record
TYPES = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['TYPES']).TYPES


def optional(path,default=None):
    return read(path) if path.exists() else default


def phase_runtime(bundle, phase):
    """Report recorded wall time and case concurrency, never today's defaults."""
    root = bundle / ('01-preparation' if phase == 'preparation' else '02-generation')
    timing = optional(root / 'timing.json', {})
    if phase == 'preparation' and not timing:
        candidate = optional(bundle / 'timing.json', {})
        if candidate.get('scope') == 'preparation':
            timing = candidate
    queues = [root / 'queue.json'] if phase == 'preparation' else sorted(root.glob('0*-round/queue.json'))
    queue = optional(queues[-1], {}) if queues else {}
    schedule = queue.get('settings', {})
    elapsed = timing.get('elapsed_seconds')
    if elapsed is None:
        elapsed = queue.get('elapsed_seconds') if phase == 'preparation' else None
    return {'elapsed_seconds': elapsed, 'started_at': timing.get('started_at'),
            'status': timing.get('status'), 'active_cases': queue.get('active'),
            'concurrency': schedule.get('max_concurrency', schedule.get('concurrency')),
            'queue_status': queue.get('status')}


def cell(record=None,source=None,carried=False):
    return {'status':record.get('status','NOT_EVALUATED') if record else 'NOT_EVALUATED',
            'reason':record.get('reason','') if record else '',
            'source':source,'carried':carried}


def column(number,rows,started,complete,attempted):
    counts=Counter(row['rounds'][number-1]['status'] for row in rows)
    return {'round':number,'state':'COMPLETED' if complete else 'RUNNING' if started else 'NOT_RUN',
            'counts':dict(counts),'attempted':attempted,'total':len(rows)}


def snapshot(bundle, *, gate=None):
    bundle=Path(bundle).resolve();prep=bundle/'01-preparation';gen=bundle/'02-generation'
    names=read(bundle/'input-selection.json')['cases']
    history=prep/'repair-history'
    original=optional(history/'01-original/batch/01-preparation/summary.json')
    repairs=optional(history/'results.json',{'results':[],'planned':0,'processed':0})
    old={r['input_id']:r for r in (original or {}).get('results',[])}
    fixed={r['input_id']:r for r in repairs['results']}
    prep_rows=[];internal_repairs=0
    for name in names:
        case=prep/name;current=optional(case/'run.json')
        initial=old.get(name,current)
        first_source=str((history/'01-original'/name/'run.json').relative_to(bundle)) if name in old and (history/'01-original'/name/'run.json').exists() else str((case/'run.json').relative_to(bundle))
        second=fixed.get(name)
        if not original:
            audit=optional(case/'02-review-and-correct/01-round/01-LLM-audit-original/03-result.json')
            revised=(case/'02-review-and-correct/01-round/02-LLM-revise-text').exists()
            if revised:
                initial=audit;second=current;internal_repairs+=1
                first_source=str((case/'02-review-and-correct/01-round/01-LLM-audit-original/03-result.json').relative_to(bundle))
        rounds=[cell(initial,first_source)]
        rounds.append(cell(second,str((case/'run.json').relative_to(bundle))) if second else {**rounds[0],'carried':True})
        rounds.append({**rounds[1],'carried':True})
        prep_rows.append({'case':name,'type':'ANSWER','rounds':rounds})
    prep_started=[bool(original) or any((prep/n).exists() for n in names),history.exists() or internal_repairs>0,False]
    prep_complete=[all(r['rounds'][0]['status'] in ('PASS','FAIL') for r in prep_rows),
                   (repairs['planned']>0 and repairs['processed']==repairs['planned']) or (internal_repairs>0 and all(optional(prep/n/'run.json') for n in names)),False]
    prep_attempts=[sum(r['rounds'][0]['status'] in ('PASS','FAIL') for r in prep_rows),len(fixed) or internal_repairs,0]
    for row in prep_rows:
        for i in range(3):
            if not prep_started[i]:row['rounds'][i]={'status':'NOT_RUN','reason':'','source':None,'carried':False}
    # Explicit batch-round records supersede the historical single-repair layout.
    round_paths=[prep/'rounds'/f'{i:02d}-round.json' for i in range(1,4)]
    if round_paths[0].exists():
        records=[optional(path) for path in round_paths]
        maps=[{r['input_id']:r for r in item.get('results',[])} if item else {} for item in records]
        prep_started=[item is not None for item in records]
        prep_attempts=[len(items) for items in maps]
        prep_rows=[]
        for name in names:
            cells=[];previous=None
            for i,items in enumerate(maps):
                if name in items:
                    previous=cell(items[name],str(round_paths[i].relative_to(bundle)))
                    cells.append(previous)
                elif prep_started[i]:
                    cells.append({**previous,'carried':True} if previous and previous['status']=='PASS' else cell())
                else:
                    cells.append({'status':'NOT_RUN','reason':'','source':None,'carried':False})
            prep_rows.append({'case':name,'type':'ANSWER','rounds':cells})
        prep_complete=[prep_started[i] and all(row['rounds'][i]['status'] in ('PASS','FAIL') for row in prep_rows) for i in range(3)]
    # Current architecture stores each actual attempt below its case.
    from finarch.dataset.viewer.preparation_paths import round_names
    physical_rounds=sorted({r for name in names for r in round_names(prep/name)})
    if physical_rounds:
        count=max(3,max(int(r.split('-')[0]) for r in physical_rounds))
        prep_started=[f'{i+1:02d}-round' in physical_rounds for i in range(count)]
        prep_attempts=[0]*count
        prep_rows=[]
        for name in names:
            cells=[];previous=None
            for i in range(count):
                path=prep/name/f'{i+1:02d}-round'/'run.json'
                item=read_status_record(path) if prep_started[i] else None
                if item is not None:
                    previous=cell(item,str(path.relative_to(bundle)))
                    cells.append(previous);prep_attempts[i]+=1
                elif path.parent.is_dir():
                    cells.append(cell({'status':'NOT_EVALUATED','reason':'ROUND_IN_PROGRESS'},str(path.relative_to(bundle))))
                elif prep_started[i]:
                    # No retry artifact cannot turn a previous failure into a pass.
                    cells.append({**previous,'carried':True} if previous else cell())
                else:
                    cells.append({'status':'NOT_RUN','reason':'','source':None,'carried':False})
            prep_rows.append({'case':name,'type':'ANSWER','rounds':cells})
        prep_complete=[prep_started[i] and all(r['rounds'][i]['status'] in ('PASS','FAIL') for r in prep_rows) for i in range(count)]
    prep_columns=[column(i+1,prep_rows,prep_started[i],prep_complete[i],prep_attempts[i]) for i in range(len(prep_started))]
    if gate is None:gate=evaluate(bundle,persist=False)
    gen_rows=[];gen_attempts=[0,0,0];execution_failures=[0,0,0]
    started=[(gen/f'{i:02d}-round').exists() for i in range(1,4)]
    completed=[(gen/f'{i:02d}-round/final-validator.json').exists() for i in range(1,4)]
    for name in gate['approved']:
        for folder,axis,label in TYPES:
            cells=[];previous=None
            for i in range(3):
                path=gen/f'{i+1:02d}-round'/name/folder/'run.json'
                # An absent round has no case outputs; avoid thousands of missing-file probes.
                item=read_status_record(path) if started[i] else None
                if item:
                    gen_attempts[i]+=1
                    if any(x in item.get('reason','') for x in ('CLI_CANCELLED','CLI_TIMEOUT')):execution_failures[i]+=1
                    previous=cell(item,str(path.relative_to(bundle)))
                    cells.append(previous)
                elif started[i]:cells.append({**previous,'carried':True} if previous else cell())
                else:cells.append({'status':'NOT_RUN','reason':'','source':None,'carried':False})
            gen_rows.append({'case':name,'type':label,'variant':folder,'rounds':cells})
    gen_columns=[{**column(i+1,gen_rows,started[i],completed[i],gen_attempts[i]),'execution_failures':execution_failures[i]} for i in range(3)]
    for i, entry in enumerate(gen_columns):
        round_dir = gen / f'{i+1:02d}-round'
        queue = optional(round_dir / 'queue.json', {})
        lifecycle = optional(round_dir / 'timing.json', {})
        if not completed[i] and ('ERROR' in (queue.get('status'), lifecycle.get('status'))):
            entry['state'] = 'ERROR'
            entry['reason'] = lifecycle.get('reason', 'Scheduler error')
    timing=optional(gen/'timing.json',{})
    from finarch.dataset.viewer.summary_reader import read_generation_summary
    finished=timing.get('status')=='COMPLETED' and bool(read_generation_summary(gen/'summary.json'))
    return {'format':'finarch-completion-v1','run':bundle.name,
            'status':'COMPLETED' if finished else 'ERROR' if timing.get('status')=='ERROR' else 'IN_PROGRESS',
            'generated_at':optional(bundle/'execution-progress.json',{}).get('heartbeat_at'),
            'input_count':len(names),'approved_cases':gate['approved'],'excluded_cases':gate['rejected'],
            'pending_cases':gate.get('pending',[]),'invalid_approvals':gate.get('invalid',[]),
            'preparation':{'unit':'cases','rounds':prep_columns,'rows':prep_rows,'runtime':phase_runtime(bundle,'preparation')},
            'generation':{'unit':'case_types','rounds':gen_columns,'rows':gen_rows,'runtime':phase_runtime(bundle,'generation')},
            'final_human_review_performed':False,
            'interpretation':'Counts are cumulative automatic outcomes; carried results are not fresh attempts. NOT_RUN and NOT_EVALUATED are not passes. Preparation and Generation use different denominators.'}


def build(bundle,require_generation=True):
    bundle=Path(bundle).resolve();result=snapshot(bundle)
    if require_generation and result['status']!='COMPLETED':raise ValueError('GENERATION_NOT_FINISHED')
    if result['status']=='COMPLETED':
        from finarch.dataset.viewer.reports.generation_report import build as generation_report
        try:
            result['generation_detail']=generation_report(bundle)
        except ValueError as error:
            if require_generation:
                raise
            result['generation_detail_error']=str(error)
        from finarch.dataset.viewer.reports.timing_report import build as timing_report
        timing_report(bundle)
    write(bundle/'completion-report.json',result)
    tables=[]
    for key,title in [('preparation','Preparation · 문항 수'),('generation','Generation · 문항×유형 수')]:
        lines=['## '+title,'','| 차수 | 실행 상태 | 이번 처리 | 누적 통과 | 누적 실패 | 미평가 |','|---|---|---:|---:|---:|---:|']
        for r in result[key]['rounds']:
            c=r['counts']
            if r['state']=='NOT_RUN':lines.append(f"|{r['round']}차|미실행|—|—|—|—|")
            else:lines.append(f"|{r['round']}차|{r['state']}|{r['attempted']}|{c.get('PASS',0)}|{c.get('FAIL',0)}|{c.get('NOT_EVALUATED',0)}|")
        tables.append('\n'.join(lines))
    template=Path(__file__).with_name('completion-report-template.md').read_text()
    (bundle/'RESULTS.md').write_text(template.format(run=result['run'],input_count=result['input_count'],approved=len(result['approved_cases']),excluded=len(result['excluded_cases']),pending=len(result['pending_cases']),tables='\n\n'.join(tables)))
    readme=bundle/'README.md'
    text=readme.read_text() if readme.exists() else '# '+bundle.name+'\n'
    marker='<!-- completion-report:start -->'
    if marker in text:
        start=text.index(marker)
        closing=text.find('<!-- completion-report:end -->',start)
        if closing>=0:
            end=closing+len('<!-- completion-report:end -->')
            text=text[:start]+text[end:]
        else:
            status_line=text.find('\n상태: ',start)
            end=text.find('\n',status_line+1) if status_line>=0 else -1
            if end>=0:text=text[:start]+text[end+1:]
    readme.write_text(text+'\n'+marker+'\n## 자동 결과 리포트\n\n[차수별 결과](RESULTS.md) · [문항별 전후 상태](completion-report.json) · [뷰어](http://127.0.0.1:8893/?run='+bundle.name+'&report=completion)\n\n상태: '+result['status']+'\n<!-- completion-report:end -->\n')
    RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs
    RunLogs.for_case(bundle).write('cli.log','completion_report.build',phase='END',value={'status':result['status'],'files':['RESULTS.md','completion-report.json'],'automatic':True})
    if result['status']=='COMPLETED' and (bundle/'hyperparameter.json').is_file():
        try:
            from finarch.dataset.viewer.reports.review_workbook import build as workbook
            result['review_workbook']={'status':'PASS','path':str(workbook(bundle))}
        except Exception as error:
            result['review_workbook']={'status':'FAIL','reason':str(error)}
            RunLogs.for_case(bundle).write('cli.log','review_workbook.build',phase='FAIL',value=result['review_workbook'])
        write(bundle/'completion-report.json',result)
    return result


def view(bundle, *, gate=None):
    bundle=Path(bundle)
    report_path=bundle/'completion-report.json'
    saved=optional(report_path)
    if saved and saved['status']=='COMPLETED':
        # A completed report is reusable only while its source records are unchanged.
        stamp=report_path.stat().st_mtime_ns
        paths=[bundle/'input-selection.json',bundle/'01-preparation/review-gate.json',bundle/'02-generation/timing.json']
        for pattern in ('01-preparation/test-*/run.json','01-preparation/test-*/*-round/run.json',
                        '02-generation/*-round/test-*/*/run.json'):
            paths.extend(bundle.glob(pattern))
        current=all(max(p.stat().st_mtime_ns,p.stat().st_ctime_ns)<=stamp for p in paths if p.exists())
        recorded={c['source'] for phase in ('preparation','generation') for row in saved[phase]['rows']
                  for c in row['rounds'] if c.get('source') and c['status'] in ('PASS','FAIL')}
        current=current and all((bundle/source).is_file() for source in recorded)
        if gate is not None:
            current=current and all(saved.get(report_key,[])==gate.get(gate_key,[]) for report_key,gate_key in
                [('approved_cases','approved'),('excluded_cases','rejected'),('pending_cases','pending'),('invalid_approvals','invalid')])
        if current:
            for phase in ('preparation','generation'):saved[phase]['runtime']=phase_runtime(bundle,phase)
            return saved
    return snapshot(bundle,gate=gate)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--wait',action='store_true');a=p.parse_args()
    root=Path(a.run)
    if a.wait:
        while optional(root/'execution-progress.json',{}).get('status')=='RUNNING':time.sleep(3)
    value=build(root)
    end = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['end']).end
    end(root,reason='Includes the original batch, authorized repair, and Generation resume intervals.')
    print('REPORT_READY '+str((root/'RESULTS.md').resolve()),flush=True)
