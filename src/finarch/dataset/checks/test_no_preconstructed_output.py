"""Offline regression checks; no model calls or historical run files."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from importlib import import_module
production_plan = import_module("finarch.dataset.02-generation.01-perturbation.production_plan")

from finarch.shared.providers.input_policy import validate_model_input
realization_request = __import__('finarch.dataset.02-generation.01-perturbation.production_plan', fromlist=['realization_request']).realization_request


class NoPreconstructedOutput(unittest.TestCase):
    def test_reject_fixed_text_and_answers(self):
        for payload in ({'reference': {'answer':'42'}},
                        {'edit_slots':[{'exact_text':''}]},
                        {'edit_slots':[{'required_prefix':'A prescribed sentence'}]},
                        {'intent':{'expected_judgment':'PASS'}},
                        {'relation':{'draft_sentence':'A prescribed relation'}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_model_input('02-generation.02-generate-text.realization',payload)

    def test_all_types_construct_without_draft(self):
        context='The loan is 100 dollars.'
        fact={'span':[12,15],'text':'100','value':'100','unit':'USD'}
        spec={'target':'principal','alternative':'110','anchor':[0,len(context)],
              'relation':{'target':'principal','operand':'principal','factor':'2','scope':{}},
              'ea':{'principal':{'span':[0,len(context)]}}}
        program={'facts':{'principal':fact},'code':'principal = fact("principal")\nanswer = principal'}
        node={'id':'n1','kind':'input','fact_id':'principal'}
        graph={'nodes':[node]}
        variants=[('IC_VALUE',{'perturb_position':'before'}),
                  ('IC_SOURCE',{'sources':[{'side':'A','role':'reviewer'}]}),
                  ('IC_SOURCE',{'sources':[{'side':'B','role':'reviewer'}]}),
                  ('IC_RELATION',{'branches':{'B':{'relation_node_ids':['n1']}},
                                  'graphs':{'B':graph},'relation':{'properties':{'operator':'multiply','parameter':'2'}}}),
                  ('EA',{'fact_id':'principal'})]
        with patch.object(production_plan,'read',return_value=spec), patch.object(production_plan,'source_program',return_value=program):
            for axis,plan in variants:
                with self.subTest(axis=axis,plan=plan):
                    request=realization_request(Path('/unused'),{'axis':axis,'plan':plan},
                        {'context':context,'question':'What is the principal?'},program,graph,{},
                        {'graph_binding':{'missing_node_ids':['n1']},'intermediate':{'context':'The loan is [EA_DELETE:principal] dollars.'}},None)
                    validate_model_input('02-generation.02-generate-text.realization',request)
                    for slot in request['edit_slots']:
                        self.assertIsNone(slot['exact_text'])
                        self.assertEqual(slot['required_prefix'],'')
                    self.assertNotIn('expressing exactly',json.dumps(request))

    def test_paragraph_separator_is_not_preconstructed_wording(self):
        for prefix in ('', '\n\n', '\n\n\n', ' '):
            with self.subTest(prefix=repr(prefix)):
                validate_model_input('02-generation.02-generate-text.realization',
                    {'edit_slots': [{'required_prefix': prefix, 'kind': 'RELATION'}]})
        for prefix in ('\n\nA prescribed sentence', 2):
            with self.subTest(prefix=prefix), self.assertRaisesRegex(ValueError, 'FIXED_RESPONSE_PREFIX_FORBIDDEN'):
                validate_model_input('02-generation.02-generate-text.realization',
                    {'edit_slots': [{'required_prefix': prefix}]})

    def test_transport_retains_input_policy_failure_without_model_call(self):
        from finarch.shared.providers.cli import CLITransport, CLIError
        saved = {}
        transport = CLITransport('/unused/config.json', lambda path, value: saved.update({path: value}))
        with self.assertRaisesRegex(CLIError, 'FIXED_RESPONSE_PREFIX_FORBIDDEN'):
            transport(role='02-generation.02-generate-text.realization',
                payload={'edit_slots': [{'required_prefix': 'A prescribed sentence'}]},
                response_schema={}, schema_mode='native')
        self.assertEqual(saved['03-result/failure.json']['reason'], 'FIXED_RESPONSE_PREFIX_FORBIDDEN')

    def test_pot_schema_excludes_reference(self):
        from finarch.dataset.schemas.validation import validate
        request={'context':'Source document', 'question':'Question', 'provider_record':{},
                 'reference_answer_type':'integer', 'reference_precision':0,
                 'answer_metadata':{'scale':None,'negative':False}}
        validate('pot.author.request',request)
        with self.assertRaises(Exception):
            validate('pot.author.request',{**request,'reference':{'answer':'42','answer_type':'integer','precision':0}})



if __name__=='__main__':
    unittest.main()
