"""Offline regression checks for concurrent recheck IO and round resolution."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
require = __import__('finarch.dataset.90-operations.stage_range', fromlist=['require']).require
completion_report = __import__('finarch.dataset.viewer.reports.completion_report', fromlist=['*'])

class RecheckIOTests(unittest.TestCase):
    def test_concurrent_atomic_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'review-gate.json'
            with ThreadPoolExecutor(max_workers=32) as pool:
                list(pool.map(lambda i:write(path,{'i':i,'payload':'x'*10000}),range(200)))
            self.assertIn(read(path)['i'],range(200))
            self.assertEqual(list(Path(tmp).glob('*.tmp')),[])

    def test_active_round_and_renamed_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'test-0048'
            write(root/'run.json',{'active_round':'02-round'})
            write(root/'02-round/data.json',{'active':True})
            write(root/'02-round/04-graph/05-save-graph/01-graph.json',{'graph':True})
            values=require(root,['data.json','04-graph/04-save-graph/01-graph.json'])
            self.assertTrue(values['data.json']['active'])
            self.assertTrue(values['04-graph/04-save-graph/01-graph.json']['graph'])
            with self.assertRaisesRegex(ValueError,'PREREQUISITE_MISSING'):
                require(root,['missing.json'])

    def test_non_strict_report_preserves_detail_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            result={'run':'test','input_count':0,'approved_cases':[],'excluded_cases':[],'pending_cases':[],'status':'COMPLETED','preparation':{'rounds':[]},'generation':{'rounds':[]}}
            with patch.object(completion_report,'snapshot',return_value=result),patch('finarch.dataset.viewer.reports.generation_report.build',side_effect=ValueError('GENERATION_NOT_FINISHED')),patch('finarch.dataset.viewer.reports.timing_report.build'):
                completion_report.build(tmp,require_generation=False)
            self.assertEqual(read(Path(tmp)/'completion-report.json')['generation_detail_error'],'GENERATION_NOT_FINISHED')

if __name__=='__main__':unittest.main()
