import copy
import unittest
from finarch.dataset.schemas.llm import ProgramResponseV5, check_knowledge_triggers

class Requirements(unittest.TestCase):
    def example(self):
        return {'code':'answer = 1','facts':[],'grounding':'Illustrative schema fixture',
          'external_evidence':[],'calculation_input_sources':['EXTERNAL_RULE'],
          'source_usage':[{'id':'rule','kind':'EXTERNAL_RULE','description':'Example rule',
            'fact_ids':[],'evidence_ids':[],'acquisition':'MODEL_KNOWLEDGE','source_title':None,
            'source_url':None,'locator':None,'quote':None,'applicability':'Fixture only',
            'code_lines':[1],'output_variables':['answer']}],
          'external_knowledge_requirements':[{'id':'need','tag':'EXTERNAL_RULE','source_usage_id':'rule',
            'triggers':[{'origin':'QUESTION','quote':'TEV','span':[8,11]}],
            'why_external':'The equation is not supplied','definition':'Illustrative formula',
            'formula':'answer = 1','bindings':[{'symbol':'answer','code_variable':'answer','meaning':'result'}],
            'data_requirements':[],'unit':None}]}
    def test_valid_links_and_exact_quote(self):
        p=self.example();ProgramResponseV5.model_validate(p);check_knowledge_triggers(p,'What is TEV?','')
        with self.assertRaises(ValueError):check_knowledge_triggers(p,'Different question','')
    def test_missing_field_formula_source_and_variable(self):
        p=self.example();del p['external_knowledge_requirements']
        with self.assertRaises(ValueError):ProgramResponseV5.model_validate(p)
        for key,value in [('formula',None),('source_usage_id','missing'),('tag','EXTERNAL_DATA')]:
            p=self.example();p['external_knowledge_requirements'][0][key]=value
            with self.assertRaises(ValueError):ProgramResponseV5.model_validate(p)
        p=self.example();p['external_knowledge_requirements'][0]['bindings'][0]['code_variable']='missing'
        with self.assertRaises(ValueError):ProgramResponseV5.model_validate(p)
    def test_no_external_rule_can_return_empty(self):
        p=self.example();p.update(source_usage=[],calculation_input_sources=[],external_knowledge_requirements=[])
        ProgramResponseV5.model_validate(p)
