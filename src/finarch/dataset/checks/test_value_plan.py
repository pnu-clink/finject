import unittest
from copy import deepcopy
branch_program = __import__('finarch.dataset.02-generation.01-perturbation.value_plan', fromlist=['branch_program']).branch_program

class ValuePlanChecks(unittest.TestCase):
    def test_alternative_does_not_rewrite_original_or_unrelated_fact(self):
        original={'code':'answer = fact("a") + fact("b")','facts':{'a':{'span':[0,2],'text':'80','value':'80','unit':'USD'},'b':{'span':[3,5],'text':'20','value':'20','unit':'USD'}}}
        snapshot=deepcopy(original);b=branch_program(original,'80 20','a','90')
        self.assertEqual(original,snapshot)
        self.assertEqual(b['code'],original['code'])
        self.assertEqual(b['facts']['b'],original['facts']['b'])
        self.assertEqual(b['context'][:5],'80 20')
        start,end=b['facts']['a']['span'];self.assertEqual(b['context'][start:end],'90')
    def test_invalid_alternatives_are_rejected(self):
        p={'facts':{'a':{'value':'80'}}}
        for value in ['80','NaN','Infinity']:
            with self.subTest(value=value),self.assertRaises(ValueError):branch_program(p,'','a',value)
        with self.assertRaisesRegex(ValueError,'UNKNOWN_FACT'):branch_program(p,'','missing','90')
