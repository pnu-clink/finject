"""Verify that resuming unsent work preserves uncertain attempts and Evaluation controls."""
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

control = importlib.import_module('finarch.experiments.90-operations.execution_control')
store = control.store


class ResumeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        store.write(self.root / 'state.json', {'models': {'solver': {'status': 'FINISHED'}},
            'execution_control': {'evaluation': {'paused': True, 'reason': 'Preserve Evaluation'},
                                  'analysis': {'paused': True}}, 'analysis': {}})
        self.attempt = self.root / '02_analysis/02_comparison/calls/a/attempt-001'
        store.write(self.attempt / 'request.json', {'trial_id': 'a', 'stage': '02_comparison',
            'model': 'fixture', 'reasoning_effort': 'low'})
        store.write(self.attempt / 'interruption.json', {'pid': 123, 'stopped_at': store.now(),
                                                        'automatic_replay': False})

    def test_resume_does_not_replay_or_discard_the_interrupted_attempt(self):
        original = (self.attempt / 'request.json').read_bytes()
        with patch.object(control.os, 'kill', side_effect=ProcessLookupError):
            result = control.resume_analysis(self.root, 'Start unsent work at concurrency 100.')
        self.assertEqual(result['new_model_calls'], 0)
        self.assertEqual(result['preserved_unknown_trial_ids'], ['a'])
        self.assertEqual((self.attempt / 'request.json').read_bytes(), original)
        self.assertEqual(store.read(self.attempt / 'result.json')['status'], 'UNKNOWN_DELIVERY')
        saved = store.read(self.root / 'state.json')
        self.assertEqual(saved['execution_control']['evaluation'], {'paused': True, 'reason': 'Preserve Evaluation'})
        self.assertFalse(saved['execution_control']['analysis']['paused'])
        self.assertFalse(self.attempt.with_name('attempt-002').exists())

    def test_resume_requires_stopped_process_and_authorization(self):
        with self.assertRaisesRegex(ValueError, 'AUTHORIZATION_REQUIRED'):
            control.resume_analysis(self.root, '')
        with patch.object(control.os, 'kill'), self.assertRaisesRegex(ValueError, 'STILL_ALIVE'):
            control.resume_analysis(self.root, 'Resume unsent work.')
        self.assertFalse((self.attempt / 'result.json').exists())
        self.assertTrue(store.read(self.root / 'state.json')['execution_control']['analysis']['paused'])

    def test_scoped_retry_selects_only_authorized_ids_and_preserves_other_work(self):
        backend = __import__('finarch.experiments.02-analysis.llm_backend', fromlist=['*'])
        stage = '02_comparison'
        folder = self.root / '02_analysis' / stage
        requests = [{'trial_id': name} for name in ('timeout', 'interrupted', 'capacity', 'valid', 'unsent')]
        store.write_rows(folder / 'manifest.jsonl', requests)
        store.write(self.root / 'state.json', {'execution_control': {'analysis': {'paused': False}}})
        state = {'status': 'RUNNING', 'valid': 3, 'requests': 5, 'pending': 1}
        with patch.object(store, 'verify'), \
             patch.object(backend, 'configuration', return_value=({'backend': 'codex'}, {})), \
             patch.object(backend, 'write_state'), \
             patch.object(backend.analysis_config, 'authorize_unknown_delivery_retry') as authorize, \
             patch.object(backend, 'run', return_value=state) as run, \
             patch.object(backend, 'latest', return_value={'status': 'VALID'}):
            result = control.retry_analysis_requests(self.root, stage,
                ['timeout', 'interrupted'], 'User authorized those two calls.')
        self.assertEqual(run.call_args.kwargs['recovery_retry_ids'], {'timeout', 'interrupted'})
        self.assertEqual(run.call_args.args[2], requests)
        self.assertEqual(authorize.call_args.args[2], ['timeout', 'interrupted'])
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['retried_outcomes'], {'timeout': 'VALID', 'interrupted': 'VALID'})

    def test_scoped_retry_rejects_unlisted_id_before_authorization(self):
        backend = __import__('finarch.experiments.02-analysis.llm_backend', fromlist=['*'])
        store.write(self.root / 'state.json', {'execution_control': {'analysis': {'paused': False}}})
        store.write_rows(self.root / '02_analysis/02_comparison/manifest.jsonl', [{'trial_id': 'known'}])
        with patch.object(store, 'verify'), \
             patch.object(backend, 'configuration', return_value=({'backend': 'codex'}, {})), \
             patch.object(backend, 'run') as run, \
             self.assertRaisesRegex(ValueError, 'IDS_NOT_IN_MANIFEST'):
            control.retry_analysis_requests(self.root, '02_comparison', ['unknown'], 'Retry.')
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
