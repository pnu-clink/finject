"""Stage16 editing boundaries, using real saved plans and local transports only."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import tempfile
import shutil
from unittest.mock import patch
make_request = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['make_request']).make_request
check_response = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['check_response']).check_response
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
checked_plan = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['checked_plan']).checked_plan
run = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['run']).run
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
from finarch.dataset.shared.calculation.python_graph import load_graph
compose_pair = __import__('finarch.dataset.02-generation.01-perturbation.value_positions', fromlist=['compose_pair']).compose_pair
from finarch.shared.providers.structured import complete
from finarch.dataset.schemas.registry import describe, CONTRACTS

ROOT=(Path(__file__).resolve().parent / '../../../..').resolve()
CASE=ROOT/'reports/run/first-10-pot-validated-v3/test-0001'

class RealizationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample=read(CASE/'00-data-preparation/01-select-input/01-input.json');cls.program=read(CASE/'02-calculation/02-prepare-code/03-program.json')
        cls.graph=load_graph(CASE);cls.variants={v['label']:v for v in read(CASE/'04-perturbation/05-list-candidates/03-result.json')}

    def request(self,label):
        return make_request(CASE,self.variants[label],self.sample,self.program,self.graph,
                            "In the past quarter, the bank's service fee income was 90,000 dollars.")

    def response(self,request):
        result=[]
        for s in request['edit_slots']:
            text=s['exact_text']
            if text is None:
                text={'VALUE':"In the past quarter, the bank's service fee income was 90,000 dollars. ",
                      'SOURCE_A':' (according to a financial analyst who checked the underlying transaction records)',
                      'SOURCE_B':s['required_prefix']+'a financial analyst who checked the underlying transaction records.',
                      'RELATION':' In the past quarter, service fee income was twice the financial product sales commission income.'}[s['kind']]
            result.append({k:s[k] for k in ('start','end','before','element_ids')}|{'text':text})
        return {'patches':result}

    def test_all_six_inputs_project_without_gold_or_answers(self):
        for label in self.variants:
            if label.endswith('_AFTER'):continue
            request=self.request(label)
            self.assertNotIn('reference',request)
            self.assertNotIn('conditional_answers',request)
            final,_=check_response(request,self.response(request))
            self.assertEqual(final['question'],self.sample['question'])
            self.assertEqual(set(final),{'context','question'})

    def test_raw_schema_and_response_boundary(self):
        request=self.request('EA_01');files={};calls=[]
        def transport(**kw):calls.append(kw);return json.dumps(self.response(request))
        result=complete('02-generation.02-generate-text.realization',request,transport=transport,save=lambda k,v:files.update({k:v}),schema_mode='native')
        self.assertEqual(result.status,'PASS');self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['response_schema'],describe('dtt.realize.response')['schema'])
        self.assertNotIn('request_schema',calls[0]);self.assertIn('02-raw-response.json',files)

    def test_no_schema_or_private_extra_stops_before_call(self):
        request=self.request('EA_01');called=[]
        def run(value):
            return complete('02-generation.02-generate-text.realization',value,transport=lambda **k:called.append(k),save=lambda *a:None,schema_mode='native')
        self.assertEqual(run(request|{'gold':'170000'}).status,'FAIL')
        with patch.dict(CONTRACTS,{k:v for k,v in CONTRACTS.items() if k!='dtt.realize.response'},clear=True):
            self.assertEqual(run(request).reason,'MISSING_LLM_SCHEMA')
        self.assertEqual(called,[])

    def test_bad_offset_before_id_extra_patch_rejected(self):
        request=self.request('EA_01')
        for change in ({'start':0},{'before':'not the source'},{'element_ids':['fake']},{'text':' unknown'}):
            response=self.response(request);response['patches'][0].update(change)
            with self.assertRaises(ValueError):check_response(request,response)
        response=self.response(request);response['patches']*=2
        with self.assertRaises(ValueError):check_response(request,response)

    def test_value_numbers_and_pair_position(self):
        request=self.request('IC_VALUE_01_BEFORE');response=self.response(request)
        for text in (' In the past quarter income was 91,000. ',' In the past quarter income was 90,000 and total 180,000. ',
                     'In the past quarter service_fee_income was 90,000. '):
            bad=deepcopy(response);bad['patches'][0]['text']=text
            with self.assertRaises(ValueError):check_response(request,bad)
        payload=read(CASE/'04-perturbation/01-plan-ic-value/04-plan-before-after/01-before/06-generation-input.json')
        pair=compose_pair(payload,response['patches'][0]['text'].strip(),'unit-pair')
        for preview in pair:
            self.assertEqual(preview['perturb_sentence'],pair[0]['perturb_sentence'])
            p=preview['patches'][0];c=preview['preview_context']
            self.assertEqual(c[:p['start']]+c[p['start']+len(p['text']):],self.sample['context'])

    def test_sources_keep_fixed_value_sentence(self):
        for label in ('IC_SOURCE_A_ONLY','IC_SOURCE_B_ONLY'):
            request=self.request(label);response=self.response(request)
            response['patches'][-1]['text']=response['patches'][-1]['text'].replace('service fee income','investment gains')
            with self.assertRaises(ValueError):check_response(request,response)

    def test_ea_removes_only_selected_input_phrase(self):
        for label,removed,preserved in [('EA_01','80,000','45,000'),('EA_02','45,000','80,000')]:
            request=self.request(label);final,patches=check_response(request,self.response(request))
            self.assertNotIn(removed,final['context']);self.assertIn(preserved,final['context'])
            self.assertIn('service fees',final['context']);self.assertIn('commissions',final['context'])
            self.assertNotIn('EA_DELETE',final['context'])
            for invalid in ('0','unreported','[EA_DELETE]', ' (missing)'):
                bad=self.response(request);bad['patches'][0]['text']=invalid
                with self.assertRaises(ValueError):check_response(request,bad)

    def test_unchecked_plan_and_base_tampering_rejected(self):
        variant=deepcopy(self.variants['IC_VALUE_01_BEFORE']);variant['plan']['base_plan_sha256']='bad'
        with self.assertRaises(ValueError):checked_plan(CASE,variant)

    def test_six_calls_seven_outputs_and_preserved_revision(self):
        with tempfile.TemporaryDirectory() as d:
            case=Path(d)/'test-0001'
            shutil.copytree(CASE,case,ignore=shutil.ignore_patterns('05-text'))
            calls=[]
            def fake_call(config,role,payload,*,save):
                calls.append(payload)
                response=self.response(payload)
                save('02-raw-response.json',{'text':json.dumps(response)})
                return StepResult('PASS','local double',response)
            with patch.object(__import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['*']), 'call',fake_call):
                result=run(case,ROOT/'config/llm.json')
                self.assertEqual(result['status'],'PASS')
                self.assertEqual(len(calls),6)
                contexts=[read(case/f'05-text/IC_VALUE_01_{side}/03-result.json') for side in ('BEFORE','AFTER')]
                self.assertEqual(contexts[0]['perturb_sentence'],contexts[1]['perturb_sentence'])
                self.assertEqual(contexts[1]['model_calls'],0)
                original=(case/'05-text/IC_VALUE_01_BEFORE/04-final-observation.json').read_bytes()
                again=run(case,ROOT/'config/llm.json','v2',list(self.variants)[:4])
                self.assertEqual(again['status'],'PASS');self.assertEqual(len(calls),9)
                self.assertEqual(original,(case/'05-text/IC_VALUE_01_BEFORE/04-final-observation.json').read_bytes())
                self.assertEqual(read(case/'05-text/IC_SOURCE_A_ONLY/latest-realization.json')['revision'],'v2')
                third=run(case,ROOT/'config/llm.json','v3',list(self.variants)[:4])
                self.assertEqual(third['status'],'PASS');self.assertEqual(len(calls),12)
                self.assertEqual(read(case/'05-text/IC_SOURCE_A_ONLY/01-generate-text/v3/previous-latest-realization.json')['revision'],'v2')
        variant=deepcopy(self.variants['IC_RELATION_01']);variant['plan']['checks']['original_preserved']=False
        with self.assertRaises(ValueError):checked_plan(CASE,variant)

if __name__=='__main__':unittest.main()
