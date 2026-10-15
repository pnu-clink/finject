"""Incremental PC/A100 code, public-input and response synchronization; no LLM calls."""
import argparse
import fcntl
import importlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from string import Template
from .sync_protocol import code_manifest, differences, digest, public_input_manifest, safe, sha, RUN_ID

PROJECT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG = PROJECT / 'config/experiments/a100-sync.toml'


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    from .sync_agent import write as atomic_write
    atomic_write(path, value)


class Synchronizer:
    def __init__(self, config=DEFAULT_CONFIG, project=PROJECT):
        self.project = Path(project)
        self.config_path = Path(config)
        self.config = tomllib.loads(self.config_path.read_text())
        self.options = self.config['sync']
        self.host = self.options['host']
        self.remote = self.options['remote_workspace'].rstrip('/')
        if not re.fullmatch(r'[a-zA-Z0-9_.@-]+', self.host) or self.host.startswith('-'):
            raise ValueError('INVALID_SSH_HOST')
        if (not self.remote.startswith('/home/') or '..' in Path(self.remote).parts
                or not re.fullmatch(r'/[a-zA-Z0-9_./-]+', self.remote)):
            raise ValueError('MANAGED_HOME_WORKSPACE_REQUIRED')
        self.log = self.project / 'log/experiments-a100-sync'
        self.log.mkdir(parents=True, exist_ok=True)
        self.agent = self.remote + '/.sync/bootstrap/sync_agent.py'
        for run, definition in self.config.get('runs', {}).items():
            if not RUN_ID.fullmatch(run):
                raise ValueError('INVALID_RUN_ID')
            if definition.get('remote_source') and not re.fullmatch(r'/[a-zA-Z0-9_./-]+', definition['remote_source']):
                raise ValueError('ABSOLUTE_REMOTE_SOURCE_REQUIRED')
        self.status = {'started_at': now(), 'host': self.host, 'remote_workspace': self.remote,
                       'new_model_calls': 0, 'code': {}, 'runs': {}, 'status': 'CHECKING'}
        previous_path = self.log / 'status.json'
        if previous_path.exists():
            previous = json.loads(previous_path.read_text())
            if previous.get('remote_workspace') == self.remote and previous.get('host') == self.host:
                self.status['runs'] = {key: value for key, value in previous.get('runs', {}).items()
                                       if key in self.config.get('runs', {})}

    def command(self, argv, **kwargs):
        started = time.monotonic()
        try:
            result = subprocess.run(argv, check=True, capture_output=True,
                                    timeout=self.options.get('transfer_timeout_seconds', 600), **kwargs)
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or b'').decode(errors='replace')[-4000:]
            raise RuntimeError('SYNC_TRANSPORT_FAILED:' + detail) from error
        with (self.log / 'events.jsonl').open('a') as handle:
            handle.write(json.dumps({'at': now(), 'event': 'SYNC_COMMAND_COMPLETED',
                         'operation': self.status.get('operation'), 'tool': argv[0],
                         'elapsed_seconds': time.monotonic() - started, 'stdout_bytes': len(result.stdout),
                         'new_model_calls': 0}) + '\n')
        return result.stdout

    def ssh(self, argv, **kwargs):
        return self.command(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                             self.host, shlex.join(argv)], **kwargs)

    def rpc(self, action, *args):
        return json.loads(self.ssh(['python3', self.agent, action, '--root', self.remote, *args]))

    def transfer(self, source, destination, names):
        if not names:
            return
        # Explicit file lists; no deletion or propagation of private/secret files.
        with tempfile.NamedTemporaryFile('w', dir=self.log, delete=False) as handle:
            handle.write('\n'.join(names) + '\n')
            list_path = handle.name
        try:
            self.command(['rsync', '-rc', '--files-from=' + list_path,
                          '-e', 'ssh -o BatchMode=yes -o ConnectTimeout=10', source, destination])
        finally:
            Path(list_path).unlink(missing_ok=True)

    def bootstrap(self):
        folder = self.remote + '/.sync/bootstrap'
        self.ssh(['mkdir', '-p', folder])
        base = Path(__file__).parent
        self.transfer(str(base) + '/', self.host + ':' + folder + '/', ['sync_agent.py', 'sync_protocol.py'])
        self.rpc('init')

    def push(self):
        expected = code_manifest(self.project)
        release = digest(expected)
        self.status['operation'] = 'DEPLOYING_CODE'
        self.save()
        target = self.remote + '/releases/' + release
        self.ssh(['mkdir', '-p', target])
        self.transfer(str(self.project) + '/', self.host + ':' + target + '/', sorted(expected))
        with tempfile.TemporaryDirectory(dir=self.log) as name:
            stage = Path(name)
            write(stage / 'sync-release.json', {'release': release, 'files': expected, 'created_at': now()})
            self.transfer(str(stage) + '/', self.host + ':' + target + '/', ['sync-release.json'])
        self.status['code'] = self.rpc('release', '--release', release)
        self.status['operation'] = 'SYNCING_PUBLIC_INPUTS'
        self.save()
        for run_id in self.config.get('runs', {}):
            root = self.project / 'reports/experiments-run' / run_id
            files = public_input_manifest(root)
            incoming = self.remote + '/.sync/incoming/' + run_id
            self.ssh(['mkdir', '-p', incoming])
            self.transfer(str(root) + '/', self.host + ':' + incoming + '/', sorted(files))
            with tempfile.TemporaryDirectory(dir=self.log) as name:
                stage = Path(name)
                write(stage / 'sync-input.json', {'run_id': run_id, 'files': files,
                      'input_digest': digest(files), 'code_release': release,
                      'excluded': ['00_input/private.jsonl', 'gold', '02_analysis'], 'at': now()})
                state = json.loads((root / 'state.json').read_text())
                write(stage / 'pc-state.json', state)
                self.transfer(str(stage) + '/', self.host + ':' + incoming + '/', ['sync-input.json', 'pc-state.json'])
            self.status['runs'].setdefault(run_id, {})['inputs'] = self.rpc('inputs', '--run-id', run_id)
            self.save()
        return self.status

    def check(self):
        remote = self.rpc('check')
        expected = code_manifest(self.project)
        diff = differences(expected, remote['code'])
        self.status['code'] = {'status': 'VERIFIED' if not any(diff.values()) else 'MISMATCH',
              'release': digest(expected), 'files': len(expected), **diff}
        for run_id in self.config.get('runs', {}):
            root = self.project / 'reports/experiments-run' / run_id
            local = public_input_manifest(root)
            actual = remote['runs'].get(run_id)
            matches = actual and actual['input_digest'] == digest(local)
            self.status['runs'].setdefault(run_id, {})['inputs'] = {
                'status': 'VERIFIED' if matches else 'MISMATCH', 'files': len(local),
                'input_digest': digest(local), 'remote': actual}
            state_digest = digest(json.loads((root / 'state.json').read_text()))
            self.status['runs'][run_id]['control'] = {
                'status': 'VERIFIED' if actual and actual.get('state_digest') == state_digest else 'MISMATCH',
                'state_digest': state_digest}
        return self.status

    def push_controls(self):
        for run_id in self.config.get('runs', {}):
            if self.status['runs'][run_id].get('control', {}).get('status') == 'VERIFIED':
                continue
            state = json.loads((self.project / 'reports/experiments-run' / run_id / 'state.json').read_text())
            incoming = self.remote + '/.sync/incoming/' + run_id
            with tempfile.TemporaryDirectory(dir=self.log) as name:
                stage = Path(name)
                write(stage / 'pc-state.json', state)
                self.transfer(str(stage) + '/', self.host + ':' + incoming + '/', ['pc-state.json'])
            self.status['runs'][run_id]['control'] = self.rpc('control', '--run-id', run_id)

    def pull(self, force=False):
        for run_id, settings in self.config.get('runs', {}).items():
            self.status['operation'] = 'CHECKING_REMOTE_OUTPUTS:' + run_id
            self.save()
            model = settings['model_key']
            root = self.project / 'reports/experiments-run' / run_id
            source = settings.get('remote_source') or (
                self.remote + '/reports/experiments-run/' + run_id + '/01_evaluation/03_execution/' + model)
            arguments = ['--source', source] + (['--force'] if force else [])
            snapshot = self.rpc('outputs', *arguments)
            base = root / '01_evaluation/03_execution' / model
            target = base / 'source-stage' if settings.get('source_layout') == 'comparison_stage' else base
            target.mkdir(parents=True, exist_ok=True)
            receipt_path = self.log / (run_id + '-received.json')
            received = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
            changed = []
            checked_dirs = set()
            # Existing immutable responses may be reused only when their bytes match.
            for relative, expected in snapshot['files'].items():
                path = safe(target, relative, checked_dirs)
                if path.exists():
                    stat = path.stat()
                    stamp = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
                    cached = received.get(relative, {})
                    actual = cached.get('sha256') if not force and cached.get('stamp') == stamp else sha(path)
                    if actual != expected:
                        raise ValueError('IMMUTABLE_OUTPUT_CONFLICT:' + run_id + ':' + relative)
                else:
                    changed.append(relative)
            with tempfile.TemporaryDirectory(dir=self.log) as name:
                stage = Path(name)
                self.transfer(self.host + ':' + source + '/', str(stage) + '/', changed)
                for relative in changed:
                    if sha(safe(stage, relative)) != snapshot['files'][relative]:
                        raise ValueError('OUTPUT_CHANGED_DURING_TRANSFER:' + relative)
                for relative in changed:
                    destination = safe(target, relative)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        raise ValueError('OUTPUT_APPEARED_DURING_TRANSFER:' + relative)
                    os.replace(safe(stage, relative), destination)
            for relative, expected in snapshot['files'].items():
                path = safe(target, relative, checked_dirs)
                stat = path.stat()
                received[relative] = {'sha256': expected, 'stamp': [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]}
            write(receipt_path, received)
            write(self.log / (run_id + '-remote-snapshot.json'), snapshot)
            if settings.get('source_layout') != 'comparison_stage' and snapshot['files']:
                from .live_collection import collect
                collection = collect(root, snapshot)
            else:
                collection = {'new_records': 0, 'mode': 'PRESERVE_REGISTERED_HISTORICAL_E04'}
            outputs = {'status': 'VERIFIED', 'at': now(), 'remote_source': source,
                 'files': len(snapshot['files']), 'new_files': len(changed),
                 'pending_unpublished': snapshot['pending_unpublished'], 'remote_state': snapshot['state'],
                 'hash_verification': 'FULL_REHASH' if force else 'CONTENT_HASH_WITH_STAT_CACHE',
                 'new_model_calls': 0, 'metadata_path': str((self.log / (run_id + '-remote-snapshot.json')).relative_to(self.project))}
            outputs['local_collection'] = collection
            write(base / 'sync-status.json', outputs)
            self.status['runs'].setdefault(run_id, {})['outputs'] = outputs
            outputs['remote_inventory_verification'] = snapshot.get('inventory_verification')
            self.save()
        return self.status

    def save(self):
        self.status['updated_at'] = now()
        if self.status.get('error'):
            self.status['status'] = 'FAILED'
        else:
            checks = [self.status['code'].get('status')] + [
                value.get(kind, {}).get('status') for value in self.status['runs'].values()
                for kind in ('inputs', 'control')]
            if checks and all(x == 'VERIFIED' for x in checks):
                complete = all(value.get('outputs', {}).get('status') == 'VERIFIED' for value in self.status['runs'].values())
                self.status['status'] = 'VERIFIED' if complete else 'INPUTS_VERIFIED'
            else:
                self.status['status'] = 'MISMATCH'
        write(self.log / 'status.json', self.status)
        with (self.log / 'events.jsonl').open('a') as handle:
            handle.write(json.dumps({'at': now(), 'status': self.status['status'],
                 'operation': self.status.get('operation'),
                 'code_release': self.status['code'].get('release'), 'error': self.status.get('error'),
                 'new_model_calls': 0}) + '\n')
        template = self.project / 'src/finarch/documentation/templates/experiments-a100-sync-log.md'
        if template.exists():
            (self.log / 'README.md').write_text(Template(template.read_text()).substitute(
                status=self.status['status'], updated_at=self.status['updated_at'],
                remote_workspace=self.remote, code_release=self.status['code'].get('release', 'UNKNOWN')))


def execute(action, config=DEFAULT_CONFIG, force=False, interval=None, cycles=None):
    sync = Synchronizer(config)
    with (sync.log / 'sync.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write(sync.log / 'process.json', {'pid': os.getpid(), 'started_at': now(), 'action': action,
              'interval_seconds': interval or sync.options.get('interval_seconds', 60)})
        watched = [Path(config), Path(__file__), Path(__file__).with_name('sync_protocol.py')]
        loaded = [sha(path) for path in watched]
        count = 0
        while True:
            try:
                sync.status.pop('error', None)
                sync.bootstrap()
                if action == 'push':
                    sync.push()
                    sync.check()
                elif action == 'check':
                    sync.check()
                elif action == 'pull':
                    sync.check()
                    sync.pull(force)
                else:
                    sync.check()
                    if sync.status['code']['status'] != 'VERIFIED' or any(
                         r['inputs']['status'] != 'VERIFIED' for r in sync.status['runs'].values()):
                        sync.push()
                        sync.check()
                    sync.push_controls()
                    sync.pull(force)
                sync.check()
                sync.save()
                sync.status['operation'] = 'IDLE'
                sync.save()
            except Exception as error:
                sync.status['error'] = str(error)
                sync.save()
                if action != 'watch':
                    raise
            count += 1
            if action != 'watch' or (cycles is not None and count >= cycles):
                return sync.status
            if (sync.log / 'STOP').exists():
                return sync.status
            if [sha(path) for path in watched] != loaded:
                argv = [sys.executable, '-B', '-m', 'finarch.experiments.pipeline', 'a100-sync',
                        '--sync-action', 'watch', '--config', str(Path(config).resolve())]
                if force:
                    argv.append('--sync-force')
                if interval:
                    argv.extend(['--sync-interval', str(interval)])
                os.execv(sys.executable, argv)
            time.sleep(interval or sync.options.get('interval_seconds', 60))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'push', 'pull', 'cycle', 'watch'])
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--force', action='store_true', help='Rehash all published response bytes.')
    parser.add_argument('--interval', type=int)
    parser.add_argument('--cycles', type=int)
    args = parser.parse_args()
    if args.interval is not None and args.interval < 10:
        parser.error('--interval must be at least 10 seconds')
    print(json.dumps(execute(args.action, args.config, args.force, args.interval, args.cycles), indent=2))


if __name__ == '__main__':
    main()
