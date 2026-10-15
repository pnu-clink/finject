"""Offline regressions for uncached paid Luna experiments."""
import copy
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])
test_pipeline = __import__('finarch.experiments.checks.test_pipeline', fromlist=['*'])
encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
openai_api = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['*'])

MODEL = {'key': 'luna-api', 'model': 'gpt-5.6-luna', 'transport': 'openai_responses',
         'reasoning_efforts': {'off': 'none', 'on': 'medium'}, 'key_variable': 'UNUSED_TEST_KEY',
         'reference_price_per_million': {'input': .2, 'output': 1.2, 'cached_input': .02, 'cache_write_input': .25},
         'price_source': 'https://developers.openai.com/api/docs/models/gpt-5.6-luna'}
ANSWER = {'status': 'answered', 'answer': '12', 'answer_meta': {'negative': False, 'scale': 'one'},
          'explanation': '10 + 2 = 12.', 'evidence': []}


def response(usage=None):
    return {'id': 'test_response', 'model': 'gpt-5.6-luna', 'status': 'completed', 'service_tier': 'default',
            'prompt_cache_options': {'mode': 'explicit'},
            'usage': usage if usage is not None else {'input_tokens': 100, 'output_tokens': 30,
                'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                'output_tokens_details': {'reasoning_tokens': 10}},
            'output': [{'type': 'reasoning', 'summary': []},
                       {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(ANSWER)}]}]}


class OpenAIErrorClassificationTest(unittest.TestCase):
    def test_quota_error_codes_and_types_preserve_provider_error(self):
        errors = [
            {'code': 'insufficient_quota'},
            {'code': 'billing_hard_limit_reached'},
            {'code': 'billing_not_active'},
            {'code': 'credit_balance_exhausted'},
            {'code': 'credit_balance_exhausted', 'type': 'insufficient_quota',
             'message': 'You have no credits remaining.'},
            {'code': None, 'type': 'insufficient_quota'},
            {'type': 'insufficient_quota'},
            {'code': 'other_provider_code', 'type': 'insufficient_quota'},
        ]
        for error in errors:
            with self.subTest(error=error):
                result = openai_api.parse_response({'error': error}, 429, {'retry-after': '65'})
                self.assertEqual(result['status'], 'QUOTA_EXHAUSTED')
                self.assertEqual(result['error'], error)
                self.assertIsNone(result['usage'])
                self.assertEqual(result['http_status'], 429)
                self.assertEqual(result['retry_after_seconds'], 65)

    def test_other_http_error_classifications_are_unchanged(self):
        cases = [
            (429, {'code': 'rate_limit_exceeded', 'type': 'requests'}, 'RATE_LIMITED'),
            (429, 'provider error', 'RATE_LIMITED'),
            (401, {'type': 'insufficient_quota'}, 'AUTH_BLOCKED'),
            (403, {'code': 'credit_balance_exhausted'}, 'AUTH_BLOCKED'),
            (503, {'code': 'server_error'}, 'TRANSIENT_ERROR'),
            (400, {'code': 'invalid_request'}, 'PROVIDER_ERROR'),
        ]
        for http_status, error, expected in cases:
            with self.subTest(http_status=http_status, error=error):
                result = openai_api.parse_response({'error': error}, http_status)
                self.assertEqual(result['status'], expected)


class OpenAIExperimentTest(unittest.TestCase):
    def setUp(self):
        self.fixture = test_pipeline.ExperimentsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.config['models'] = [copy.deepcopy(MODEL)]
        self.fixture.config['schedule']['concurrency'] = 200
        write(self.fixture.root / 'config.json', {'experiments': self.fixture.config})
        self.root = self.fixture.prepare()
        self.requests = rows(self.root / 'luna-api/01-requests/manifest.jsonl')

    def test_body_keeps_prompt_schema_and_effort_without_cache_or_history(self):
        for request in self.requests[:2]:
            body = openai_api.body_for(MODEL, request)
            self.assertEqual(body['instructions'], request['prompt'])
            self.assertEqual(json.loads(body['input'][0]['content'][0]['text']), request['input'])
            self.assertEqual(body['reasoning']['effort'], MODEL['reasoning_efforts'][request['reasoning']])
            self.assertEqual(body['prompt_cache_options'], {'mode': 'explicit'})
            self.assertNotIn('previous_response_id', body)
            self.assertFalse(body['store'])
            self.assertTrue(body['text']['format']['strict'])
            self.assertEqual(body['text']['format']['schema'], {k: v for k, v in request['response_schema'].items() if k not in ('$schema', 'title')})
        for field, value in [('response_schema', {}), ('prompt', '')]:
            with self.assertRaises(ValueError):
                openai_api.body_for(MODEL, {**self.requests[0], field: value})
        body = openai_api.body_for(MODEL, self.requests[0])
        body['input'][0]['content'][0]['prompt_cache_breakpoint'] = {'mode': 'explicit'}
        with self.assertRaisesRegex(ValueError, 'BREAKPOINT'):
            openai_api.validate_cache_body(body)

    def test_wire_request_preserves_raw_usage_and_cost(self):
        payload = response()
        class Reply:
            status = 200
            headers = {'x-request-id': 'request-id', 'Set-Cookie': 'not-saved'}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return encoded(payload)
        captured = []
        captured_bytes = []
        def http(wire, timeout):
            captured.append(json.loads(wire.data))
            captured_bytes.append(wire.data)
            self.assertEqual(wire.full_url, openai_api.ENDPOINT)
            return Reply()
        folder = self.root / 'wire-test'
        request = copy.deepcopy(self.requests[0])
        order = ['evidence', 'explanation', 'answer', 'answer_meta', 'status']
        request['response_schema']['required'] = order
        request['response_schema']['properties']['answer_meta']['required'] = ['scale', 'negative']
        # Manifests sort object keys, so the required array must restore wire order.
        request = json.loads(encoded(request))
        before = copy.deepcopy(request)
        with patch.object(providers, 'credential', return_value='secret-test-key'), patch.object(openai_api.urllib.request, 'urlopen', side_effect=http):
            result = providers.call(MODEL, request, folder, 60)
        self.assertEqual(result['status'], 'VALID')
        self.assertEqual(result['cache_check']['status'], 'VERIFIED_ZERO')
        self.assertAlmostEqual(result['token_cost_estimate_usd'], .000056)
        self.assertEqual(read(folder / 'raw-response.json'), payload)
        self.assertEqual(read(folder / 'provider-request.json'), captured[0])
        self.assertEqual((folder / 'provider-request-wire.json').read_bytes(), captured_bytes[0])
        sent_schema = captured[0]['text']['format']['schema']
        self.assertEqual(list(sent_schema['properties']), order)
        self.assertEqual(list(sent_schema['properties']['answer_meta']['properties']), ['scale', 'negative'])
        self.assertEqual(request, before)
        self.assertNotIn('Set-Cookie', read(folder / 'http.json')['headers'])
        self.assertFalse(any('secret-test-key' in p.read_text() for p in folder.iterdir()))
        self.assertEqual(call_layout.response_text(payload), json.dumps(ANSWER))

    def test_usage_cost_and_error_types(self):
        for fields, expected in [({'cached_tokens': 1, 'cache_write_tokens': 0}, 'CACHE_POLICY_VIOLATION'),
                                 ({'cached_tokens': 0, 'cache_write_tokens': 1}, 'CACHE_POLICY_VIOLATION'),
                                 ({'cached_tokens': 0}, 'CACHE_USAGE_UNVERIFIED')]:
            usage = {'input_tokens': 100, 'output_tokens': 30, 'input_tokens_details': fields}
            self.assertEqual(cache_policy.usage_check('openai_responses', usage)['status'], expected)
        self.assertIsNone(openai_api.cost_from_usage({'input_tokens': 100}, MODEL['reference_price_per_million']))
        self.assertEqual(openai_api.parse_response({'error': {'code': 'insufficient_quota'}}, 429)['status'], 'QUOTA_EXHAUSTED')
        self.assertEqual(openai_api.parse_response({'error': {'code': 'rate_limit_exceeded'}}, 429)['status'], 'RATE_LIMITED')
        incomplete = {**response(), 'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}}
        self.assertEqual(openai_api.parse_response(incomplete)['status'], 'OUTPUT_TRUNCATED')

    def test_scheduler_probes_both_modes_then_runs_a_200_limit_wave(self):
        calls = []
        lock = threading.Lock()
        def fake(model, request, folder, timeout):
            with lock:
                calls.append(request['reasoning'])
            result = {'status': 'VALID', 'transport': 'openai_responses', 'billing_mode': 'PAID_OPENAI_API',
                      'response': ANSWER, 'usage': response()['usage'], 'cache_check': {'status': 'VERIFIED_ZERO'},
                      'token_cost_estimate_usd': .000056}
            write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), patch.object(providers, 'call', side_effect=fake):
            pipeline.run(self.root)
            pipeline.run(self.root)
        self.assertEqual(len(calls), 8)
        self.assertEqual(set(calls[:2]), {'off', 'on'})
        waves = [row for row in rows(self.root / 'events.jsonl') if row['event'] == 'WAVE_START']
        self.assertEqual([row['requests'] for row in waves], [1, 1, 6])
        self.assertTrue(all(row['concurrency'] == 200 for row in waves))
        summary = reporting.build(self.root)['models'][0]
        self.assertEqual(summary['cache_verification']['status'], 'VERIFIED_ZERO')
        self.assertEqual(summary['cache_read_tokens'], 0)
        self.assertEqual(summary['cache_creation_tokens'], 0)
        self.assertEqual(summary['reported_reasoning_output_tokens'], 80)
        self.assertAlmostEqual(summary['paid_api_usage_cost_estimate_usd'], .000448)

    def test_cache_failure_prevents_broad_dispatch_and_resume(self):
        def fake(model, request, folder, timeout):
            result = {'status': 'CACHE_USAGE_UNVERIFIED', 'transport': 'openai_responses',
                      'usage': {'input_tokens': 100, 'output_tokens': 30}, 'cache_check': {'status': 'CACHE_USAGE_UNVERIFIED'}}
            write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), patch.object(providers, 'call', side_effect=fake) as call:
            pipeline.run(self.root)
            pipeline.run(self.root)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(read(self.root / 'state.json')['models']['luna-api']['status'], 'CACHE_USAGE_UNVERIFIED')

    def test_unknown_delivery_is_not_retried_or_marked_finished(self):
        def fake(model, request, folder, timeout):
            result = {'status': 'UNKNOWN_DELIVERY', 'usage': None}
            write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), patch.object(providers, 'call', side_effect=fake) as call:
            pipeline.run(self.root)
            pipeline.run(self.root)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(read(self.root / 'state.json')['models']['luna-api']['status'], 'UNKNOWN_DELIVERY')


if __name__ == '__main__':
    unittest.main()
