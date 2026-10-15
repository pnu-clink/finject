"""Read-only, offset-paged access to the purpose-specific JSON line logs."""
import json
from pathlib import Path

FILES = ('default.log','pipeline.log','detail.log','llm.log','llm-ic-value.log',
         'llm-ic-source.log','llm-ic-relation.log','llm-ea.log','cli.log')


def list_runs(root):
    directory=Path(root)/'run'
    return sorted((p.name for p in directory.iterdir() if p.is_dir() and not p.is_symlink()),reverse=True) if directory.exists() else []


def read_log(root, run, filename, offset=0, limit=200):
    root=Path(root)
    if Path(filename).name not in FILES or Path(filename).is_absolute() or '..' in Path(filename).parts or not run or Path(run).name!=run or run in ('.','..'):
        raise ValueError('INVALID_LOG_SELECTION')
    directory=root/'run'/run
    if directory.is_symlink() or not directory.is_dir() or directory.resolve().parent!=(root/'run').resolve():
        raise ValueError('UNKNOWN_LOG_RUN')
    path=root/filename if filename=='cli.log' else directory/filename
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p.is_relative_to(root)) or not path.resolve().is_relative_to(root.resolve()):raise ValueError('INVALID_LOG_PATH')
    if offset<0 or not 1<=limit<=500:raise ValueError('INVALID_LOG_PAGE')
    if not path.exists():return {'records':[],'offset':0,'more':False,'damaged':[]}
    records=[];damaged=[]
    with path.open('rb') as stream:
        stream.seek(0,2);size=stream.tell()
        stream.seek(offset if offset<=size else 0)
        while len(records)<limit:
            position=stream.tell();line=stream.readline()
            if not line:break
            if not line.endswith(b'\n'):
                stream.seek(position);break  # Writer may still be appending.
            try:record=json.loads(line)
            except (ValueError,UnicodeDecodeError):
                damaged.append(position);continue
            if filename=='cli.log' and record.get('run_id')!=run:continue
            records.append(record)
        cursor=stream.tell()
    return {'records':records,'offset':cursor,'more':cursor<size,'damaged':damaged}


def list_files(root,run):
    if not run or Path(run).name!=run or run in (".",".."):raise ValueError("INVALID_LOG_SELECTION")
    directory=Path(root)/"run"/run
    if directory.is_symlink():raise ValueError("INVALID_LOG_PATH")
    return ["default.log","cli.log"]+sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*.log") if p.name in FILES and p.name!="default.log" and not p.is_symlink())
