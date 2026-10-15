"""Recover terminal GPU runs with byte-preserving raw files and SHA-256 checks."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile

REMOTE_PACK = r'''
import hashlib, io, json, pathlib, sys, tarfile, time
root, archive = map(pathlib.Path, sys.argv[1:3])
state_path = root / (sys.argv[3] if len(sys.argv) > 3 else 'remote-state.json')
state_bytes = state_path.read_bytes()
state = json.loads(state_bytes)
if state['status'] != 'EVALUATION_RECEIVED':
    raise ValueError('REMOTE_NOT_COMPLETE')
request_file, = root.glob('01_evaluation/02_request/*/manifest.jsonl')
requests = [json.loads(line) for line in request_file.open() if line.strip()]
expected = {r['trial_id'] for r in requests}
if len(expected) != len(requests) or state['total'] != len(requests):
    raise ValueError('REMOTE_REQUEST_COUNT_MISMATCH')
if state_path.name == 'state.json':
    prepared = json.loads((root / 'prepared.json').read_text())
    if prepared['requests'] != len(requests) or hashlib.sha256(request_file.read_bytes()).hexdigest() != prepared['manifest_sha256']:
        raise ValueError('PREPARED_MANIFEST_HASH_MISMATCH')
    source = pathlib.Path(prepared['source_manifest'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != prepared['source_manifest_sha256']:
        raise ValueError('SOURCE_MANIFEST_HASH_MISMATCH')
if {p.name for p in (root / 'remote-results').iterdir()} != expected:
    raise ValueError('REMOTE_TRIAL_SET_MISMATCH')
summary = json.loads((root / 'collection-index.json').read_text())
collection = root / 'collection/responses.jsonl'
if hashlib.sha256(collection.read_bytes()).hexdigest() != summary['responses_sha256']:
    raise ValueError('REMOTE_COLLECTION_HASH_MISMATCH')
collected = [json.loads(line)['trial_id'] for line in collection.open() if line.strip()]
if len(collected) != len(expected) or set(collected) != expected:
    raise ValueError('REMOTE_COLLECTION_TRIAL_SET_MISMATCH')
hashes = {}
archive.parent.mkdir(parents=True, exist_ok=True)
temporary = archive.with_suffix(archive.suffix + '.partial')
with tarfile.open(temporary, 'w:gz', compresslevel=1) as output:
    def add(path, name, data=None):
        if path.is_symlink():
            raise ValueError('SYMLINK_REJECTED:' + str(path))
        data = path.read_bytes() if data is None else data
        hashes[name] = hashlib.sha256(data).hexdigest()
        info = tarfile.TarInfo(name)
        info.size, info.mode, info.mtime = len(data), 0o600, path.stat().st_mtime
        output.addfile(info, io.BytesIO(data))
    for index, request in enumerate(requests, 1):
        trial = request['trial_id']
        folder = root / 'remote-results' / trial
        delivery = json.loads((folder / 'delivery.json').read_text())
        if delivery['status'] != 'RECEIVED':
            raise ValueError('UNCONFIRMED_DELIVERY:' + trial)
        raw = (folder / 'raw-response.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != delivery['response_sha256']:
            raise ValueError('RAW_RESPONSE_HASH_MISMATCH:' + trial)
        for name in ('provider-request.json', 'raw-response.json', 'delivery.json', 'format-check.json'):
            add(folder / name, 'remote-results/' + trial + '/' + name,
                raw if name == 'raw-response.json' else None)
        if index % 5000 == 0:
            print(root.name, 'packed', index, '/', len(requests), flush=True)
    for path in (root / 'collection').iterdir():
        if path.is_file():
            add(path, 'collection/' + path.name)
    for path in root.iterdir():
        if path.is_file():
            add(path, 'remote-evidence/' + path.name)
    for path in (root / '01_evaluation/02_request').rglob('*'):
        if path.is_file():
            add(path, 'remote-evidence/' + str(path.relative_to(root)))
    for path in (root / 'control').rglob('*'):
        if path.is_file():
            add(path, 'remote-evidence/' + str(path.relative_to(root)))
    receipt = {'source_run': str(root), 'requests': len(requests),
               'raw_response_hashes_verified': len(requests), 'created_at_unix': time.time(),
               'files': len(hashes), 'collection_sha256': summary['responses_sha256']}
    for name, value in (('manifest.json', hashes), ('receipt.json', receipt)):
        data = json.dumps(value, sort_keys=True).encode()
        info = tarfile.TarInfo('_recovery/' + name)
        info.size, info.mode = len(data), 0o600
        output.addfile(info, io.BytesIO(data))
if state_path.read_bytes() != state_bytes:
    raise ValueError('REMOTE_STATE_CHANGED_DURING_RECOVERY')
temporary.replace(archive)
sha = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix(archive.suffix + '.sha256').write_text(sha + '\n')
print(json.dumps({'archive': str(archive), 'sha256': sha, **receipt}), flush=True)
'''


def recover(root, remote_root, host='a100', output=None):
    store = importlib.import_module('finarch.experiments.90-operations.storage')
    root = Path(root).resolve()
    store.verify(root)
    logroot = Path(output).resolve() if output else store.PROJECT / 'reports/run/20260930-a100-recovery'
    logroot.mkdir(parents=True, exist_ok=True)
    remote_run = remote_root.rstrip('/') + '/runs/' + root.name
    remote_archive = remote_root.rstrip('/') + '/incoming/recovery-' + root.name + '.tar.gz'
    archive = logroot / ('recovery-' + root.name + '.tar.gz')
    if (root / 'recovery-receipt.json').exists():
        receipt = store.read(root / 'recovery-receipt.json')
        if store.file_hash(archive) != receipt['archive_sha256']:
            raise ValueError('EXISTING_RECOVERY_ARCHIVE_CHANGED')
        print(json.dumps(receipt), flush=True)
        return receipt
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host]
    command = shlex.join(['python3', '-c', REMOTE_PACK, remote_run, remote_archive])
    subprocess.run([*ssh, command], check=True)
    expected = subprocess.check_output([*ssh, 'cat ' + shlex.quote(remote_archive + '.sha256')], text=True).strip()
    subprocess.run(['scp', '-o', 'BatchMode=yes', host + ':' + remote_archive, str(archive)], check=True)
    if store.file_hash(archive) != expected:
        raise ValueError('RECOVERY_ARCHIVE_HASH_MISMATCH')
    staging = logroot / (root.name + '-staging')
    staging.mkdir(exist_ok=True)
    with tarfile.open(archive) as package:
        package.extractall(staging, filter='data')
    hashes = store.read(staging / '_recovery/manifest.json')
    for name, digest in hashes.items():
        path = store.path_in(staging, name)
        if path.is_symlink() or store.file_hash(path) != digest:
            raise ValueError('RECOVERY_FILE_HASH_MISMATCH:' + name)
    for name in ('remote-results', 'collection', 'remote-evidence', '_recovery'):
        if (root / name).exists():
            raise ValueError('RECOVERY_TARGET_ALREADY_EXISTS:' + name)
    for name in ('remote-results', 'collection', 'remote-evidence', '_recovery'):
        shutil.move(str(staging / name), str(root / name))
    shutil.copyfile(root / 'remote-evidence/remote-state.json', root / 'remote-state.json')
    store.verify(root)
    receipt = {**store.read(root / '_recovery/receipt.json'), 'recovered_at': store.now(),
               'archive_path': str(archive.relative_to(store.PROJECT)), 'archive_sha256': expected,
               'local_files_verified': len(hashes), 'model_calls': 0}
    store.write(root / 'recovery-receipt.json', receipt)
    store.event(root, 'A100_RECOVERY_VERIFIED', **receipt)
    print(json.dumps(receipt), flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--remote-root', required=True)
    parser.add_argument('--host', default='a100')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    recover(args.run, args.remote_root, args.host, args.output)


if __name__ == '__main__':
    main()
