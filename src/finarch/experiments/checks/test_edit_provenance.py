"""Saved-run metadata revisions must leave every solver and evaluation artifact intact."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

migration = __import__('finarch.experiments.00-input.edit_provenance', fromlist=['*'])
store, dataset, layout = migration.store, migration.dataset, migration.layout


class SavedEditProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'experiment'
        source = Path(temporary.name) / 'dataset'
        base = {'question': 'Amount?', 'context': 'A=10.'}
        final = {**base, 'context': 'A=10. B=20.'}
        value_patch = {'start': 5, 'end': 5, 'before': '', 'text': ' B=20.',
                       'segments': [{'kind': 'VALUE', 'text': ' B=20.'}]}
        records = [dataset.provenance.build('test-1', 'ORIGINAL', base, base),
                   dataset.provenance.build('test-1', dataset.LABELS[0], base, final,
                       {'reference': base, 'working': final, 'patches': [value_patch]})]
        files = {}
        store.write(source / 'results/00-input.json', [{'id': 'test-1', 'input': base,
                                                       'edit_provenance': records[0]}])
        for index, (label, name) in enumerate(zip(dataset.LABELS, dataset.RESULT_FILES)):
            store.write(source / 'results' / name, [{'id': 'test-1', 'type': label,
                **(final if index == 0 else {}), 'edit_provenance': records[1] if index == 0 else None}])
        for name in ['00-input.json', *dataset.RESULT_FILES]:
            files[name] = {'sha256': store.file_hash(source / 'results' / name)}
        store.write(source / 'results/manifest.json', {'source_run': source.name, 'selected_count': 1, 'files': files})
        store.write(self.root / 'config.json', {'layout_version': 2, 'evaluation': {
            'dataset': {'source_run': str(source)}, 'models': [{'key': 'luna-api'}]}, 'analysis': {'enabled': False}})
        public = [{'item_id': name, **data, 'answer_format': {'decimal_places': 0}}
                  for name, data in [('original', base), ('value', final)]]
        private = [{'item_id': name, 'case': 'test-1', 'variant': label, 'reference': {'reference_answer': '10'}}
                   for name, label in [('original', 'ORIGINAL'), ('value', dataset.LABELS[0])]]
        store.write_rows(layout.inputs(self.root) / 'public.jsonl', public)
        store.write_rows(layout.inputs(self.root) / 'private.jsonl', private)
        store.write_rows(layout.requests(self.root, 'luna-api'), [
            {'trial_id': item['item_id'], 'item_id': item['item_id'],
             'input': {k: v for k, v in item.items() if k != 'item_id'}} for item in public])
        store.write(self.root / 'manifest.json', {str(p.relative_to(self.root)): store.file_hash(p)
                    for p in self.root.rglob('*') if p.is_file()})
        store.write(self.root / '01_evaluation/03_execution/luna-api/calls/raw-response.json', {'answer': 10})
        store.write(self.root / '02_analysis/01_response_review/scores.json', {'match': True})

    def fingerprint(self):
        return {str(path.relative_to(self.root)): store.file_hash(path) for path in self.root.rglob('*')
                if path.is_file() and path.name not in ('events.jsonl', '.pipeline.lock')}

    def test_backfill_only_changes_private_and_manifest_then_is_idempotent(self):
        before = self.fingerprint()
        old_private = store.rows(layout.inputs(self.root) / 'private.jsonl')
        result = migration.attach(self.root)
        self.assertEqual(result['status_counts'], {'VERIFIED': 2})
        self.assertEqual(result['requests_checked'], 2)
        self.assertEqual({name for name, sha in before.items() if self.fingerprint()[name] != sha},
                         {'manifest.json', '00_input/private.jsonl'})
        now = store.rows(layout.inputs(self.root) / 'private.jsonl')
        self.assertEqual([{k: v for k, v in row.items() if k != 'edit_provenance'} for row in now], old_private)
        self.assertEqual(store.rows(self.root / 'events.jsonl')[-1]['new_model_calls'], 0)
        after = self.fingerprint()
        self.assertFalse(migration.attach(self.root)['changed'])
        self.assertEqual(self.fingerprint(), after)

    def test_changed_frozen_request_blocks_revision(self):
        store.write_rows(layout.requests(self.root, 'luna-api'), [])
        before = self.fingerprint()
        with self.assertRaisesRegex(ValueError, 'FROZEN_ARTIFACT_CHANGED'):
            migration.attach(self.root)
        self.assertEqual(self.fingerprint(), before)

    def test_failure_to_log_rolls_back_metadata(self):
        before = self.fingerprint()
        with patch.object(store, 'event', side_effect=OSError('disk unavailable')):
            with self.assertRaisesRegex(OSError, 'disk unavailable'):
                migration.attach(self.root)
        self.assertEqual(self.fingerprint(), before)


if __name__ == '__main__':
    unittest.main()
