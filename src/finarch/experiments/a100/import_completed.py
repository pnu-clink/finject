"""Register sealed remote definitions and collect completed evaluation without model calls."""
import importlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile

store = importlib.import_module('finarch.experiments.90-operations.storage')


def remote_json(host, path):
    data = subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                                    host, 'cat ' + shlex.quote(str(path))], text=True)
    return json.loads(data)


def register(root, remote_root, host, output):
    """Use the sealed package and matching local private input, never regenerate requests."""
    if (root / 'manifest.json').exists():
        store.verify(root)
        return
    if root.exists() and any(root.iterdir()):
        raise ValueError('UNREGISTERED_TARGET_NOT_EMPTY')
    remote_run = remote_root.rstrip('/') + '/runs/' + root.name
    state = remote_json(host, remote_run + '/remote-state.json')
    if state.get('status') != 'EVALUATION_RECEIVED':
        raise ValueError('REMOTE_NOT_COMPLETE')
    seal = remote_json(host, remote_run + '/package-seal.json')
    if seal.get('status') != 'SEALED' or seal.get('run') != root.name:
        raise ValueError('REMOTE_PACKAGE_NOT_SEALED_FOR_RUN')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ('definitions-' + root.name + '.tar.gz')
    subprocess.run(['scp', '-o', 'BatchMode=yes', host + ':' + seal['archive'], str(archive)], check=True)
    if store.file_hash(archive) != seal['archive_sha256']:
        raise ValueError('SEALED_PACKAGE_ARCHIVE_HASH_MISMATCH')
    staging = output / (root.name + '-definitions-staging')
    if staging.exists():
        raise ValueError('DEFINITION_STAGING_ALREADY_EXISTS')
    staging.mkdir()
    with tarfile.open(archive) as package:
        names = package.getnames()
        if len(names) != len(set(names)) or any(not m.isfile() for m in package.getmembers()):
            raise ValueError('PACKAGE_REQUIRES_UNIQUE_REGULAR_FILES')
        for name in names:
            if not name.startswith(root.name + '/'):
                raise ValueError('PACKAGE_RUN_PATH_MISMATCH')
            store.path_in(staging / root.name, name[len(root.name) + 1:])
        package.extractall(staging, filter='data')
    prepared = staging / root.name
    transfer = store.read(prepared / 'transfer-manifest.json')
    files = {str(p.relative_to(prepared)) for p in prepared.rglob('*') if p.is_file()}
    if files != set(transfer) | {'transfer-manifest.json'} or len(transfer) != seal['transfer_files']:
        raise ValueError('SEALED_PACKAGE_FILE_SET_MISMATCH')
    for name, expected in transfer.items():
        if store.file_hash(store.path_in(prepared, name)) != expected:
            raise ValueError('SEALED_PACKAGE_FILE_CHANGED:' + name)
    provenance = store.read(prepared / 'source-provenance.json')
    source = store.path_in(store.PROJECT, provenance['source_run'])
    store.verify(source)
    for name in ('public', 'private'):
        if store.file_hash(source / ('00_input/' + name + '.jsonl')) != provenance['source_' + name + '_sha256']:
            raise ValueError('LOCAL_SOURCE_COHORT_HASH_MISMATCH:' + name)
    if store.file_hash(prepared / '00_input/public.jsonl') != provenance['source_public_sha256']:
        raise ValueError('REMOTE_PUBLIC_COHORT_DIFFERS_FROM_LOCAL_SOURCE')
    shutil.copyfile(source / '00_input/private.jsonl', prepared / '00_input/private.jsonl')
    store.write(prepared / 'package-seal.json', seal)
    store.write(prepared / 'manifest.json', {str(p.relative_to(prepared)): store.file_hash(p)
                                           for p in prepared.rglob('*') if p.is_file()})
    order = importlib.import_module('finarch.experiments.01-evaluation.02-request.request_order')
    selection = order.selection_from_manifests(prepared, public=store.rows(prepared / '00_input/public.jsonl'),
                                              require_same_items=True)
    if selection['originals'] != 1080 or selection['variants'] != 7560:
        raise ValueError('REGISTERED_COHORT_SIZE_MISMATCH')
    store.verify(prepared)
    root.parent.mkdir(parents=True, exist_ok=True)
    if root.exists():
        root.rmdir()
    shutil.move(str(prepared), str(root))
    receipt = {'registered_at': store.now(), 'source_run': remote_run,
               'sealed_archive_sha256': seal['archive_sha256'], 'transfer_files_verified': len(transfer),
               'private_source_run': provenance['source_run'],
               'private_sha256': provenance['source_private_sha256'], 'private_transferred': False,
               'new_model_calls': 0}
    store.write(root / 'registration-receipt.json', receipt)
    store.write(root / 'state.json', {'status': 'IMPORTING', 'evaluation': {'status': 'COLLECTING'},
                                    'analysis': {'status': 'NOT_STARTED'}})
    store.event(root, 'REMOTE_SEALED_DEFINITIONS_REGISTERED', **receipt)
    print(json.dumps(receipt), flush=True)


def ensure_report_templates(root):
    """Attach local navigation templates omitted from the public GPU package."""
    receipt_path = root / 'imported-report-templates.json'
    receipt = store.read(receipt_path, {})
    for target_name, source_name in (('model-readme-template.md', 'ordered-model-readme-template.md'),
                                      ('run-readme-template.md', 'ordered-run-readme-template.md')):
        relative = '01_evaluation/01_preparation/' + target_name
        target = root / relative
        if target.exists():
            if relative in receipt and store.file_hash(target) != receipt[relative]['sha256']:
                raise ValueError('IMPORTED_REPORT_TEMPLATE_CHANGED:' + relative)
            continue
        source = store.PROJECT / 'src/finarch/experiments/templates' / source_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        receipt[relative] = {'source': str(source.relative_to(store.PROJECT)), 'sha256': store.file_hash(target)}
        store.write(receipt_path, receipt)
        store.event(root, 'A100_LOCAL_REPORT_TEMPLATE_ATTACHED', path=relative,
                    **receipt[relative], model_calls=0)
    store.verify(root)


def run(root, remote_root, host='a100', output=None):
    root = Path(root).resolve()
    output = Path(output).resolve() if output else store.PROJECT / ('reports/run/' + store.now()[:10].replace('-', '') + '-a100-recovery')
    output.mkdir(parents=True, exist_ok=True)
    with store.locked(output / (root.name + '.lock')):
        register(root, remote_root, host, output)
        ensure_report_templates(root)
        recover = importlib.import_module('finarch.experiments.a100.recover_completed')
        collect = importlib.import_module('finarch.experiments.a100.collect')
        report = importlib.import_module('finarch.experiments.a100.summarize_recovered')
        recover.recover(root, remote_root, host, output)
        collect.collect(root)
        summary = report.summarize(root)
        report.render_index([summary], output)
        state = store.read(root / 'state.json')
        state['execution_control'] = {'analysis': {'paused': True,
                                      'reason': 'Only completed Evaluation retrieval was requested; Analysis remains stopped.',
                                      'updated_at': store.now()}}
        state['full_pipeline'] = {'status': 'EVALUATION_COMPLETE', 'stage': 'WAIT_ANALYSIS',
                                  'analysis_execution': 'PAUSED_BY_USER', 'updated_at': store.now(),
                                  'new_model_calls': 0}
        store.write(root / 'state.json', state)
        store.event(root, 'A100_COMPLETED_EVALUATION_REGISTERED', statuses=summary['statuses'],
                    responses=summary['responses'], analysis_execution='PAUSED_BY_USER', new_model_calls=0)
        return {'status': 'EVALUATION_COMPLETE', 'responses': summary['responses'],
                'statuses': summary['statuses'], 'new_model_calls': 0}
