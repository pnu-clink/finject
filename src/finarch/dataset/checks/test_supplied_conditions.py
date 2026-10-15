"""Textual conditions need exact supplied evidence, not fabricated numeric facts."""
import copy
import importlib
import unittest
from finarch.dataset.schemas.llm import ProgramResponse
verify = importlib.import_module('finarch.dataset.01-preparation.05-verification.stage')

class Conditions(unittest.TestCase):
    def test_quote_is_required_and_checked_against_input(self):
        p={'code':'answer = round(2.1)','facts':[],'grounding':'Output instruction',
           'external_evidence':[],'calculation_input_sources':['IN_CONTEXT_DATA'],
           'source_usage':[{'id':'instruction','kind':'IN_CONTEXT_DATA','description':'Round output',
           'fact_ids':[],'evidence_ids':[],'acquisition':'SUPPLIED','source_title':None,
           'source_url':None,'locator':None,'quote':'Round to integer.','applicability':'Final output',
           'code_lines':[1],'output_variables':['answer']}]}
        class Sink:
            def save(self,*args): pass
        ProgramResponse.model_validate(p)
        payload={'program':p,'sample':{'question':'Round to integer.','context':''}}
        self.assertEqual(verify.pp03_check_provenance_structure(Sink(),payload)['status'],'PASS')
        payload['sample']['question']='Do not round.'
        self.assertEqual(verify.pp03_check_provenance_structure(Sink(),payload)['status'],'FAIL')
        bad=copy.deepcopy(p);bad['source_usage'][0]['quote']=None
        with self.assertRaises(ValueError):ProgramResponse.model_validate(bad)
