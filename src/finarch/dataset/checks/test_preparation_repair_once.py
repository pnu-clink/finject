"""Check repair bounds, provenance preservation, and approval exclusion."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
repair_case = __import__('finarch.dataset.01-preparation.repair_failed_preparation', fromlist=['repair_case']).repair_case


class RepairOnceTests(unittest.TestCase):
    def seed(self,root,accepted):
        case=root/'01-preparation/test-0001'
        sample={'context':'2','question':'Find twice the quantity.', 'reference_answer':'4'}
        write(case/'run.json',{'status':'FAIL','reason':'ORIGINAL_AUDIT_NOT_PASSED' if not accepted else 'GRAPH_UNSUPPORTED_SYNTAX'})
        for rel,obj in [('01-source/01-receive-input/01-input.json',sample),
                        ('01-source/02-record-source/01-provenance.json',{}),
                        ('01-source/03-compare-source/01-result.json',{}),
                        ('02-review-and-correct/01-round/01-LLM-audit-original/03-result.json',{'status':'PASS' if accepted else 'FAIL','findings':[]})]:write(case/rel,obj)
        if accepted:
            write(case/'02-review-and-correct/accepted-audit.json',{'status':'PASS'})
            write(case/'02-review-and-correct/accepted-input.json',sample)
        history=root/'01-preparation/repair-history/01-original';history.mkdir(parents=True)
        return case,history

    def test_unresolved_revision_is_attempted_once_and_never_approved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);case,history=self.seed(root,False)
            original=(case/'run.json').read_bytes()
            with patch.object(__import__('finarch.dataset.01-preparation.repair_failed_preparation', fromlist=['*']), 'revise',side_effect=ValueError('SOURCE_REVISION_UNRESOLVED')) as revise,patch.object(__import__('finarch.dataset.01-preparation.repair_failed_preparation', fromlist=['*']), 'calculate') as calc:
                result=repair_case(root,'test-0001',history)
            self.assertEqual(revise.call_count,1);calc.assert_not_called()
            self.assertEqual(result['status'],'FAIL')
            self.assertEqual((history/'test-0001/run.json').read_bytes(),original)
            provenance=read(case/'repair-provenance.json')
            self.assertEqual(provenance['original_files_sha256']['run.json'],hashlib.sha256(original).hexdigest())
            self.assertEqual(read(case/'05-human-review/02-record-decision/decision.json')['decision'],'REJECTED')
            with self.assertRaisesRegex(ValueError,'ALREADY_STARTED'):repair_case(root,'test-0001',history)

    def test_accepted_source_is_reused_and_failed_calculation_stays_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);case,history=self.seed(root,True)
            with patch.object(__import__('finarch.dataset.01-preparation.repair_failed_preparation', fromlist=['*']), 'revise') as revise,patch.object(__import__('finarch.dataset.01-preparation.repair_failed_preparation', fromlist=['*']), 'calculate',side_effect=ValueError('GRAPH_UNSUPPORTED_SYNTAX')) as calc:
                result=repair_case(root,'test-0001',history)
            revise.assert_not_called();self.assertEqual(calc.call_count,1)
            self.assertEqual(result['status'],'FAIL')
            self.assertFalse(read(case/'02-review-and-correct/reused-audit.json')['new_model_call'])
            self.assertEqual(read(case/'05-human-review/02-record-decision/decision.json')['decision'],'REJECTED')
