"""Retrieve a completed comparison stage unchanged, without Evaluation or Analysis calls."""
import importlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
from string import Template

store = importlib.import_module('finarch.experiments.90-operations.storage')
packer = importlib.import_module('finarch.experiments.a100.recover_completed')


def experiment_destination(root):
    root = Path(root).resolve()
    base = (store.PROJECT / 'reports/experiments-run').resolve()
    if root == base or not root.is_relative_to(base):
        raise ValueError('EXPERIMENT_RESULTS_REQUIRE_REPORTS_EXPERIMENTS_RUN')
    return root


def render_stage_readme(root):
    receipt = store.read(root / 'recovery-receipt.json')
    prepared = store.read(root / 'remote-evidence/prepared.json')
    summary = store.read(root / 'remote-evidence/collection-index.json')
    template = Template((store.PROJECT / 'src/finarch/experiments/templates/a100-stage-recovery.md').read_text())
    store.write_text(root / 'README.md', template.substitute(
        model=prepared['model'], revision=prepared['revision'], source=receipt['source_run'],
        local_root=str(root.relative_to(store.PROJECT)), requests=receipt['requests'],
        files=receipt['local_files_verified'], statuses=json.dumps(summary['format_status'], ensure_ascii=False),
        archive_sha256=receipt['archive_sha256']))


def index(root, relocate_from=None):
    root = experiment_destination(root)
    if not relocate_from and not list(root.glob('*/recovery-receipt.json')) and (root / 'verification.json').exists():
        registration = importlib.import_module('finarch.experiments.a100.register_stage')
        return registration.finish_group(root)
    relocation = None
    if relocate_from:
        source = Path(relocate_from).resolve()
        if not source.is_relative_to(store.PROJECT / 'reports/run') or source == store.PROJECT / 'reports/run':
            raise ValueError('RELOCATION_SOURCE_MUST_BE_A_RECOVERY_FOLDER')
        if root.exists() or not list(source.glob('*/recovery-receipt.json')):
            raise ValueError('RELOCATION_TARGET_EXISTS_OR_SOURCE_NOT_RECOVERED')
        relocation = {'from': str(source.relative_to(store.PROJECT)), 'to': str(root.relative_to(store.PROJECT)),
                      'at': store.now(), 'model_calls': 0}
        root.parent.mkdir(parents=True, exist_ok=True)
        source.rename(root)
    rows = []
    verified = []
    for receipt_path in sorted(root.glob('*/recovery-receipt.json')):
        stage = receipt_path.parent
        receipt = store.read(receipt_path)
        prepared = store.read(stage / 'remote-evidence/prepared.json')
        summary = store.read(stage / 'remote-evidence/collection-index.json')
        if receipt.get('local_files_verified') != receipt['files']:
            raise ValueError('STAGE_RECOVERY_NOT_VERIFIED:' + stage.name)
        if relocation:
            if store.file_hash(stage / 'source-files.tar.gz') != receipt['archive_sha256']:
                raise ValueError('RELOCATED_ARCHIVE_CHANGED:' + stage.name)
            for name, expected in store.read(stage / '_recovery/manifest.json').items():
                if store.file_hash(store.path_in(stage, name)) != expected:
                    raise ValueError('RELOCATED_FILE_CHANGED:' + stage.name + '/' + name)
        request_file, = stage.glob('remote-evidence/01_evaluation/02_request/*/manifest.jsonl')
        if store.file_hash(request_file) != prepared['manifest_sha256']:
            raise ValueError('RECOVERED_PREPARED_MANIFEST_CHANGED:' + stage.name)
        if store.file_hash(stage / 'collection/responses.jsonl') != summary['responses_sha256']:
            raise ValueError('RECOVERED_COLLECTION_CHANGED:' + stage.name)
        if summary['total_manifest_requests'] != receipt['requests'] or not summary['complete_delivery_coverage']:
            raise ValueError('RECOVERED_COLLECTION_COVERAGE_MISMATCH:' + stage.name)
        verified.append({'stage': stage.name, 'model': prepared['model'], 'requests': receipt['requests'],
                         'collection_sha256': summary['responses_sha256'],
                         'manifest_sha256': prepared['manifest_sha256'], 'status': 'PASS'})
        rows.append('|[' + prepared['model'] + '](' + stage.name + '/README.md)|' +
                    str(receipt['requests']) + '|' + str(summary['format_status'].get('VALID', 0)) + '|' +
                    str(receipt['local_files_verified']) + '|')
        render_stage_readme(stage)
    if not rows:
        raise ValueError('NO_VERIFIED_STAGE_RECOVERIES')
    template = Template((store.PROJECT / 'src/finarch/experiments/templates/a100-stage-recovery-index.md').read_text())
    store.write_text(root / 'README.md', template.substitute(rows='\n'.join(rows)))
    store.write(root / 'verification.json', {'status': 'PASS', 'at': store.now(), 'stages': verified, 'model_calls': 0})
    if relocation:
        store.write(root / 'relocation-receipt.json', {**relocation, 'status': 'PASS', 'stages': verified,
                                                     'scope': 'All original files and archives verified after same-filesystem relocation.'})
        store.event(root, 'EXPERIMENT_RECOVERY_RELOCATED', **relocation)
    return {'status': 'RECOVERY_INDEX_READY', 'stages': len(rows), 'model_calls': 0}


def run(root, remote_stage, host='a100'):
    root = experiment_destination(root)
    root.mkdir(parents=True, exist_ok=True)
    receipt_path = root / 'recovery-receipt.json'
    archive = root / 'source-files.tar.gz'
    with store.locked(root / 'recovery.lock'):
        if receipt_path.exists():
            receipt = store.read(receipt_path)
            if receipt['source_run'] != remote_stage or store.file_hash(archive) != receipt['archive_sha256']:
                raise ValueError('EXISTING_STAGE_RECOVERY_CHANGED')
        else:
            ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host]
            # Store the export beside the comparison, outside the finished stage.
            remote_archive = str(Path(remote_stage).parent / ('recovery-' + Path(remote_stage).name + '.tar.gz'))
            subprocess.run([*ssh, shlex.join(['python3', '-c', packer.REMOTE_PACK,
                                             remote_stage, remote_archive, 'state.json'])], check=True)
            expected = subprocess.check_output([*ssh, 'cat ' + shlex.quote(remote_archive + '.sha256')], text=True).strip()
            subprocess.run(['scp', '-o', 'BatchMode=yes', host + ':' + remote_archive, str(archive)], check=True)
            if store.file_hash(archive) != expected:
                raise ValueError('STAGE_ARCHIVE_HASH_MISMATCH')
            with tarfile.open(archive) as package:
                names = package.getnames()
                if len(names) != len(set(names)) or any(not entry.isfile() for entry in package.getmembers()):
                    raise ValueError('STAGE_ARCHIVE_REQUIRES_UNIQUE_REGULAR_FILES')
                for name in names:
                    store.path_in(root, name)
                package.extractall(root, filter='data')
            receipt = {**store.read(root / '_recovery/receipt.json'),
                       'host': host, 'archive_sha256': expected, 'recovered_at': store.now(),
                       'model_calls': 0, 'analysis_status': 'NOT_STARTED',
                       'scope': 'Original responses, requests, collection and execution evidence; no Evaluation reclassification.'}
        hashes = store.read(root / '_recovery/manifest.json')
        for name, expected in hashes.items():
            path = store.path_in(root, name)
            if path.is_symlink() or store.file_hash(path) != expected:
                raise ValueError('STAGE_FILE_HASH_MISMATCH:' + name)
        receipt['local_files_verified'] = len(hashes)
        store.write(receipt_path, receipt)
        render_stage_readme(root)
        store.event(root, 'A100_COMPLETED_STAGE_RECOVERED', **receipt)
        print(json.dumps(receipt), flush=True)
        return receipt
