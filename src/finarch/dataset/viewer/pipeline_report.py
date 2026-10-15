"""Adapt current pipeline evidence to the established 012 report view."""
from pathlib import Path
from finarch.dataset.viewer.reports.completion_report import view
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read


def build(bundle, *, completion=None):
    bundle=Path(bundle);data=completion if completion is not None else view(bundle);rows=[]
    for row in data['generation']['rows']:
        if not any(c['status']=='FAIL' for c in row['rounds']):continue
        failed=False;cells=[]
        for cell in row['rounds']:
            status=cell['status']
            if status=='FAIL':failed=True;value='FAIL'
            elif status=='PASS':value='RESOLVED' if failed else 'NO_FAILURE'
            elif status=='NOT_RUN':value='NOT_RUN'
            else:value='PENDING'
            cells.append({'status':value,'reason':cell.get('reason','') if status!='PASS' else ''})
        rows.append({'case':row['case'],'label':row['type'],'rounds':cells})
    rounds=[];previous=set()
    for r in data['generation']['rounds']:
        number=r['round'];current={(row['case'],row['type']) for row in data['generation']['rows'] if row['rounds'][number-1]['status']=='FAIL'}
        guidance=[]
        for path in sorted((bundle/'02-generation'/f'{number:02d}-round'/'feedback').glob('*/02-result.json')):
            value=read(path);guidance.append({k:value.get(k) for k in ('axis','version','changes','guidance')})
        complete=r['state']=='COMPLETED'
        rounds.append({'round':number,'complete':complete,'failed':len(current) if complete else None,'resolved':len(previous-current) if complete and number>1 else None,'guidance':guidance})
        if complete:previous=current
    exclusions=[]
    for row in data['preparation']['rows']:
        cells=[c for c in row['rounds'] if c['status']!='NOT_RUN']
        if cells and cells[-1]['status']=='FAIL':exclusions.append({'case':row['case'],**cells[-1]})
    return {'status':data['status'],'rounds':rounds,'rows':rows,'exclusions':exclusions,'preparation':data['preparation'],'layout':'preparation-generation-v1'}
