import unittest
make_plan = __import__('finarch.dataset.02-generation.01-perturbation.source_plan', fromlist=['make_plan']).make_plan
check_base = __import__('finarch.dataset.02-generation.01-perturbation.source_plan', fromlist=['check_base']).check_base
from finarch.dataset.schemas.source_plan import SourcePlan

class SourcePlanChecks(unittest.TestCase):
    def test_only_assigned_side_has_source(self):
        plans=[make_plan('base','a'*64,c) for c in ['A_ONLY','B_ONLY']]
        for p,side in zip(plans,'AB'):
            self.assertEqual(len(p['sources']),1)
            self.assertEqual(p['sources'][0]['side'],side)
            self.assertEqual(p['sources'][0]['intended_reliability'],'H')
            self.assertEqual(p['claim_order'],['B','A'] if side=='A' else ['A','B'])
            self.assertEqual(p['base_plan_sha256'],'a'*64)
            self.assertNotIn('graphs',p)
        self.assertEqual({k:v for k,v in plans[0]['sources'][0].items() if k!='side'}, {k:v for k,v in plans[1]['sources'][0].items() if k!='side'})
    def test_wrong_side_extra_source_and_low_source_fail(self):
        for mutation in ['side','extra','low']:
            p=make_plan('base','a'*64,'A_ONLY')
            if mutation=='side':p['sources'][0]['side']='B'
            if mutation=='extra':p['sources'].append(dict(p['sources'][0]))
            if mutation=='low':p['sources'][0]['intended_reliability']='L'
            with self.assertRaises(ValueError):SourcePlan.model_validate(p)
    def test_failed_or_equal_answer_base_is_blocked(self):
        for base in [{},{'axis':'IC_VALUE','checks':{}},{'axis':'IC_VALUE','checks':{k:True for k in ['same_code','original_preserved','python_graph_equal','different_final_answers']},'answers':{'A':{'computed':'1'},'B':{'computed':'1'}}}]:
            with self.assertRaises(ValueError):check_base(base)
