"""Offline model-change checks: archive bytes, isolate identities, and reject live work."""
import copy
import importlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

restart = importlib.import_module('finarch.experiments.90-operations.analysis_restart')
store, backend = restart.store, restart.backend


class RestartTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / '20261003-exp-004-fixture'
        self.root.mkdir()
        self.path = self.root.parent / 'hyperparameter.json'
        store.write(self.path, {'fixture': True})
        self.old = {'enabled': True, 'backend': 'codex', 'schedule': {'concurrency': 100},
                    'backends': {'codex': {'model': 'gpt-6-luna', 'reasoning_effort': 'max',
                                         'profile': {'config_overrides': {'model_reasoning_effort': 'max'}}}}}
        self.new = copy.deepcopy(self.old)
        self.new['backends']['codex'].update(model='gpt-6.1-sol', reasoning_effort='low',
                                            profile={'config_overrides': {'model_reasoning_effort': 'low'}})
        store.write(self.root / 'config.json', {'evaluation': {'models': []}, 'analysis': self.old})
        store.write_text(self.root / '00_input/public.jsonl', '{"fixture": true}\n')
        store.write(self.root / 'manifest.json', {n: store.file_hash(self.root / n)
                    for n in ('config.json', '00_input/public.jsonl')})
        store.write(self.root / 'state.json', {'status': 'FINISHED', 'models': {'solver': {'status': 'FINISHED'}},
                    'analysis': {'status': 'PAUSED_BY_USER'},
                    'execution_control': {'evaluation': {'paused': True}, 'analysis': {'paused': True}}})
        store.write(self.root / '02_analysis/config.json', {'analysis': self.old,
                    'analysis_sha256': store.digest(self.old)})
        schema = {'type': 'object', 'properties': {'value': {'type': 'number'}}}
        self.req = backend.request(self.root, '02_comparison', 'case', 'Review saved responses.',
                                   schema, {'case': 'case', 'responses': []})
        folder = backend.freeze(self.root, '02_comparison', [self.req])
        self.result = folder / 'calls' / self.req['trial_id'] / 'attempt-001/result.json'
        store.write(self.result, {'status': 'VALID', 'original': True})

    def execute(self, authorization='User selected Sol low and 100 concurrent calls.'):
        with patch.object(restart.settings, 'load_file', return_value=({}, self.new)), \
             patch.object(restart.subprocess, 'run', return_value=SimpleNamespace(stdout='')):
            return restart.run(self.root, self.path, authorization)

    def test_archive_preserves_results_and_rebuilds_model_identity_only(self):
        frozen = store.read(self.root / 'manifest.json')
        raw = self.result.read_bytes()
        record = self.execute()
        archive = self.root / record['archive']
        previous_result = archive / self.result.relative_to(self.root / '02_analysis')
        self.assertEqual(previous_result.read_bytes(), raw)
        for n, digest in store.read(archive / 'history-manifest.json').items():
            self.assertEqual(store.file_hash(archive / n), digest)
        current = store.rows(self.root / '02_analysis/02_comparison/manifest.jsonl')[0]
        self.assertEqual(current['model'], 'gpt-6.1-sol')
        self.assertEqual(current['reasoning_effort'], 'low')
        self.assertNotEqual(current['trial_id'], self.req['trial_id'])
        for field in ('prompt', 'input', 'response_schema'):
            self.assertEqual(current[field], self.req[field])
        self.assertFalse(list((self.root / '02_analysis').glob('*/calls/*/attempt-*')))
        self.assertEqual(store.read(self.root / 'manifest.json'), frozen)
        store.verify(self.root)
        saved = store.read(self.root / 'state.json')
        self.assertTrue(saved['execution_control']['evaluation']['paused'])
        self.assertFalse(saved['execution_control']['analysis']['paused'])
        self.assertEqual(record['new_model_calls'], 0)

    def test_requires_explicit_authorization_and_paused_analysis(self):
        with self.assertRaisesRegex(ValueError, 'AUTHORIZATION_REQUIRED'):
            self.execute('')
        saved = store.read(self.root / 'state.json')
        saved['execution_control']['analysis']['paused'] = False
        store.write(self.root / 'state.json', saved)
        with self.assertRaisesRegex(ValueError, 'REQUIRES_PAUSED_RUN'):
            self.execute()
        self.assertTrue(self.result.exists())

    def test_restore_preserves_new_attempt_and_original_model_results(self):
        record = self.execute()
        new_result = self.root / '02_analysis/attempt-note.json'
        store.write(new_result, {'new_attempt': 'preserve'})
        saved = store.read(self.root / 'state.json')
        saved['execution_control']['analysis']['paused'] = True
        store.write(self.root / 'state.json', saved)
        history = Path(record['archive']).name
        with patch.object(restart.subprocess, 'run', return_value=SimpleNamespace(stdout='')):
            restored = restart.restore(self.root, history, 'Restore original and use a separate tagged variant.')
        self.assertTrue(self.result.exists())
        self.assertEqual(restart.configuration.read(self.root), self.old)
        self.assertTrue(store.read(self.root / 'state.json')['execution_control']['analysis']['paused'])
        self.assertEqual(store.read(self.root / restored['preserved_current'] / 'attempt-note.json'),
                         {'new_attempt': 'preserve'})
        store.verify(self.root)

    def test_running_coordinator_cannot_be_archived(self):
        store.write(self.root / '02_analysis/scheduler.json', {'pid': 987654})
        with patch.object(restart.settings, 'load_file', return_value=({}, self.new)), \
             patch.object(restart.subprocess, 'run', return_value=SimpleNamespace(
                 stdout='python -m finarch.experiments.90-operations.analysis_sequence --run ' + str(self.root))):
            with self.assertRaisesRegex(ValueError, 'COORDINATOR_STILL_RUNNING'):
                restart.run(self.root, self.path, 'User approved migration.')
        self.assertTrue(self.result.exists())

    def test_active_codex_is_rejected_without_changing_history(self):
        work = str((self.root.parent / 'work').resolve())
        store.write(self.result.with_name('provider-request.json'), {'command': ['codex', '-C', work]})
        with patch.object(restart.settings, 'load_file', return_value=({}, self.new)), \
             patch.object(restart.subprocess, 'run', return_value=SimpleNamespace(stdout='n' + work)):
            with self.assertRaisesRegex(ValueError, 'CODEX_STILL_RUNNING'):
                restart.run(self.root, self.path, 'User approved migration.')
        self.assertTrue(self.result.exists())


if __name__ == '__main__':
    unittest.main()
