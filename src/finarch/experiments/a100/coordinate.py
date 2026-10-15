"""Recover completed remote evaluations, then run the local configured analysis."""
import argparse
import fcntl
import importlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time

REMOTE = '/home/clink-wooix/workspace/fexperiment/finarch-a100-20260928'


def archive_command(root, archive):
    """Archive published files only; runtime directories can still be changing."""
    script = '''import json, pathlib, sys, tarfile
root, destination = map(pathlib.Path, sys.argv[1:])
files = set(json.loads((root / 'recovery-manifest.json').read_text()))
files.update(json.loads((root / 'transfer-manifest.json').read_text()))
files.update(('recovery-manifest.json', 'transfer-manifest.json', 'remote-state.json'))
with tarfile.open(destination, 'w:gz') as output:
    for name in sorted(files):
        path = root / name
        path.resolve().relative_to(root.resolve())
        if path.is_symlink():
            raise ValueError('UNSAFE_RECOVERY_PATH:' + name)
        output.add(path, arcname=name, recursive=False)
'''
    return shlex.join(['python3', '-c', script, root, archive])


def main():
    store = importlib.import_module('finarch.experiments.90-operations.storage')
    project = store.PROJECT
    roots = [project / 'reports/experiments-run' / ('20260928-a100-qwen3-' + size + 'b') for size in ('8', '14')]
    logroot = project / 'reports/run/20260928-a100-transfer'
    logroot.mkdir(parents=True, exist_ok=True)
    with (logroot / 'coordinator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for root in roots:
            while True:
                command = 'cat ' + shlex.quote(REMOTE + '/runs/' + root.name + '/remote-state.json')
                probe = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', 'a100', command], capture_output=True, text=True, timeout=30)
                failure = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', 'a100', 'cat ' + shlex.quote(REMOTE + '/runs/' + root.name + '/remote-failure.json')], capture_output=True, text=True, timeout=30)
                if failure.returncode == 0:
                    store.write(root / 'remote-failure.json', json.loads(failure.stdout))
                    raise RuntimeError('REMOTE_EVALUATION_FAILED:' + root.name)
                if probe.returncode == 0:
                    status = json.loads(probe.stdout)
                    store.write(root / 'remote-state.json', status)
                    if status['status'] == 'EVALUATION_RECEIVED':
                        break
                time.sleep(60)
            archive = logroot / (root.name + '.tar.gz')
            # Only this request's public inputs, raw outputs, and runtime evidence are returned.
            command = archive_command(REMOTE + '/runs/' + root.name, REMOTE + '/' + archive.name)
            subprocess.run(['ssh', 'a100', command], check=True, timeout=600)
            subprocess.run(['scp', 'a100:' + REMOTE + '/' + archive.name, str(archive)], check=True, timeout=600)
            staging = logroot / (root.name + '-recovered')
            staging.mkdir(exist_ok=True)
            with tarfile.open(archive) as tar:
                tar.extractall(staging, filter='data')
            hashes = store.read(staging / 'recovery-manifest.json')
            if not hashes:
                raise ValueError('RECOVERY_HASHES_REQUIRED')
            for relative, expected in hashes.items():
                path = staging / relative
                if not path.resolve().is_relative_to(staging.resolve()) or path.is_symlink() or store.file_hash(path) != expected:
                    raise ValueError('RECOVERY_HASH_MISMATCH:' + relative)
            import shutil
            for path in staging.rglob('*'):
                if not path.is_file():
                    continue
                relative = path.relative_to(staging)
                target = root / relative
                if target.exists() and str(relative) in store.read(root / 'manifest.json'):
                    if store.file_hash(target) != store.file_hash(path):
                        raise ValueError('FROZEN_RECOVERY_CONFLICT:' + str(relative))
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            store.event(root, 'A100_RECOVERY_VERIFIED', files=len(hashes), archive_sha256=store.file_hash(archive))
            for module in ('collect',):
                with (root / (module + '.log')).open('a') as log:
                    subprocess.run([sys.executable, '-u', '-B', '-m', 'finarch.experiments.a100.' + module,
                                    '--run', str(root)], cwd=project, stdout=log, stderr=subprocess.STDOUT, check=True)
        # Recover both completed evaluations before starting lengthy local analysis.
        for root in roots:
            with (root / 'analyze.log').open('a') as log:
                subprocess.run([sys.executable, '-u', '-B', '-m', 'finarch.experiments.a100.analyze',
                                '--run', str(root)], cwd=project, stdout=log, stderr=subprocess.STDOUT, check=True)
            store.write(logroot / (root.name + '-complete.json'), {'status': 'COMPLETE', 'at': store.now()})


if __name__ == '__main__':
    main()
