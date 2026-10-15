"""Offline regressions for the agreed preparation flow."""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from finarch.dataset.schemas.verification import CRITERIA

verify = importlib.import_module('finarch.dataset.01-preparation.05-verification.stage')
review = importlib.import_module('finarch.dataset.01-preparation.02-review.stage')
calculation = importlib.import_module('finarch.dataset.01-preparation.03-calculation.stage')

class Context:
    def __init__(self): self.saved = {}
    def save(self, path, value): self.saved[path] = value

class PreparationFlowUpdate(unittest.TestCase):
    def test_llm_pass_cannot_override_python_fail(self):
        ctx = Context()
        response = {'cohort': 'INTERNAL', 'findings': [{'criterion': c, 'judgment': 'PASS', 'reason': 'Checked',
                                'evidence': ['code line 1']} for c in CRITERIA]}
        with self.assertRaisesRegex(ValueError, 'VERIFICATION_FAILED'):
            verify.pp08_record_verdict(ctx, response, {}, {'answer': {'status': 'FAIL'}})
        self.assertEqual(ctx.saved['05-verification/08-record-verdict/01-result.json']['status'], 'FAIL')

    def test_gold_mismatch_does_not_repair_pot(self):
        sample = {'reference_answer': '10', 'reference_answer_type': 'integer', 'reference_precision': 0}
        returned = calculation.pp05_compare_answer(Context(), None, sample, {}, {'exact_value': '11'}, {}, '03-calculation')
        self.assertFalse(returned[-1]['matches'])
        self.assertIs(returned[0], sample)

    def test_review_calls_once_without_inner_loop(self):
        with patch.object(review, 'pp01_read_input', return_value={}), \
             patch.object(review, 'pp02_LLM_review_original', return_value={}) as model, \
             patch.object(review, 'pp03_record_result', return_value=({}, {'status': 'FAIL'})):
            self.assertEqual(review.run(Context(), None, {}, maximum=3)[1]['status'], 'FAIL')
            model.assert_called_once()

    def test_invalid_llm_response_is_recorded(self):
        ctx = Context()
        with self.assertRaises(ValueError):
            verify.pp07_check_verification_response(ctx, {'findings': []})
        self.assertEqual(ctx.saved['05-verification/07-check-verification-response/01-result.json']['status'], 'FAIL')

if __name__ == '__main__': unittest.main()
