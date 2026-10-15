"""Portable generated selection, leakage and integrity regression checks."""
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

generated = import_module('finarch.experiments.00-input.generated')
inputs = import_module('finarch.experiments.00-input.pipeline')
store = generated.store


class GeneratedInputTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'generated'
        self.folder.mkdir()
        self.records = []
        for case in ('test-0001', 'test-0002'):
            items = []
            for label in ('ORIGINAL', *generated.contract.TYPES):
                qc = {'question': 'What is the amount?', 'context': 'Amount is 12.'}
                content_hash = hashlib.sha256(json.dumps(qc, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                items.append({'item_id': f'run:{case}:{label}', 'type': label, **qc,
                    'content_sha256': content_hash, 'automatic_validation': {'status': 'PASS'},
                    'production_review': {'decision': None}, 'annotation': {'status': 'UNREVIEWED', 'ratings': []},
                    'source': {'file': '/nonexistent/production/secret.json'},
                    'metadata': {'reference_answer': '12', 'reference_answer_type': 'integer',
                                 'reference_precision': 0, 'external_knowledge': {'used': False, 'used_types': []}}})
            self.records.append({'format': generated.contract.FORMAT, 'run': 'run', 'id': case,
                'source_input': {}, 'original': items[0], 'variants': items[1:],
                'production_selection': {'eligible': True}})
        self.save()
        self.settings = {'generated_path': str(self.folder), 'count': 1,
                         'require_all_variants_pass': True, 'require_external_knowledge': True}

    def save(self):
        store.write_rows(self.folder / 'dataset.jsonl', self.records)
        store.write(self.folder / 'manifest.json', {'format': generated.contract.FORMAT, 'source_run': 'run',
            'files': {'dataset.jsonl': {'sha256': store.file_hash(self.folder / 'dataset.jsonl')}},
            'counts': {'cases': len(self.records)}})

    def test_portable_two_files_no_production_reads(self):
        other = self.root / 'copy'
        shutil.copytree(self.folder, other)
        a = generated.select(self.settings)
        opened = []
        actual_open = Path.open
        def isolated(path, *args, **kwargs):
            self.assertTrue(path.resolve().is_relative_to(other.resolve()), str(path))
            opened.append(path.name)
            return actual_open(path, *args, **kwargs)
        with patch.object(Path, 'open', isolated):
            b = generated.select({**self.settings, 'generated_path': str(other)})
        self.assertEqual(a[0], b[0])
        self.assertEqual([x['item_id'] for x in a[1]], [x['item_id'] for x in b[1]])
        self.assertEqual(set(opened), {'manifest.json', 'dataset.jsonl'})
        self.assertEqual(set(b[0][0]), {'item_id', 'question', 'context', 'answer_format'})
        self.assertEqual(b[1][0]['human_decision'], 'UNKNOWN')
        self.assertEqual(b[1][0]['annotation']['status'], 'UNREVIEWED')
        self.assertEqual(b[2]['analysis_metadata_status'], 'INCOMPLETE')

    def test_file_tamper(self):
        with (self.folder / 'dataset.jsonl').open('a') as f:
            f.write('\n')
        with self.assertRaisesRegex(ValueError, 'HASH_MISMATCH'):
            generated.select(self.settings)

    def test_content_hash_even_if_manifest_updated(self):
        self.records[0]['original']['context'] = 'Tampered'
        self.save()
        with self.assertRaisesRegex(ValueError, 'CONTENT_HASH_MISMATCH'):
            generated.select(self.settings)

    def test_rejected_variant_excludes_complete_cohort(self):
        self.records[0]['variants'][0]['production_review']['decision'] = 'REJECTED'
        self.records[0]['production_selection']['eligible'] = False
        self.save()
        result = generated.select(self.settings)
        self.assertEqual(result[2]['case_ids'], ['test-0002'])
        partial = generated.select({**self.settings, 'require_all_variants_pass': False})
        self.assertEqual(partial[2]['variants'], 6)

    def test_annotation_requires_policy_and_content_binding(self):
        item = self.records[0]['original']
        item['annotation'] = {'status': 'ANNOTATED', 'ratings': [{
            'item_id': item['item_id'], 'content_sha256': item['content_sha256'],
            'reviewer': 'reviewer', 'decision': 'APPROVED', 'confirmed': True}]}
        self.save()
        with self.assertRaisesRegex(ValueError, 'ANNOTATION_SELECTION_POLICY_REQUIRED'):
            generated.select(self.settings)
        item['annotation']['ratings'][0]['content_sha256'] = 'bad'
        self.save()
        with self.assertRaisesRegex(ValueError, 'ANNOTATION_CONTENT_MISMATCH'):
            generated.select(self.settings)

    def test_original_only_keeps_seven_pass_requirement(self):
        self.records[0]['variants'][0]['automatic_validation']['status'] = 'FAIL'
        self.records[0]['production_selection']['eligible'] = False
        self.save()
        public, private, selection = inputs.prepare({'dataset': {**self.settings, 'originals_only': True}})
        self.assertEqual(len(public), 1)
        self.assertEqual(selection['case_ids'], ['test-0002'])
        self.assertEqual(selection['eligible_variants_checked'], 7)

    def test_missing_or_mixed_generated_rejected(self):
        with self.assertRaisesRegex(ValueError, 'GENERATED_DATASET_REQUIRED'):
            inputs.prepare({'dataset': {'require_generated': True, 'reuse_input_run': 'old'}})
        with self.assertRaisesRegex(ValueError, 'CANNOT_MIX'):
            generated.select({**self.settings, 'source_run': '/old'})

    def test_preparation_freezes_input_and_report_rebuild_preserves_hashes(self):
        settings = import_module('finarch.experiments.90-operations.settings')
        prepare = import_module('finarch.experiments.01-evaluation.01-preparation.prepare')
        reporting = import_module('finarch.experiments.01-evaluation.04-validation.reporting')
        layout = import_module('finarch.experiments.90-operations.run_layout')
        raw, profile = settings.read_source(store.PROJECT / 'config/experiments/config.toml')
        config, analysis = settings.load(raw, profile_path=profile)
        config['dataset'] = {**self.settings, 'require_generated': True}
        config_path = self.root / 'config.json'
        store.write(config_path, {'evaluation': config, 'analysis': analysis})
        destination = self.root / 'prepared'
        destination.mkdir()
        prepare.prepare(config_path, reserved_root=destination)
        store.verify(destination)
        reporting.build(destination)
        store.verify(destination)
        self.assertEqual(store.read(destination / 'state.json')['status'], 'PREPARED')
        trials = store.rows(layout.requests(destination, 'luna-api'))
        self.assertEqual(len(trials), 32)
        self.assertTrue(all(set(row['input']) == {'question', 'context', 'answer_format'} for row in trials))
        self.assertIn('INCOMPLETE', (destination / '00_input/README.md').read_text())


if __name__ == '__main__':
    unittest.main()
