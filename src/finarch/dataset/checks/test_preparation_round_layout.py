"""Real stage/storage/transport boundary with fake HTTP, no paid requests."""
import copy
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from finarch.dataset.schemas.verification import CRITERIA
PREPARATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['PREPARATION']).PREPARATION

schedule=importlib.import_module('finarch.dataset.01-preparation.prepare_schedule')
ROOT=(Path(__file__).resolve().parent / '../../../..').resolve()

class Inputs:
    def case(self,name):
        return {'sample':{'id':name,'raw_id':'finance-test','context':'Amount: 2.',
            'question':'What is the amount?','reference_answer':'2','reference_answer_type':'integer',
            'reference_precision':0,'answer_metadata':{'scale':None,'negative':False}},
            'comparison':{},'provider_record':{}}

class RoundLayout(unittest.TestCase):
    def run_batch(self,root,fail_first=False):
        counts={'pot':0,'calls':0};requests=[]
        def post(endpoint,body,key,timeout):
            if endpoint.endswith('/input_tokens'):return json.dumps({'input_tokens':1000})
            counts['calls']+=1;requests.append(copy.deepcopy(body));payload=json.loads(body['input'])
            if 'allowed_steps' in payload:
                value={'retryable':True,'target_step':'03-calculation','diagnosis':'Fix missing provenance reference.',
                       'guidance':'Link the amount fact to its source usage. Preserve its value.'}
            elif 'deterministic_checks' in payload:
                value={'findings':[{'criterion':c,'judgment':'PASS','reason':'Checked','evidence':['amount']} for c in CRITERIA],
                       'cohort':'INTERNAL','cohort_reason':'All data supplied.','required_external_sources':[]}
            elif 'findings' in payload:
                value={'disposition':'UNCHANGED','edits':[],'reason':'Source is clear.'}
            else:
                counts['pot']+=1
                value={'code':'amount = fact("amount")\nanswer = amount\n','facts':[{'id':'amount','text':'2','value':'2','span':[8,9],'unit':None,'origin':'CONTEXT'}],
                  'grounding':'Use the supplied amount.','external_evidence':[],'external_knowledge_requirements':[],
                  'calculation_input_sources':['IN_CONTEXT_DATA'],
                  'source_usage':[{'id':'input','kind':'IN_CONTEXT_DATA','description':'Amount','fact_ids':['amount'],
                    'evidence_ids':[],'acquisition':'SUPPLIED','source_title':None,'source_url':None,'locator':None,
                    'quote':'2','applicability':'Given amount','code_lines':[1],'output_variables':['amount']}]}
                if fail_first and counts['pot']==1:value['source_usage'][0]['fact_ids']=[]
            return json.dumps({'id':f'resp_fake_{counts["calls"]}','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}],
                              'usage':{'input_tokens':1000,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0},'output_tokens':100,'output_tokens_details':{'reasoning_tokens':50},'total_tokens':1100}})
        with patch('finarch.shared.providers.api._post',side_effect=post),patch('finarch.shared.providers.api.api_key',return_value='fake-local-test'):
            result=schedule.run_case_rounds(Inputs(),'test-0001',root,ROOT/'config/llm.json',PREPARATION,{'max_rounds':3})
        return result,counts,requests

    def test_full_pipeline_keeps_schema_writers_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'test-0001';result,counts,_=self.run_batch(root)
            self.assertEqual(result['status'],'PASS',result)
            self.assertEqual(counts['calls'],3)
            for folder in ('02-review/02-LLM-review-original','03-calculation/02-LLM-generate-code','05-verification/06-LLM-verify-semantics'):
                path=root/'01-round'/folder/'01-input'
                self.assertTrue((path/'handler-schema.json').exists())
                self.assertTrue((path/'response-schema.json').exists())
            self.assertFalse((root/'02-review-and-correct').exists())
            self.assertTrue((root/'01-round/04-graph/05-save-graph/01-graph.json').exists())

    def test_retry_preserves_first_round_and_transmits_scoped_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'test-0001';result,counts,requests=self.run_batch(root,True)
            self.assertEqual(result['status'],'PASS',result)
            self.assertEqual(result['active_round'],'02-round')
            self.assertEqual(counts['pot'],2)
            self.assertTrue((root/'01-round/06-exception-handler/feedback/02-round/feedback.json').exists())
            call=root/'02-round/03-calculation/02-LLM-generate-code/01-input'
            ref=json.loads((call/'feedback-ref.json').read_text());self.assertTrue(ref['applied'])
            self.assertIn('Link the amount fact',json.loads((call/'rendered-prompt.json').read_text())['instruction'])
            seed=json.loads((root/'02-round/00-round-input/seed.json').read_text());self.assertTrue(seed['artifacts'])
            self.assertEqual((root/'01-round/01-source/01-receive-input/01-input.json').read_bytes(),(root/'02-round/01-source/01-receive-input/01-input.json').read_bytes())
            self.assertEqual(sum('findings' in json.loads(x['input']) for x in requests),1)
