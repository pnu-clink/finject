"""One-line JSON logs, partitioned by purpose and mirrored into default.log."""
import fcntl
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.RLock()
AXES = {'IC_VALUE':'ic-value', 'IC_SOURCE':'ic-source',
        'IC_RELATION':'ic-relation', 'EA':'ea'}


def append(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n'
    with path.open('a', encoding='utf-8') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())


class RunLogs:
    def __init__(self, log_root, run_id):
        self.root = Path(log_root)
        self.run_id = run_id
        self.round = None
        self.context_path = None
        self.directory = self.root/'run'/run_id
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            with (self.directory/'README.md').open('x', encoding='utf-8') as stream:
                stream.write(Path(__file__).with_name('run-log-readme.md').read_text().replace('{run_id}',run_id))
        except FileExistsError:
            pass

    @classmethod
    def for_case(cls, case_root):
        path = Path(case_root).resolve()
        for ancestor in (path, *path.parents):
            if ancestor.parent.name == 'run' and ancestor.parent.parent.name == 'reports':
                obj=cls(ancestor.parent.parent.parent/'log', ancestor.name)
                relative=path.relative_to(ancestor).parts
                obj.round=relative[0] if relative and relative[0].endswith('-round') else None
                if obj.round:obj.context_path=str(Path(*relative[1:]))
                elif relative and relative[0] in ('01-preparation', '02-generation'):
                    obj.context_path=str(Path(*relative))
                return obj
        # Offline checks stay alongside their temporary data, not in project logs.
        return cls(path/'log', path.name)

    def write(self, filename, function, *, value=None, **metadata):
        # One lock covers routing and the run-wide sequence across processes/cases.
        with _LOCK, (self.directory/'.write.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            counter = self.directory/'.sequence'
            sequence = int(counter.read_text())+1 if counter.exists() else 1
            record = {'timestamp':datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds"),
                      'sequence':sequence, 'event_id':uuid.uuid4().hex,
                      'run_id':self.run_id, 'function':function,
                      'log':filename, **metadata}
            if value is not None:
                record[function] = value
            counter.write_text(str(sequence))
            stage = metadata.get('stage') or (value.get('stage') if isinstance(value,dict) else None)
            problem = metadata.get('problem_id')
            artifact_path = value.get('path') if isinstance(value,dict) else None
            if artifact_path and '/' in artifact_path:
                stage = str(Path(artifact_path).parent)
            elif stage and stage != 'pipeline' and metadata.get('step') not in (None,'','pipeline'):
                step = {'P01-author':'01-generate-code','P02-execute':'03-execute-python'}.get(str(metadata['step']),str(metadata['step']))
                stage = str(Path(stage)/step)
            relative = filename
            if stage and problem and filename != 'cli.log':
                stage = {'human-review':'06-human-review/01-collect-results','pipeline':'08-records'}.get(stage,stage)
                parts = Path(str(stage)).parts
                if Path(str(stage)).is_absolute() or '..' in parts or Path(str(problem)).name != problem:
                    raise ValueError('INVALID_STAGE_LOG_PATH')
                relative = str(Path(self.context_path or problem)/stage/filename)
            if stage and not problem and filename != 'cli.log':
                relative=str(Path(stage)/filename)
            if self.round:
                relative=str(Path(self.round)/relative)
                record['round']=self.round
            record['log_path'] = relative
            record['artifact_directory'] = str(Path(relative).parent) if stage else None
            target = self.root/filename if filename == 'cli.log' else self.directory/relative
            append(target, record)
            append(self.directory/'default.log', record)
            if self.round:append(self.directory/self.round/'default.log', record)
            return record

    def event(self, event, *, value=None):
        function = event.get('pipeline_function') or event.get('function') or event.get('hook') or event.get('step') or 'pipeline'
        meta = {k:event.get(k) for k in ('problem_id','call_id','parent_call_id','phase','kind','axis','stage','step')}
        if event.get('phase') == 'START' and event.get('pipeline', False):
            self.write('pipeline.log', function, **meta)
        details = {k:v for k,v in event.items() if k not in {'format','sequence','run_id'}}
        if value is not None:
            details['value'] = value
        self.write('detail.log', function, value=details, **meta)
        if event.get('kind') == 'llm':
            axis = AXES.get(event.get('axis'))
            self.write('llm-'+axis+'.log' if axis else 'llm.log', function, value=details, **meta)
