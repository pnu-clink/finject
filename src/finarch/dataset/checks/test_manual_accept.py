"""Manual acceptance preserves automatic failures and production validation."""
import tempfile
import unittest
from pathlib import Path
record_decision = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['record_decision']).record_decision
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
from finarch.dataset.viewer.build import collect
from finarch.dataset.viewer.server import save_generation_review


class ManualAcceptChecks(unittest.TestCase):
    def test_failed_preparation_accept_is_saved_but_does_not_bypass_generation_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder)
            case = bundle / '01-preparation/test-1'
            write(bundle / 'input-selection.json', {'cases': ['test-1']})
            write(case / '01-source/01-receive-input/01-input.json', {'question': 'Q'})
            checks = {key: True for key in ('02-review', '03-calculation', '04-graph')}
            with self.assertRaises(ValueError):
                record_decision(case, 'APPROVED', 'user', checklist=checks)
            decision = record_decision(case, 'APPROVED', 'user', checklist=checks, allow_failed_review=True)
            self.assertEqual(decision['decision'], 'APPROVED')
            self.assertIn('PREPARATION_ARTIFACT_MISSING', decision['automatic_validation_error'])
            self.assertIn('source', decision['files'])
            report = evaluate(bundle, persist=False)
            self.assertFalse(report['allow_generation'])
            self.assertEqual(len(report['invalid']), 1)
            checks['04-graph'] = False
            with self.assertRaisesRegex(ValueError, 'REVIEW_CHECKLIST_INCOMPLETE'):
                record_decision(case, 'APPROVED', 'user', checklist=checks, allow_failed_review=True)

    def test_failed_generation_accept_preserves_status_and_snapshot_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder)
            target = bundle / '02-generation/01-round/test-1/ic-value'
            result_path = target / '05-human-review/01-result.json'
            write(result_path, {'automatic_status': 'FAIL'})
            payload = {'round': '01-round', 'case': 'test-1', 'variant': 'ic-value',
                       'review': {'decision': 'APPROVED', 'reviewer': 'user',
                                  'snapshot_sha256': collect(target, allow_partial=True)['snapshot_sha256']}}
            saved = save_generation_review(bundle, payload)['decision']
            self.assertEqual(saved['decision'], 'APPROVED')
            self.assertEqual(saved['automatic_status'], 'FAIL')
            self.assertEqual(read(result_path)['automatic_status'], 'FAIL')
            payload['review']['snapshot_sha256'] = 'stale'
            with self.assertRaisesRegex(ValueError, 'REVIEW_SNAPSHOT_CHANGED'):
                save_generation_review(bundle, payload)
