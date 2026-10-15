"""Offline checks for review retries, nonblocking target failures, and A04 provenance."""
import copy
from importlib import import_module
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

reviews = import_module('finarch.experiments.02-analysis.02-comparison.response_assessments')
failures = import_module('finarch.experiments.02-analysis.failure_analysis')
backend = import_module('finarch.experiments.02-analysis.llm_backend')
store = reviews.store
fixture = import_module('finarch.experiments.checks.test_analysis_pipeline')


class ReviewGateTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / '02_analysis/02_comparison'
        example = fixture.ResponseAssessmentContractTest()
        example.setUp()
        self.req = copy.deepcopy(example.req)
        self.req.update(trial_id='judge', prompt='Offline fixture.', model='gpt-6.1-sol',
                        reasoning_effort='low', item_id='case')
        for row in self.req['input']['responses']:
            row.update(case='case', model='target', prompt_condition='guided', reasoning='off')
        store.write(self.root / 'state.json', {})

    def save_failure(self):
        store.write(self.folder / 'calls/judge/attempt-001/request.json', self.req)
        store.write(self.folder / 'calls/judge/attempt-001/result.json',
                    {'status': 'INVALID_RESPONSE', 'error': 'ASSESSMENT_QUOTE_NOT_IN_SOURCE'})

    def test_unreviewed_and_failed_block_but_unavailable_and_source_missing_do_not(self):
        for status in ('NOT_REVIEWED', 'REVIEW_FAILED', 'NOT_REVIEWABLE', 'SOURCE_MISSING'):
            summary = {'overall': {'review_status': {'COMPLETED': 7, status: 1}}}
            gate = reviews.gate(summary)
            self.assertEqual(gate['blocked'], status in reviews.RECHECK_STATUSES)
            state = reviews.apply_gate({'status': 'PARTIAL'}, summary)
            self.assertEqual(state['status'], 'BLOCKED' if gate['blocked'] else 'COLLECTED')
            self.assertEqual(state['model_call_status'], 'PARTIAL')
        self.assertEqual(reviews.apply_gate({'status': 'PAUSED_BY_USER'}, summary)['status'], 'PAUSED_BY_USER')

    def test_failed_judge_does_not_change_invalid_target_into_review_failed(self):
        self.req['input']['responses'][1]['status'] = 'INVALID_RESPONSE'
        self.save_failure()
        summary = reviews.collect(self.root, [self.req], backend)
        self.assertEqual(summary['overall']['review_status'], {'NOT_REVIEWABLE': 1})
        self.assertFalse(summary['review_gate']['blocked'])
        self.assertEqual(reviews.recheck_trials([self.req], backend, self.folder), set())
        original = self.req['input']['responses'][1]['response']
        detail = failures.build(self.root, [self.req], backend)
        row = store.read(self.root / detail['records'][0]['page'])['records'][0]
        self.assertEqual(row['target_response'], original)
        self.assertEqual(row['public_input'], self.req['input']['inputs']['v']['public'])
        self.assertFalse(row['recheck_required'])
        self.assertEqual(row['judge_error'], 'ASSESSMENT_QUOTE_NOT_IN_SOURCE')
        self.assertIn('not structurally valid', row['decision_grounding']['reason'])

    def test_mixed_failed_case_retries_reviewable_target_without_losing_unavailable_row(self):
        row = self.req['input']['responses'][1]
        self.req['input']['responses'].append(copy.deepcopy(row) | {'response_id': 'invalid', 'status': 'INVALID_RESPONSE'})
        self.save_failure()
        summary = reviews.collect(self.root, [self.req], backend)
        self.assertEqual(summary['overall']['review_status'], {'REVIEW_FAILED': 1, 'NOT_REVIEWABLE': 1})
        self.assertTrue(summary['review_gate']['blocked'])
        self.assertEqual(reviews.recheck_trials([self.req], backend, self.folder), {'judge'})
        details = failures.build(self.root, [self.req], backend)
        self.assertEqual(details['review_gate']['recheck_required'], 1)
        self.assertEqual(details['record_count'], 2)

    def test_missing_judge_review_is_not_reviewed_and_selected_for_execution(self):
        summary = reviews.collect(self.root, [self.req], backend)
        self.assertEqual(summary['overall']['review_status'], {'NOT_REVIEWED': 1})
        self.assertEqual(reviews.recheck_trials([self.req], backend, self.folder), {'judge'})

    def test_saved_target_failure_does_not_call_codex_again(self):
        self.req['input']['responses'][1]['status'] = 'INVALID_RESPONSE'
        self.save_failure()
        with patch.object(backend.analysis_config, 'authorized_unknown_delivery_retries', return_value=set()), \
             patch.object(backend.codex, 'call', side_effect=AssertionError('Unavailable target was retried')):
            state = backend.run_codex(self.root, self.folder, [self.req], {'technical_retry_limit': 3})
        self.assertEqual(state['status'], 'PARTIAL')
        self.assertEqual(len(backend.attempts(self.folder, self.req)), 1)

    def test_missing_source_is_distinct_from_failed_judge(self):
        self.req['input']['inputs']['v']['public']['context'] = ''
        self.save_failure()
        summary = reviews.collect(self.root, [self.req], backend)
        self.assertEqual(summary['overall']['review_status'], {'SOURCE_MISSING': 1})
        self.assertFalse(summary['review_gate']['blocked'])


if __name__ == '__main__':
    unittest.main()
