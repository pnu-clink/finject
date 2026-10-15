"""Offline cross-process scheduler exclusion and read-only gate checks."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
schedule_lock = __import__('finarch.dataset.90-operations.schedule_lock', fromlist=['schedule_lock']).schedule_lock
require_generation_inputs = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['require_generation_inputs']).require_generation_inputs

class ScheduleLockTests(unittest.TestCase):
    def test_dead_owner_recovery_and_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            script='schedule_lock = __import__("finarch.dataset.90-operations.schedule_lock", fromlist=["schedule_lock"]).schedule_lock; import sys,time\nwith schedule_lock(sys.argv[1]):\n print("locked",flush=True)\n time.sleep(30)\n'
            proc=subprocess.Popen([sys.executable,'-c',script,tmp],stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(proc.stdout.readline().strip(),'locked')
                with self.assertRaisesRegex(ValueError,'SCHEDULER_ALREADY_RUNNING'):
                    with schedule_lock(tmp):pass
            finally:
                proc.kill();proc.wait();proc.stdout.close()
            with schedule_lock(tmp):
                self.assertEqual(json.loads((Path(tmp)/'schedule.lock').read_text())['pid'],os.getpid())
            self.assertEqual(json.loads((Path(tmp)/'schedule.lock').read_text())['status'],'RELEASED')

    def test_exception_releases_and_same_process_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError,'test'):
                with schedule_lock(tmp):
                    with self.assertRaises(ValueError):
                        with schedule_lock(tmp):pass
                    raise RuntimeError('test')
            with schedule_lock(tmp):pass

    def test_gate_read_only_by_default(self):
        report={'allow_generation':True,'approved_inputs':{'test-1':{}}}
        with patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'evaluate',return_value=report) as evaluate,patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'write') as write:
            self.assertEqual(require_generation_inputs('/unused'),report['approved_inputs'])
            evaluate.assert_called_once_with('/unused',persist=False)
            write.assert_not_called()

    def test_failure_analysis_cannot_write_during_another_scheduler(self):
        execute = __import__('finarch.dataset.90-operations.failure_analysis', fromlist=['execute']).execute
        with tempfile.TemporaryDirectory() as tmp:
            with schedule_lock(tmp):
                with self.assertRaisesRegex(ValueError,'SCHEDULER_ALREADY_RUNNING'):
                    execute(tmp,'001-preparation','preparation')

if __name__=='__main__':unittest.main()
