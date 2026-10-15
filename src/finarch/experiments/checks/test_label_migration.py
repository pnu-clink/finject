"""Metadata-only EA normalization retains executable requests and provenance."""
import tempfile
import unittest
import zipfile
from pathlib import Path

canonical = __import__('finarch.experiments.90-operations.label_migration', fromlist=['canonical']).canonical
reconcile = __import__('finarch.experiments.90-operations.label_migration', fromlist=['reconcile']).reconcile
encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write


class LabelMigrationTest(unittest.TestCase):
    def fixture(self, tmp):
        root = Path(tmp) / '20260920-exp-003'
        relative = 'model/01-requests/manifest.jsonl'
        path = root / relative
        path.parent.mkdir(parents=True)
        before = encoded({'variant': 'EA_03', 'trial_id': 'saved-id', 'prompt': 'Solve Q.', 'input': {'question': 'Q'}}) + b'\n'
        path.write_bytes(before)
        write(root / 'manifest.json', {relative: file_hash(path)})
        archive = Path(tmp) / 'backup.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('report/experiments-run/' + root.name + '/' + relative, before)
        return root, path, archive

    def test_mapping_is_simultaneous_and_verified_original_is_preserved(self):
        self.assertEqual(canonical(b'EA_02 EA_03 EA-02 EA-03'), b'EA_01 EA_02 EA-01 EA-02')
        with tempfile.TemporaryDirectory() as tmp:
            root, path, archive = self.fixture(tmp)
            original = path.read_bytes()
            path.write_bytes(canonical(original))
            result = reconcile(root, archive)
            self.assertEqual(result['status'], 'VERIFIED')
            self.assertEqual(read(path)['variant'], 'EA_02')
            self.assertEqual(reconcile(root, archive)['status'], 'VERIFIED')
            self.assertEqual(read(path)['variant'], 'EA_02')
            with zipfile.ZipFile(root / 'label-migration/originals.zip') as z:
                self.assertEqual(z.read('model/01-requests/manifest.jsonl'), original)

    def test_other_request_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path, archive = self.fixture(tmp)
            write(path, {'variant': 'EA_02', 'prompt': 'Different prompt'})
            with self.assertRaisesRegex(ValueError, 'CONCURRENT_EDIT'):
                reconcile(root, archive)


if __name__ == '__main__':
    unittest.main()
