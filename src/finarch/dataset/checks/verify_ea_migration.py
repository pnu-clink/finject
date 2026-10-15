"""Bounded final integrity verification for the one-time label migration."""
import json
import hashlib
import io
import sys
from collections import Counter
from pathlib import Path
import ijson
Migration = __import__('finarch.dataset.90-operations.finish_ea_migration', fromlist=['Migration']).Migration
digest = __import__('finarch.dataset.90-operations.finish_ea_migration', fromlist=['digest']).digest

def stats(stream):
    counts=Counter()
    for prefix,event,value in ijson.parse(stream):
        key=prefix.rsplit('.',1)[-1]
        if event=='string' and key in ('label','variant','status'):
            if key=='status' or value.startswith('EA_'):
                counts[key+':'+value]+=1
    return counts

def reconcile():
    """Validate the seven reviewed concurrent changes without rewriting their files."""
    m=Migration(Path.cwd())
    result=json.loads((m.out/'final-integrity.json').read_text())
    rows=json.loads((m.out/'concurrent-differences.json').read_text())
    notes=[]
    for row in rows:
        rel=row['path']
        b=io.BytesIO()
        relabel=bool(m.db.execute('select relabel from files where path=?',(rel,)).fetchone()[0])
        with m.original(rel) as f:
            m.transform(rel,f,b,True,relabel)
        expected=b.getvalue()
        assert hashlib.sha256(expected).hexdigest()==row['expected'],rel
        target=Path('viewer/dataset/index.html') if rel=='viewer/index.html' else Path(rel)
        current=target.read_bytes()
        if rel=='viewer/dataset/shell.html':
            assert current==expected.replace(b'./viewer/start.command',b'./viewer/dataset/start.command')
            reason='Viewer launcher relocated to dataset workspace'
        elif rel in ('src/finarch/dataset/checks/test_viewer_audit.js','src/finarch/dataset/checks/test_viewer_answer.cjs','src/finarch/dataset/checks/test_viewer_generation_failure.cjs'):
            assert current==expected.replace(b'viewer/index.html',b'viewer/dataset/index.html')
            reason='Viewer test path updated for dataset workspace'
        elif rel=='viewer/index.html':
            adjusted=expected.replace(b'./viewer/start.command',b'./viewer/dataset/start.command')
            adjusted=adjusted.replace(b"EA_01:'07-ea-later-input'",b"EA_02:'07-ea-later-input'")
            assert current==adjusted
            assert b"EA_01:'06-ea-earlier-input',EA_02:'07-ea-later-input'" in current
            reason='Generated viewer relocated and rebuilt from canonical EA source mapping'
        elif rel=='viewer/README.md':
            assert current==Path('src/finarch/dataset/viewer/workspaces-readme-template.md').read_bytes()
            moved=Path('viewer/dataset/README.md').read_bytes()
            assert moved==expected.replace(b'viewer/index.html',b'viewer/dataset/index.html').replace(b'../docs/',b'../../docs/').replace(b'../reports/',b'../../reports/')
            reason='Workspace index generated; previous guide preserved under dataset with adjusted links'
        elif rel=='reports/run/20260919-financial-qa-survey/research-log.jsonl':
            assert current.startswith(expected)
            extra=current[len(expected):].splitlines()
            for line in extra:json.loads(line)
            reason=f'Independent research task appended {len(extra)} JSONL records; migrated prefix unchanged'
        else:
            raise ValueError(f'Unreviewed concurrent change: {rel}')
        notes.append({**row,'current_path':str(target),'verified_current_sha256':hashlib.sha256(current).hexdigest(),'reason':reason})
    m.db.rollback()
    assert m.db.execute('pragma quick_check').fetchone()[0]=='ok'
    (m.out/'concurrent-changes.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2))
    result.update(status='VERIFIED',reviewed_concurrent_changes=len(notes),unresolved_differences=0,database_integrity='ok')
    (m.out/'final-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'status':result['status'],'files':result['files'],'reviewed_concurrent_changes':len(notes)}))

def main():
    m=Migration(Path.cwd())
    if not (m.out/'hashes-completed.json').exists():
        raise ValueError('Hash refresh has not completed')
    checked=0
    differences=[]
    for rel,before,expected in m.db.execute('select path,before,after from files where done=1'):
        with m.original(rel) as f:
            original=digest(f)
        if original!=before:
            raise ValueError(f'Original backup digest mismatch: {rel}')
        target=m.root/rel
        actual=None
        if target.exists():
            with target.open('rb') as f:
                actual=digest(f)
        if actual!=expected:
            differences.append({'path':rel,'expected':expected,'actual':actual})
        checked+=1
        if checked%1000==0:
            print(json.dumps({'phase':'final_digest','checked':checked}),flush=True)
    summaries={}
    for run in ('20260917-002','20260917-003'):
        rel=f'reports/run/{run}/02-generation/summary.json'
        with m.original(rel) as f:
            before=stats(f)
        with (m.root/rel).open('rb') as f:
            after=stats(f)
        expected=Counter()
        for k,v in before.items():
            # Simultaneous mapping of original labels, not sequential decrement.
            a,b=k.split(':',1)
            expected[a+':'+{'EA_02':'EA_01','EA_03':'EA_02'}.get(b,b)]+=v
        if after!=expected:
            raise ValueError(f'Summary status/label mismatch: {run}')
        summaries[run]={'before':dict(before),'after':dict(after),'status_counts_unchanged':True}
    (m.out/'concurrent-differences.json').write_text(json.dumps(differences,ensure_ascii=False,indent=2))
    result={'status':'REVIEW_REQUIRED' if differences else 'VERIFIED','files':checked,'differences':len(differences),'summaries':summaries,'new_model_calls':0}
    (m.out/'final-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'status':result['status'],'files':checked,'differences':len(differences)}),flush=True)

if __name__=='__main__':
    reconcile() if "--reconcile" in sys.argv else main()
