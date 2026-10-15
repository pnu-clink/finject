"""Offline routing checks for the documented preparation stages."""
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

pipeline = importlib.import_module('finarch.dataset.01-preparation.preparation_pipeline')
audit = importlib.import_module('finarch.dataset.01-preparation.02-review.stage')
working = importlib.import_module('finarch.dataset.01-preparation.01-source.working_data')

class FlowChecks(unittest.TestCase):
    def check_route(self, accepted):
        sample = {'id':'test-0001','context':'Revenue is 10.','question':'What is revenue?','reference_answer':'10','reference_answer_type':'integer','reference_precision':0}
        class Inputs:
            def case(self, name):
                return {'sample':sample,'comparison':{'status':'PASS'}}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'config.json';config.write_text('{}')
            output=root/'01-preparation/test-0001';calls=[]
            def review(ctx, cfg, current, maximum):
                self.assertTrue((output/'01-source/03-compare-source/01-result.json').exists())
                calls.append('audit')
                return current, {'status':'PASS' if accepted else 'FAIL'}
            def publish(ctx, original, current, result):
                ctx.save('data.json',current)
            def calculate(ctx, cfg, current, report):
                self.assertTrue((output/'02-review-and-correct/accepted-audit.json').exists())
                calls.append('calculation');report.update(status='PASS',reason='AWAITING_HUMAN_REVIEW')
            with patch.object(audit,'run',side_effect=review),patch.object(working,'publish',side_effect=publish),patch.object(pipeline,'calculate',side_effect=calculate),patch('finarch.shared.providers.cli.call',side_effect=AssertionError('No model calls allowed')):
                result=pipeline.run_case(Inputs(),'test-0001',output,config)
            self.assertEqual(calls,['audit','calculation'] if accepted else ['audit'])
            self.assertEqual(result['status'],'PASS' if accepted else 'FAIL')
            self.assertFalse(result['allow_next_stage'])
            self.assertTrue((output/'05-human-review/01-collect-results/01-result.json').exists())
    def test_audit_failure_blocks_calculation(self): self.check_route(False)
    def test_source_and_audit_precede_calculation(self): self.check_route(True)
    def test_current_calculation_does_not_import_old_runner(self):
        module=importlib.import_module('finarch.dataset.01-preparation.03-calculation.stage')
        self.assertNotIn('data-pipeline.1_pot.run',Path(module.__file__).read_text())
