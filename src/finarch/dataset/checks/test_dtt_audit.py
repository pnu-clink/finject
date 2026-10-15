"""Scoped audit gates and explicit counterexamples; no live model calls."""
from copy import deepcopy
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from finarch.dataset.shared.review.dtt_audit import prepare, evaluate, evaluate_saved, adversarial_requests, run
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
from finarch.dataset.schemas.llm import AUDIT_CRITERIA
from finarch.dataset.schemas.registry import CONTRACTS, describe
from finarch.shared.providers.structured import complete
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
StepStopped = __import__('finarch.dataset.90-operations.staging', fromlist=['StepStopped']).StepStopped

ROOT=(Path(__file__).resolve().parent / '../../../..').resolve()
CASE=ROOT/'reports/run/first-10-pot-validated-v3/test-0001'


def response_for(request):
    return {'findings':[{'criterion':c,'judgment':'PASS','reason':''} for c in AUDIT_CRITERIA]}


class AuditChecks(unittest.TestCase):
    def request(self,label='IC_VALUE_01_BEFORE'):return prepare(CASE,label)[0]

    def test_saved_eight_inputs_and_question_preservation(self):
        for label in ['ANSWER']+[v['label'] for v in read(CASE/'04-perturbation/05-list-candidates/03-result.json')]:
            request,binding=prepare(CASE,label)
            self.assertEqual(request['question'],read(CASE/'00-data-preparation/01-select-input/01-input.json')['question'])
            self.assertNotIn('reference_answer',request);self.assertNotIn('conditional_answers',request)
            self.assertEqual(evaluate(request,response_for(request))['status'],'PASS')
            self.assertTrue(binding['observation_sha256'])

    def test_schema_sent_and_raw_preserved_before_grounding(self):
        request=self.request();files={};calls=[]
        def transport(**kw):calls.append(kw);return json.dumps(response_for(request))
        result=complete('shared.01-02.02-03.review-and-validation',request,transport=transport,save=lambda k,v:files.update({k:v}),schema_mode='native')
        self.assertEqual(result.status,'PASS');self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['response_schema'],describe('dtt.audit.response')['schema'])
        self.assertNotIn('request_schema',calls[0]);self.assertIn('02-raw-response.json',files)

    def test_missing_schema_private_extra_never_calls_model(self):
        request=self.request();calls=[]
        def go(p):return complete('shared.01-02.02-03.review-and-validation',p,transport=lambda **kw:calls.append(kw),save=lambda *a:None,schema_mode='native')
        self.assertEqual(go(request|{'reference_answer':'170000'}).status,'FAIL')
        with patch.dict(CONTRACTS,{k:v for k,v in CONTRACTS.items() if k!='dtt.audit.response'},clear=True):
            self.assertEqual(go(request).reason,'MISSING_LLM_SCHEMA')
        self.assertEqual(calls,[])

    def test_invalid_shape_or_unexplained_failure_is_rejected(self):
        request=self.request()
        for kind in ('missing','duplicate','quote','na','empty_reason','old_state'):
            r=deepcopy(response_for(request))
            if kind=='missing':r['findings'].pop()
            if kind=='duplicate':r['findings'][1]=r['findings'][0]
            if kind=='quote':r['findings'][0]['evidence']=[{'field':'context','quote':'invented'}]
            if kind=='na':r['findings'][0]['judgment']='NOT_APPLICABLE'
            if kind=='empty_reason':r['findings'][0]['judgment']='FAIL'
            if kind=='old_state':r['observed_state']='CONFLICT'
            with self.subTest(kind=kind),self.assertRaises(ValueError):evaluate(request,r)

    def test_semantic_failure_or_unknown_is_blocked(self):
        request=self.request()
        for judgment,expected in [('FAIL','FAIL'),('UNKNOWN','NOT_EVALUATED')]:
            r=response_for(request);r['findings'][2].update(judgment=judgment,reason='문장 결함 또는 불확실')
            self.assertEqual(evaluate(request,r)['status'],expected)
        r['findings'][0].update(judgment='FAIL',reason='다른 기간의 금액')
        self.assertEqual(evaluate(request,r)['status'],'FAIL')

    def test_source_assignment_input_preserved_without_second_gate(self):
        request=self.request('IC_SOURCE_A_ONLY');r=response_for(request)
        report=evaluate(request,r)
        self.assertEqual(report['status'],'PASS');self.assertNotIn('observed_state',report)
        rows=request['intent']['source_assignment_by_value']
        self.assertEqual([(x['side'],x['value'],x['source'] is not None) for x in rows],
                         [('A','80000',True),('B','90000',False)])

    def test_historical_audits_keep_old_decisions(self):
        # All saved valid responses are replayed under their historical version.
        count=0
        for pointer in CASE.parent.glob('test-*/05-text/*/latest-audit.json'):
            case=pointer.parents[2];folder=case/read(pointer)['stage']
            report=read(folder/'03-result.json')
            if report.get('failure_kind')=='AUDIT_RESPONSE_INVALID':continue
            raw=read(folder/'audit/02-raw-response.json')
            if isinstance(raw,dict) and set(raw)=={'text'}:raw=json.loads(raw['text'])
            self.assertEqual(evaluate_saved(read(folder/'01-input.json'),raw,report)['status'],report['status'])
            count+=1
        self.assertGreater(count,40)
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_AUDIT_VERSION'):
            evaluate_saved(self.request(),response_for(self.request()),{'audit_version':99})

    def test_ea_pass_never_proves_nonrecoverability(self):
        request=self.request('EA_01');report=evaluate(request,response_for(request))
        self.assertEqual(report['full_EA_verdict'],'NOT_EVALUATED')
        self.assertEqual(report['recovery_review'],'DEFERRED_BY_USER')
        self.assertEqual(report['stage18'],'NOT_RUN')
        other=self.request('EA_02')
        self.assertEqual(other['intent']['authorized_edit_slots'][0]['before'],' reaching 45,000')

    def test_selected_retry_has_one_call_and_preserves_other_audits(self):
        with tempfile.TemporaryDirectory() as d:
            case=Path(d)/'test-0001';shutil.copytree(CASE,case);calls=[]
            pointer=case/'05-text/ANSWER/latest-audit.json'
            old=pointer.read_bytes() if pointer.exists() else None
            def local(config,role,payload,*,save):
                calls.append(role);save('02-raw-response.json',{'text':json.dumps(response_for(payload))});return StepResult('PASS','local only',response_for(payload))
            with patch('finarch.dataset.shared.review.dtt_audit.call',local):
                result=run(case,ROOT/'config/llm.json','local-selected',labels=['EA_02'])
            self.assertEqual(calls,['shared.01-02.02-03.review-and-validation']);self.assertEqual(len(result['results']),1)
            self.assertEqual(pointer.read_bytes() if pointer.exists() else None,old)
            build = __import__('finarch.dataset.02-generation.05-human-review.human_review', fromlist=['build']).build
            review=build(case,'compact-local')
            self.assertGreater(review['ready'],0)
            item=read(case/'06-human-review/01-collect-results/compact-local/EA_02.json')
            self.assertEqual(item['status'],'AWAITING_HUMAN')
            self.assertEqual(item['semantic_audit']['audit_version'],3)

    def test_final_tampering_and_gold_exclusion_fail_before_calls(self):
        with self.assertRaises(StepStopped):prepare(CASE.parent/'test-0008','ANSWER')
        with tempfile.TemporaryDirectory() as d:
            case=Path(d)/'test-0001';shutil.copytree(CASE,case)
            p=case/'05-text/EA_01/01-generate-text/v3/04-final-observation.json';v=read(p)
            v['context']+=' 80,000';p.write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,'FINAL_TEXT_PATCH_MISMATCH'):prepare(case,'EA_01')

    def test_eight_actual_jobs_two_error_fixtures_and_no_answer_calls(self):
        with tempfile.TemporaryDirectory() as d:
            case=Path(d)/'test-0001';shutil.copytree(CASE,case);calls=[]
            def local(config,role,payload,*,save):
                calls.append(role);r=response_for(payload)
                if 'next quarter' in payload['context']:r['findings'][0].update(judgment='FAIL',reason='다른 기간')
                if payload['axis']=='IC_SOURCE' and payload['intent']['source_condition']=='A_ONLY' and '90000 dollars for the same bank, according' in payload['context']:
                    r['findings'][0].update(judgment='FAIL',reason='출처가 다른 값에 배정됨')
                save('02-raw-response.json',{'text':json.dumps(r)})
                return StepResult('PASS','local control test only',r)
            with patch('finarch.dataset.shared.review.dtt_audit.call',local):
                summary=run(case,ROOT/'config/llm.json','local-test',True)
            self.assertEqual(calls,['shared.01-02.02-03.review-and-validation']*10)
            self.assertEqual(len(summary['results']),8);self.assertTrue(all(c['caught'] for c in summary['counterexamples']))
            self.assertFalse((case/'05-text/wrong-period/latest-audit.json').exists())
            self.assertEqual(read(case/'05-text/EA_01/latest-audit.json')['stage16_ref'],'05-text/EA_01/01-generate-text/v3')
            self.assertEqual(summary['stage18'],'NOT_RUN')

if __name__=='__main__':unittest.main()
