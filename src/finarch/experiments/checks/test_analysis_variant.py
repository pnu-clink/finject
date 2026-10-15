"""Verify fresh tagged Analysis snapshots and start announcements without model calls."""
import importlib
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

variant = importlib.import_module('finarch.experiments.90-operations.analysis_variant')
startup = importlib.import_module('finarch.experiments.90-operations.execution_start')
store = variant.store


class VariantTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.source = Path(temp.name).resolve() / '20261003-exp-001-fixture'
        self.target = self.source.with_name(self.source.name + '-sol-low')
        self.selected = {'backend': 'codex', 'schedule': {'concurrency': 100, 'timeout_seconds': 1800,
                        'adaptive': {'enabled': False}}, 'backends': {'codex': {
                        'model': 'gpt-6.1-sol', 'reasoning_effort': 'low'}}}
        store.write(self.source / 'config.json', {'layout_version': 2, 'evaluation': {'models': []}, 'analysis': {}})
        for relative in ('00_input/public.jsonl', '00_input/private.jsonl',
                         '01_evaluation/04_validation/numeric-comparisons.jsonl'):
            store.write_text(self.source / relative, '')
        store.write_text(self.source / '01_evaluation/raw.json', 'unchanged response bytes')
        store.write(self.source / 'manifest.json', {'config.json': store.file_hash(self.source / 'config.json')})
        store.write(self.source / 'state.json', {'models': {'solver': {'status': 'FINISHED'}}})
        store.write_text(self.source / '02_analysis/old-result.json', 'old analyst result')
        self.config = self.source.parent / 'settings.json'
        store.write(self.config, {'fixture': True})

    def prepare(self):
        with patch.object(variant.settings, 'load_file', return_value=({}, self.selected)):
            return variant.prepare(self.source, self.target, self.config, 'sol-low', 'User requested a separate sol-low analysis.')

    def test_fresh_analysis_keeps_evaluation_bytes_and_excludes_old_judgments(self):
        self.prepare()
        self.assertEqual((self.target / '01_evaluation/raw.json').read_bytes(), b'unchanged response bytes')
        self.assertFalse((self.target / '02_analysis/old-result.json').exists())
        self.assertFalse((self.target / '02_analysis/01_results').exists())
        self.assertEqual(store.read(self.target / 'config.json')['analysis_tag'], 'sol-low')
        self.assertTrue(store.read(self.target / 'state.json')['execution_control']['evaluation']['paused'])
        store.write(self.source / '02_analysis/new-state.json', {'status': 'changed'})
        self.assertTrue(variant.results.verify_reuse(self.target))
        store.write_text(self.source / '01_evaluation/raw.json', 'tampered')
        with self.assertRaisesRegex(ValueError, 'SOURCE_EVALUATION_CHANGED'):
            variant.results.verify_reuse(self.target)

    def test_a01_can_rebuild_from_saved_evaluation_without_prior_analysis(self):
        self.prepare()
        state = variant.results.build(self.target)
        self.assertEqual(state['planned'], 0)
        self.assertTrue(state['source_hashes'])
        self.assertEqual(state['source_run'], self.source.name)
        self.assertFalse((self.target / '02_analysis/02_comparison').exists())

    def test_start_output_contains_actual_model_effort_tag_task_and_fixed_limit(self):
        self.prepare()
        output = StringIO()
        with redirect_stdout(output):
            startup.announce(self.target, 'A02', 'Review relationships.', processor='LLM', requests=291)
        text = output.getvalue()
        for value in ('TASK_START', 'gpt-6.1-sol', 'low', 'sol-low', 'Review relationships.', '291', '100'):
            self.assertIn(value, text)
        log = (self.target / 'pipeline.log').read_text()
        self.assertIn('"reasoning_effort": "low"', log)
        self.assertIn('"adaptive_enabled": false', log)

    def test_tag_mismatch_is_rejected_before_creating_target(self):
        with patch.object(variant.settings, 'load_file', return_value=({}, self.selected)):
            with self.assertRaisesRegex(ValueError, 'TAG_MUST_MATCH'):
                variant.prepare(self.source, self.target, self.config, 'other', 'User approved.')
        self.assertFalse(self.target.exists())


if __name__ == '__main__':
    unittest.main()
