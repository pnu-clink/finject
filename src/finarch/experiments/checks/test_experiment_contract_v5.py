"""Offline checks for shared V5 output structure and isolated P1 guidance."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

answer_format = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])
test_pipeline = __import__('finarch.experiments.checks.test_pipeline', fromlist=['*'])
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
answer_contract = __import__('finarch.experiments.01-evaluation.02-request.answer_contract', fromlist=['*'])
openai_api = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['*'])


class ContractV5Test(unittest.TestCase):
    def setUp(self):
        self.fixture = test_pipeline.ExperimentsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.config.update(definition_source_run=str(pipeline.PROJECT / 'src/finarch/experiments/checks/fixtures/experiment-v5'), response_contract=answer_contract.TITLE)
        write(self.fixture.root / 'config.json', {'experiments': self.fixture.config})
        self.root = self.fixture.prepare()
        self.model = self.fixture.config['models'][0]
        self.requests = rows(self.root / self.model['key'] / '01-requests/manifest.jsonl')
        self.request = next(r for r in self.requests if r['experiment'] == 1)
        self.answer = {'answer': 12, 'answer_meta': {'negative': False, 'scale': 'one'},
                       'explanation': '10 + 2 = 12.', 'evidence': ['Amount A is 10.']}

    def test_actual_payloads_share_schema_without_p0_behavior_cues(self):
        schemas = []
        for request in self.requests:
            for body in [providers.gemini_body(request)]:
                schema = body['generationConfig']['responseJsonSchema']
                schemas.append(schema)
                self.assertNotIn('description', json.dumps(schema))
                self.assertNotIn('status', schema['properties'])
                self.assertFalse(answer_contract.BEHAVIOR_WORDS.search(json.dumps(schema)))
                if request['prompt_condition'] == 'unguided':
                    self.assertFalse(answer_contract.BEHAVIOR_WORDS.search(request['prompt']))
                else:
                    self.assertIn('conflicting facts', request['prompt'])
                    self.assertIn('set `answer` to null', request['prompt'])
        self.assertTrue(all(s == schemas[0] for s in schemas))
        model = {'model': 'gpt-5.6-luna', 'transport': 'openai_responses',
                 'reasoning_efforts': {'off': 'none', 'on': 'medium'}}
        request = {**self.request, 'model': model['model'],
                   'reasoning_effort': model['reasoning_efforts'][self.request['reasoning']]}
        body = openai_api.body_for(model, request)
        self.assertEqual(body['text']['format']['schema'], schemas[0])
        self.assertEqual(body['instructions'], request['prompt'])
        self.assertEqual(set(json.loads(body['input'][0]['content'][0]['text'])),
                         {'question', 'context', 'answer_format'})

    def test_injected_annotations_or_behavior_cues_fail_before_dispatch(self):
        bad = copy.deepcopy(self.request)
        bad['response_schema']['properties']['answer']['description'] = 'Return a result.'
        with self.assertRaisesRegex(ValueError, 'STRUCTURAL_ONLY'):
            providers.validate_request(bad)
        bad = copy.deepcopy(self.request)
        bad['prompt'] += '\nAbstain if necessary.'
        with self.assertRaisesRegex(ValueError, 'UNGUIDED_CONTAINS_BEHAVIOR'):
            providers.validate_request(bad)
        bad = copy.deepcopy(self.request)
        bad['response_schema']['properties']['status'] = {'type': 'string'}
        with self.assertRaisesRegex(ValueError, 'SCHEMA_CONTAINS_BEHAVIOR'):
            providers.validate_request(bad)

    def test_response_checks_accept_signed_numbers_and_do_not_invent_a_status(self):
        self.assertEqual(answer_format.response_errors(self.answer, self.request), [])
        for answer in [12, -12, 12.0, -12.5, 0, 0.0, 12.375]:
            self.assertEqual(answer_format.response_errors({**self.answer, 'answer': answer}, self.request), [])
        for answer in ['-12', '12.0', '$12', True, float('inf'), float('nan')]:
            self.assertTrue(answer_format.response_errors({**self.answer, 'answer': answer}, self.request))
        self.assertTrue(answer_format.response_errors({**self.answer, 'status': 'answered'}, self.request))
        empty = {**self.answer, 'answer': None, 'answer_meta': {'negative': None, 'scale': 'one'}}
        self.assertEqual(answer_format.response_errors(empty, self.request), [])
        checks = reporting.screen(empty, self.request['input'], {'experiment': 1})
        self.assertIsNone(checks['declared_abstention'])
        self.assertFalse(checks['numeric_answer_present'])
        self.assertEqual(checks['semantic_assessment'], 'NOT_REVIEWED')
        self.assertNotIn('numeric_comparison', checks)
        self.assertNotIn('status', empty)
        self.assertEqual(answer_format.response_errors(
            {**empty, 'answer_meta': {'negative': False, 'scale': 'one'}}, self.request), [])
        checks = reporting.screen(self.answer, self.request['input'],
                                  {'experiment': 1, 'reference': self.fixture.original})
        self.assertTrue(checks['numeric_comparison']['matches'])

    def test_numeric_value_is_preserved_without_sign_reconstruction_or_rounding(self):
        numeric_analysis = __import__('finarch.experiments.01-evaluation.04-validation.numeric_analysis', fromlist=['*'])
        for value in [-12, -12.5, 0, 0.125]:
            response = {**self.answer, 'answer': value}
            reference = {**self.fixture.original, 'reference_answer': str(value)}
            checks = reporting.screen(response, self.request['input'],
                                      {'experiment': 1, 'reference': reference})
            self.assertTrue(checks['numeric_answer_present'])
            self.assertTrue(checks['numeric_comparison']['matches'])
            self.assertEqual(checks['numeric_comparison']['computed'], str(value))
            tags, _ = numeric_analysis.response_diagnostics(
                {'experiment': 1, 'status': 'VALID'}, {'response': response}, reference)
            self.assertEqual(tags, [])

    def test_provider_preserves_raw_v5_response_and_uses_same_validator(self):
        for response, status in [(self.answer, 'VALID'), ({**self.answer, 'status': 'answered'}, 'INVALID_RESPONSE')]:
            folder = self.fixture.root / status
            with patch.object(providers, 'claude_call', return_value={
                'status': 'RECEIVED', 'text': json.dumps(response), 'finish_reason': 'STOP',
                'usage': {'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}}):
                result = providers.call({'transport': 'claude_code'}, self.request, folder, 1)
            self.assertEqual(result['status'], status)
            self.assertEqual(read(folder / 'result.json')['response'], response)

    def test_summary_handles_empty_answers_without_abstention_counts(self):
        call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
        model_dir = self.root / self.model['key']
        for request in self.requests:
            folder = call_layout.attempt_path(model_dir, request, 1)
            empty = {**self.answer, 'answer': None, 'answer_meta': {'negative': None, 'scale': 'one'}}
            write(folder / 'request.json', request)
            write(folder / 'result.json', {'status': 'VALID', 'response': empty, 'usage': {}})
        summary = reporting.build(self.root)
        self.assertEqual(sum(g['numeric_answers_absent'] for g in summary['models'][0]['groups']), len(self.requests))
        self.assertTrue(all('declared_abstentions' not in g for g in summary['models'][0]['groups']))
        numeric_analysis = __import__('finarch.experiments.01-evaluation.04-validation.numeric_analysis', fromlist=['*'])
        numeric_analysis.build(self.root)
        diagnostics = rows(self.root / 'analysis/response-diagnostics.jsonl')
        self.assertTrue(all('NUMERIC_ANSWER_ABSENT' in row['tags'] for row in diagnostics))
        self.assertTrue(all('DECLARED_ABSTENTION' not in row['tags'] for row in diagnostics))


if __name__ == '__main__':
    unittest.main()
