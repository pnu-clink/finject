"""Reconcile the delegated EA metadata rename against its original backup."""
import json
import re
import zipfile
from hashlib import sha256
from pathlib import Path
from finarch.paths import SOURCE

event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
locked = __import__('finarch.experiments.90-operations.storage', fromlist=['locked']).locked
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text


def canonical(data):
    return re.sub(rb'EA([_-])0([23])', lambda m: b'EA' + m[1] + b'0' + str(int(m[2]) - 1).encode(), data)


def reconcile(root, backup):
    """Change labels once, retaining frozen provenance and provider payloads."""
    verify = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['verify']).verify
    root, backup = Path(root), Path(backup)
    folder = root / 'label-migration'
    if (folder / 'verification.json').exists():
        verify(root)
        return read(folder / 'verification.json')
    with locked(root / '.pipeline.lock'), zipfile.ZipFile(backup) as archive:
        prefix = 'report/experiments-run/' + root.name + '/'
        manifest = read(root / 'manifest.json')
        original_manifest = read(folder / 'manifest-before.json', manifest)
        changes, originals = [], {}
        for name in archive.namelist():
            if not name.startswith(prefix):
                continue
            relative = name[len(prefix):]
            path = root / relative
            # Reports are regenerated separately. Preserve append-only run events.
            if path.suffix not in ('.json', '.jsonl') or path.name == 'events.jsonl':
                continue
            if path.name in ('raw-response.json', 'raw-results.json', 'result.json'):
                raise ValueError('EA_RENAME_MUST_NOT_CHANGE_PROVIDER_RESPONSE:' + relative)
            before = archive.read(name)
            after = canonical(before)
            if path.read_bytes() not in (before, after):
                raise ValueError('EA_MIGRATION_CONCURRENT_EDIT:' + relative)
            if relative in original_manifest and sha256(before).hexdigest() != original_manifest[relative]:
                raise ValueError('EA_BACKUP_DIFFERS_FROM_FROZEN_MANIFEST:' + relative)
            if relative.endswith(('01-requests/manifest.jsonl', '03-results/results.jsonl')):
                old_rows = [json.loads(s) for s in before.splitlines() if s]
                new_rows = [json.loads(s) for s in after.splitlines() if s]
                for old, new in zip(old_rows, new_rows):
                    if {k: v for k, v in old.items() if k != 'variant'} != {k: v for k, v in new.items() if k != 'variant'}:
                        raise ValueError('EA_MIGRATION_CHANGED_ACTUAL_REQUEST')
            originals[relative] = before
            changes.append({'path': relative, 'before_sha256': sha256(before).hexdigest(),
                            'after_sha256': sha256(after).hexdigest(), 'frozen': relative in manifest})
        folder.mkdir(exist_ok=True)
        if not (folder / 'manifest-before.json').exists():
            (folder / 'manifest-before.json').write_bytes((root / 'manifest.json').read_bytes())
        with zipfile.ZipFile(folder / 'originals.zip', 'w', zipfile.ZIP_DEFLATED) as saved:
            for relative, before in originals.items():
                saved.writestr(relative, before)
        for change in changes:
            path = root / change['path']
            path.write_bytes(canonical(originals[change['path']]))
            if file_hash(path) != change['after_sha256']:
                raise ValueError('EA_MIGRATION_WRITE_FAILED:' + change['path'])
            if change['frozen']:
                manifest[change['path']] = change['after_sha256']
        write(root / 'manifest.json', manifest)
        verify(root)
        result = {'status': 'VERIFIED', 'verified_at': now(), 'labels': {'EA_02': 'EA_01', 'EA_03': 'EA_02'},
                  'new_model_calls': 0, 'trial_ids_and_provider_requests_unchanged': True,
                  'provider_raw_responses_unchanged': True, 'files': changes}
        write(folder / 'verification.json', result)
        write_text(folder / 'README.md', (SOURCE / 'experiments/templates/ea-label-readme-template.md').read_text())
        event(root, 'EA_METADATA_MIGRATION_VERIFIED', changed_files=len(changes),
              frozen_metadata_files=sum(x['frozen'] for x in changes), new_model_calls=0)
        return {'run_id': root.name, 'status': 'VERIFIED', 'changed_files': len(changes),
                'frozen_metadata_files': sum(x['frozen'] for x in changes), 'new_model_calls': 0}
