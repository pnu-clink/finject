"""Offline exception diagnosis and bounded retry checks."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
load = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['load']).load

handler = importlib.import_module('finarch.dataset.01-preparation.06-exception-handler.stage')
schedule = importlib.import_module('finarch.dataset.01-preparation.prepare_schedule')
driver = importlib.import_module('finarch.dataset.01-preparation.prepare_run')

class HandlerChecks(unittest.TestCase):
    def test_feedback_is_bound_to_step_case_and_round(self):
        with tempfile.TemporaryDirectory() as directory:
            class Context:
                root = Path(directory)
                def save(self, name, value):
                    path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            result=handler.pp03_record_feedback(Context(), {'case':'x','source_round':'01-round'},
                {'retryable':True,'target_step':'03-calculation','diagnosis':'Misspelled variable', 'guidance':'Use a consistent variable name.'})
            record=load(result['feedback_ref'],case='x',target_round='02-round')
            self.assertEqual(record['target_step'],'03-calculation')
            with self.assertRaisesRegex(ValueError,'CASE_MISMATCH'):
                load(result['feedback_ref'],case='other')

    def test_bad_target_is_not_retried(self):
        with self.assertRaisesRegex(ValueError,'INVALID_FEEDBACK_TARGET'):
            handler.pp03_record_feedback(None,{}, {'target_step':'unknown'})

    def test_schedule_applies_feedback_only_on_next_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'case';root.mkdir()
            class Context:
                def __init__(self):self.root=root
                def save(self,name,value):
                    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            ctx=Context()
            recovery=handler.pp03_record_feedback(ctx,{'case':'x','source_round':'01-round'},
                {'retryable':True,'target_step':'03-calculation','diagnosis':'Typo','guidance':'Use the declared variable.'})
            calls=[]
            def run(*args,**kwargs):
                calls.append(kwargs)
                if len(calls)==1:return {'status':'FAIL','recovery':recovery}
                from finarch.shared.providers.cli import prepare_instruction
                instruction,definition=prepare_instruction('01-preparation.03-calculation.pot',{'axis':'ANSWER'})
                self.assertIn('Use the declared variable.',instruction)
                self.assertTrue(any(p.get('feedback_ref') for p in definition['parts']))
                return {'status':'PAUSED'}
            with patch.object(driver,'run',side_effect=run):
                value=schedule.run_case_rounds(None,'x',root,None,('01-source','02-review','03-calculation'),{'max_rounds':2})
            self.assertEqual(value['status'],'PAUSED')
            self.assertEqual(calls[1]['start_stage'],'01-source')
            self.assertEqual(calls[1]['reuse_before'],'03-calculation')
            self.assertEqual(calls[1]['round_number'],2)
            self.assertTrue((root/'01-round/run.json').exists())

    def test_limit_keeps_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(driver,'run',return_value={'status':'FAIL','recovery':{'retryable':True,'target_step':'01-source'}}):
                value=schedule.run_case_rounds(None,'x',Path(directory),None,('01-source',),{'max_rounds':1})
            self.assertEqual(value['status'],'FAIL')
            self.assertTrue(value['retry_limit_reached'])

if __name__=='__main__':unittest.main()
