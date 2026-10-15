"""Offline checks for bounded waves, frozen implementations, quota and cost."""
import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
test_pipeline = __import__('finarch.experiments.checks.test_pipeline', fromlist=['*'])
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
runner = __import__('finarch.experiments.02-analysis.legacy.comparison.improvement_run', fromlist=['*'])

MODEL = {'key': 'luna-api', 'model': 'gpt-5.6-luna', 'transport': 'openai_responses',
         'reasoning_efforts': {'off': 'none', 'on': 'medium'}, 'key_variable': 'UNUSED',
         'reference_price_per_million': {'input': .2, 'output': 1.2, 'cached_input': .02, 'cache_write_input': .25}}
USAGE = {'input_tokens': 100, 'output_tokens': 20,
         'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}}


def evidence(used=10, age=0):
    return {'source': 'mcp__codex_app__get_usage_limits',
            'observed_at': (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
            'rateLimitsByLimitId': {'codex': {'primary': {'usedPercent': used, 'windowDurationMins': 300},
                                            'secondary': {'usedPercent': used, 'windowDurationMins': 10080}}}}


class ImprovementRunTest(unittest.TestCase):
    def setUp(self):
        self.fixture = test_pipeline.ExperimentsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.config['models'] = [copy.deepcopy(MODEL)]
        self.fixture.config['schedule'].update(concurrency=3, max_rate_limit_attempts=1)
        self.fixture.config['billing']['api_budget_usd'] = 1
        write(self.fixture.root / 'config.json', {'experiments': self.fixture.config})
        self.root = runner.prepare(self.fixture.root / 'config.json')
        self.requests = rows(self.root / 'luna-api/01-requests/manifest.jsonl')

    def attempt(self, index=0, number=1, status='VALID', usage=USAGE):
        folder = call_layout.attempt_path(self.root / 'luna-api', self.requests[index], number)
        write(folder / 'request.json', self.requests[index])
        write(folder / 'result.json', {'status': status, 'usage': usage})
        return folder

    def mutate_config(self, change):
        config = read(self.root / 'config.json')
        change(config)
        write(self.root / 'config.json', config)
        manifest = read(self.root / 'manifest.json')
        manifest['config.json'] = file_hash(self.root / 'config.json')
        write(self.root / 'manifest.json', manifest)

    def test_prepare_freezes_code_and_templates_and_rejects_live_drift(self):
        runner.verify_implementation(self.root)
        frozen = read(self.root / '00-implementation/manifest.json')['files']
        self.assertIn('src/finarch/experiments/02-analysis/legacy/comparison/improvement_run.py', frozen)
        self.assertIn('src/finarch/experiments/01-evaluation/pipeline.py', frozen)
        self.assertTrue(any('template' in name for name in frozen))
        with patch.object(runner, 'implementation_files', return_value=[]):
            with self.assertRaisesRegex(runner.WaveBlocked, 'LIVE_IMPLEMENTATION_MISMATCH'):
                runner.verify_implementation(self.root)
        snapshot = self.root / '00-implementation/src/finarch/experiments/01-evaluation/pipeline.py'
        snapshot.write_text('modified')
        with self.assertRaisesRegex(ValueError, 'FROZEN_ARTIFACT_CHANGED'):
            runner.verify_implementation(self.root)

    def test_runtime_overrides_even_empty_are_forbidden(self):
        write(self.root / 'runtime-overrides.json', {})
        with patch.object(pipeline.providers, 'call') as calls:
            with self.assertRaisesRegex(runner.WaveBlocked, 'RUNTIME_OVERRIDES'):
                runner.run_wave(self.root, 1, evidence())
            calls.assert_not_called()
        self.assertEqual(read(self.root / 'improvement-status.json')['new_model_calls'], 0)

    def test_quota_stale_missing_boundary_and_unavailable(self):
        self.assertEqual(runner.quota_check(evidence())['status'], 'VERIFIED')
        for item, reason in [(None, 'OFFICIAL'), (evidence(age=601), 'STALE'),
                             (evidence(used=85), 'RESERVE'), (evidence(used=95), 'RESERVE')]:
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(runner.WaveBlocked, reason):
                    runner.quota_check(item)
        item = evidence()
        item['rateLimitsByLimitId']['codex']['secondary'] = None
        with self.assertRaisesRegex(runner.WaveBlocked, 'QUOTA_USAGE_UNKNOWN'):
            runner.quota_check(item)
        item['rateLimitsByLimitId']['codex']['primary']['usedPercent'] = None
        with self.assertRaisesRegex(runner.WaveBlocked, 'UNKNOWN'):
            runner.quota_check(item)

    def test_dangling_unknown_and_missing_usage_stop_without_call(self):
        folder = self.attempt()
        for status in ('dangling', 'UNKNOWN_DELIVERY', 'VALID'):
            with self.subTest(status=status):
                if status == 'dangling':
                    (folder / 'result.json').unlink()
                else:
                    write(folder / 'result.json', {'status': status, 'usage': None})
                with patch.object(providers, 'call') as calls:
                    with self.assertRaises(runner.WaveBlocked):
                        runner.run_wave(self.root, 1, evidence())
                    calls.assert_not_called()
                self.assertEqual(read(self.root / 'improvement-status.json')['new_model_calls'], 0)

    def test_user_managed_usage_requires_explicit_frozen_authorization(self):
        with self.assertRaisesRegex(runner.WaveBlocked, 'OFFICIAL'):
            runner.account_usage_policy({'billing': {}}, None)
        billing = {'quota_policy_confirmation': runner.USER_MANAGED_USAGE}
        with self.assertRaisesRegex(runner.WaveBlocked, 'AUTHORIZATION_RECORD'):
            runner.account_usage_policy({'billing': billing}, None)
        billing.update(quota_policy_authorization_record='execution-authorization.json',
                       quota_policy_authorization_recorded_at=datetime.now(timezone.utc).isoformat())
        with patch.object(runner, 'quota_check', side_effect=AssertionError('Must not check account quota')):
            self.assertEqual(runner.account_usage_policy({'billing': billing}, None)['status'], 'USER_MANAGED')

    def test_user_managed_wave_runs_without_quota_and_keeps_api_budget(self):
        self.mutate_config(lambda c: c['billing'].update(
            quota_policy_confirmation=runner.USER_MANAGED_USAGE,
            quota_policy_authorization_record='execution-authorization.json',
            quota_policy_authorization_recorded_at=datetime.now(timezone.utc).isoformat()))
        def fake_call(model, request, folder, timeout):
            result = {'status': 'INVALID_RESPONSE', 'usage': copy.deepcopy(USAGE),
                      'cache_check': {'status': 'VERIFIED_ZERO'}}
            write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), \
             patch.object(providers, 'call', side_effect=fake_call) as calls, \
             patch.object(pipeline.reporting, 'build', return_value={}), \
             patch.object(runner, 'quota_check', side_effect=AssertionError('Must not check account quota')):
            self.assertEqual(runner.run_wave(self.root, 2)['new_model_calls'], 2)
            self.assertEqual(calls.call_count, 2)
            self.mutate_config(lambda c: c['billing'].update(api_budget_usd=.000001))
            with self.assertRaisesRegex(runner.WaveBlocked, 'API_BUDGET'):
                runner.run_wave(self.root, 2)
            self.assertEqual(calls.call_count, 2)

    def test_retry_cap_persists_across_restarts(self):
        self.attempt(status='TRANSIENT_ERROR')
        self.assertGreater(runner.budget_check(self.root, 1)['next_wave_reserved_estimate_usd'], 0)
        self.attempt(number=2, status='TRANSIENT_ERROR')
        with patch.object(providers, 'call') as calls:
            with self.assertRaisesRegex(runner.WaveBlocked, 'TRIAL_RETRY_CAP_REACHED'):
                runner.run_wave(self.root, 1, evidence())
            calls.assert_not_called()
        self.assertEqual(len(call_layout.attempt_dirs(self.root / 'luna-api', self.requests[0])), 2)

    def test_cost_counts_all_attempts_and_reserves_full_output(self):
        self.attempt(status='TRANSIENT_ERROR')
        self.attempt(number=2)
        report = runner.budget_check(self.root, 2)
        self.assertAlmostEqual(report['known_usage_cost_estimate_usd'], .000088)
        self.assertEqual(report['prior_attempts'], 2)
        self.assertEqual(len(report['reserved_requests']), 2)
        self.assertEqual(report['reserved_requests'][0]['max_output_tokens'], self.fixture.config['max_output_tokens'])
        self.mutate_config(lambda c: c['billing'].update(api_budget_usd=.00001))
        with patch.object(providers, 'call') as calls:
            with self.assertRaisesRegex(runner.WaveBlocked, 'API_BUDGET'):
                runner.run_wave(self.root, 2, evidence())
            calls.assert_not_called()
        self.assertTrue(list((self.root / 'improvement-waves').glob('wave-*/cost-block.json')))

    def test_explicit_budget_no_automatic_retries_and_call_cap(self):
        for changed, expected in [({'billing': {}}, 'BUDGET'),
                                  ({'schedule': {'max_rate_limit_attempts': 2}}, 'RETRIES')]:
            config = copy.deepcopy(self.fixture.config)
            config.update(changed)
            with self.assertRaisesRegex(runner.WaveBlocked, expected):
                runner._config(config)
        for maximum in (None, 0, -1, 101, True):
            with self.assertRaisesRegex(runner.WaveBlocked, 'MAX_NEW'):
                runner.run_wave(self.root, maximum, evidence())

    def test_preflight_is_inside_pipeline_lock_and_calls_are_bounded(self):
        calls = []
        def mocked_call(model, request, folder, timeout):
            calls.append(request['trial_id'])
            result = {'status': 'INVALID_RESPONSE', 'usage': copy.deepcopy(USAGE),
                      'schema_errors': ['Offline fixture'], 'cache_check': {'status': 'VERIFIED_ZERO'},
                      'token_cost_estimate_usd': .000044}
            write(folder / 'result.json', result)
            return result
        original = runner.verify_implementation
        def verify_while_locked(root):
            locked = __import__('finarch.experiments.90-operations.storage', fromlist=['locked']).locked
            with self.assertRaisesRegex(RuntimeError, 'ANOTHER_PIPELINE'):
                with locked(root / '.pipeline.lock'):
                    pass
            return original(root)
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), \
             patch.object(providers, 'call', side_effect=mocked_call), \
             patch.object(pipeline.reporting, 'build', return_value={'offline': True}), \
             patch.object(runner, 'verify_implementation', side_effect=verify_while_locked):
            status = runner.run_wave(self.root, 2, evidence())
        self.assertEqual(len(calls), 2)
        self.assertEqual(status['status'], 'WAVE_FINISHED')
        self.assertEqual(status['budget_after']['prior_attempts'], 2)

    def test_unknown_delivery_during_wave_stops_and_next_wave_cannot_resume(self):
        def unknown(model, request, folder, timeout):
            result = {'status': 'UNKNOWN_DELIVERY', 'usage': None}
            write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), \
             patch.object(providers, 'call', side_effect=unknown) as calls, \
             patch.object(pipeline.reporting, 'build', return_value={}):
            with self.assertRaisesRegex(runner.WaveBlocked, 'UNKNOWN_DELIVERY'):
                runner.run_wave(self.root, 100, evidence())
            self.assertEqual(calls.call_count, 1)
            with self.assertRaisesRegex(runner.WaveBlocked, 'UNKNOWN_DELIVERY'):
                runner.run_wave(self.root, 100, evidence())
            self.assertEqual(calls.call_count, 1)

    def test_explicit_second_wave_resumes_one_known_usage_failure(self):
        trial_ids = []
        def transient_then_final(model, request, folder, timeout):
            trial_ids.append(request['trial_id'])
            result = {'status': 'TRANSIENT_ERROR' if len(trial_ids) == 1 else 'INVALID_RESPONSE',
                      'usage': copy.deepcopy(USAGE), 'cache_check': {'status': 'VERIFIED_ZERO'}}
            write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), \
             patch.object(providers, 'call', side_effect=transient_then_final), \
             patch.object(pipeline.reporting, 'build', return_value={}):
            first = runner.run_wave(self.root, 1, evidence())
            second = runner.run_wave(self.root, 1, evidence())
        self.assertEqual(first['new_model_calls'], 1)
        self.assertEqual(second['new_model_calls'], 1)
        self.assertEqual(trial_ids, [self.requests[0]['trial_id']] * 2)
        self.assertEqual(len(call_layout.attempt_dirs(self.root / 'luna-api', self.requests[0])), 2)


if __name__ == '__main__':
    unittest.main()
