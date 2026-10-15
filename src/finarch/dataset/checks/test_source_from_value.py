import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import patch
source = import_module('finarch.dataset.02-generation.01-perturbation.source_from_value')
request_from_value = source.request_from_value
check_response = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['check_response']).check_response

class SourceInheritance(unittest.TestCase):
    def test_both_conditions_preserve_existing_claims(self):
        original='Fees were 80,000 dollars.'
        added='Fees were 90,000 dollars. '
        observation={'context':added+original,'question':'What are the fees?'}
        patches=[{'start':0,'end':0,'text':added,'element_ids':['n1']}]
        with patch.object(source, 'value_base', return_value=(observation,patches,{},{})):
            for side,position in [('A',len(added)),('B',0)]:
                request,_=request_from_value(Path('.'),{'plan':{'sources':[{'side':side,'role':'analyst'}]}},
                    observation,{'code':'answer = 1'},[{'id':'n1'}],{'value':'80000'})
                self.assertEqual(request['context'],observation['context'])
                self.assertEqual(len(request['edit_slots']),1)
                slot=request['edit_slots'][0]
                self.assertEqual(slot['start'],position)
                self.assertEqual(slot['allowed_numbers'],[])
                response={'patches':[{k:slot[k] for k in ('start','end','before','element_ids')}|{'text':'According to the analyst, '}]}
                final,_=check_response(request,response)
                self.assertEqual(final['context'].replace('According to the analyst, ',''),observation['context'])
                self.assertEqual(final['question'],observation['question'])

    def test_type_two_uses_after_and_preserves_boundary(self):
        make_plan = __import__('finarch.dataset.02-generation.01-perturbation.source_plan', fromlist=['make_plan']).make_plan
        original='Fees were 80,000 dollars.'
        added=' Fees were 90,000 dollars.'
        observation={'context':original+added,'question':'What are the fees?'}
        patches=[{'start':len(original),'end':len(original),'text':added,'element_ids':['n1']}]
        plan=make_plan('base.json','a'*64,'B_ONLY')
        self.assertEqual(plan['claim_order'],['A','B'])
        with patch.object(source, 'value_base', return_value=(observation,patches,{},{})) as read_base:
            request,_=request_from_value(Path('.'),{'plan':plan},observation,{'code':'answer = 1'},[],{})
            read_base.assert_called_once_with(Path('.'),'IC_VALUE_01_AFTER')
            slot=request['edit_slots'][0]
            self.assertEqual(slot['start'],len(original)+1)
            response={'patches':[{k:slot[k] for k in ('start','end','before','element_ids')}|{'text':'According to the analyst, '}]}
            final,_=check_response(request,response)
            self.assertEqual(final['context'],original+' According to the analyst, '+added.lstrip())
        self.assertEqual(make_plan('base.json','a'*64,'A_ONLY')['base_variant'],'IC_VALUE_01_BEFORE')
