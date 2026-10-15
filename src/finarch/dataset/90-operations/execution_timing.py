"""Local-time lifecycle records with monotonic elapsed time and replayable argv."""
import json
import os
import shlex
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)


def now():
    return datetime.now().astimezone().isoformat(sep=' ',timespec='milliseconds')


def emit(root, value, phase):
    function='execution.'+value['scope']
    logs=RunLogs.for_case(root)
    logs.write('cli.log',function,phase=phase,value=value)
    logs.write('pipeline.log',function,phase=phase)
    logs.write('detail.log',function,phase=phase,value=value)
    print(json.dumps({'event':phase,'run_id':logs.run_id,**value},ensure_ascii=False),flush=True)


def begin(root, scope, argv=None):
    root=Path(root)
    argv=list(argv if argv is not None else getattr(sys,'orig_argv',[sys.executable,*sys.argv]))
    value={'scope':scope,'status':'RUNNING','started_at':now(),'ended_at':None,
           'elapsed_seconds':None,'measurement':'lifecycle_monotonic','monotonic_start':time.monotonic(),
           'argv':argv,'cwd':str(Path.cwd()),'environment':{'PYTHONPATH':os.environ.get('PYTHONPATH')},
           'command':('PYTHONPATH='+shlex.quote(os.environ['PYTHONPATH'])+' ' if 'PYTHONPATH' in os.environ else '')+shlex.join(argv)}
    save(root/'timing.json',value);emit(root,value,'START')
    return value


def end(root, status='COMPLETED', reason=None):
    root=Path(root);path=root/'timing.json'
    if not path.is_file():return None
    value=json.loads(path.read_text())
    if value.get('ended_at'):return value
    elapsed=max(0,time.monotonic()-value['monotonic_start'])
    hours,remainder=divmod(int(elapsed),3600);minutes,seconds=divmod(remainder,60)
    value.update(status=status,ended_at=now(),elapsed_seconds=round(elapsed,3),
                 elapsed_display=f'{hours:02d}:{minutes:02d}:{seconds:02d}')
    if reason:value['reason']=reason
    save(path,value);emit(root,value,'END')
    return value


@contextmanager
def measure(root, scope, argv=None):
    begin(root,scope,argv)
    try:yield
    except BaseException as error:
        end(root,'INTERRUPTED' if isinstance(error,KeyboardInterrupt) else 'ERROR',type(error).__name__+': '+str(error))
        raise
    else:end(root)
