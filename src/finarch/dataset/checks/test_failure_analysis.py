"""Offline failure-interpretation contract/lifecycle tests; no paid API calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
fa = __import__('finarch.dataset.90-operations.failure_analysis', fromlist=['*'])
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
from finarch.dataset.shared.review.failure_interpretation import interpret, validate_references, validate_translation
from finarch.dataset.schemas.failure_interpretation import ROLE, TRANSLATION_ROLE
from finarch.dataset.schemas.registry import require_llm_schema
from finarch.shared.providers.structured import complete
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult

VALUE = {'rejection_summary':'Recorded value mismatch.',
 'observations':[{'statement':'The saved run failed.','evidence_ids':['E001'],'kind':'RECORDED'}],
 'assessment':'INSUFFICIENT_EVIDENCE','rationale':'The saved result does not establish the cause.',
 'recommended_action':'Inspect the recorded calculation.','target_step':None,'limitations':['Code is missing.'],
 'repair_plan':{'action':'HUMAN_REQUIRED','target_step':None,'evidence_ids':['E001'],
                'instructions':['Inspect the recorded calculation.'],'preserve':['Original Q and C.'],
                'acceptance_checks':['Locate the missing code before rechecking.'],
                'required_information':['Missing calculation code.']}}

class FailureAnalysisTests(unittest.TestCase):
    def make_run(self, root):
        p=root/'01-preparation/test-0001'
        write(p/'run.json',{'status':'FAIL','active_round':'01-round','stopped_at':'03-calculation','reason':'MISMATCH'})
        write(p/'01-round/01-source/01-receive-input/01-input.json',{'question':'Add 1 and 2','context':'Values: 1, 2','reference_answer':3})
        write(root/'01-preparation/test-0002/run.json',{'status':'PASS'})
        return p

    def test_preview_read_only_and_no_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp); self.make_run(b)
            before={str(p):p.read_bytes() for p in b.rglob('*') if p.is_file()}
            with patch('finarch.shared.providers.cli.call',side_effect=AssertionError('paid call')):
                value=fa.preview(b,'preparation')
            self.assertEqual(value['planned'],1);self.assertEqual(value['calls'],2)
            self.assertEqual((value['model'],value['effort']),('gpt-6-luna','max'))
            costs=value['cost_breakdown']
            self.assertEqual(costs['input_token_budget']+costs['output_token_budget'],500000)
            self.assertEqual((costs['input_per_million'], costs['output_per_million']), (.1, .5))
            self.assertIsNone(value['estimated_cost_usd'])
            self.assertIsNone(costs['per_call_usd'])
            self.assertIsNone(costs['analysis_usd'])
            self.assertIsNone(costs['translation_usd'])
            self.assertEqual(before,{str(p):p.read_bytes() for p in b.rglob('*') if p.is_file()})

    def test_confirm_snapshot_and_analysis_leave_verdict_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);p=self.make_run(b);before=(p/'run.json').read_bytes()
            confirmation=fa.preview(b,'preparation')
            with patch.object(fa.subprocess,'Popen',return_value=Mock(pid=999999)) as spawn:
                job=fa.launch(b,'preparation',confirmation['preview_id'])
            self.assertIn('finarch.dataset.01-preparation.prepare_schedule',job['command'])
            self.assertIn('--analysis-job',job['command']);spawn.assert_called_once()
            fa._PROCESSES.clear()
            def worker(request,*args):
                value=copy.deepcopy(VALUE);value['observations'][0]['evidence_ids']=[request['artifacts'][0]['id']]
                return {'status':'COMPLETED','analysis':value,'display_ko':None}
            result=fa.execute(b,job['id'],'preparation',worker_override=worker)
            self.assertEqual(result['status'],'COMPLETED')
            self.assertEqual((p/'run.json').read_bytes(),before)
            self.assertTrue(list((p/'01-round/07-human-review/failure-analysis').glob('*.ref.json')))
            self.assertFalse(fa.overview(b)['jobs'][0]['results'][0]['stale'])
            write(p/'run.json',{'status':'PASS'})
            self.assertTrue(fa.overview(b)['jobs'][0]['results'][0]['stale'])

    def test_changed_confirmation_rejected_without_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);p=self.make_run(b);v=fa.preview(b,'preparation')
            write(p/'run.json',{'status':'PASS'})
            with patch.object(fa.subprocess,'Popen') as spawn:
                with self.assertRaisesRegex(ValueError,'PREVIEW_CHANGED'):
                    fa.launch(b,'preparation',v['preview_id'])
                spawn.assert_not_called()

    def test_schema_raw_preservation_and_unknown_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);self.make_run(b)
            request=fa._snapshot(b,'preparation')['requests'][0]
            saved={}
            result=complete(ROLE,request,transport=lambda **kw:json.dumps(VALUE),save=lambda k,v:saved.__setitem__(k,v),schema_mode='native')
            self.assertEqual(result.status,'PASS');self.assertIn('02-raw-response.json',saved)
            bad=copy.deepcopy(VALUE);bad['observations'][0]['evidence_ids']=['NOT_FOUND']
            with self.assertRaisesRegex(ValueError,'UNKNOWN_ANALYSIS'):
                validate_references(bad,request)
            result=complete(ROLE,request,transport=lambda **kw:'{"wrong":1}',save=lambda k,v:saved.__setitem__(k,v),schema_mode='native')
            self.assertEqual(result.reason,'RESPONSE_SCHEMA_INVALID')
            self.assertEqual(saved['02-raw-response.json']['text'],'{"wrong":1}')

    def test_translation_failure_keeps_english_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);self.make_run(b);request=fa._snapshot(b,'preparation')['requests'][0]
            model=Mock(side_effect=[StepResult('PASS','schema passed',copy.deepcopy(VALUE)),StepResult('FAIL','TRANSLATION_FAILED')])
            result=interpret(request,b/'analysis',b/'config',b/'profiles',model_call=model)
            self.assertEqual(model.call_count,2);self.assertEqual(result['status'],'PARTIAL')
            self.assertTrue(all(call.kwargs['profile_id']=='luna-max-api' for call in model.call_args_list))
            self.assertEqual(result['analysis'],VALUE);self.assertIsNone(result['display_ko'])
            changed=copy.deepcopy(VALUE);changed['assessment']='TOO_STRICT'
            with self.assertRaisesRegex(ValueError,'TRANSLATION_CHANGED'):
                validate_translation(VALUE,changed)

    def test_generation_latest_variant_and_mixed_partial_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);self.make_run(b)
            for round_,variant,status in [('01-round','ic-a','FAIL'),('02-round','ic-a','PASS'),('02-round','ea-b','FAIL'),('02-round','ea-c','FAIL')]:
                write(b/'02-generation'/round_/'test-0001'/variant/'run.json',{'status':status,'reason':'CHECK_FAILED','restart':'03-validation'})
            snap=fa._snapshot(b,'generation');self.assertEqual([t['variant'] for t in snap['targets']],['ea-b','ea-c'])
            d=b/'failure-analysis/001-generation';write(d/'snapshot.json',snap)
            write(d/'job.json',{'id':'001-generation','phase':'generation','status':'QUEUED','planned':2,'results':[]})
            def worker(request,*args):
                if request['variant']=='ea-b':raise ValueError('one failed')
                return {'status':'COMPLETED','analysis':VALUE,'display_ko':None}
            result=fa.execute(b,'001-generation','generation',worker_override=worker)
            self.assertEqual(result['status'],'PARTIAL');self.assertEqual(result['completed'],2)
            self.assertEqual(sorted(x['status'] for x in result['results']),['COMPLETED','ERROR'])

    def test_schemas_and_language_boundary(self):
        from finarch.shared.providers.cli import prepare_instruction
        from finarch.shared.providers.api import wire_schema
        for role in (ROLE,TRANSLATION_ROLE):
            schema=require_llm_schema(role)['schema']; wire_schema(schema)
            prompt,_=prepare_instruction(role,{})
            self.assertTrue(prompt.startswith('MANDATORY'))
        prompt,_=prepare_instruction(TRANSLATION_ROLE,{})
        self.assertNotIn('keep generated explanations in English',prompt)

if __name__=='__main__':unittest.main()
