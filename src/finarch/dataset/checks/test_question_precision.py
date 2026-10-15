"""Offline checks of the narrowly authorized question precision correction."""
import importlib
import unittest
from unittest.mock import patch, MagicMock

m=importlib.import_module('finarch.dataset.01-preparation.02-review.question_precision')
s=importlib.import_module('finarch.dataset.01-preparation.02-review.stage')
class PrecisionChecks(unittest.TestCase):
    def sample(self,q,gold='12.340',precision=3):
        return {'question':q,'context':'Revenue is $123.45.','reference_answer':gold,'reference_precision':precision,'reference_answer_type':'float'}
    def test_count_only_and_preserve_original(self):
        source=self.sample('For 2019, round the answer to 2 decimal places.')
        working,report=m.align(source)
        self.assertEqual(working['question'],'For 2019, round the answer to 3 decimal places.')
        self.assertEqual(source['question'],'For 2019, round the answer to 2 decimal places.')
        self.assertEqual(working['context'],source['context']);self.assertEqual(working['reference_answer'],'12.340')
        self.assertEqual(len(report['edits']),1)
    def test_words(self):
        self.assertIn('three decimal places',m.align(self.sample('Answer with two decimal places.'))[0]['question'])
    def test_no_instruction_or_significant_figures(self):
        for q in ['What is 2 plus 3?','Round to 2 significant figures.','Round to the nearest dollar.']:
            self.assertEqual(m.align(self.sample(q))[0]['question'],q)
    def test_matching_and_idempotent(self):
        a=self.sample('Round to 3 decimal places.');b,r=m.align(a)
        self.assertEqual(a,b);self.assertEqual(r['edits'],[])
    def test_invalid_metadata_blocked(self):
        with self.assertRaisesRegex(ValueError,'REFERENCE_PRECISION_MISMATCH'):
            m.align(self.sample('Round to 2 decimal places.','12.3',3))
    def test_qca_metadata_sent_and_llm_edit_reaudited(self):
        revisions=importlib.import_module('finarch.dataset.01-preparation.02-review.revisions')
        source=self.sample('Round to 2 decimal places.')
        response={'disposition':'REVISED','reason':'Precision alignment','edits':[{'field':'question','start':9,'end':10,'before':'2','text':'3','reason':'Match precision'}]}
        ctx=MagicMock()
        with patch.object(s,'audit_one',return_value={'status':'PASS'}) as audit, patch.object(revisions,'invoke',return_value=response) as invoke, patch.object(revisions,'audit_one',return_value={'status':'PASS'}) as recheck:
            working,result=s.run(ctx,{},source,0)
        request=audit.call_args.args[2]
        self.assertEqual(request['question'],source['question'])
        self.assertEqual(request['reference_answer'],'12.340')
        self.assertEqual(request['reference_answer_type'],'float')
        self.assertEqual(invoke.call_args.args[4]['reference_precision'],3)
        self.assertIn('3 decimal places',recheck.call_args.args[2]['question'])
        self.assertEqual(result['status'],'PASS')
    def test_other_numeric_changes_rejected(self):
        revisions=importlib.import_module('finarch.dataset.01-preparation.02-review.revisions')
        source=self.sample('For 2019, round to 2 decimal places.')
        with self.assertRaises(ValueError):
            revisions.apply_revision(source,{'disposition':'REVISED','edits':[{'field':'question','start':4,'end':8,'before':'2019','text':'2020'}]})
if __name__=='__main__':unittest.main()
