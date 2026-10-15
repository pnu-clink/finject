"""Exercise bounded A02 recovery offline, including successful-call preservation."""
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

recovery = importlib.import_module('finarch.experiments.02-analysis.recovery')
backend = importlib.import_module('finarch.experiments.02-analysis.llm_backend')
store = recovery.store
fixture = importlib.import_module('finarch.experiments.checks.test_analysis_pipeline')


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / '02_analysis/02_comparison'
        self.config = {'backend': 'codex', 'schedule': {'concurrency': 100}, 'technical_retry_limit': 1}
        self.requests = [{'trial_id': name, 'model': 'gpt-6.1-sol', 'reasoning_effort': 'low'}
                         for name in ('valid', 'capacity', 'timeout')]
        store.write(self.root / 'state.json', {})
        for req, status, error in zip(self.requests, ('VALID', 'PROVIDER_ERROR', 'UNKNOWN_DELIVERY'),
                (None, 'Selected model is at capacity. Please try a different model.', 'TIMEOUT')):
            dest = self.folder / 'calls' / req['trial_id'] / 'attempt-001'
            store.write(dest / 'request.json', req)
            store.write(dest / 'result.json', {'trial_id': req['trial_id'], 'status': status, 'error': error})
            store.write(dest / 'process.json', {'state': 'TIMEOUT', 'ended_at': 'fixture', 'exit_code': -9})
        self.config_patch = patch.object(recovery.configuration, 'read', return_value=self.config)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.policy = recovery.configure(self.root, 'User authorized bounded retries.')
        self.clock = 0
        self.delays = []

    def test_auth_retry_requires_explicit_scope_and_ended_process(self):
        req = self.requests[1]
        result = {'status': 'AUTH_BLOCKED'}
        self.assertIsNone(recovery.reason(self.folder, req, result))
        self.assertEqual(recovery.reason(self.folder, req, result, ['AUTH_BLOCKED']), 'ENDED_AUTH_BLOCK')
        store.write(self.folder / 'calls/capacity/attempt-001/process.json', {'state': 'RUNNING'})
        self.assertIsNone(recovery.reason(self.folder, req, result, ['AUTH_BLOCKED']))

    def sleep(self, seconds):
        self.clock += seconds

    def run_recovery(self, call):
        def run(root, stage, requests, *, recovery_retry_ids):
            self.delays.append(self.clock)
            return backend.run_codex(root, self.folder, requests, self.config,
                                     recovery_retry_ids=recovery_retry_ids)
        state = backend.write_state(self.root, self.folder, self.requests, 'codex')
        with patch.object(recovery.time, 'time', side_effect=lambda: self.clock), \
             patch.object(recovery.time, 'sleep', side_effect=self.sleep), \
             patch.object(backend, 'run', side_effect=run), patch.object(backend, 'mark_running'), \
             patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend.codex, 'call', side_effect=call):
            return recovery.recover(self.root, '02_comparison', self.requests, state, backend)

    def response(self, req, dest, timeout, validator, *, status='VALID'):
        store.write(dest / 'request.json', req)
        result = {'trial_id': req['trial_id'], 'status': status, 'error': 'Selected model is at capacity.'}
        store.write(dest / 'result.json', result)
        return result

    def test_only_two_failures_retried_and_all_old_attempts_preserved(self):
        originals = {p: p.read_bytes() for p in self.folder.glob('calls/*/attempt-001/*')}
        calls = []
        def call(req, dest, timeout, validator):
            calls.append(req['trial_id'])
            return self.response(req, dest, timeout, validator)
        result = self.run_recovery(call)
        self.assertEqual(result['status'], 'COLLECTED')
        self.assertEqual(sorted(calls), ['capacity', 'timeout'])
        self.assertEqual(self.delays, [60])
        self.assertTrue(all(p.read_bytes() == value for p, value in originals.items()))
        self.assertFalse((self.folder / 'calls/valid/attempt-002').exists())

    def test_recovery_waits_for_fresh_queue_and_running_calls_to_drain(self):
        for pending, active, queued in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            with self.subTest(pending=pending, active=active, queued=queued):
                state = backend.write_state(self.root, self.folder, self.requests, 'codex')
                state['pending'] = pending
                store.write(self.root / '02_analysis/scheduler.json', {
                    'stage': '02_comparison', 'active_calls': active, 'queued_calls': queued})
                with patch.object(backend, 'run') as invoke:
                    self.assertEqual(recovery.recover(self.root, '02_comparison', self.requests, state, backend), state)
                invoke.assert_not_called()
                self.assertFalse((self.folder / 'retry-rounds').exists())

    def test_saved_retry_wait_queue_can_resume_its_existing_round(self):
        store.write(self.root / '02_analysis/scheduler.json', {'stage': '02_comparison',
                    'status': 'RETRY_WAIT', 'active_calls': 0, 'queued_calls': 2})
        result = self.run_recovery(self.response)
        self.assertEqual(result['status'], 'COLLECTED')
        self.assertEqual(self.delays, [60])

    def test_global_account_block_preserves_retry_budget(self):
        state = backend.write_state(self.root, self.folder, self.requests, 'codex')
        state.update(status='BLOCKED', reason='QUOTA_EXHAUSTED')
        with patch.object(backend, 'run') as invoke:
            self.assertEqual(recovery.recover(self.root, '02_comparison', self.requests, state, backend), state)
        invoke.assert_not_called()
        self.assertFalse((self.folder / 'retry-rounds').exists())

    def test_managed_validation_failure_waits_until_fresh_requests_finish(self):
        store.write(self.root / '02_analysis/runtime-schedule.json', {
            'analysis_sha256': store.digest(self.config), 'schedule': {'concurrency': 1}})
        recovery.configure(self.root, 'Retry accumulated validation failures.', include_validation_failures=True)
        fresh = {'trial_id': 'fresh', 'model': 'gpt-6.1-sol', 'reasoning_effort': 'low'}
        requests = [fresh, {**fresh, 'trial_id': 'next'}]
        calls = []
        def call(req, dest, timeout, validator):
            calls.append(req['trial_id'])
            status = 'INVALID_RESPONSE' if req['trial_id'] == 'fresh' and len(calls) == 1 else 'VALID'
            return self.response(req, dest, timeout, validator, status=status)
        def run(root, stage, requests, *, recovery_retry_ids):
            schedule = store.read(root / '02_analysis/scheduler.json')
            self.assertEqual(schedule['status'], 'RETRY_WAIT')
            self.assertEqual(schedule['active_calls'], 0)
            self.assertEqual(schedule['queued_calls'], len(recovery_retry_ids))
            return backend.run_codex(root, self.folder, requests, self.config, recovery_retry_ids=recovery_retry_ids)
        with patch.object(backend, 'mark_running'), patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend.codex, 'call', side_effect=call), \
             patch.object(recovery.time, 'time', side_effect=lambda: self.clock), \
             patch.object(recovery.time, 'sleep', side_effect=self.sleep), patch.object(backend, 'run', side_effect=run):
            state = backend.run_codex(self.root, self.folder, requests, self.config)
            self.assertEqual(calls, ['fresh', 'next'])
            schedule = store.read(self.root / '02_analysis/scheduler.json')
            self.assertEqual((schedule['queued_calls'], schedule['active_calls']), (0, 0))
            state = recovery.recover(self.root, '02_comparison', requests, state, backend)
        self.assertEqual(calls, ['fresh', 'next', 'fresh'])
        self.assertEqual(state['status'], 'COLLECTED')

    def test_three_round_budget_survives_restart_and_policy_configuration(self):
        result = self.run_recovery(lambda *args, **kwargs: self.response(*args, **kwargs, status='PROVIDER_ERROR'))
        self.assertEqual(result['reason'], 'ANALYSIS_RETRY_LIMIT_REACHED')
        self.assertEqual(self.delays, [60, 180, 420])
        self.assertEqual(recovery.configure(self.root, 'Repeated start.'), self.policy)
        self.run_recovery(lambda *args, **kwargs: self.fail('Exhausted budget replayed a request'))
        self.assertEqual(len(list(self.folder.glob('retry-rounds/*.json'))), 3)
        self.assertEqual(len(backend.attempts(self.folder, self.requests[1])), 4)

    def test_auth_quota_interruption_and_unconfirmed_timeout_are_excluded(self):
        req = self.requests[2]
        result = backend.latest(self.folder, req)
        for status, error in [('AUTH_BLOCKED', 'at capacity'), ('QUOTA_EXHAUSTED', 'at capacity'),
                              ('UNKNOWN_DELIVERY', 'INTERRUPTED'), ('UNKNOWN_DELIVERY', 'connection reset'),
                              ('PROVIDER_ERROR', 'invalid model')]:
            self.assertIsNone(recovery.reason(self.folder, req, {'status': status, 'error': error}))
        store.write(self.folder / 'calls/timeout/attempt-001/process.json', {'state': 'TIMEOUT'})
        self.assertIsNone(recovery.reason(self.folder, req, result))

    def test_scoped_validation_retry_is_one_attempt_and_excludes_other_ids_and_stages(self):
        for req in self.requests:
            for number in (1, 2):
                dest = self.folder / 'calls' / req['trial_id'] / f'attempt-{number:03d}'
                store.write(dest / 'request.json', req)
                store.write(dest / 'result.json', {'trial_id': req['trial_id'],
                            'status': 'VALID' if req['trial_id'] == 'valid' else 'INVALID_RESPONSE'})
                store.write(dest / 'process.json', {'state': 'EXITED', 'ended_at': 'fixture', 'exit_code': 0})
        store.write_rows(self.folder / 'manifest.jsonl', self.requests)
        policy = recovery.configure(self.root, 'Retry capacity only once.', include_validation_failures=True,
                                    validation_trial_ids=['capacity'], validation_stage='02_comparison')
        self.assertEqual(policy['policy_id'], self.policy['policy_id'])
        self.assertNotIn('additional_retry_statuses', policy)
        calls = []
        def call(req, dest, timeout, validator):
            calls.append(req['trial_id'])
            return self.response(req, dest, timeout, validator, status='INVALID_RESPONSE')
        result = self.run_recovery(call)
        self.assertEqual(calls, ['capacity'])
        self.assertNotEqual(result['status'], 'COLLECTED')
        self.run_recovery(lambda *a, **kw: self.fail('Consumed scoped authority was replayed'))
        self.assertEqual(recovery.allowed_statuses(policy, self.folder, self.requests[1]), [])
        other = self.root / '02_analysis/03_research'
        self.assertEqual(recovery.allowed_statuses(policy, other, self.requests[1]), [])

    def test_authorized_capacity_does_not_block_unsent_requests(self):
        fresh = {'trial_id': 'fresh', 'model': 'gpt-6.1-sol', 'reasoning_effort': 'low'}
        requests = self.requests + [fresh]
        calls = []
        def call(req, dest, timeout, validator):
            calls.append(req['trial_id'])
            return self.response(req, dest, timeout, validator)
        with patch.object(backend, 'mark_running'), patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend.codex, 'call', side_effect=call):
            state = backend.run_codex(self.root, self.folder, requests, self.config)
        self.assertEqual(calls, ['fresh'])
        self.assertEqual(state['pending'], 0)
        self.assertFalse((self.folder / 'calls/capacity/attempt-002').exists())

    def test_saved_validation_failure_is_deferred_without_bypassing_retry_scope(self):
        req = self.requests[1]
        store.write(self.folder / 'calls/capacity/attempt-001/result.json', {
            'trial_id': req['trial_id'], 'status': 'INVALID_RESPONSE'})
        fresh = {**req, 'trial_id': 'fresh'}
        calls = []
        def call(req, dest, timeout, validator):
            calls.append(req['trial_id'])
            return self.response(req, dest, timeout, validator)
        with patch.object(backend, 'mark_running'), patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend.codex, 'call', side_effect=call):
            state = backend.run_codex(self.root, self.folder, self.requests + [fresh], self.config)
        self.assertEqual(calls, ['fresh'])
        self.assertEqual(state['pending'], 0)
        self.assertEqual(len(backend.attempts(self.folder, req)), 1)

    def test_noneligible_failure_does_not_prevent_eligible_retry_or_enter_a03(self):
        path = self.folder / 'calls/timeout/attempt-001/process.json'
        store.write(path, {'state': 'RUNNING'})
        calls = []
        def call(req, dest, timeout, validator):
            calls.append(req['trial_id'])
            return self.response(req, dest, timeout, validator)
        result = self.run_recovery(call)
        self.assertEqual(calls, ['capacity'])
        self.assertNotEqual(result['status'], 'COLLECTED')

    def test_pause_during_backoff_prevents_transmission(self):
        def sleep(seconds):
            self.clock += seconds
            store.write(self.root / 'state.json', {'execution_control': {'analysis': {'paused': True}}})
        with patch.object(self, 'sleep', side_effect=sleep):
            result = self.run_recovery(lambda *args, **kwargs: self.fail('Paused retry transmitted'))
        self.assertEqual(result['status'], 'PAUSED_BY_USER')

    def test_changed_frozen_model_is_rejected(self):
        self.config['model'] = 'another model'
        with self.assertRaisesRegex(ValueError, 'POLICY_CONFIG_CHANGED'):
            self.run_recovery(lambda *args, **kwargs: self.fail('Changed config transmitted'))

    def test_started_round_is_not_blindly_replayed(self):
        store.write(self.folder / 'retry-rounds/round-001.json', {
            'policy_id': self.policy['policy_id'], 'status': 'STARTED'})
        result = self.run_recovery(lambda *args, **kwargs: self.fail('Unconfirmed round replayed'))
        self.assertEqual(result['reason'], 'RETRY_ROUND_DELIVERY_UNCONFIRMED')

    def test_validation_extension_preserves_used_round_and_waits_120_seconds(self):
        path = self.folder / 'retry-rounds/round-001.json'
        store.write(path, {'policy_id': self.policy['policy_id'], 'status': 'FINISHED'})
        original_round = path.read_bytes()
        for req in self.requests[1:]:
            dest = self.folder / 'calls' / req['trial_id'] / 'attempt-001/result.json'
            value = store.read(dest)
            value['status'] = 'INVALID_RESPONSE' if req['trial_id'] == 'capacity' else 'VALID'
            store.write(dest, value)
        self.assertIsNone(recovery.reason(self.folder, self.requests[1], backend.latest(self.folder, self.requests[1])))
        extended = recovery.configure(self.root, 'Retry validation failures and A03.',
            include_validation_failures=True, include_research=True)
        self.assertEqual(extended['policy_id'], self.policy['policy_id'])
        self.assertIn('03_research', extended['stages'])
        calls = []
        def call(req, dest, timeout, validator):
            calls.append(req['trial_id'])
            return self.response(req, dest, timeout, validator)
        result = self.run_recovery(call)
        self.assertEqual(result['status'], 'COLLECTED')
        self.assertEqual(calls, ['capacity'])
        self.assertEqual(self.delays, [120])
        self.assertEqual(path.read_bytes(), original_round)
        self.assertEqual(len(list((self.root / '02_analysis').glob('retry-policy-extension-*.json'))), 1)

    def test_research_wait_is_published_as_a03(self):
        record = {'round': 1, 'trial_ids': ['failed'], 'not_before_epoch': 60}
        recovery.publish_wait(self.root, self.root / '02_analysis/03_research', {'status': 'PARTIAL'}, record)
        self.assertEqual(store.read(self.root / 'state.json')['analysis']['stage'], 'A03')

    def test_quadrant_policy_extension_preserves_budget_and_wait_stage(self):
        extended = recovery.configure(self.root, 'Monitor through Haiku A04.', include_quadrant=True)
        self.assertEqual(extended['policy_id'], self.policy['policy_id'])
        self.assertEqual(extended['max_rounds'], self.policy['max_rounds'])
        self.assertIn('04_quadrant', extended['stages'])
        record = {'round': 1, 'trial_ids': ['failed'], 'not_before_epoch': 60}
        recovery.publish_wait(self.root, self.root / '02_analysis/04_quadrant', {'status': 'PARTIAL'}, record)
        self.assertEqual(store.read(self.root / 'state.json')['analysis']['stage'], 'A04')

    def test_quadrant_capacity_retry_preserves_valid_calls(self):
        recovery.configure(self.root, 'Monitor through Haiku A04.', include_quadrant=True)
        folder = self.root / '02_analysis/04_quadrant'
        self.folder.rename(folder)
        calls = []
        def run(root, stage, requests, *, recovery_retry_ids):
            calls.extend(sorted(recovery_retry_ids))
            for req in requests:
                if req['trial_id'] in recovery_retry_ids:
                    self.response(req, folder / 'calls' / req['trial_id'] / 'attempt-002', 1800, None)
            return backend.write_state(root, folder, requests, 'codex')
        state = backend.write_state(self.root, folder, self.requests, 'codex')
        with patch.object(recovery.time, 'time', side_effect=lambda: self.clock), \
             patch.object(recovery.time, 'sleep', side_effect=self.sleep), \
             patch.object(backend, 'run', side_effect=run):
            result = recovery.recover(self.root, '04_quadrant', self.requests, state, backend)
        self.assertEqual(result['status'], 'COLLECTED')
        self.assertEqual(calls, ['capacity', 'timeout'])
        self.assertFalse((folder / 'calls/valid/attempt-002').exists())


class PipelineRecoveryGateTest(unittest.TestCase):
    def test_pipeline_retries_capacity_before_collecting_and_entering_a03(self):
        example = fixture.AnalysisPipelineTest()
        example.setUp()
        self.addCleanup(example.doCleanups)
        root = example.root
        # Freeze the Analysis selection without executing any model call.
        recovery.configuration.freeze(root)
        recovery.configure(root, 'User authorized bounded A02 and A03 retries.',
                           include_validation_failures=True, include_research=True)
        clock = [0]
        calls = []
        def call(req, dest, timeout, validator):
            calls.append(req['stage'])
            if len(calls) in (1, 3):
                store.write(dest / 'request.json', req)
                value = {'trial_id': req['trial_id'],
                    'status': 'PROVIDER_ERROR' if len(calls) == 1 else 'INVALID_RESPONSE',
                    'error': 'Selected model is at capacity.' if len(calls) == 1 else 'ASSESSMENT_QUOTE_NOT_IN_SOURCE'}
                store.write(dest / 'result.json', value)
                return value
            return example.call(req, dest, timeout, validator)
        with patch.object(recovery.time, 'time', side_effect=lambda: clock[0]), \
             patch.object(recovery.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
             patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend.codex, 'call', side_effect=call):
            result = fixture.analysis.run(root)
        self.assertEqual(calls, ['02_comparison', '02_comparison', '03_research', '03_research', '04_quadrant'])
        self.assertEqual(result['status'], 'COLLECTED')
        summary = store.read(root / '02_analysis/02_comparison/response-assessment-summary.json')
        self.assertEqual(summary['overall']['review_status'], {'COMPLETED': 4})
        research_round = store.read(root / '02_analysis/03_research/retry-rounds/round-001.json')
        self.assertEqual(research_round['status'], 'FINISHED')
        self.assertEqual(research_round['delay_seconds'], 60)


if __name__ == '__main__':
    unittest.main()
