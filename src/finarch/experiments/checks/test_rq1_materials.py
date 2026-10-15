"""Behavioral denominators and source-cohort selection must not imply semantics."""
import importlib
import unittest
m=importlib.import_module('finarch.experiments.02-analysis.01-results.rq1_materials')


def row(x,y,label=None):
    return {'x':x,'y':y,'quadrant':m.pairs.quadrant(x,y),'classification':label,
            'placement_status':'UNASSESSED','response_id':str((x,y))}


class MaterialsTest(unittest.TestCase):
    def test_unguided_and_failed_are_not_negative(self):
        self.assertEqual(m.submitted({'status':'VALID','response':{'classification':None}},'unguided','CONFLICT'),(None,'CLASSIFICATION_NOT_REQUESTED'))
        self.assertEqual(m.submitted({'status':'INVALID_RESPONSE','response':{'classification':'CONFLICT'}},'guided','CONFLICT')[0],None)
        self.assertEqual(m.submitted({'status':'VALID','response':{'classification':'ANSWERABLE'}},'guided','CONFLICT')[0],False)

    def test_joint_vs_marginal_and_fixed_denominator(self):
        rows=[row(True,True,'CONFLICT'),row(False,True,'CONFLICT'),row(True,False,'ANSWERABLE'),row(True,None)]
        ov=m.aggregate(rows,'OV');source=m.aggregate(rows,'OVS_all')
        self.assertEqual(ov['fraction'],'1/4');self.assertEqual(source['fraction'],'2/4')
        self.assertEqual(source['answerable_rate'],.25);self.assertEqual(source['unplaced'],1)
        self.assertEqual(source['quadrants']['2']['fraction'],'1/4')

    def test_source_parent_is_exact_not_any_successful_value(self):
        obs={'before':{'metric':'OV','original_item_id':'o','x':True,'y':True},
             'after':{'metric':'OV','original_item_id':'o','x':True,'y':False}}
        meta={'original_item_id':'o','matched_value_parent_ids':['after']}
        self.assertFalse(m.parent_eligibility(meta,obs)[0])
        meta['matched_value_parent_ids']=['before'];self.assertTrue(m.parent_eligibility(meta,obs)[0])
        meta['matched_value_parent_ids']=['before','after'];self.assertIsNone(m.parent_eligibility(meta,obs)[0])

    def test_parent_unknown_and_wrong_original(self):
        meta={'original_item_id':'o','matched_value_parent_ids':['p']}
        obs={'p':{'metric':'OV','original_item_id':'o','x':True,'y':None}}
        self.assertIsNone(m.parent_eligibility(meta,obs)[0])
        obs['p'].update(y=True,original_item_id='other')
        self.assertIsNone(m.parent_eligibility(meta,obs)[0])

    def test_zero_denominator_and_tbd(self):
        self.assertIsNone(m.aggregate([],'OVS')['rate'])
        self.assertEqual(m.aggregate([],'OVS')['fraction'],'0/0')
        self.assertIsNone(m.inverse_reconstruction([{'answer':42}]))

if __name__=='__main__':unittest.main()
