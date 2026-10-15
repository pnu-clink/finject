"""Offline regression checks for neutral prompts and consistent V6 values."""
import copy
import json
import unittest
from unittest.mock import patch

answer_format = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
test_pipeline = __import__('finarch.experiments.checks.test_pipeline', fromlist=['*'])
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
answer_contract = __import__('finarch.experiments.01-evaluation.02-request.answer_contract', fromlist=['*'])
openai_api = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['*'])


class ContractV6Test(unittest.TestCase):
    def setUp(self):
        self.fixture = test_pipeline.ExperimentsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.config.update(definition_source_run=str(pipeline.PROJECT / 'src/finarch/experiments/checks/fixtures/experiment-v6'),
                                   response_contract=answer_contract.STABLE_TITLE)
        write(self.fixture.root / 'config.json', {'experiments': self.fixture.config})
        self.root = self.fixture.prepare()
        key = self.fixture.config['models'][0]['key']
        self.requests = rows(self.root / key / '01-requests/manifest.jsonl')
        self.request = next(r for r in self.requests if r['prompt_condition'] == 'unguided')
        self.answer = {'answer': -12, 'answer_meta': {'negative': True, 'scale': 'one'},
                       'explanation': 'The reported signed difference is -12.',
                       'evidence': ['Amount A is 10.']}

    def test_neutral_schema_and_p0_share_exact_structure_with_p1(self):
        schema = self.request['response_schema']
        for request in self.requests:
            providers.validate_request(request)
            self.assertEqual(schema, request['response_schema'])
            if request['prompt_condition'] == 'unguided':
                self.assertFalse(answer_contract.BEHAVIOR_WORDS.search(request['prompt']))
            else:
                broken = {**request, 'prompt': request['prompt'].replace('conflicting facts', 'facts')}
                with self.assertRaisesRegex(ValueError, 'GUIDED_GUIDANCE_MISSING'):
                    providers.validate_request(broken)
        bad = copy.deepcopy(self.request)
        bad['response_schema']['properties']['answer']['description'] = 'Abstain on conflict.'
        with self.assertRaisesRegex(ValueError, 'STRUCTURAL_ONLY'):
            providers.validate_request(bad)

    def test_current_p1_self_classification_stays_out_of_p0_and_schema(self):
        p1 = next(r for r in self.requests if r['prompt_condition'] == 'guided')
        self.assertEqual(self.request['response_schema'], p1['response_schema'])
        for label in ('ANSWERABLE', 'CONFLICT', 'INSUFFICIENT_EVIDENCE', 'UNRESOLVED',
                      'CONDITIONAL', 'ABSTAIN'):
            self.assertIn(label, p1['prompt'])
            self.assertNotIn(label, self.request['prompt'])
        self.assertIn('Classification: <CLASS>; Response: <MODE>.', p1['prompt'])
        self.assertIn('The labels are text within the existing `explanation` field', p1['prompt'])
        self.assertEqual(p1['response_schema']['required'],
                         ['evidence', 'explanation', 'answer', 'answer_meta'])
        ordered = openai_api.schema_in_output_order(p1['response_schema'])
        self.assertEqual(list(ordered['properties']), p1['response_schema']['required'])

    def test_sign_and_null_metadata_consistency_without_value_repair(self):
        original = copy.deepcopy(self.answer)
        self.assertEqual(answer_format.response_errors(self.answer, self.request), [])
        self.assertEqual(self.answer, original)
        invalid = {**self.answer, 'answer_meta': {'negative': False, 'scale': 'one'}}
        self.assertTrue(answer_format.response_errors(invalid, self.request))
        empty = {**self.answer, 'answer': None, 'answer_meta': {'negative': None, 'scale': None}}
        self.assertEqual(answer_format.response_errors(empty, self.request), [])
        for field, value in [('negative', False), ('scale', 'one')]:
            bad = copy.deepcopy(empty)
            bad['answer_meta'][field] = value
            self.assertTrue(answer_format.response_errors(bad, self.request))
        zero = {**self.answer, 'answer': -0.0, 'answer_meta': {'negative': False, 'scale': 'one'}}
        self.assertEqual(answer_format.response_errors(zero, self.request), [])

    def test_rounding_is_numeric_not_trailing_zero_text(self):
        request = copy.deepcopy(self.request)
        request['input']['answer_format']['decimal_places'] = 2
        for number in [-12, -12.0, -12.25]:
            self.assertEqual(answer_format.response_errors({**self.answer, 'answer': number}, request), [])
        for number in [-12.251, float('inf'), float('nan')]:
            self.assertTrue(answer_format.response_errors({**self.answer, 'answer': number}, request))

    def test_api_payload_and_saved_failure_keep_the_same_contract(self):
        model = {'model': 'gpt-5.6-luna', 'transport': 'openai_responses',
                 'reasoning_efforts': {'off': 'none', 'on': 'medium'}}
        request = {**self.request, 'model': model['model'],
                   'reasoning_effort': model['reasoning_efforts'][self.request['reasoning']]}
        body = openai_api.body_for(model, request)
        self.assertEqual(body['instructions'], request['prompt'])
        self.assertEqual(body['text']['format']['schema']['properties'], request['response_schema']['properties'])
        invalid = {**self.answer, 'answer_meta': {'negative': False, 'scale': 'one'}}
        folder = self.fixture.root / 'v6-invalid'
        with patch.object(providers, 'claude_call', return_value={
            'status': 'RECEIVED', 'text': json.dumps(invalid), 'finish_reason': 'STOP',
            'usage': {'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}}):
            result = providers.call({'transport': 'claude_code'}, request, folder, 1)
        self.assertEqual(result['status'], 'INVALID_RESPONSE')
        self.assertEqual(read(folder / 'result.json')['response'], invalid)


if __name__ == '__main__':
    unittest.main()
