"""Check missing reference handoff without changing the accepted question."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest

export = importlib.import_module('finarch.dataset.03-release.export_run_results')


class ReferenceHandoffTest(unittest.TestCase):
    def test_restore_and_preserve_input(self):
        sample = {'id': 'test-1', 'question': 'Change?', 'context': '12 to 10'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'accepted.json'
            path.write_text(json.dumps({**sample, 'reference_answer': '-2',
                'reference_answer_type': 'integer', 'reference_precision': 0}))
            restored, record = export.complete_reference(sample, path)
            self.assertEqual(restored['reference_precision'], 0)
            self.assertNotIn('reference_precision', sample)
            self.assertEqual(record['source_sha256'], export.sha(path))
            path.write_text(path.read_text().replace('12 to 10', '12 to 11'))
            with self.assertRaisesRegex(ValueError, 'QC_MISMATCH'):
                export.complete_reference(sample, path)

    def test_existing_reference_does_not_read_fallback(self):
        sample = {'reference_answer': '2', 'reference_answer_type': 'integer', 'reference_precision': 0}
        self.assertEqual(export.complete_reference(sample, Path('/missing')), (sample, None))
