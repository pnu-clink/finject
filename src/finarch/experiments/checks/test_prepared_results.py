"""Verify byte-preserving delivery and fail-closed prepared-input selection."""
import importlib
import json
import tempfile
import unittest
from pathlib import Path

release = importlib.import_module('finarch.dataset.03-release.export_run_results')
dataset = importlib.import_module('finarch.experiments.00-input.dataset')


class PreparedResultsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source-run'
        self.destination = self.root / 'prepared/source-run'
        result = self.source / 'results'
        release.save(self.source / '02-generation/result-report.json', {'status': 'FINISHED'})
        originals = [{'id': 'one', 'status': 'PASS', 'input': {'id': 'one'},
                      'external_knowledge': {'used': False}}]
        release.save(result / '00-input.json', originals)
        files = {'00-input.json': {'count': 1, 'sha256': release.sha(result / '00-input.json')}}
        for label, name in release.TYPES:
            filename = name + '.json'
            release.save(result / filename, [{'id': 'one', 'type': label, 'status': 'PASS'}])
            files[filename] = {'count': 1, 'sha256': release.sha(result / filename)}
        release.save(result / 'manifest.json', {'source_run': self.source.name,
            'selected_count': 1, 'files': files,
            'source_report_sha256': release.sha(self.source / '02-generation/result-report.json')})
        release.save(result / 'export-log.json', {'model_calls': 0})
        (result / 'README.md').write_text('# Source results\n')

    def test_copy_preserves_bytes_and_reader_identity(self):
        before = {path.name: path.read_bytes() for path in (self.source / 'results').iterdir()}
        record = release.prepare_copy(self.source, self.destination)
        self.assertEqual(record['automatic_complete_seven_pass'], 1)
        self.assertEqual(record['model_calls'], 0)
        for name, content in before.items():
            self.assertEqual((self.source / 'results' / name).read_bytes(), content)
            copied = 'SOURCE-README.md' if name == 'README.md' else name
            self.assertEqual((self.destination / copied).read_bytes(), content)
        old = dataset.collected_results(self.source)
        new = dataset.collected_results(self.source, self.destination)
        self.assertEqual((old[0], old[1], old[3]), (new[0], new[1], new[3]))
        self.assertEqual(new[2], self.destination.resolve() / 'manifest.json')
        with self.assertRaisesRegex(ValueError, 'DESTINATION_ALREADY_EXISTS'):
            release.prepare_copy(self.source, self.destination)

    def test_failed_variants_remain_in_delivery(self):
        filename = release.TYPES[-1][1] + '.json'
        release.save(self.source / 'results' / filename,
                     [{'id': 'one', 'type': release.TYPES[-1][0], 'status': 'FAIL'}])
        manifest = release.read(self.source / 'results/manifest.json')
        manifest['files'][filename]['sha256'] = release.sha(self.source / 'results' / filename)
        release.save(self.source / 'results/manifest.json', manifest)
        record = release.prepare_copy(self.source, self.destination)
        self.assertEqual(record['originals'], 1)
        self.assertEqual(record['automatic_complete_seven_pass'], 0)
        self.assertEqual(release.read(self.destination / filename)[0]['status'], 'FAIL')

    def test_modified_prepared_row_is_rejected(self):
        release.prepare_copy(self.source, self.destination)
        (self.destination / '00-input.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'PREPARED_RESULTS_FILE_CHANGED'):
            dataset.collected_results(self.source, self.destination)

    def test_stale_source_or_wrong_origin_is_rejected(self):
        release.prepare_copy(self.source, self.destination)
        manifest = self.source / 'results/manifest.json'
        manifest.write_text(manifest.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'PREPARED_RESULTS_SOURCE_CHANGED'):
            dataset.collected_results(self.source, self.destination)
        wrong = self.root / 'other-run'
        with self.assertRaisesRegex(ValueError, 'PREPARED_RESULTS_SOURCE_MISMATCH'):
            dataset.collected_results(wrong, self.destination)


if __name__ == '__main__':
    unittest.main()
