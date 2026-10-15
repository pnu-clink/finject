"""Offline verification verdict and generation diagnosis contracts."""
import importlib
import unittest
from pydantic import ValidationError
from finarch.dataset.schemas.verification import VerificationResponse, CRITERIA

p=importlib.import_module('finarch.dataset.01-preparation.05-verification.stage')
g=importlib.import_module('finarch.dataset.02-generation.04-exception-handler.stage')

class VerificationChecks(unittest.TestCase):
    def test_missing_criterion_fails_schema(self):
        with self.assertRaises(ValidationError):VerificationResponse(findings=[])

    def test_unknown_is_not_pass(self):
        class Context:
            def save(self,path,value):self.saved=value
        ctx=Context()
        with self.assertRaisesRegex(ValueError,'UNKNOWN'):
            p.pp08_record_verdict(ctx,{'findings':[{'judgment':'UNKNOWN'}]}, {}, {'python': {'status': 'PASS'}})
        self.assertEqual(ctx.saved['status'],'FAIL')

    def test_complete_pass_preserves_findings(self):
        response=VerificationResponse(findings=[{'criterion':c,'judgment':'PASS','reason':'Checked','evidence':['code line 1']} for c in CRITERIA], cohort='INTERNAL', cohort_reason='Only supplied facts and arithmetic are needed.', required_external_sources=[]).model_dump()
        class Context:
            def save(self,path,value):self.saved=value
        result={};p.pp08_record_verdict(Context(),response,result,{'python': {'status': 'PASS'}})
        self.assertEqual(result['status'],'PASS')

    def test_generation_error_keeps_variant_evidence(self):
        request=g.gg01_collect_error({'round':'02-round','restart':'03-validation','reason':'Wrong scope','audit':{'status':'FAIL'},'generation_response':{'patches':[]}},'case1')
        self.assertEqual(request['failed_step'],'03-validation')
        self.assertEqual(request['source_round'],'02-round')
        self.assertEqual(request['evidence']['audit']['status'],'FAIL')

if __name__=='__main__':unittest.main()
