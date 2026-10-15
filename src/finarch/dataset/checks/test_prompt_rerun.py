"""Regression: a usage-limit response must not crash final run accounting."""
import json
from pathlib import Path
import tempfile
import unittest
report = __import__('finarch.dataset.02-generation.02-generate-text.prompt_rerun', fromlist=['report']).report


class ReportChecks(unittest.TestCase):
    def test_missing_usage_preserves_failed_call_without_claiming_zero_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);call=root/'test-0001/05-text/EA_02/realize';call.mkdir(parents=True)
            def save(path,value):path.write_text(json.dumps(value))
            save(root/'plan.json',{'baseline':[],'prompts':{'02-generation.02-generate-text.realization':[{'id':'ea','sha256':'expected'}]}})
            save(root/'summary.json',{})
            save(root/'test-0001/copied-inputs.json',{'sha256':{}})
            save(call/'03-result/usage.json',{'cli_invocations':1,'reported_usage':None})
            save(call/'01-input.json',{'role':'02-generation.02-generate-text.realization','model':'gpt-5.3-codex-spark','effort':'low',
                'prompt_selection':{'id':'ea','sha256':'expected'}})
            save(call/'02-raw-response/cli-execution.json',{'exit_code':1,'elapsed_seconds':2.7})
            state={'status':'COMPLETED','source':str(root),'cases':{'test-0001':{'status':'ERROR','reason':'usage limit'}}}
            result=report(root,state)
            self.assertEqual(result['call_count'],{'02-generation.02-generate-text.realization':1})
            self.assertAlmostEqual(result['cli_seconds_by_role']['02-generation.02-generate-text.realization'],2.7)
            self.assertFalse(result['usage_records_complete'])
            self.assertEqual(len(result['missing_usage_paths']),1)
            self.assertEqual(result['reported_usage'],{})
            self.assertTrue((root/'README.md').exists())
