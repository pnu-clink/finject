"""One-time, backed-up migration of legacy EA identifiers in project artifacts."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path

PATTERN = re.compile(rb'EA([_-])0([23])(?![0-9])')
TEXT = {'.py', '.js', '.cjs', '.mjs', '.html', '.css', '.json', '.jsonl',
        '.ndjson', '.md', '.txt', '.toml', '.yaml', '.yml', '.csv', '.tsv', '.log', '.sh'}
SKIP = {'.git', '.venv', 'node_modules', '__pycache__', 'archive', 'worktrees'}
DELEGATED = ('src/finarch/experiments/', 'src/finarch/dashboard/', 'viewer/experiments/', 'viewer/dashboard/', 'exp-viewer/', 'experiment/', 'reports/experiments-run/',
             'report/experiments-run/', 'docs/experiments', 'docs/exp-viewer',
             'handoff/understanding-check.md', 'config/hyperparameter.json', 'README.md')

def delegated(root,path):
    return str(path.relative_to(root)).startswith(DELEGATED)

def replace(value):
    if b'EA_02' not in value and b'EA_03' not in value and b'EA-02' not in value and b'EA-03' not in value:
        return value
    value=value.replace(b'feedback-011-017/EA_02',b'feedback-011-017/__CANONICAL_SECOND_EA__')
    def shift(m):
        previous=value[m.start()-1:m.start()] if m.start() else b''
        if previous and (b'A'<=previous<=b'Z' or b'a'<=previous<=b'z' or b'0'<=previous<=b'9'):
            return m[0]
        return b'EA'+m[1]+b'0'+str(int(m[2])-1).encode()
    return PATTERN.sub(shift, value).replace(b'__CANONICAL_SECOND_EA__',b'EA_02')

def replace_file(path,raw):
    if 'feedback-011-017' in path.parts:
        raw=re.sub(rb'("type"\s*:\s*)"EA_02"',rb'\1"__CANONICAL_SECOND_EA__"',raw)
    return replace(raw).replace(b'__CANONICAL_SECOND_EA__',b'EA_02')

def search_files(root,pattern_args):
    command=['rg','-l','--null','--no-ignore','-g','*.{'+','.join(sorted(x[1:] for x in TEXT))+'}']
    for excluded in SKIP:command+=['-g',f'!**/{excluded}/**']
    for prefix in DELEGATED:
        if '/' in prefix:command+=['-g','!'+prefix+('**' if prefix.endswith('/') else '*')]
    command+=['-g','!log/ea-label-migration-20260920/**','-g','!**/migrate_ea_labels.py',*pattern_args,'.']
    found=subprocess.run(command,stdout=subprocess.PIPE,check=False)
    if found.returncode not in (0,1):raise RuntimeError('Candidate search failed')
    return [path for p in found.stdout.split(b'\0') if p
            if not delegated(root,path:=root/os.fsdecode(p))]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.apply:
        raise SystemExit('Unsafe bulk writer disabled after interruption; use the read-only staged audit first.')
    root = Path.cwd()
    out = root/'log/ea-label-migration-20260920'
    if (out/'completed.json').exists():
        raise SystemExit('Migration already applied; refusing a second decrement.')
    if args.apply and (out/'started.json').exists() and not args.resume:
        raise SystemExit('Prior migration started; restore its backup before retrying.')
    out.mkdir(exist_ok=True)
    paths=[]; renames=[]
    pending=[] if args.resume else [root];directories=0
    if args.resume:
        if json.loads((out/'started.json').read_text())['renames']:
            raise SystemExit('Resume requires a migration without directory renames.')
        print('Collecting matching label files with rg',flush=True)
        paths=search_files(root,[r'EA[_-]0[23]'])
        books=subprocess.run(['rg','--files','--no-ignore','-g','*.xlsx','-g','!archive/**'],stdout=subprocess.PIPE,check=True)
        paths.extend(root/os.fsdecode(p) for p in books.stdout.splitlines())
        with zipfile.ZipFile(out/'originals.zip') as saved:
            paths.extend(root/p for p in saved.namelist())
        paths=list(dict.fromkeys(p for p in paths if p.exists() and not delegated(root,p)
                    and not ('feedback-011-017' in p.parts and p.suffix in {'.md','.txt'})))
        (out/'label-candidates.json').write_text(json.dumps([str(p.relative_to(root)) for p in paths]))
    while pending:
        base=pending.pop();directories+=1
        if directories%10000==0:print(json.dumps({'directories':directories,'files':len(paths)}),flush=True)
        with os.scandir(base) as entries:
            for entry in entries:
                if entry.is_symlink():continue
                p=Path(entry.path);name=entry.name
                if entry.is_dir():
                    if name in SKIP or name.startswith('.') or p==out:continue
                    pending.append(p)
                elif p.name!='migrate_ea_labels.py' and (p.suffix.lower() in TEXT or p.suffix=='.xlsx'):
                    # This older report already uses normalized display categories.
                    if not ('feedback-011-017' in p.parts and p.suffix in {'.md','.txt'}):paths.append(p)
                if replace(name.encode())!=name.encode() and p.parent!=root/'reports/feedback-011-017':
                    renames.append(p)
    # Detect legacy target collisions before changing any file.
    rename_set=set(renames)
    collisions=[str(p) for p in renames if p.with_name(replace(p.name.encode()).decode()).exists()
                and p.with_name(replace(p.name.encode()).decode()) not in rename_set]
    if collisions:
        (out/'collisions.json').write_text(json.dumps(collisions,indent=2))
        raise SystemExit(f'RENAME_COLLISIONS: {len(collisions)}; see collisions.json')
    changes=[]; hashes={}; binding_paths=[]
    def register(before,after):
        if before==after:return
        hashes[hashlib.sha256(before).hexdigest().encode()]=hashlib.sha256(after).hexdigest().encode()
    def register_json(before,after):
        if before==after:return
        for ascii_only in (False,True):
            for compact in (False,True):
                opts={'sort_keys':True,'ensure_ascii':ascii_only}
                if compact:opts['separators']=(',',':')
                register(json.dumps(before,**opts).encode(),json.dumps(after,**opts).encode())
        if isinstance(before,dict) and isinstance(after,dict):
            for key,value in before.items():
                newkey=replace(key.encode()).decode()
                if newkey in after:register_json(value,after[newkey])
        elif isinstance(before,list) and isinstance(after,list):
            for a,b in zip(before,after):register_json(a,b)
    if args.apply:
        (out/'started.json').write_text(json.dumps({'paths':len(paths),'renames':len(renames)}))
    backup=zipfile.ZipFile(out/'originals.zip','a' if args.resume else 'w',zipfile.ZIP_DEFLATED,compresslevel=1) if args.apply else None
    backed=set(backup.namelist()) if backup else set()
    try:
        print(json.dumps({'scanned_files':len(paths),'path_renames':len(renames)}),flush=True)
        for index,p in enumerate(paths):
            if index%10000==0:print(json.dumps({'files_checked':index,'changed':len(changes)}),flush=True)
            rel=str(p.relative_to(root))
            raw=backup.read(rel) if rel in backed else p.read_bytes()
            if p.suffix=='.xlsx':
                import io
                buf=io.BytesIO()
                with zipfile.ZipFile(io.BytesIO(raw)) as src, zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as dst:
                    for info in src.infolist():
                        content=src.read(info.filename)
                        dst.writestr(info,replace(content) if info.filename.endswith('.xml') else content)
                changed=buf.getvalue()
                # ZIP serialization alone must not count as a label change.
                with zipfile.ZipFile(io.BytesIO(raw)) as src:
                    if not any(PATTERN.search(src.read(n)) for n in src.namelist() if n.endswith('.xml')):continue
            else:
                changed=replace_file(p,raw)
                if changed==raw:continue
            entry={'path':str(p.relative_to(root)), 'before_sha256':hashlib.sha256(raw).hexdigest(),
                   'after_sha256':hashlib.sha256(changed).hexdigest()}
            changes.append(entry)
            register(raw,changed)
            if p.suffix=='.json':
                try:register_json(json.loads(raw),json.loads(changed))
                except (ValueError,UnicodeError):pass
            if backup:
                if rel not in backed:backup.writestr(entry['path'],raw);backed.add(rel)
                tmp=p.with_name(p.name+'.ea-migration-tmp');tmp.write_bytes(changed);tmp.replace(p)
        if args.apply:
            # Refresh content bindings for files and nested plan/schema objects.
            backed={e['path'] for e in changes}
            searched=set();binding_paths=set()
            for _ in range(8):
                new_keys=set(hashes)-searched
                if new_keys:
                    patterns=out/'hash-patterns.txt';patterns.write_bytes(b'\n'.join(sorted(new_keys))+b'\n')
                    print(json.dumps({'hash_lookup_pass':_+1,'new_hashes':len(new_keys)}),flush=True)
                    binding_paths.update(search_files(root,['-F','-f',str(patterns)]));searched.update(new_keys)
                updated=0
                for p in binding_paths:
                    raw=p.read_bytes()
                    rel=str(p.relative_to(root))
                    original=backup.read(rel) if rel in backed else raw
                    baseline=replace_file(p,original)
                    changed=re.sub(rb'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',lambda m:hashes.get(m[0],m[0]),baseline)
                    if changed==raw:continue
                    if rel not in backed:
                        backup.writestr(rel,raw);backed.add(rel)
                        changes.append({'path':rel,'before_sha256':hashlib.sha256(raw).hexdigest()})
                    register(original,changed)
                    if p.suffix=='.json':
                        try:register_json(json.loads(original),json.loads(changed))
                        except (ValueError,UnicodeError):pass
                    tmp=p.with_name(p.name+'.ea-migration-tmp');tmp.write_bytes(changed);tmp.replace(p)
                    updated+=1
                print(json.dumps({'hash_refresh_pass':_+1,'updated':updated}),flush=True)
                if not updated:break
            else:raise RuntimeError('HASH_BINDINGS_DID_NOT_CONVERGE')
            for entry in changes:
                entry['after_sha256']=hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()
            # Rename deepest first and stage siblings to avoid EA_02 collisions.
            for parent in sorted({p.parent for p in renames},key=lambda p:len(p.parts),reverse=True):
                staged=[]
                for p in [p for p in renames if p.parent==parent]:
                    if not p.exists():continue
                    target=p.with_name(replace(p.name.encode()).decode())
                    temp=p.with_name(p.name+'.ea-migration-move')
                    if target.exists() and target not in renames:
                        raise RuntimeError(f'RENAME_COLLISION: {target}')
                    p.rename(temp);staged.append((temp,target))
                for temp,target in staged:temp.rename(target)
    finally:
        if backup:backup.close()
    result={'applied':args.apply,'files':len(changes),'renames':len(renames),
            'changes':changes,'path_changes':[{'from':str(p.relative_to(root)),
            'to':replace(str(p.relative_to(root)).encode()).decode()} for p in renames],
            'preserved':'Archive, dependencies, Git history and worktrees remain historical originals.'}
    (out/('completed.json' if args.apply else 'plan.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('changes','path_changes')}),flush=True)

if __name__=='__main__':main()
