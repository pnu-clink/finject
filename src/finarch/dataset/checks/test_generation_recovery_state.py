"""Recovery updates preserve the immutable attempt and survive repeated resume."""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
m = importlib.import_module('finarch.dataset.02-generation.generate_run')

class RecoveryStateTests(unittest.TestCase):
    def test_failure_before_llm_has_journal_and_records_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            bundle = Path(d)
            rnd = bundle / '02-generation/02-round'
            approved = {'test-0001': {'case_path': '01-preparation/test-0001'}}
            def read_input(path):
                if Path(path).name == 'run.json':
                    import json
                    return json.loads(Path(path).read_text())
                return {}
            with patch.object(m, 'read', side_effect=read_input), patch.object(m.g01_perturbation, 'run', side_effect=ValueError('dependency missing')), patch.object(m.g04_exception_handler, 'run', return_value={'retryable': True}):
                result = m.process(bundle, rnd, 'test-0001', 0, {}, approved, {})
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(result['retryable'])
            root = bundle / result['path']
            self.assertGreater((root / 'events.jsonl').stat().st_size, 0)
            self.assertTrue((root / '04-exception-handler/pre-feedback-run.json').exists())

    def test_restore_is_idempotent_and_preserves_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'test-0001/variant'
            ctx = m.RunContext(p, {}, 'test-0001')
            ctx.trace.emit(phase='START', status='RUNNING')
            old = {'status': 'FAIL', 'reason': 'test'}
            ctx.save('run.json', old)
            ctx.save('04-exception-handler/03-retry.json', {'retryable': True})
            result = m.restore_saved_result(p / 'run.json')
            self.assertTrue(result['retryable'])
            self.assertEqual(m.read(p / '04-exception-handler/pre-feedback-run.json'), old)
            self.assertEqual(m.restore_saved_result(p / 'run.json'), result)
            with self.assertRaises(FileExistsError):
                ctx.save('04-exception-handler/03-retry.json', {})

if __name__ == '__main__':
    unittest.main()
