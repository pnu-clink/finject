"""Package portable generated datasets and current experiment code without secrets."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import tarfile

protocol = importlib.import_module('finarch.experiments.a100.sync_protocol')
generated = importlib.import_module('finarch.experiments.00-input.generated')
store = generated.store


def build(destination):
    root = store.PROJECT
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    names = ['20261003-003', '20261003-concat-002']
    audit = {}
    for name in names:
        records, manifest = generated.load(root / 'data/generated' / name)
        count = sum(r['production_selection']['eligible'] for r in records)
        public, private, selection = generated.select({'generated_path': 'data/generated/' + name,
            'count': count, 'require_all_variants_pass': True, 'require_external_knowledge': True})
        audit[name] = {'cases': len(records), 'selected_originals': count, 'selected_items': len(public),
            'requests_per_model': len(public) * 4, 'selection': selection,
            'source_datasets': sorted({r['source_input']['provenance']['dataset'] for r in records})}
    roots = [*protocol.CODE_ROOTS, 'pyproject.toml', 'README.md', 'AGENTS.md',
             *['data/generated/' + name for name in names]]
    files = protocol.inventory(root, roots)
    forbidden = [p for p in files if Path(p).name == '.env' or p.endswith(('.pem', '.key'))]
    if forbidden:
        raise ValueError('SECRET_FILE_IN_PACKAGE:' + str(forbidden))
    manifest = {'schema_version': 1, 'files': files, 'dataset_audit': audit,
        'remote_root': '/home/clink-wooix/workspace/finarch/experiments',
        'scope': 'Code and full generated archives. Gold/private metadata never belongs in solver messages.',
        'status': 'PACKAGED_NOT_EVALUATED', 'new_model_calls': 0}
    manifest_path = destination / 'transfer-manifest.json'
    store.write(manifest_path, manifest)
    archive = destination / 'finarch-experiments.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for name in files:
            tar.add(root / name, arcname=name, recursive=False)
        tar.add(manifest_path, arcname='transfer-manifest.json', recursive=False)
    store.write(destination / 'archive-sha256.json', {'file': archive.name, 'sha256': protocol.sha(archive)})
    print(json.dumps({'archive': str(archive), 'files': len(files),
        'datasets': {k: {x:v[x] for x in ('cases','selected_originals','requests_per_model')} for k,v in audit.items()}}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    build(parser.parse_args().output)
