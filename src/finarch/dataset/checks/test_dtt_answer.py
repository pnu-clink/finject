"""R18 boundary and failure controls, using local substitutes; no real calls."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

prepare = __import__('finarch.dataset.02-generation.03-validation.dtt_answer', fromlist=['prepare']).prepare
run = __import__('finarch.dataset.02-generation.03-validation.dtt_answer', fromlist=['run']).run
read = __import__('finarch.dataset.02-generation.03-validation.dtt_answer', fromlist=['read']).read
from finarch.shared.providers.structured import complete
from finarch.dataset.schemas.registry import CONTRACTS, describe

ROOT=(Path(__file__).resolve().parent / '../../../..').resolve()
CASE=ROOT/'reports/run/first-10-pot-validated-v3/test-0001'
CONFIG=ROOT/'config/llm.json'


class AnswerChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.case=Path(self.temp.name)/'test-0001'
        shutil.copytree(CASE,self.case,ignore=shutil.ignore_patterns('viewer','answers','stage18-*'))

    def save(self,path,value):path.write_text(json.dumps(value))

    def test_eight_current_observations_CQ_only(self):
        for label in ['ANSWER']+[v['label'] for v in read(CASE/'04-perturbation/05-list-candidates/03-result.json')]:
            obs,b=prepare(self.case,label)
            self.assertEqual(set(obs),{'context','question'})
            self.assertTrue(b['audit_ref']);self.assertTrue(b['audit_sha256'])
            self.assertEqual(obs['question'],read(CASE/'00-data-preparation/01-select-input/01-input.json')['question'])

    def test_failed_unknown_and_tampered_audit_blocks(self):
        stage=read(self.case/'05-text/ANSWER/latest-audit.json')['stage']
        path=self.case/stage/'03-result.json';original=read(path)
        for change in ({'status':'FAIL'},{'status':'NOT_EVALUATED'},{'findings':[]},
                       {'observation_sha256':'changed'}):
            self.save(path,original|change)
            with self.assertRaises(ValueError):prepare(self.case,'ANSWER')

    def test_changed_text_plan_and_foreign_pointer_blocks(self):
        label='IC_VALUE_01_BEFORE';p=self.case/f'05-text/{label}/latest-audit.json';old=read(p)
        request=self.case/old['stage']/'01-input.json';q=read(request);q['context']+=' tampered'
        self.save(request,q)
        with self.assertRaisesRegex(ValueError,'AUDIT_TEXT_CHANGED'):prepare(self.case,label)
        self.save(p,{'stage':'05-text/ANSWER/03-audit-meaning/v1'})
        with self.assertRaisesRegex(ValueError,'AUDIT_PATH_OUTSIDE'):prepare(self.case,label)

    def test_schema_missing_or_private_fields_never_transport(self):
        obs=prepare(self.case,'ANSWER')[0];calls=[]
        def invoke(data):return complete('dtt.answer',data,transport=lambda **kw:calls.append(kw),
                                        save=lambda *a:None,schema_mode='native')
        for field in ('gold','axis','plan','original_context','audit_result'):
            self.assertEqual(invoke(obs|{field:'PRIVATE'}).status,'FAIL')
        with patch.dict(CONTRACTS,{k:v for k,v in CONTRACTS.items() if k!='dtt.answer.response'},clear=True):
            self.assertEqual(invoke(obs).reason,'MISSING_LLM_SCHEMA')
        self.assertEqual(calls,[])

    def substitute(self,raw,requests):
        def handler(config,role,payload,*,save):
            def transport(**kw):
                requests.append(deepcopy(kw))
                if isinstance(raw,Exception):raise raw
                return raw
            return complete(role,payload,transport=transport,save=save,schema_mode='native')
        return handler

    def test_single_call_raw_schema_and_no_replay_overwrite(self):
        calls=[];raw=json.dumps({'text':'LOCAL TEST ONLY'})
        with patch.object(__import__('finarch.dataset.02-generation.03-validation.dtt_answer', fromlist=['*']), 'call',self.substitute(raw,calls)):
            result=run(self.case,CONFIG,'local',labels=['ANSWER'])
            with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
                run(self.case,CONFIG,'local',labels=['ANSWER'])
        self.assertEqual(len(calls),1)
        self.assertEqual(set(calls[0]['payload']),{'context','question'})
        self.assertNotIn('request_schema',calls[0])
        self.assertEqual(calls[0]['response_schema'],describe('dtt.answer.response')['schema'])
        p=self.case/result['results'][0]['answer_ref']
        self.assertEqual(read(p/'answer/02-raw-response.json')['text'],raw)
        self.assertEqual(read(p/'independent-answer.json')['status'],'RECEIVED')
        self.assertEqual(read(p/'review-bundle.json')['human_decision'],'PENDING')

    def test_bad_response_and_transport_failure_preserved(self):
        for index,raw in enumerate(('not json',json.dumps({'answer':123}),RuntimeError('local failure'))):
            calls=[]
            with patch.object(__import__('finarch.dataset.02-generation.03-validation.dtt_answer', fromlist=['*']), 'call',self.substitute(raw,calls)):
                result=run(self.case,CONFIG,'failed'+str(index),labels=['ANSWER'])
            self.assertEqual(len(calls),1)
            p=self.case/result['results'][0]['answer_ref'];report=read(p/'independent-answer.json')
            self.assertEqual(report['status'],'FAIL');self.assertIsNone(report['response'])
            self.assertEqual(read(p/'review-bundle.json')['human_decision'],'PENDING')
            self.assertEqual((p/'answer/02-raw-response.json').exists(),not isinstance(raw,Exception))

    def test_gate_failure_does_not_block_other_selected_variant(self):
        p=self.case/'05-text/ANSWER/latest-audit.json';a=self.case/read(p)['stage']/'03-result.json'
        self.save(a,read(a)|{'status':'FAIL'});calls=[]
        with patch.object(__import__('finarch.dataset.02-generation.03-validation.dtt_answer', fromlist=['*']), 'call',self.substitute('{"text":"LOCAL TEST"}',calls)):
            result=run(self.case,CONFIG,'mixed',labels=['ANSWER','EA_01'])
        self.assertEqual([r['status'] for r in result['results']],['FAIL','RECEIVED'])
        self.assertEqual(len(calls),1)

    def test_changed_during_call_retains_raw_but_not_current_answer(self):
        calls=[];handler=self.substitute('{"text":"LOCAL TEST"}',calls)
        def mutate(*args,**kwargs):
            result=handler(*args,**kwargs)
            p=self.case/'05-text/ANSWER/03-audit-meaning/v1/03-result.json'
            self.save(p,read(p)|{'status':'FAIL'})
            return result
        with patch.object(__import__('finarch.dataset.02-generation.03-validation.dtt_answer', fromlist=['*']), 'call',mutate):
            result=run(self.case,CONFIG,'stale',labels=['ANSWER'])
        p=self.case/result['results'][0]['answer_ref']
        self.assertEqual(read(p/'independent-answer.json')['status'],'FAIL')
        self.assertTrue((p/'answer/02-raw-response.json').exists())


if __name__=='__main__':unittest.main()
