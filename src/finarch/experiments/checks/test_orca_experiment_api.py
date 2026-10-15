"""Offline checks for the paid transport, run-scoped cache permission and dispatch gate."""
import copy
import json
import unittest
from unittest.mock import patch

orca = __import__('finarch.experiments.01-evaluation.03-execution.orca_api', fromlist=['*'])
policy = orca.cache_policy
providers = orca.providers
store = orca.store
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
fixtures = __import__('finarch.experiments.checks.test_pipeline', fromlist=['*'])
layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
MODEL = {'key': 'deepseek-test', 'model': orca.MODEL, 'transport': 'orca_api',
         'reasoning_efforts': {'off': 'none', 'on': 'max'}, 'output_limits': {'off': 8192, 'on': 8192},
         'key_variable': 'UNUSED_TEST_KEY',
         'reference_price_per_million': {'input': .15, 'output': .6, 'cached_input': .003}}
ANSWER = {'status': 'answered', 'answer': '12', 'answer_meta': {'negative': False, 'scale': 'one'},
          'explanation': '10 + 2 = 12.', 'evidence': []}


def envelope(reasoning=0):
    return {'id': 'test-response', 'model': 'deepseek-v4.1-flash',
            'usage': {'prompt_tokens': 100, 'completion_tokens': 30, 'cost_usd': .00002,
                      'prompt_tokens_details': {'cached_tokens': 80},
                      'completion_tokens_details': {'reasoning_tokens': reasoning}},
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(ANSWER),
                          'reasoning_content': 'Reason trace' if reasoning else ''}}]}


class OrcaTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ExperimentsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.config['models'] = [copy.deepcopy(MODEL)]
        self.fixture.config['reasoning_modes'] = ['off', 'on']
        store.write(self.fixture.root / 'config.json', {'experiments': self.fixture.config})
        self.root = self.fixture.prepare()
        self.requests = store.rows(layout.requests(self.root, MODEL['key']))

    def authorize(self):
        policy.authorize_orca(self.root, MODEL['key'], 'User approved this test run.')
        return store.configuration(self.root)['models'][0]

    def test_cache_default_blocks_without_credentials(self):
        with patch.object(providers, 'credential') as credential:
            with self.assertRaises(policy.CachePolicyError):
                providers.preflight(MODEL)
        credential.assert_not_called()

    def test_off_on_wire_and_missing_write_counter(self):
        model = self.authorize()
        self.assertEqual([r['reasoning'] for r in self.requests[:2]], ['off', 'on'])
        for mode in ('off', 'on'):
            request = next(r for r in self.requests if r['reasoning'] == mode)
            body = orca.body_for(model, request)
            self.assertEqual(body['thinking']['type'], 'disabled' if mode == 'off' else 'enabled')
            self.assertEqual(body.get('reasoning_effort'), None if mode == 'off' else 'max')
            self.assertNotIn('reference_answer', body['messages'][1]['content'])
            self.assertEqual(body['response_format']['type'], 'json_schema')
        check = policy.usage_check('orca_api', envelope()['usage'])
        self.assertEqual(check['cache_read_tokens'], 80)
        self.assertIsNone(check['cache_write_tokens'])

    def test_authorization_preserves_frozen_manifest_and_scope(self):
        before = store.file_hash(self.root / 'manifest.json')
        model = self.authorize()
        store.verify(self.root)
        self.assertEqual(store.file_hash(self.root / 'manifest.json'), before)
        other = copy.deepcopy(model)
        other['key'] = 'other-model'
        self.assertIsNone(policy.implicit_cache_exception(other))
        self.assertEqual(policy.control(other)['status'], 'CACHE_POLICY_BLOCKED')
        original = store.read(self.root / 'config.json')
        self.assertNotIn('_cache_exception', original['models'][0])

    def test_permission_cannot_be_added_after_dispatch(self):
        store.write(layout.execution(self.root, MODEL['key']) / 'call' / 'started.json', {'at': store.now()})
        with self.assertRaisesRegex(ValueError, 'MUST_PRECEDE_SUBMISSION'):
            self.authorize()

    def test_target_and_frozen_limits_cannot_drift(self):
        model = self.authorize()
        request = copy.deepcopy(self.requests[0])
        request['max_output_tokens'] += 1
        with self.assertRaisesRegex(ValueError, 'OUTPUT_LIMIT_MISMATCH'):
            orca.body_for(model, request)
        model['endpoint'] = 'https://untrusted.example/chat'
        with self.assertRaisesRegex(ValueError, 'TARGET_REQUIRED'):
            orca.validate_model(model)

    def test_actual_reasoning_off_is_checked_and_wrong_model_rejected(self):
        off = next(r for r in self.requests if r['reasoning'] == 'off')
        self.assertEqual(orca.parse_response(envelope(5), 200, {}, off)['error'], 'REASONING_OFF_RETURNED_REASONING')
        raw = envelope()
        raw['model'] = 'other-model'
        self.assertEqual(orca.parse_response(raw, 200, {}, off)['error'], 'RETURNED_MODEL_MISMATCH')

    def test_non_json_throttle_and_uncertain_gateway_error(self):
        request = self.requests[0]
        r = orca.parse_response({}, 429, {'retry-after': '17'}, request)
        self.assertEqual((r['status'], r['retry_after_seconds']), ('RATE_LIMITED', 17))
        for code, status in ((401, 'AUTH_BLOCKED'), (402, 'QUOTA_EXHAUSTED'), (503, 'UNKNOWN_DELIVERY')):
            self.assertEqual(orca.parse_response({}, code, {}, request)['status'], status)

    def test_dated_response_requires_run_approval_and_preserves_reported_id(self):
        model = self.authorize()
        off = next(r for r in self.requests if r['reasoning'] == 'off')
        raw = envelope()
        raw['model'] = orca.DATED_MODEL
        self.assertEqual(orca.parse_response(raw, 200, {}, off, model)['error'], 'RETURNED_MODEL_MISMATCH')
        before = store.file_hash(self.root / 'manifest.json')
        orca.configure_returned_model(self.root, MODEL['key'], 'User approved the dated returned identifier.')
        model = store.configuration(self.root)['models'][0]
        result = orca.parse_response(raw, 200, {}, off, model)
        self.assertEqual((result['status'], result['model_version']), ('RECEIVED', orca.DATED_MODEL))
        self.assertEqual(store.file_hash(self.root / 'manifest.json'), before)
        self.assertEqual(orca.body_for(model, off)['model'], orca.MODEL)
        for field, value in [('run_id', 'different-run'), ('authorization', ''),
                             ('accepted_additional_identifiers', ['other-model'])]:
            changed = copy.deepcopy(model)
            changed['returned_model_policy'][field] = value
            with self.assertRaises(ValueError):
                orca.body_for(changed, off)

    def test_saved_dated_response_recovery_keeps_raw_and_original_failure(self):
        model = self.authorize()
        request = next(r for r in self.requests if r['reasoning'] == 'off')
        calls = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
        folder = calls.attempt_path(layout.execution(self.root, MODEL['key']), request, 1)
        raw = envelope(); raw['model'] = orca.DATED_MODEL
        old = orca.parse_response(raw, 200, {}, request, model)
        store.write(folder / 'request.json', request)
        store.write(folder / 'provider-request.json', orca.body_for(model, request))
        store.write(folder / 'raw-response.json', raw)
        store.write(folder / 'http.json', {'status': 200, 'headers': {}})
        store.write(folder / 'result.json', old)
        before = store.file_hash(folder / 'raw-response.json')
        orca.configure_returned_model(self.root, MODEL['key'], 'User approved the dated returned identifier.')
        recovered = orca.revalidate_returned_models(self.root, MODEL['key'], [request['trial_id']])
        self.assertEqual(recovered[0]['new_model_calls'], 0)
        self.assertEqual(store.read(folder / 'result.json')['status'], 'VALID')
        self.assertEqual(store.read(folder / 'result-before-returned-model-recovery.json'), old)
        self.assertEqual(store.file_hash(folder / 'raw-response.json'), before)

    def test_peak_prices_and_reasoning_not_double_counted(self):
        offpeak, peak = orca.rates_at(MODEL, '2026-10-09T12:00:00+00:00')
        high, is_peak = orca.rates_at(MODEL, '2026-10-09T06:00:00+00:00')
        self.assertFalse(peak)
        self.assertTrue(is_peak)
        self.assertEqual(high['output'], 1.2)
        self.assertAlmostEqual(orca.cost_from_usage(envelope(10)['usage'], offpeak), .00002124)

    def test_two_mode_probe_gate_and_usage_reporting(self):
        self.authorize()
        calls = []
        def fake(model, request, folder, timeout):
            calls.append(request['reasoning'])
            result = orca.parse_response(envelope(10 if request['reasoning'] == 'on' else 0), 200, {}, request)
            result.update(status='VALID', response=json.loads(result.pop('text')), transport='orca_api',
                          billing_mode='PAID_ORCA_API', token_cost_estimate_usd=.00002124)
            policy.enforce_result(model, result)
            store.write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), patch.object(providers, 'call', side_effect=fake):
            summary = pipeline.run(self.root)
        self.assertEqual(calls[:2], ['off', 'on'])
        self.assertEqual(summary['models'][0]['statuses'], {'VALID': 8})
        self.assertEqual(summary['models'][0]['reported_reasoning_output_tokens'], 40)
        self.assertIsNone(summary['models'][0]['cache_creation_tokens'])
        self.assertAlmostEqual(summary['models'][0]['provider_reported_cost_usd'], .00016)
        self.assertEqual(store.read(self.root / 'state.json')['models'][MODEL['key']]['validated_reasoning_modes'], ['off', 'on'])

    def test_unknown_delivery_stops_and_is_not_resent(self):
        self.authorize()
        def fake(model, request, folder, timeout):
            result = {'status': 'UNKNOWN_DELIVERY', 'usage': None}
            store.write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), patch.object(providers, 'call', side_effect=fake) as call:
            pipeline.run(self.root)
            pipeline.run(self.root)
        self.assertEqual(call.call_count, 1)

    def test_disconnect_is_unknown_and_transport_sends_only_once(self):
        model = self.authorize()
        folder = self.root / 'disconnect-attempt'
        with patch.object(providers, 'credential', return_value='offline-test-key'), \
                patch.object(orca.urllib.request, 'build_opener') as opener:
            opener.return_value.open.side_effect = ConnectionResetError(54, 'Connection reset by peer')
            result = providers.call(model, self.requests[0], folder, 300)
        opener.return_value.open.assert_called_once()
        self.assertEqual(result['status'], 'UNKNOWN_DELIVERY')
        self.assertEqual(result['delivery_status'], 'UNKNOWN')
        self.assertEqual(result['response_unavailable_reason'], 'NETWORK_DISCONNECT')
        self.assertIsNone(result['usage'])
        self.assertFalse((folder / 'raw-response.json').exists())
        self.assertEqual(store.read(folder / 'http.json')['delivery_status'], 'UNKNOWN')

    def authorize_disconnect_continuation(self, authorization='User requested recovery of this run.'):
        self.authorize()
        state = store.read(self.root / 'state.json')
        state['models'][MODEL['key']].update(status='PENDING', validated_reasoning_modes=['off', 'on'],
            first_call_checked=True, disconnect_recovery={
                'continue_unsubmitted': True, 'authorization': authorization})
        store.write(self.root / 'state.json', state)

    def test_authorized_disconnect_preserves_failed_attempt_and_continues_fresh_requests(self):
        self.authorize_disconnect_continuation()
        calls = []
        def fake(model, request, folder, timeout):
            calls.append(request['trial_id'])
            result = ({'status': 'UNKNOWN_DELIVERY', 'usage': None,
                       'response_unavailable_reason': 'NETWORK_DISCONNECT'} if len(calls) == 1 else
                      {'status': 'VALID', 'usage': None, 'response': ANSWER})
            store.write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), \
                patch.object(providers, 'call', side_effect=fake):
            summary = pipeline.run(self.root)
            hashes = {str(p): store.file_hash(p) for p in self.root.rglob('result.json')}
            pipeline.run(self.root)
        self.assertEqual(len(calls), len(self.requests))
        self.assertEqual(len(set(calls)), len(calls))
        self.assertEqual(summary['models'][0]['statuses'], {'UNKNOWN_DELIVERY': 1, 'VALID': 7})
        self.assertEqual(hashes, {str(p): store.file_hash(p) for p in self.root.rglob('result.json')})
        store.verify(self.root)

    def test_authorized_disconnect_outage_still_stops(self):
        self.authorize_disconnect_continuation()
        def fake(model, request, folder, timeout):
            result = {'status': 'UNKNOWN_DELIVERY', 'usage': None,
                      'response_unavailable_reason': 'NETWORK_DISCONNECT'}
            store.write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), \
                patch.object(providers, 'call', side_effect=fake) as call:
            pipeline.run(self.root)
            before = call.call_count
            pipeline.run(self.root)
        self.assertEqual(before, self.fixture.config['schedule']['concurrency'])
        self.assertEqual(call.call_count, before)

    def test_continuation_requires_authorization_and_does_not_cover_gateway_errors(self):
        for authorization, reason in [('', 'NETWORK_DISCONNECT'), ('User requested recovery.', None)]:
            with self.subTest(authorization=authorization, reason=reason):
                self.authorize_disconnect_continuation(authorization)
                def fake(model, request, folder, timeout):
                    result = {'status': 'UNKNOWN_DELIVERY', 'usage': None,
                              'response_unavailable_reason': reason}
                    store.write(folder / 'result.json', result)
                    return result
                with patch.object(providers, 'preflight', return_value={'status': 'READY'}), \
                        patch.object(providers, 'call', side_effect=fake) as call:
                    pipeline.run(self.root)
                self.assertGreater(call.call_count, 0)
                self.assertEqual(store.read(self.root / 'state.json')['models'][MODEL['key']]['status'], 'UNKNOWN_DELIVERY')


if __name__ == '__main__':
    unittest.main()
