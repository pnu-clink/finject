from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from finarch.experiments.a100 import import_completed as recovery
from finarch.experiments.a100 import recover_completed, collect, summarize_recovered


class CompletedImportTests(unittest.TestCase):
    def test_registered_versioned_run_reserves_its_sequence_number(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '20260929-exp-003-a100-qwen3.8-27b').mkdir()
            with patch.object(recovery.store, 'now', return_value='2026-09-29T12:00:00+09:00'):
                self.assertEqual(recovery.store.allocate(root).name, '20260929-exp-004')

    def test_remote_incomplete_stops_before_transfer(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(recovery, 'remote_json', return_value={'status': 'RUNNING'}), \
                    patch.object(recovery.subprocess, 'run') as transfer:
                with self.assertRaisesRegex(ValueError, 'REMOTE_NOT_COMPLETE'):
                    recovery.register(Path(folder) / 'run', '/remote', 'host', Path(folder) / 'out')
                transfer.assert_not_called()

    def test_archive_hash_mismatch_stops_before_registration(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output = Path(folder) / 'run', Path(folder) / 'out'
            seal = {'status': 'SEALED', 'run': 'run', 'archive': '/remote/defs.tar.gz',
                    'archive_sha256': 'expected'}
            def transfer(*args, **kwargs):
                (output / 'definitions-run.tar.gz').write_bytes(b'wrong bytes')
            with patch.object(recovery, 'remote_json', side_effect=[{'status': 'EVALUATION_RECEIVED'}, seal]), \
                    patch.object(recovery.subprocess, 'run', side_effect=transfer):
                with self.assertRaisesRegex(ValueError, 'ARCHIVE_HASH_MISMATCH'):
                    recovery.register(root, '/remote', 'host', output)
            self.assertFalse(root.exists())

    def test_pipeline_collects_saved_results_and_keeps_analysis_paused(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output = Path(folder) / 'run', Path(folder) / 'out'
            root.mkdir()
            recovery.store.write(root / 'state.json', {'status': 'FINISHED', 'analysis': {'status': 'NOT_STARTED'}})
            summary = {'responses': 32, 'statuses': {'VALID': 30, 'OUTPUT_TRUNCATED': 2}}
            with patch.object(recovery, 'register') as register, \
                    patch.object(recovery, 'ensure_report_templates'), \
                    patch.object(recover_completed, 'recover') as fetch, \
                    patch.object(collect, 'collect') as validate, \
                    patch.object(summarize_recovered, 'summarize', return_value=summary), \
                    patch.object(summarize_recovered, 'render_index') as index:
                result = recovery.run(root, '/remote', output=output)
            register.assert_called_once()
            fetch.assert_called_once()
            validate.assert_called_once_with(root.resolve())
            index.assert_called_once_with([summary], output.resolve())
            state = recovery.store.read(root / 'state.json')
            self.assertTrue(state['execution_control']['analysis']['paused'])
            self.assertEqual(state['analysis']['status'], 'NOT_STARTED')
            self.assertEqual(result['new_model_calls'], 0)


if __name__ == '__main__':
    unittest.main()
