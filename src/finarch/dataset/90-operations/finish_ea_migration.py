"""Bounded, journaled recovery of the interrupted EA label migration.

Originals are immutable. Each write is derived from its original, never from
already migrated bytes. No model calls are performed.
"""
import argparse
import contextlib
import fcntl
import gzip
from functools import lru_cache
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import zipfile
from pathlib import Path
replace_file = __import__('finarch.dataset.90-operations.migrate_ea_labels', fromlist=['replace_file']).replace_file
delegated = __import__('finarch.dataset.90-operations.migrate_ea_labels', fromlist=['delegated']).delegated
SKIP = __import__('finarch.dataset.90-operations.migrate_ea_labels', fromlist=['SKIP']).SKIP
TEXT = __import__('finarch.dataset.90-operations.migrate_ea_labels', fromlist=['TEXT']).TEXT
DELEGATED = __import__('finarch.dataset.90-operations.migrate_ea_labels', fromlist=['DELEGATED']).DELEGATED

CHUNK = 1024 * 1024
HASH = re.compile(rb'[0-9a-f]{64}(?![0-9a-f])')

def digest(stream):
    h = hashlib.sha256()
    while block := stream.read(CHUNK):
        h.update(block)
    return h.hexdigest()

def recover(out):
    target = out / 'originals-recovered.zip'
    if target.exists():
        return target
    temp = target.with_suffix('.building')
    with (out / 'originals.zip').open('rb') as src, temp.open('wb') as dst:
        shutil.copyfileobj(src, dst, CHUNK)
    infos = []
    with temp.open('rb') as src:
        size = temp.stat().st_size
        while src.tell() < size:
            offset = src.tell()
            sig, version, flags, method, tm, dt, crc, compressed, plain, n, extra = struct.unpack('<4s5H3I2H', src.read(30))
            if sig != b'PK\x03\x04' or flags & 8 or compressed == 0xffffffff:
                raise ValueError(f'Unsupported local header at {offset}')
            name = src.read(n).decode('utf-8' if flags & 2048 else 'cp437')
            info = zipfile.ZipInfo(name, ((dt >> 9) + 1980, (dt >> 5) & 15, dt & 31, tm >> 11, (tm >> 5) & 63, (tm & 31) * 2))
            info.extra = src.read(extra)
            info.header_offset, info.flag_bits, info.compress_type = offset, flags, method
            info.CRC, info.compress_size, info.file_size = crc, compressed, plain
            info.extract_version = version
            infos.append(info)
            src.seek(compressed, 1)
            if src.tell() > size:
                raise ValueError('Truncated payload')
    # The interrupted archive has no directory. Append one to a separate copy.
    with zipfile.ZipFile(temp, 'a', allowZip64=True) as dst:
        if dst.filelist:
            raise ValueError('Expected an interrupted archive without a directory')
        dst.filelist = infos
        dst.NameToInfo = {x.filename: x for x in infos}
        dst._didModify = True
    with zipfile.ZipFile(temp) as check:
        if len(check.infolist()) != len(infos):
            raise ValueError('Recovery member count mismatch')
        for i, info in enumerate(check.infolist(), 1):
            with check.open(info) as stream:
                digest(stream)  # ZipExtFile checks CRC at EOF, bounded reads.
            if i % 1000 == 0:
                print(json.dumps({'phase':'backup_crc', 'checked':i}), flush=True)
    temp.replace(target)
    return target

class Migration:
    def __init__(self, root):
        self.root = root
        self.out = root / 'log/ea-label-migration-20260920'
        self.db = sqlite3.connect(self.out / 'finish.sqlite')
        self.db.execute('create table if not exists files(path text primary key, source text, before text, after text, done integer default 0)')
        self.db.execute('create table if not exists hashes(old text primary key, new text)')
        self.db.execute('create table if not exists dependencies(path text,old text,applied text,primary key(path,old))')
        self.db.execute('create table if not exists hash_checked(path text primary key)')
        if 'relabel' not in [r[1] for r in self.db.execute('pragma table_info(files)')]:
            self.db.execute('alter table files add column relabel integer default 1')
        self.backup = zipfile.ZipFile(recover(self.out))
        self.names = set(self.backup.namelist())
        (self.out / 'additional-originals').mkdir(exist_ok=True)

    @contextlib.contextmanager
    def original(self, rel):
        row = self.db.execute('select source from files where path=?', (rel,)).fetchone()
        if rel in self.names:
            with self.backup.open(rel) as f:
                yield f
        elif row and row[0]:
            opener=gzip.open if row[0].endswith('.gz') else open
            with opener(self.out / row[0], 'rb') as f:
                yield f
        else:
            with (self.root / rel).open('rb') as f:
                yield f

    def preserve(self, rel, relabel=True):
        if self.db.execute('select 1 from files where path=?', (rel,)).fetchone():
            return
        if rel in self.names:
            source = 'originals-recovered.zip'
        else:
            stem='additional-originals/' + hashlib.sha256(rel.encode()).hexdigest()
            source = stem + '.gz'
            target = self.out / source
            temp = target.with_suffix('.building')
            cloned=False
            if (self.root/rel).stat().st_size > 8*CHUNK:
                clone=self.out/(stem+'.clone')
                result=subprocess.run(['/bin/cp','-c',str(self.root/rel),str(clone)],stderr=subprocess.PIPE)
                if result.returncode==0:
                    source=stem+'.clone'; cloned=True
            if not cloned:
                with (self.root / rel).open('rb') as src, gzip.open(temp, 'wb', compresslevel=1) as dst:
                    shutil.copyfileobj(src, dst, CHUNK)
                temp.replace(target)
        with self.original(rel) as stream:
            before = digest(stream)
        self.db.execute('insert into files(path,source,before,relabel) values(?,?,?,?)', (rel, source, before,int(relabel)))
        self.db.commit()

    def register(self, a, b):
        if a != b:
            self.db.execute('insert into hashes values(?,?) on conflict(old) do update set new=excluded.new',
                            (hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest()))

    def objects(self, a, b):
        if a == b:
            return
        for ascii_only in (True, False):
            for compact in (True, False):
                opts = dict(sort_keys=True, ensure_ascii=ascii_only)
                if compact:
                    opts['separators'] = (',', ':')
                self.register(json.dumps(a, **opts).encode(), json.dumps(b, **opts).encode())
        if isinstance(a, dict) and isinstance(b, dict):
            if 'review_sha256' in a:
                old = a['review_sha256']
                new = hashlib.sha256(json.dumps({k:v for k,v in b.items() if k != 'review_sha256'}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                expected_old = hashlib.sha256(json.dumps({k:v for k,v in a.items() if k != 'review_sha256'}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                if old == expected_old:
                    self.db.execute('insert into hashes values(?,?) on conflict(old) do update set new=excluded.new', (old, new))
            for k,v in a.items():
                nk = replace_file(Path('object.json'), k.encode()).decode()
                if nk in b:
                    self.objects(v, b[nk])
        elif isinstance(a, list) and isinstance(b, list):
            for x,y in zip(a,b):
                self.objects(x,y)

    def transform(self, rel, src, dst, hashes=False, relabel=True):
        pending_dependencies=[]
        def flush_dependencies():
            if pending_dependencies:
                self.db.executemany('insert into dependencies values(?,?,?) on conflict(path,old) do update set applied=excluded.applied',pending_dependencies)
                pending_dependencies.clear()
        @lru_cache(maxsize=65536)
        def mapped(value):
            row=self.db.execute('select new from hashes where old=?',(value.decode(),)).fetchone()
            result=row[0].encode() if row else value
            pending_dependencies.append((rel,value.decode(),result.decode()))
            if len(pending_dependencies)>=4096:
                flush_dependencies()
            return result
        def convert(block):
            if relabel:
                block = replace_file(Path(rel), block)
            if hashes:
                block = HASH.sub(lambda m:m[0] if m.start() and block[m.start()-1] in b'0123456789abcdef' else mapped(m[0]), block)
            return block
        pending = b''
        while block := src.read(CHUNK):
            pending += block
            # Choose a delimiter so neither a label nor a hash straddles writes.
            cut = len(pending) - 4096
            if cut <= 0:
                continue
            while cut > 0 and (chr(pending[cut-1]).isalnum() or pending[cut-1] in b'_-'):
                cut -= 1
            if not cut:
                raise ValueError(f'Unbounded token in {rel}')
            dst.write(convert(pending[:cut]))
            pending = pending[cut:]
        dst.write(convert(pending))
        flush_dependencies()

    def apply(self, rel, hashes=False):
        p = self.root / rel
        if delegated(self.root, p) or not p.is_file():
            return False
        if 'feedback-011-017' in p.parts and p.suffix in ('.md','.txt'):
            return False
        if hashes and self.db.execute('select 1 from hash_checked where path=?',(rel,)).fetchone():
            stale=self.db.execute('select 1 from dependencies d left join hashes h on h.old=d.old where d.path=? and coalesce(h.new,d.old)!=d.applied limit 1',(rel,)).fetchone()
            if not stale:
                return False
        self.preserve(rel, not hashes or rel in self.names)
        relabel=bool(self.db.execute('select relabel from files where path=?',(rel,)).fetchone()[0])
        temp = p.with_name(p.name + '.ea-safe-tmp')
        if p.suffix == '.xlsx':
            # ZipFile needs seeking; stage the original on disk, not in RAM.
            original_temp = self.out / 'workbook-original.tmp'
            with self.original(rel) as src, original_temp.open('wb') as dst:
                shutil.copyfileobj(src,dst,CHUNK)
            with zipfile.ZipFile(original_temp) as src, zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as dst:
                for info in src.infolist():
                    with src.open(info) as a, dst.open(info,'w') as b:
                        if info.filename.endswith('.xml'):
                            self.transform(rel,a,b,hashes,relabel)
                        else:
                            shutil.copyfileobj(a,b,CHUNK)
            same=True
            with zipfile.ZipFile(original_temp) as src,zipfile.ZipFile(temp) as dst:
                for name in src.namelist():
                    with src.open(name) as a,dst.open(name) as b:
                        if digest(a)!=digest(b):
                            same=False;break
            if same:
                original_temp.replace(temp)
            else:
                original_temp.unlink()
        else:
            with self.original(rel) as src, temp.open('wb') as dst:
                self.transform(rel,src,dst,hashes,relabel)
        with temp.open('rb') as f:
            after = digest(f)
        row = self.db.execute('select before,after from files where path=?',(rel,)).fetchone()
        with p.open('rb') as f:
            current = digest(f)
        if current not in (row[0],after,row[1]):
            temp.unlink()
            raise ValueError(f'Unexpected current change: {rel}')
        changed = current != after
        if changed:
            temp.chmod(p.stat().st_mode)
            temp.replace(p)
        else:
            temp.unlink()
        self.db.execute('update files set after=?,done=1 where path=?',(after,rel))
        if hashes:
            self.db.execute('insert or ignore into hash_checked values(?)',(rel,))
        if row[0] != after:
            self.db.execute('insert into hashes values(?,?) on conflict(old) do update set new=excluded.new',(row[0],after))
            if p.suffix == '.json' and p.stat().st_size < 8*CHUNK:
                with self.original(rel) as src:
                    try:
                        a=json.load(src); b=json.loads(p.read_bytes())
                        self.objects(a,b)
                    except (ValueError, UnicodeError):
                        pass
        self.db.commit()
        return changed

    def search(self, args, name):
        command=['rg','--threads','4','--no-mmap','-l','--null','--no-ignore',
                 '-g','*.{'+','.join(sorted(x[1:] for x in TEXT))+'}']
        for excluded in SKIP:
            command+=['-g',f'!**/{excluded}/**']
        for prefix in DELEGATED:
            if '/' in prefix:
                command+=['-g','!'+prefix+('**' if prefix.endswith('/') else '*')]
        command+=['-g','!log/ea-label-migration-20260920/**','-g','!**/*ea*migration*',
                  '-g','!**/migrate_ea_labels.py',*args,'.']
        output=self.out/(name+'.paths')
        with output.open('wb') as f:
            result=subprocess.run(command,stdout=f)
        if result.returncode not in (0,1):
            raise RuntimeError(f'Search failed: {name}')
        # Paths are small metadata, never artifact payloads.
        return [str(Path(os.fsdecode(x))) for x in output.read_bytes().split(b'\0')
                if x and not delegated(self.root,self.root/os.fsdecode(x))]

    def hashes(self):
        self.db.execute('create table if not exists searched(old text primary key)')
        self.db.execute('create table if not exists bindings(path text primary key)')
        self.db.execute("insert or ignore into bindings select path from files where path like '%.xlsx'")
        self.db.commit()
        for iteration in range(1,17):
            keys=[x[0] for x in self.db.execute('select old from hashes where old not in (select old from searched)')]
            if keys:
                patterns=self.out/'safe-hash-patterns.txt'
                # Short prefixes bound ripgrep's search automaton memory. Actual
                # replacements still require an exact 64-character hash match.
                patterns.write_text('\n'.join(sorted({k[:8] for k in keys}))+'\n')
                print(json.dumps({'phase':'hash_search','pass':iteration,'keys':len(keys)}),flush=True)
                found=self.search(['-F','-f',str(patterns)],f'hash-pass-{iteration}')
                self.db.executemany('insert or ignore into bindings values(?)',((x,) for x in found))
                self.db.executemany('insert or ignore into searched values(?)',((x,) for x in keys))
                self.db.commit()
            paths=[x[0] for x in self.db.execute('select path from bindings order by path')]
            changed=0
            for i,rel in enumerate(paths,1):
                changed+=self.apply(rel,True)
                if i%1000==0:
                    print(json.dumps({'phase':'hash_apply','pass':iteration,'checked':i,'total':len(paths),'changed':changed}),flush=True)
            print(json.dumps({'phase':'hash_pass','pass':iteration,'changed':changed,'bindings':len(paths)}),flush=True)
            if not changed and not self.db.execute('select 1 from hashes where old not in (select old from searched) limit 1').fetchone():
                (self.out/'hashes-completed.json').write_text(json.dumps({'passes':iteration,'bindings':len(paths)}))
                return
        raise RuntimeError('Hash bindings did not converge')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode', choices=['recover','labels','hashes','refresh'])
    parser.add_argument('--paths')
    args=parser.parse_args()
    if args.mode!='recover' and (Path.cwd()/'log/ea-label-migration-20260920/completed.json').exists():
        raise SystemExit('Migration is complete; refusing another write pass')
    lock=(Path.cwd()/'log/ea-label-migration-20260920/migration.lock').open('a+')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Another migration writer is running')
    lock.seek(0); lock.truncate(); lock.write(str(os.getpid())); lock.flush()
    m=Migration(Path.cwd())
    if args.mode=='recover':
        print('BACKUP_CRC_ALL_PASS',flush=True); return
    if args.mode=='refresh':
        m.hashes(); return
    if args.paths:
        paths=json.loads(Path(args.paths).read_text())
    else:
        paths=list(dict.fromkeys(m.backup.namelist()+json.loads((m.out/'label-candidates.json').read_text())))
    changed=0
    for i,rel in enumerate(paths,1):
        row=m.db.execute('select done from files where path=?',(rel,)).fetchone()
        if args.mode=='labels' and row and row[0]:
            continue
        changed+=m.apply(rel,args.mode=='hashes')
        if i%100==0:
            print(json.dumps({'phase':args.mode,'checked':i,'changed':changed,'total':len(paths)}),flush=True)
    print(json.dumps({'phase':args.mode,'checked':len(paths),'changed':changed,'complete':True}),flush=True)

if __name__=='__main__':
    main()
