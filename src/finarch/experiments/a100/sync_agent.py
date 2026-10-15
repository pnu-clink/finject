"""SSH-side file verification only. No provider or engine is invoked here."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from string import Template
from datetime import datetime, timezone

if __package__:
    from .sync_protocol import code_manifest, differences, digest, safe, sha, RUN_ID
else:
    from sync_protocol import code_manifest, differences, digest, safe, sha, RUN_ID


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=str(path.parent), prefix='.sync-')
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def verify_files(root, manifest):
    errors = []
    for name, expected in manifest.items():
        path = safe(root, name)
        if not path.is_file() or sha(path) != expected:
            errors.append(name)
    if errors:
        raise ValueError('SYNC_HASH_MISMATCH:' + ','.join(errors[:10]))


def publish_release(root, release):
    if len(release) != 64 or any(c not in '0123456789abcdef' for c in release):
        raise ValueError('INVALID_RELEASE_ID')
    target = root / 'releases' / release
    expected = json.loads((target / 'sync-release.json').read_text())['files']
    actual = code_manifest(target)
    diff = differences(expected, actual)
    if digest(expected) != release or any(diff.values()):
        raise ValueError('RELEASE_NOT_VERIFIED:' + json.dumps(diff))
    reports = target / 'reports'
    if not reports.exists():
        reports.symlink_to(root / 'reports', target_is_directory=True)
    temporary = root / '.current-next'
    temporary.unlink(missing_ok=True) if sys.version_info >= (3, 8) else None
    temporary.symlink_to(target, target_is_directory=True)
    os.replace(temporary, root / 'current')
    write(root / '.sync/active-release.json', {'release': release, 'files': len(expected),
          'at': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0})
    return {'release': release, 'files': len(expected), 'status': 'VERIFIED'}


def publish_inputs(root, run_id):
    if not RUN_ID.fullmatch(run_id):
        raise ValueError('INVALID_RUN_ID')
    source = root / '.sync/incoming' / run_id
    definition = json.loads((source / 'sync-input.json').read_text())
    verify_files(source, definition['files'])
    target = root / 'reports/experiments-run' / run_id
    target.mkdir(parents=True, exist_ok=True)
    for name in ('00_input', '01_evaluation/01_preparation', '01_evaluation/02_request',
                 '01_evaluation/03_execution', '01_evaluation/04_validation', '02_analysis'):
        (target / name).mkdir(parents=True, exist_ok=True)
    for name, expected in definition['files'].items():
        dest = safe(target, name)
        if dest.exists() and sha(dest) != expected:
            raise ValueError('FROZEN_REMOTE_INPUT_CONFLICT:' + name)
    previous = target / 'sync-input.json'
    if previous.exists() and json.loads(previous.read_text())['files'] != definition['files']:
        raise ValueError('EXISTING_RUN_INPUT_SCOPE_CHANGED_USE_NEW_RUN')
    import shutil
    for name in definition['files']:
        dest = safe(target, name)
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe(source, name), dest)
    write(target / 'sync-input.json', definition)
    # This state belongs to the PC; evaluation never resumes by copying it.
    write(target / 'pc-state.json', json.loads((source / 'pc-state.json').read_text()))
    template = root / 'current/src/finarch/documentation/templates/experiments-a100-remote-input.md'
    if template.exists():
        (target / 'README.md').write_text(Template(template.read_text()).substitute(
            run_id=run_id, code_release=definition['code_release'], input_digest=digest(definition['files'])))
    verify_files(target, definition['files'])
    return {'run_id': run_id, 'status': 'VERIFIED', 'files': len(definition['files']),
            'input_digest': digest(definition['files'])}


def publish_control(root, run_id):
    if not RUN_ID.fullmatch(run_id):
        raise ValueError('INVALID_RUN_ID')
    target = root / 'reports/experiments-run' / run_id
    if not (target / 'sync-input.json').is_file():
        raise ValueError('PUBLIC_INPUTS_REQUIRED_BEFORE_CONTROL')
    state = json.loads((root / '.sync/incoming' / run_id / 'pc-state.json').read_text())
    write(target / 'pc-state.json', state)
    return {'status': 'VERIFIED', 'state_digest': digest(state), 'new_model_calls': 0}


def outputs(source, force=False, cache_dir=None):
    """Snapshot terminal requests; mutable execution metadata is copied separately."""
    source = Path(source)
    cache_dir = Path(cache_dir) if cache_dir else source
    cache_dir.mkdir(parents=True, exist_ok=True)
    state_path = next((source / n for n in ('remote-state.json', 'state.json') if (source / n).is_file()), None)
    state = json.loads(state_path.read_text()) if state_path else None
    state_key = digest({k: (state or {}).get(k) for k in ('status', 'total', 'completed',
                       'attempt_records', 'unknown_delivery', 'remaining_unstarted')})
    published_path = cache_dir / '.sync-published.json'
    published = json.loads(published_path.read_text()) if not force and published_path.exists() else None
    cache_path = cache_dir / '.sync-hash-cache.json'
    cache = {} if force or not cache_path.exists() else json.loads(cache_path.read_text())
    files, excluded = {}, 0
    directory = source / 'remote-results'
    reused = published and published.get('state_key') == state_key
    if reused:
        files = published['files']
        excluded = published['pending_unpublished']
    elif directory.exists():
        for folder in directory.iterdir():
            if not folder.is_dir() or folder.is_symlink():
                continue
            delivery = folder / 'delivery.json'
            if not delivery.exists():
                excluded += 1
                continue
            record = json.loads(delivery.read_text())
            if record.get('status') not in ('RECEIVED', 'UNKNOWN_DELIVERY', 'TIMEOUT', 'FAILED'):
                excluded += 1
                continue
            for path in folder.iterdir():
                if not path.is_file() or path.name.endswith('.tmp'):
                    continue
                rel = path.relative_to(source).as_posix()
                if path.is_symlink():
                    raise ValueError('SYMLINK_OUTPUT_FILE:' + rel)
                stat = path.stat()
                stamp = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
                old = cache.get(rel, {})
                value = old.get('sha256') if old.get('stamp') == stamp else sha(path)
                if path.name == 'raw-response.json' and record.get('response_sha256') and value != record['response_sha256']:
                    raise ValueError('RAW_RESPONSE_HASH_MISMATCH:' + folder.name)
                cache[rel] = {'stamp': stamp, 'sha256': value}
                files[rel] = value
    if not reused:
        write(cache_path, cache)
        write(published_path, {'state_key': state_key, 'files': files, 'pending_unpublished': excluded})
    metadata = {}
    for name in ('remote-state.json', 'state.json', 'cache-initial.json', 'cache-final.json',
                 'server-command.json', 'prepared.json', 'gpu-binding.json', 'runtime-provenance.json'):
        path = source / name
        if path.is_file():
            metadata[name] = json.loads(path.read_text())
    return {'files': files, 'state': state, 'metadata': metadata, 'pending_unpublished': excluded,
            'at': datetime.now(timezone.utc).isoformat(), 'source': str(source), 'new_model_calls': 0,
            'inventory_verification': 'UNCHANGED_EXECUTION_PUBLISHED_HASHES' if reused else 'FILE_HASH_SCAN'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'check', 'release', 'inputs', 'control', 'outputs'])
    parser.add_argument('--root', required=True)
    parser.add_argument('--release')
    parser.add_argument('--run-id')
    parser.add_argument('--source')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    root = Path(args.root)
    if not root.is_absolute() or len(root.parts) < 4 or root.is_symlink():
        raise ValueError('MANAGED_ABSOLUTE_WORKSPACE_REQUIRED')
    if args.action == 'init':
        for name in ('.sync', 'releases', 'reports/experiments-run'):
            (root / name).mkdir(parents=True, exist_ok=True)
        result = {'status': 'INITIALIZED'}
    elif args.action == 'release':
        result = publish_release(root, args.release)
    elif args.action == 'inputs':
        result = publish_inputs(root, args.run_id)
    elif args.action == 'control':
        result = publish_control(root, args.run_id)
    elif args.action == 'outputs':
        result = outputs(args.source, args.force, root / '.sync/output-cache' / digest(str(Path(args.source))))
    else:
        release = root / 'current'
        result = {'code': code_manifest(release.resolve()) if release.exists() else {}, 'runs': {}}
        for run in (root / 'reports/experiments-run').iterdir():
            definition = run / 'sync-input.json'
            if definition.exists():
                item = json.loads(definition.read_text())
                verify_files(run, item['files'])
                state = run / 'pc-state.json'
                result['runs'][run.name] = {'input_digest': digest(item['files']), 'files': len(item['files']),
                    'state_digest': digest(json.loads(state.read_text())) if state.exists() else None}
    print(json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    main()
