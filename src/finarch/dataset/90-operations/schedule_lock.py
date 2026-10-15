"""One scheduler per run. Keep the inode stable; the OS releases dead owners."""
import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

@contextmanager
def schedule_lock(bundle):
    path = Path(bundle).resolve()/'schedule.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+', encoding='utf-8') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('SCHEDULER_ALREADY_RUNNING:'+str(path)) from None
        def record(status):
            stream.seek(0)
            stream.truncate()
            json.dump({'pid':os.getpid(), 'status':status,
                       'updated_at':datetime.now(timezone.utc).isoformat()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            record('RUNNING')
            yield
        finally:
            record('RELEASED')
            fcntl.flock(stream, fcntl.LOCK_UN)
    # Never unlink: another process may already hold this same inode.

def scheduler_owned(function):
    @wraps(function)
    def wrapped(bundle, *args, **kwargs):
        with schedule_lock(bundle):
            return function(bundle, *args, **kwargs)
    return wrapped
