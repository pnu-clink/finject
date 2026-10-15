"""Read summary metadata without materializing discarded generation records.

The native parser validates the complete JSON. Only top-level values other
than `latest` become Python objects; a request owns its parser, so concurrent
requests cannot invalidate one another. Small metadata is cached in memory
with file-identity invalidation; source files and sidecars are never written.
"""
import json
from pathlib import Path

def _read_generation_summary(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink():return None
    try:
        try:
            import simdjson
        except ImportError:
            return {k:v for k,v in json.loads(path.read_text()).items() if k!='latest'} or None
        parser=simdjson.Parser()
        document=parser.load(str(path))
        def materialize(value):
            if isinstance(value,simdjson.Object):return value.as_dict()
            if isinstance(value,simdjson.Array):return value.as_list()
            return value
        return {key:materialize(document[key]) for key in document if key!='latest'} or None
    except (OSError,ValueError) as error:
        return {'read_error':str(error)}


# [VP01] Cache only small metadata, keyed by file identity and nanosecond times.
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
_cache = OrderedDict()
_lock = Lock()

# Keep only status/reason projections, not the plans and prompts in run.json.
_status_cache = OrderedDict()
_status_bytes = 0
_status_lock = Lock()

def read_status_record(path):
    global _status_bytes
    path = Path(path)
    if not path.is_file() or path.is_symlink():return None
    stat = path.stat()
    stamp = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    key = str(path)
    with _status_lock:
        cached = _status_cache.get(key)
        if cached and cached[0] == stamp:
            _status_cache.move_to_end(key)
            return dict(cached[1])
    try:
        import simdjson
    except ImportError:
        document = json.loads(path.read_text())
    else:
        document = simdjson.Parser().load(str(path))
    value = {name:document[name] for name in ('status','reason') if name in document}
    after = path.stat()
    if stamp == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        size = len(key.encode()) + len(json.dumps(value).encode())
        with _status_lock:
            previous = _status_cache.pop(key, None)
            if previous:_status_bytes -= previous[2]
            if size <= 65536:
                _status_cache[key] = (stamp, dict(value), size)
                _status_bytes += size
            while _status_cache and (_status_bytes > 8*1024*1024 or len(_status_cache)>20000):
                _status_bytes -= _status_cache.popitem(last=False)[1][2]
    return value

def read_generation_summary(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        stat = path.stat()
        stamp = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        key = str(path.resolve())
        with _lock:
            cached = _cache.get(key)
            if cached and cached[0] == stamp:
                _cache.move_to_end(key)
                return deepcopy(cached[1])
            value = _read_generation_summary(path)
            after = path.stat()
            stable = stamp == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            if stable and not (isinstance(value, dict) and 'read_error' in value) and len(json.dumps(value)) < 65536:
                _cache[key] = (stamp, deepcopy(value))
                while len(_cache) > 16:
                    _cache.popitem(last=False)
            else:
                _cache.pop(key, None)
            return value
    except OSError as error:
        return {'read_error': str(error)}
