"""Verify retry diagnostics offline; never start Codex or alter frozen evidence."""
import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

feedback = importlib.import_module('finarch.experiments.02-analysis.retry_feedback')
codex = importlib.import_module('finarch.experiments.02-analysis.backends.codex')
fixture = importlib.import_module('finarch.experiments.checks.test_analysis_pipeline')
store = feedback.store


class RetryFeedbackTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / 'calls' / 'judge'
        self.next = self.folder / 'attempt-002'
        example = fixture.ResponseAssessmentContractTest()
        example.setUp()
        self.req = copy.deepcopy(example.req) | {'trial_id': 'judge', 'item_id': 'case',
            'model': 'gpt-6.1-sol', 'reasoning_effort': 'low', 'prompt': 'Analyze the supplied data.'}
        self.req['input']['responses'][1]['response']['explanation'] = 'Margin = ($373 ÷ $4,999.5) × 100.'
        self.value = fixture.fake_response(self.req)
        self.value['response_assessments'][0]['decision_grounding']['citations'][1]['quote'] = '(373 ÷ 4,999.5)'
        self.errors = codex.contract.validate_response(self.value, self.req)
        self.assertEqual(self.errors[0]['message'], 'ASSESSMENT_QUOTE_NOT_IN_SOURCE')

    def save(self, status='INVALID_RESPONSE', number=1):
        path = self.folder / f'attempt-{number:03d}'
        store.write(path / 'request.json', self.req)
        store.write(path / 'result.json', {'status': status, 'response': self.value, 'schema_errors': self.errors})
        return path

    def test_exact_response_source_and_field_are_explained(self):
        previous = self.save()
        before = {p.name: p.read_bytes() for p in previous.iterdir()}
        req_before = copy.deepcopy(self.req)
        hint = feedback.build(self.req, self.next)
        issue = hint['citation_errors'][0]
        self.assertEqual(issue['path'], 'response_assessments[0].decision_grounding.citations[1]')
        self.assertEqual(issue['response_id'], 'variant')
        self.assertEqual(issue['previous_quote']['text'], '(373 ÷ 4,999.5)')
        self.assertIn('$373', issue['saved_source']['text'])
        self.assertEqual(hint['validation_errors'], self.errors)
        self.assertEqual(hint['previous_response'], self.value)
        self.assertEqual(hint['previous_response']['response_assessments'][0]['decision_grounding']['verdict'],
                         self.value['response_assessments'][0]['decision_grounding']['verdict'])
        self.assertEqual(self.req, req_before)
        self.assertEqual(before, {p.name: p.read_bytes() for p in previous.iterdir()})

    def test_first_attempt_and_valid_previous_have_no_hint(self):
        self.assertIsNone(feedback.build(self.req, self.folder / 'attempt-001'))
        self.save('VALID')
        self.assertIsNone(feedback.build(self.req, self.next))
        self.assertEqual(feedback.prompt(self.req['prompt'], None), self.req['prompt'])

    def test_observation_paraphrase_points_to_exact_saved_response(self):
        row = self.req['input']['responses'][1]
        self.value['observations'] = [{'excerpts': [{'response_id': row['response_id'],
            'field': 'explanation', 'quote': 'The margin is 373 divided by 4999.5.'}]}]
        before = copy.deepcopy(self.value)
        errors = feedback.citation_errors(self.value, self.req)
        issue = next(e for e in errors if e['error'] == 'EXCERPT_NOT_IN_SAVED_RESPONSE')
        self.assertEqual(issue['path'], 'observations[0].excerpts[0]')
        self.assertEqual(issue['saved_sources'][0]['text'], row['response']['explanation'])
        self.assertEqual(self.value, before)
        self.value['observations'][0]['excerpts'][0]['quote'] = row['response']['explanation']
        self.assertFalse(any(e['error'] == 'EXCERPT_NOT_IN_SAVED_RESPONSE'
                             for e in feedback.citation_errors(self.value, self.req)))

    def test_latest_attempt_does_not_reuse_stale_validation_error(self):
        self.save()
        self.save('UNKNOWN_DELIVERY', 2)
        self.assertIsNone(feedback.build(self.req, self.folder / 'attempt-003'))

    def test_changed_request_is_rejected(self):
        self.save()
        changed = copy.deepcopy(self.req)
        changed['prompt'] = 'Changed frozen prompt.'
        with self.assertRaisesRegex(ValueError, 'ANALYSIS_REQUEST_CHANGED_AFTER_EXECUTION'):
            feedback.build(changed, self.next)

    def test_malformed_response_and_large_feedback_are_bounded(self):
        self.value['response_assessments'][0]['decision_grounding']['citations'][0]['source'] = []
        self.errors = [{'path': 'x' * 10000, 'rule': 'SCHEMA', 'message': 'bad' * 10000}] * 40
        self.save()
        hint = feedback.build(self.req, self.next)
        diagnostics = {k: v for k, v in hint.items() if not k.startswith('previous_response')}
        self.assertLessEqual(len(json.dumps(diagnostics, ensure_ascii=True)), feedback.MAX_FEEDBACK)
        self.assertEqual(hint['previous_response'], self.value)
        self.assertGreater(hint['validation_errors_omitted'], 0)

    def test_evidence_index_failure_is_located(self):
        citation = self.value['response_assessments'][0]['decision_grounding']['citations'][1]
        citation.update(source='evidence', evidence_index=5)
        self.save()
        hint = feedback.build(self.req, self.next)
        self.assertEqual(hint['citation_errors'][0]['error'], 'ASSESSMENT_EVIDENCE_INDEX_INVALID')
        self.assertTrue(hint['citation_errors'][0]['saved_source']['source_missing'])

    def test_research_schema_error_is_available_without_a02_fields(self):
        self.req['stage'] = '03_research'
        self.value = {}
        self.errors = [{'path': 'findings[0].interpretation_ids', 'rule': 'ANALYSIS_CONTRACT',
                        'message': 'UNKNOWN_INTERPRETATION_REFERENCE'}]
        self.save()
        hint = feedback.build(self.req, self.next)
        self.assertEqual(hint['validation_errors'], self.errors)
        self.assertEqual(hint['citation_errors'], [])

    def test_complete_prior_response_survives_diagnostic_limit(self):
        self.value['coverage_note'] = 'Unchanged prior analysis. ' * 2000
        self.save()
        hint = feedback.build(self.req, self.next)
        self.assertEqual(hint['previous_response'], self.value)
        self.assertGreater(len(json.dumps(hint['previous_response'])), feedback.MAX_FEEDBACK)
        effective = feedback.prompt(self.req['prompt'], hint)
        payload = json.loads(effective.split('Previous response and additional validation information:\n', 1)[1])
        self.assertEqual(payload['previous_response'], self.value)
        self.assertIn('retain its existing judgments', effective)
        self.assertIn('Do not\nrestart the analysis from scratch', effective)

    def test_actual_wire_prompt_has_feedback_and_strict_validator_still_fails(self):
        previous = self.save()
        original_bytes = (previous / 'result.json').read_bytes()
        process = {'state': 'EXITED', 'exit_code': 0, 'stdout': 'offline', 'stderr': '', 'elapsed_seconds': 0.1}
        with patch('finarch.shared.providers.cli.build_command', return_value=['codex', 'exec', '-']), \
                patch('finarch.shared.providers.cli.run_process', return_value=process) as transport, \
                patch.object(codex.cli, 'parse', return_value={'status': 'RECEIVED', 'text': json.dumps(self.value)}):
            result = codex.call(self.req, self.next, 1800)
        command, input_text = transport.call_args.args[:2]
        effective = json.loads(next(v.split('=', 1)[1] for v in command if v.startswith('developer_instructions=')))
        self.assertTrue(effective.startswith(self.req['prompt']))
        self.assertIn('decision_grounding.citations[1]', effective)
        self.assertIn('ASSESSMENT_QUOTE_NOT_IN_SOURCE', effective)
        payload = json.loads(effective.split('Previous response and additional validation information:\n', 1)[1])
        self.assertEqual(payload['previous_response'], self.value)
        self.assertEqual(json.loads(input_text), self.req['input'])
        self.assertEqual(store.read(self.next / 'request.json'), self.req)
        self.assertTrue((self.next / 'retry-feedback.json').is_file())
        self.assertEqual(store.read(self.next / 'provider-request.json')['effective_prompt'], effective)
        self.assertEqual(result['status'], 'INVALID_RESPONSE')
        self.assertEqual(result['schema_errors'], self.errors)
        self.assertEqual((previous / 'result.json').read_bytes(), original_bytes)


if __name__ == '__main__':
    unittest.main()
