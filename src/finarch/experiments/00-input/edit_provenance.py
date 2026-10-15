"""Attach review-only edit provenance to an existing run, retaining its requests."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

dataset = __import__('finarch.experiments.00-input.dataset', fromlist=['*'])
layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])


def attach(root):
    """Revise only private metadata and its frozen checksum; append the audit log."""
    root = Path(root).resolve()
    with store.locked(root / '.pipeline.lock'):
        manifest_path = root / 'manifest.json'
        manifest = store.read(manifest_path)
        for name, expected in manifest.items():
            if store.file_hash(store.path_in(root, name)) != expected:
                raise ValueError('FROZEN_ARTIFACT_CHANGED:' + name)
        private_path = layout.inputs(root) / 'private.jsonl'
        public_path = layout.inputs(root) / 'public.jsonl'
        private = store.rows(private_path)
        public_rows = store.rows(public_path)
        public = {row['item_id']: row for row in public_rows}
        if (len(public) != len(public_rows) or len({row['item_id'] for row in private}) != len(private) or
                {row['item_id'] for row in private} != set(public)):
            raise ValueError('PUBLIC_PRIVATE_ITEM_ALIGNMENT_MISMATCH')
        originals = {row['case']: public[row['item_id']] for row in private if row['variant'] == 'ORIGINAL'}
        config = layout.evaluation_config(root)
        source = (store.PROJECT / config['dataset']['source_run']).resolve()
        collected = dataset.collected_results(source, config['dataset'].get('results_path'))
        if not collected:
            raise ValueError('CONSOLIDATED_RESULTS_REQUIRED')
        old_private, old_manifest = private_path.read_bytes(), manifest_path.read_bytes()
        private_relative = str(private_path.relative_to(root))
        if private_relative not in manifest:
            raise ValueError('PRIVATE_NOT_IN_FROZEN_MANIFEST')
        changes = []
        for row in private:
            case, variant = row['case'], row['variant']
            saved = collected[3][case] if variant == 'ORIGINAL' else collected[1][variant][case]
            record = dataset.provenance.checked(saved.get('edit_provenance'), case, variant,
                                                originals[case], public[row['item_id']])
            if row.get('edit_provenance') != record:
                changes.append({'item_id': row['item_id'], 'previously_present': 'edit_provenance' in row,
                                'previous_edit_provenance': row.get('edit_provenance')})
                row['edit_provenance'] = record
        counts = dict(Counter(row['edit_provenance']['status'] for row in private))
        if not changes:
            return {'changed': False, 'rows': len(private), 'status_counts': counts, 'new_model_calls': 0}
        strip = lambda rows: [{k: v for k, v in row.items() if k != 'edit_provenance'} for row in rows]
        original_rows = [json.loads(line) for line in old_private.splitlines() if line.strip()]
        if strip(private) != strip(original_rows):
            raise ValueError('PROVENANCE_REVISION_CHANGED_EVALUATION_DATA')
        requests_checked = 0
        for model in config['models']:
            for request in store.rows(layout.requests(root, model['key'])):
                item = public[request['item_id']]
                if request['input'] != {k: v for k, v in item.items() if k != 'item_id'}:
                    raise ValueError('SAVED_REQUEST_PUBLIC_INPUT_MISMATCH:' + request['trial_id'])
                requests_checked += 1
        # Hash all saved results as well as frozen definitions; changing the viewer metadata
        # must not change target-model inputs, responses, classifications, or scores.
        protected = {str(path.relative_to(root)): store.file_hash(path) for path in root.rglob('*')
                     if path.is_file() and path.suffix in ('.json', '.jsonl') and
                     path not in (private_path, manifest_path, root / 'events.jsonl')}
        if private_path.read_bytes() != old_private or manifest_path.read_bytes() != old_manifest:
            raise ValueError('PROVENANCE_REVISION_CONCURRENT_EDIT')
        new_private = ''.join(store.encoded(row).decode() + '\n' for row in private)
        written_private = written_manifest = False
        try:
            store.write_text(private_path, new_private)
            written_private = True
            manifest[private_relative] = store.file_hash(private_path)
            store.write(manifest_path, manifest)
            written_manifest = True
            for name, expected in {**protected, **manifest}.items():
                if store.file_hash(root / name) != expected:
                    raise ValueError('PROTECTED_ARTIFACT_CHANGED:' + name)
            result = {'changed': True, 'rows': len(private), 'changed_rows': len(changes),
                      'status_counts': counts, 'new_model_calls': 0,
                      'requests_checked': requests_checked, 'protected_files_checked': len(protected),
                      'public_requests_responses_and_scores_unchanged': True,
                      'source_run': source.name, 'source_manifest_sha256': store.file_hash(collected[2]),
                      'private_before_sha256': hashlib.sha256(old_private).hexdigest(),
                      'private_after_sha256': manifest[private_relative]}
            store.event(root, 'EDIT_PROVENANCE_ATTACHED', **result,
                        manifest_before_sha256=hashlib.sha256(old_manifest).hexdigest(),
                        manifest_after_sha256=store.file_hash(manifest_path),
                        previous_metadata=changes)
        except Exception:
            if written_private:
                store.write_text(private_path, old_private.decode())
            if written_manifest:
                store.write_text(manifest_path, old_manifest.decode())
            raise
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    print(json.dumps(attach(parser.parse_args().run), ensure_ascii=False))
