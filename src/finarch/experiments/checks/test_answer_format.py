"""Offline tests for numeric output, metadata isolation and frozen v2 support."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

answer_format = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])
PROJECT = __import__('finarch.experiments.90-operations.storage', fromlist=['PROJECT']).PROJECT
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read


class AnswerFormatTest(unittest.TestCase):
    def setUp(self):
        self.schema = read(PROJECT / 'src/finarch/experiments/checks/fixtures/experiment-v4/00-definition/response.schema.json')
        self.request = {'response_schema': self.schema, 'prompt': 'Solve the question using the supplied context.',
                        'input': {'question': 'What is the change in profit, in millions, to one decimal place?',
                                  'context': 'Profit was $1136.0 million this year and $1148.6 million last year.',
                                  'answer_format': {'decimal_places': 1}},
                        'reasoning': 'off', 'max_output_tokens': 8192, 'thinking_budget': 2048}
        self.response = {'status': 'answered', 'answer': '12.6', 'answer_meta': {'negative': True, 'scale': 'million'},
                         'explanation': '1136.0 - 1148.6 = -12.6.', 'evidence': []}
        self.reference = {'reference_answer': '-12.6', 'reference_answer_type': 'float', 'reference_precision': 1}

    def test_metadata_is_only_precision_and_reaches_provider_with_schema(self):
        payload = answer_format.model_input(dict(self.request['input'], item_id='public-item'), self.schema)
        self.assertEqual(payload['answer_format'], {'decimal_places': 1})
        wire = providers.gemini_body(self.request)
        self.assertEqual(json.loads(wire['contents'][0]['parts'][0]['text']), payload)
        self.assertEqual(wire['generationConfig']['responseJsonSchema']['properties'], self.schema['properties'])
        for secret in ['reference_answer', 'negative', 'scale', 'unit']:
            altered = copy.deepcopy(self.request)
            altered['input']['answer_format'][secret] = True
            with self.assertRaisesRegex(ValueError, 'PRIVATE'):
                providers.validate_request(altered)

    def test_scale_is_recorded_and_signed_coefficient_is_compared(self):
        self.assertEqual(answer_format.response_errors(self.response, self.request), [])
        private = {'experiment': 1, 'reference': self.reference, 'answer_metadata': {'scale': 'million', 'negative': True}}
        check = reporting.screen(self.response, self.request['input'], private)
        self.assertEqual(check['numeric_comparison']['computed'], '-12.6')
        self.assertTrue(check['numeric_comparison']['matches'])
        self.assertEqual(check['reported_scale'], 'million')
        self.assertEqual(check['scale_assessment'], 'RECORDED_NO_AUTOMATIC_RESCALING')
        wrong = dict(self.response, answer='12600000.0')
        self.assertFalse(reporting.screen(wrong, self.request['input'], private)['numeric_comparison']['matches'])

    def test_public_payload_rejects_hidden_reference_fields_and_empty_qc(self):
        for public in [dict(self.request['input'], reference_answer='-12.6'),
                       dict(self.request['input'], answer_format={'decimal_places': 1, 'negative': True})]:
            with self.assertRaisesRegex(ValueError, 'PRIVATE'):
                answer_format.model_input(public, self.schema)
        for key in ('question', 'context'):
            with self.assertRaisesRegex(ValueError, 'EMPTY_OR_INVALID'):
                answer_format.model_input(dict(self.request['input'], **{key: ''}), self.schema)
        with self.assertRaisesRegex(ValueError, 'PUBLIC_PAYLOAD_CONTRACT_MISMATCH'):
            answer_format.model_input(self.request['input'], {'title': 'FinancialAnswerMinimalDraftV2'})

    def test_currency_sign_comma_expression_and_precision_are_rejected(self):
        for value in ['-$12.6 million', '-12.6', '$12.6', '1,200.6', '(12.6)', '12.60', '12', '12.6 + 1', '1.26e1', 12.6]:
            self.assertTrue(answer_format.response_errors(dict(self.response, answer=value), self.request), value)
        self.assertTrue(answer_format.response_errors(dict(self.response, unit='USD'), self.request))
        self.assertTrue(answer_format.response_errors(dict(self.response, answer_meta={'negative': True, 'scale': 'USD'}), self.request))

    def test_zero_and_abstention_have_explicit_sign_rules(self):
        zero = dict(self.response, answer='0.0', answer_meta={'negative': False, 'scale': 'million'})
        self.assertEqual(answer_format.response_errors(zero, self.request), [])
        self.assertTrue(answer_format.response_errors(dict(zero, answer_meta={'negative': True, 'scale': 'million'}), self.request))
        abstained = dict(self.response, status='abstained', answer=None, answer_meta={'negative': None, 'scale': 'million'})
        self.assertEqual(answer_format.response_errors(abstained, self.request), [])
        for change in [{'answer': '0.0'}, {'answer_meta': {'negative': False, 'scale': 'million'}}, {'status': 'answered'}]:
            self.assertTrue(answer_format.response_errors(dict(abstained, **change), self.request))
        checked = reporting.screen(abstained, self.request['input'], {'experiment': 2})
        self.assertTrue(checked['declared_abstention'])
        self.assertNotIn('numeric_comparison', checked)

    def test_integer_is_direct_comparison_not_legacy_truncation(self):
        request = copy.deepcopy(self.request)
        request['input']['answer_format']['decimal_places'] = 0
        response = dict(self.response, answer='3', answer_meta={'negative': False, 'scale': 'million'})
        self.assertEqual(answer_format.response_errors(response, request), [])
        self.assertTrue(answer_format.response_errors(dict(response, answer='2.8'), request))
        reference = {'reference_answer': '3', 'reference_answer_type': 'integer', 'reference_precision': 0}
        self.assertTrue(answer_format.compare_answer(response, reference)['matches'])
        self.assertEqual(answer_format.compare_answer(response, reference)['policy'], 'DIRECT_SIGNED_DECIMAL_IN_QUESTION_SCALE')

    def test_frozen_legacy_contract_remains_usable(self):
        schema = {'title': 'FinancialAnswerMinimalDraftV2', 'type': 'object',
                  'required': ['answer', 'explanation', 'evidence'], 'additionalProperties': False,
                  'properties': {'answer': {'type': 'string'}, 'explanation': {'type': 'string'}, 'evidence': {'type': 'array', 'items': {'type': 'string'}}}}
        legacy = copy.deepcopy(self.request)
        legacy['response_schema'] = schema
        legacy['input'].pop('answer_format')
        providers.validate_request(legacy)
        response = {'answer': '-$12.6 million', 'explanation': '', 'evidence': []}
        self.assertEqual(answer_format.response_errors(response, legacy), [])
        self.assertTrue(reporting.screen(response, legacy['input'], {'experiment': 1, 'reference': self.reference})['numeric_comparison']['matches'])

    def test_direct_provider_uses_same_validation_and_preserves_bad_answer(self):
        for response, status in [(self.response, 'VALID'), (dict(self.response, answer='-$12.6 million'), 'INVALID_RESPONSE')]:
            with tempfile.TemporaryDirectory() as folder:
                with patch.object(providers, 'claude_call', return_value={'status': 'RECEIVED', 'text': json.dumps(response), 'finish_reason': 'STOP',
                                  'usage': {'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}}):
                    result = providers.call({'transport': 'claude_code'}, self.request, folder, 1)
                self.assertEqual(result['status'], status)
                self.assertEqual(read(Path(folder) / 'result.json')['response'], response)

    def test_nested_metadata_is_required_without_flat_duplicates(self):
        self.assertEqual(answer_format.response_errors(self.response, self.request), [])
        self.assertEqual(reporting.screen(self.response, self.request['input'], {'experiment': 1, 'reference': self.reference})['response_format'], 'FinancialAnswerMagnitudeV4')
        for meta in [None, {}, {'negative': True}, {'scale': 'million'}, {'negative': True, 'scale': 'million', 'unit': 'USD'}]:
            self.assertTrue(answer_format.response_errors(dict(self.response, answer_meta=meta), self.request))
        flat = {k: v for k, v in self.response.items() if k != 'answer_meta'}
        flat.update(self.response['answer_meta'])
        self.assertTrue(answer_format.response_errors(flat, self.request))
        self.assertTrue(answer_format.response_errors(dict(self.response, negative=True), self.request))
        wire = providers.gemini_body(self.request)['generationConfig']['responseJsonSchema']
        self.assertIn('answer_meta', wire['properties'])
        self.assertEqual(wire['properties']['answer_meta']['required'], ['negative', 'scale'])
        self.assertNotIn('negative', wire['properties'])

    def test_frozen_flat_v3_still_uses_its_original_contract(self):
        request = copy.deepcopy(self.request)
        schema = request['response_schema']
        schema['title'] = 'FinancialAnswerMagnitudeV3'
        schema['properties'].update(schema['properties'].pop('answer_meta')['properties'])
        schema['required'] = ['status', 'answer', 'negative', 'scale', 'explanation', 'evidence']
        response = {k: v for k, v in self.response.items() if k != 'answer_meta'}
        response.update(self.response['answer_meta'])
        providers.validate_request(request)
        self.assertEqual(answer_format.response_errors(response, request), [])
        self.assertTrue(answer_format.compare_answer(response, self.reference)['matches'])

    def test_batch_applies_cross_field_rules_without_rewriting_response(self):
        collect = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['collect']).collect
        write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'model/02-batches/batch-001'
            request = dict(self.request, trial_id='case-key', case='test-0001', variant='ORIGINAL', prompt_condition='P0')
            write(folder / 'trials.json', [{'request': request, 'attempt': 1}])
            bad = dict(self.response, answer='0.0', answer_meta={'negative': True, 'scale': 'million'})
            operation = {'name': 'batches/test', 'done': True, 'response': {'inlinedResponses': {'inlinedResponses': [
                {'metadata': {'key': 'case-key'}, 'response': {'candidates': [{'finishReason': 'STOP',
                    'content': {'parts': [{'text': json.dumps(bad)}]}}]}}]}}}
            collect(root, {'key': 'model', 'reference_price_per_million': {'input': .05, 'output': .2}}, folder, operation)
            result = read(root / 'model/calls/test-0001/00-Original/_records/case-key/attempt-001/result.json')
            self.assertEqual(result['status'], 'INVALID_RESPONSE')
            self.assertEqual(result['response'], bad)
            self.assertEqual(result['schema_errors'][0]['path'], ['answer_meta', 'negative'])


if __name__ == '__main__':
    unittest.main()
