"""Atomic artifacts, immutable manifests, and a process-wide run lock."""
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT = (Path(__file__).resolve().parent / '../../../..').resolve()


def now():
    return datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')


def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_hash(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def verify(root):
    """Verify frozen inputs and definitions without changing any run artifact."""
    root = Path(root)
    for relative, expected in read(root / 'manifest.json').items():
        if file_hash(root / relative) != expected:
            raise ValueError('FROZEN_ARTIFACT_CHANGED:' + relative)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_rows(path, rows):
    write_text(path, ''.join(encoded(row).decode() + '\n' for row in rows))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()] if Path(path).exists() else []


def event(root, action, **details):
    record = {'time': now(), 'event': action, **details}
    with (Path(root) / 'events.jsonl').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(encoded(record).decode() + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    # Keep full details in events.jsonl and a compact live progress log beside it.
    fields = {}
    for key, value in details.items():
        if key in ('command', 'model', 'batch_id', 'name', 'batch_name', 'batch_stats', 'status', 'provider_status', 'stage',
                   'requests', 'request_counts', 'processed', 'returned_records', 'round', 'delay_seconds', 'valid',
                   'originals', 'variants', 'error', 'error_type', 'reason',
                   'token_cost_estimate_usd', 'new_model_calls', 'execution_scope', 'analysis_tag',
                   'reasoning_effort', 'task', 'processor', 'backend', 'concurrency', 'adaptive_enabled', 'evaluation_source'):
            fields[key] = value
    line = f"[{record['time']}] {action} {encoded(fields).decode()}\n"
    with (Path(root) / 'pipeline.log').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(line)
        handle.flush()


def command(root):
    """Record the actual Python CLI invocation without copying credential values."""
    argv = list(sys.orig_argv)
    prefix = 'PYTHONPATH=' + shlex.quote(os.environ['PYTHONPATH']) + ' ' if os.environ.get('PYTHONPATH') else ''
    event(root, 'PIPELINE_COMMAND', command=prefix + shlex.join(argv), pid=os.getpid())


@contextlib.contextmanager
def locked(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('ANOTHER_PIPELINE_PROCESS_IS_ACTIVE') from None
        yield


RUN_NAME = re.compile(r'(?P<date>\d{8})-exp-(?P<number>\d{3,})(?:-(?P<suffix>[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*|\d+))?')


def allocate(root, seed=None, label=None):
    if seed is not None and (type(seed) is not int or seed < 0):
        raise ValueError('RUN_SEED_MUST_BE_NONNEGATIVE_INTEGER')
    if label is not None and (not isinstance(label, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', label)):
        raise ValueError('RUN_LABEL_MUST_BE_SAFE_LOWERCASE_NAME')
    if seed is not None and label is not None:
        raise ValueError('RUN_SEED_AND_LABEL_ARE_MUTUALLY_EXCLUSIVE')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with locked(root / '.sequence.lock'):
        date = now()[:10].replace('-', '')
        numbers = [int(match['number']) for p in root.iterdir()
                   if (match := RUN_NAME.fullmatch(p.name)) and match['date'] == date]
        suffix = f'-{label}' if label is not None else '' if seed is None else f'-{seed}'
        result = root / f'{date}-exp-{max(numbers, default=0) + 1:03d}{suffix}'
        result.mkdir()
        return result


def path_in(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError('PATH_OUTSIDE_ARTIFACT_ROOT')
    return target


def configuration(root):
    value = read(Path(root) / 'config.json')
    value = value.get('evaluation', value)
    overrides = read(Path(root) / 'runtime-overrides.json', {})
    exceptions = read(Path(root) / 'cache-exceptions.json', {})
    if exceptions and exceptions.get('run_id') != Path(root).name:
        raise ValueError('CACHE_EXCEPTION_RUN_MISMATCH')
    for model in value['models']:
        model.update(overrides.get('models', {}).get(model['key'], {}))
        model.pop('_cache_exception', None)
        if model['key'] in exceptions.get('models', {}):
            record = exceptions['models'][model['key']]
            if record.get('run_id') != Path(root).name:
                raise ValueError('CACHE_EXCEPTION_RUN_MISMATCH')
            model['_cache_exception'] = record
    return value
