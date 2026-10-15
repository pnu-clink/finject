"""Actual driver Path configuration must reach the EA gate, without real model calls."""
import json
from pathlib import Path
import tempfile
from importlib import import_module
import unittest
from unittest.mock import patch

driver=import_module('finarch.dataset.02-generation.generate_run')
ROOT=(Path(__file__).resolve().parent / '../../../..').resolve()

class QualityApiGateChecks(unittest.TestCase):
    def test_old_regex_examples_are_not_evidence_of_equation_recovery(self):
        quality=json.loads((ROOT/'reports/run/20260916-quality-v1/quality_scope.json').read_text())
        for identifier in ('test-0026/06-ea-earlier-input','test-0074/06-ea-earlier-input'):
            row=next(r for r in quality['records'] if r['id']==identifier)
            saved=json.loads((ROOT/row['references']['generation']['path']).read_text());case=identifier.split('/')[0]
            approval=json.loads((ROOT/row['references']['generation']['path']).with_name('approved-input.json').read_text())
            base=ROOT/'reports/run/20260916-001'/approval['case_path']
            values=[json.loads((base/approval['files'][k]['path']).read_text()) for k in ('working_input','program','graph')]
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);config=root/'config.json';driver.write(config,{'ea_recovery_policy':{'enabled':True}})
                for name,value in zip(('data.json','03-calculation/02-prepare-code/03-program.json','04-graph/04-save-graph/01-graph.json'),values):driver.write(root/'prep'/name,value)
                with patch.object(driver.g01_perturbation,'run',return_value=saved['plan']),patch.object(driver.g02_generate_text,'run',return_value=tuple(saved[k] for k in ('generation_request','generation_response','observation','patches'))),patch.object(driver,'audit_one',return_value={'status':'PASS','findings':[],'reason':'local mock'}) as audit:
                    result=driver._process_attempt(root,root/'02-generation/01-round',case,5,config,{case:{'case_path':'prep'}},{})
                self.assertEqual(audit.call_count,1);self.assertEqual(result['audit']['status'],'PASS')
                self.assertEqual(result['status'],'PASS')
                self.assertEqual(result['recovery_screen']['status'],'NOT_EVALUATED')

    def test_path_policy_off_preserves_result(self):
        verify=driver.g03_verification
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'config.json';driver.write(path,{})
            result={'status':'PASS'};verify.gg04_screen_recovery(Mock(),path,{}, {},'EA',result)
            self.assertEqual(result['status'],'PASS')
            self.assertEqual(result['recovery_screen']['status'],'NOT_EVALUATED')

    def test_saved_real_calls_wire_schema_gate_and_readonly_viewer(self):
        import hashlib
        from finarch.dataset.viewer.server import batch_data
        from finarch.dataset.viewer.reports.quality_report import source
        root=ROOT/'reports/run/20260916-luna-low-quality-v2'
        report=json.loads((root/'quality-api-check.json').read_text())
        self.assertEqual(report['summary']['generation_requests'],4);self.assertEqual(report['summary']['ea_counterexamples_blocked'],2)
        self.assertLess(report['summary']['estimated_cost_usd'],0.50)
        for r in report['records']:
            self.assertTrue(r['wire_luna_low_verified']);self.assertTrue(r['raw_response_saved'])
            wire=json.loads((ROOT/r['artifacts']['wire']['path']).read_text())
            self.assertEqual(wire['request']['reasoning']['effort'],'low');self.assertEqual(wire['request']['model'],'gpt-5.6-luna');self.assertEqual(wire['automatic_retries'],0)
            self.assertEqual(json.loads((ROOT/r['artifacts']['schema_check']['path']).read_text())['status'],'PASS')
        for ref in json.loads((root/'manifest.json').read_text())['inputs']:
            self.assertEqual(hashlib.sha256((ROOT/ref['path']).read_bytes()).hexdigest(),ref['sha256'])
        with patch.object(Path,'write_text',side_effect=AssertionError('write')):
            self.assertEqual(batch_data(ROOT/'reports/run',root.name)['batch']['quality_api_check']['summary']['raw_responses'],4)
            self.assertTrue(source(root,report['records'][0]['artifacts']['raw']['path']))

if __name__=='__main__':unittest.main()
