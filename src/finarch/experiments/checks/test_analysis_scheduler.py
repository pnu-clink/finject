"""Check CPU-based admission, frozen-input preservation, and concurrent refill offline."""
import importlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

scheduler = importlib.import_module('finarch.experiments.02-analysis.scheduler')
configuration = importlib.import_module('finarch.experiments.02-analysis.configuration')
backend = importlib.import_module('finarch.experiments.02-analysis.llm_backend')
store = scheduler.store


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = {'schedule': {'concurrency': 20, 'timeout_seconds': 600,
            'adaptive': {'enabled': True, 'interval_seconds': 60,
                         'cpu_threshold_percent': 60, 'growth_percent': 10}}}
        self.now = 0

    def controller(self, samples, total=100):
        return scheduler.Controller(self.root, '02_comparison', self.config, total,
                                    clock=lambda: self.now, cpu=Mock(side_effect=samples))

    def test_a04_timeout_authority_is_one_attempt_and_stage_scoped(self):
        folder = self.root / '02_analysis/04_quadrant'
        attempt = folder / 'calls/q/attempt-001'
        store.write(attempt / 'result.json', {'trial_id': 'q', 'status': 'UNKNOWN_DELIVERY', 'error': 'TIMEOUT'})
        store.write(attempt / 'process.json', {'state': 'TIMEOUT', 'exit_code': -9, 'ended_at': store.now()})
        store.write(folder / 'state.json', {'unresolved_trial_ids': ['q']})
        configuration.authorize_unknown_delivery_retry(self.root, '04_quadrant', ['q'],
            'Resume stalled Analysis through Haiku A04.', self.config)
        self.assertEqual(configuration.authorized_unknown_delivery_retries(self.root, '04_quadrant', self.config), {'q'})
        self.assertEqual(configuration.authorized_unknown_delivery_retries(self.root, '03_research', self.config), set())
        store.write(folder / 'calls/q/attempt-002/result.json', {'status': 'UNKNOWN_DELIVERY', 'error': 'TIMEOUT'})
        self.assertEqual(configuration.authorized_unknown_delivery_retries(self.root, '04_quadrant', self.config), set())

    def test_full_interval_required_and_threshold_is_inclusive(self):
        control = self.controller([0, 60, 59, 61])
        self.now = 59
        control.tick(100)
        self.assertEqual(control.limit, 20)
        self.now = 60
        control.tick(100)
        self.assertEqual(control.limit, 22)
        control.tick(100)
        self.assertEqual(control.limit, 22)
        self.now = 120
        control.tick(100)
        self.assertEqual(control.limit, 25)
        self.now = 180
        control.tick(100)
        self.assertEqual(control.limit, 25)
        self.assertEqual(len(store.rows(self.root / 'events.jsonl')), 3)

    def test_failed_missing_and_nonfinite_cpu_do_not_increase(self):
        for sample in (None, float('nan'), RuntimeError('Unavailable')):
            with self.subTest(sample=sample):
                self.now = 0
                control = self.controller([0, sample])
                self.now = 60
                control.tick(100)
                self.assertEqual(control.limit, 20)
                self.assertIsNone(control.sample['cpu_percent'])

    def test_bounds_remaining_work_and_holds_on_remote_stop(self):
        control = self.controller([0, 10], total=21)
        self.now = 60
        control.tick(21, stopped=True)
        self.assertEqual(control.limit, 20)
        control.tick(21)
        self.assertEqual(control.limit, 21)
        control.publish(10, 11)
        saved = store.read(self.root / '02_analysis/scheduler.json')
        self.assertEqual(saved['current_limit'], 21)
        self.assertEqual(saved['active_calls'], 10)

    def test_frozen_schedule_without_adaptive_remains_fixed(self):
        self.config['schedule'].pop('adaptive')
        control = self.controller([0])
        self.now = 1000
        control.tick(100)
        self.assertEqual(control.limit, 20)

    def test_fixed_limit_still_records_cpu_without_growth(self):
        self.config['schedule']['adaptive']['enabled'] = False
        control = self.controller([0, 10])
        self.now = 60
        control.tick(100)
        self.assertEqual(control.limit, 20)
        self.assertEqual(control.sample['cpu_percent'], 10)

    def test_runtime_override_cannot_change_model_or_frozen_base(self):
        path = self.root / '02_analysis/runtime-schedule.json'
        store.write(path, {'analysis_sha256': store.digest(self.config),
                          'schedule': {'model': 'different'}})
        with self.assertRaisesRegex(ValueError, 'FIELDS_INVALID'):
            scheduler.policy(self.root, self.config)
        store.write(path, {'analysis_sha256': 'changed', 'schedule': {'concurrency': 20}})
        with self.assertRaisesRegex(ValueError, 'BASE_CHANGED'):
            scheduler.policy(self.root, self.config)
        store.write(path, {'analysis_sha256': store.digest(self.config),
                          'schedule': {'concurrency': 7, 'timeout_seconds': 1800}})
        self.assertEqual(scheduler.policy(self.root, self.config)['timeout_seconds'], 1800)

    def test_resumed_runner_starts_parallel_work_without_new_serial_probe(self):
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'max'} for i in range(6)]
        folder = self.root / '02_analysis/02_comparison'
        first = folder / 'calls/0/attempt-001'
        store.write(first / 'request.json', requests[0])
        store.write(first / 'result.json', {'trial_id': '0', 'status': 'VALID'})
        self.config['schedule'] = {'concurrency': 3}
        seen, active = [], 0
        mutex = threading.Lock()
        started = threading.Event()

        def call(req, dest, timeout, validator):
            nonlocal active
            with mutex:
                active += 1
                seen.append(req['trial_id'])
                if active == 3:
                    started.set()
            if not started.wait(3):
                raise RuntimeError('Parallel requests did not start together')
            store.write(dest / 'request.json', req)
            result = {'trial_id': req['trial_id'], 'status': 'VALID'}
            store.write(dest / 'result.json', result)
            with mutex:
                active -= 1
            return result

        with patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), patch.object(backend.codex, 'call', side_effect=call):
            state = backend.run_codex(self.root, folder, requests, self.config)
        self.assertTrue(started.is_set())
        self.assertEqual(state['valid'], 6)
        self.assertEqual(sorted(seen), ['1', '2', '3', '4', '5'])

    def test_fresh_stage_admits_100_calls_before_any_response(self):
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'low'} for i in range(101)]
        folder = self.root / '02_analysis/02_comparison'
        self.config['schedule'] = {'concurrency': 100, 'adaptive': {'enabled': False}}
        started, mutex = threading.Event(), threading.Lock()
        seen = []

        def call(req, dest, timeout, validator):
            with mutex:
                seen.append(req['trial_id'])
                if len(seen) == 100:
                    started.set()
            if not started.wait(10):
                raise RuntimeError('Initial wave waited for a serial response')
            store.write(dest / 'request.json', req)
            result = {'trial_id': req['trial_id'], 'status': 'VALID'}
            store.write(dest / 'result.json', result)
            return result

        with patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), patch.object(backend.codex, 'call', side_effect=call):
            state = backend.run_codex(self.root, folder, requests, self.config)
        self.assertTrue(started.is_set())
        self.assertEqual(state['valid'], 101)
        self.assertEqual(len(set(seen)), 101)
        self.assertNotIn('PROVIDER_PROBE', {row.get('status') for row in store.rows(self.root / 'events.jsonl')})

    def test_growth_admits_calls_even_without_a_completed_response(self):
        self.config['schedule']['concurrency'] = 2
        self.config['schedule']['adaptive']['interval_seconds'] = .05
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'max'} for i in range(5)]
        folder = self.root / '02_analysis/02_comparison'
        first = folder / 'calls/0/attempt-001'
        store.write(first / 'request.json', requests[0])
        store.write(first / 'result.json', {'trial_id': '0', 'status': 'VALID'})
        seen, mutex, grown = [], threading.Lock(), threading.Event()

        def call(req, dest, timeout, validator):
            with mutex:
                seen.append(req['trial_id'])
                if len(seen) >= 3:
                    grown.set()
            if not grown.wait(4):
                raise RuntimeError('Growth waited for a response')
            store.write(dest / 'request.json', req)
            result = {'trial_id': req['trial_id'], 'status': 'VALID'}
            store.write(dest / 'result.json', result)
            return result

        with patch.object(scheduler.psutil, 'cpu_percent', return_value=20), \
             patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), patch.object(backend.codex, 'call', side_effect=call):
            result = backend.run_codex(self.root, folder, requests, self.config)
        self.assertTrue(grown.is_set())
        self.assertEqual(result['valid'], 5)
        self.assertEqual(len(set(seen)), 4)

    def test_saved_timeout_is_never_replayed_while_unsent_work_continues(self):
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'max'} for i in range(3)]
        folder = self.root / '02_analysis/02_comparison'
        for index, status in ((0, 'VALID'), (1, 'UNKNOWN_DELIVERY')):
            dest = folder / f'calls/{index}/attempt-001'
            store.write(dest / 'request.json', requests[index])
            store.write(dest / 'result.json', {'trial_id': str(index), 'status': status, 'error': 'TIMEOUT'})
            store.write(dest / 'process.json', {'state': 'TIMEOUT', 'exit_code': -9, 'ended_at': store.now()})
        def call(req, dest, timeout, validator):
            self.assertEqual(req['trial_id'], '2')
            store.write(dest / 'request.json', req)
            result = {'trial_id': '2', 'status': 'VALID'}
            store.write(dest / 'result.json', result)
            return result
        with patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), patch.object(backend.codex, 'call', side_effect=call) as invoke:
            result = backend.run_codex(self.root, folder, requests, self.config)
        invoke.assert_called_once()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['unresolved_trial_ids'], ['1'])
        self.assertFalse((folder / 'calls/1/attempt-002').exists())

    def test_explicit_timeout_authorization_replays_only_selected_id_once(self):
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'max'} for i in range(3)]
        folder = self.root / '02_analysis/02_comparison'
        for index in (0, 1):
            dest = folder / f'calls/{index}/attempt-001'
            store.write(dest / 'request.json', requests[index])
            store.write(dest / 'result.json', {'trial_id': str(index), 'status': 'UNKNOWN_DELIVERY', 'error': 'TIMEOUT'})
            store.write(dest / 'process.json', {'state': 'TIMEOUT', 'exit_code': -9, 'ended_at': store.now()})
        valid = folder / 'calls/2/attempt-001'
        store.write(valid / 'request.json', requests[2])
        store.write(valid / 'result.json', {'trial_id': '2', 'status': 'VALID'})
        self.config['schedule'] = {'concurrency': 1}
        store.write(folder / 'state.json', {'unresolved_trial_ids': ['0', '1']})
        configuration.authorize_unknown_delivery_retry(self.root, '02_comparison', ['1'], 'User explicitly requested retry.', self.config)
        def call(req, dest, timeout, validator):
            self.assertEqual(req['trial_id'], '1')
            store.write(dest / 'request.json', req)
            result = {'trial_id': '1', 'status': 'VALID'}
            store.write(dest / 'result.json', result)
            return result
        with patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), patch.object(backend.codex, 'call', side_effect=call) as invoke:
            result = backend.run_codex(self.root, folder, requests, self.config)
        invoke.assert_called_once()
        self.assertTrue((folder / 'calls/1/attempt-002/result.json').exists())
        self.assertFalse((folder / 'calls/0/attempt-002').exists())
        self.assertEqual(result['unresolved_trial_ids'], ['0'])

    def test_interrupted_request_is_preserved_while_fresh_calls_start_together(self):
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'low'} for i in range(4)]
        folder = self.root / '02_analysis/02_comparison'
        first = folder / 'calls/0/attempt-001'
        store.write(first / 'request.json', requests[0])
        store.write(first / 'result.json', {'trial_id': '0', 'status': 'UNKNOWN_DELIVERY', 'error': 'INTERRUPTED'})
        store.write(first / 'interruption.json', {'stopped_at': store.now(), 'automatic_replay': False})
        self.config['schedule'] = {'concurrency': 3}
        seen, mutex, together = [], threading.Lock(), threading.Event()

        def call(req, dest, timeout, validator):
            with mutex:
                seen.append(req['trial_id'])
                if len(seen) == 3:
                    together.set()
            if not together.wait(3):
                raise RuntimeError('Unsent work did not start together')
            store.write(dest / 'request.json', req)
            result = {'trial_id': req['trial_id'], 'status': 'VALID'}
            store.write(dest / 'result.json', result)
            return result

        with patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), patch.object(backend.codex, 'call', side_effect=call):
            state = backend.run_codex(self.root, folder, requests, self.config)
        self.assertEqual(sorted(seen), ['1', '2', '3'])
        self.assertEqual(state['valid'], 3)
        self.assertEqual(state['unresolved_trial_ids'], ['0'])
        self.assertEqual(state['status'], 'BLOCKED')
        self.assertFalse((folder / 'calls/0/attempt-002').exists())

    def test_interrupted_retry_requires_dead_pid_and_replays_once(self):
        req = {'trial_id': 'interrupted', 'model': 'fixture', 'reasoning_effort': 'low'}
        folder = self.root / '02_analysis/02_comparison'
        first = folder / 'calls/interrupted/attempt-001'
        store.write(first / 'request.json', req)
        store.write(first / 'result.json', {'trial_id': req['trial_id'], 'status': 'UNKNOWN_DELIVERY', 'error': 'INTERRUPTED'})
        store.write(first / 'interruption.json', {'pid': 12345, 'stopped_at': store.now(), 'automatic_replay': False})
        store.write(folder / 'state.json', {'unresolved_trial_ids': [req['trial_id']]})
        with patch.object(configuration.os, 'kill', return_value=None):
            with self.assertRaisesRegex(ValueError, 'CONFIRMED_PROCESS_END'):
                configuration.authorize_unknown_delivery_retry(self.root, folder.name, [req['trial_id']], 'Retry interrupted request.', self.config)
        with patch.object(configuration.os, 'kill', side_effect=ProcessLookupError):
            configuration.authorize_unknown_delivery_retry(self.root, folder.name, [req['trial_id']], 'Retry interrupted request.', self.config)
        original = (first / 'result.json').read_bytes()

        def call(req, dest, timeout, validator):
            store.write(dest / 'request.json', req)
            result = {'trial_id': req['trial_id'], 'status': 'VALID'}
            store.write(dest / 'result.json', result)
            return result

        with patch.object(backend.codex, 'preflight', return_value={}), patch.object(backend, 'mark_running'), \
             patch.object(backend.codex, 'call', side_effect=call) as invoke:
            self.assertEqual(backend.run_codex(self.root, folder, [req], self.config)['status'], 'COLLECTED')
            backend.run_codex(self.root, folder, [req], self.config)
        invoke.assert_called_once()
        self.assertEqual((first / 'result.json').read_bytes(), original)

    def test_timeout_after_technical_retry_gets_exactly_one_authorized_attempt(self):
        req = {'trial_id': 'case', 'model': 'fixture', 'reasoning_effort': 'max'}
        folder = self.root / '02_analysis/02_comparison'
        first = folder / 'calls/case/attempt-001'
        second = folder / 'calls/case/attempt-002'
        for dest, status in ((first, 'INVALID_RESPONSE'), (second, 'UNKNOWN_DELIVERY')):
            store.write(dest / 'request.json', req)
            store.write(dest / 'result.json', {'trial_id': 'case', 'status': status,
                                                'error': 'TIMEOUT' if status == 'UNKNOWN_DELIVERY' else None})
        store.write(second / 'process.json', {'state': 'TIMEOUT', 'exit_code': -9,
                                             'ended_at': store.now()})
        store.write(folder / 'state.json', {'unresolved_trial_ids': ['case']})
        record = configuration.authorize_unknown_delivery_retry(
            self.root, '02_comparison', ['case'], 'User explicitly requested retry.', self.config)
        self.assertEqual(record['authorized_after_attempt'], {'case': 2})

        def timeout(req, dest, timeout, validator):
            store.write(dest / 'request.json', req)
            store.write(dest / 'process.json', {'state': 'TIMEOUT', 'exit_code': -9,
                                                'ended_at': store.now()})
            result = {'trial_id': req['trial_id'], 'status': 'UNKNOWN_DELIVERY', 'error': 'TIMEOUT'}
            store.write(dest / 'result.json', result)
            return result

        with patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), \
             patch.object(backend.codex, 'call', side_effect=timeout) as invoke:
            first_run = backend.run_codex(self.root, folder, [req], self.config)
            second_run = backend.run_codex(self.root, folder, [req], self.config)
        invoke.assert_called_once()
        self.assertEqual(first_run['status'], 'BLOCKED')
        self.assertEqual(second_run['status'], 'BLOCKED')
        self.assertTrue((folder / 'calls/case/attempt-003/result.json').exists())
        self.assertFalse((folder / 'calls/case/attempt-004').exists())
        next_record = configuration.authorize_unknown_delivery_retry(
            self.root, '02_comparison', ['case'], 'User explicitly requested another retry.', self.config)
        self.assertEqual(next_record['authorized_after_attempt'], {'case': 3})
        self.assertTrue((folder / 'unknown-delivery-retry-002.json').exists())

        def succeed(req, dest, timeout, validator):
            store.write(dest / 'request.json', req)
            result = {'trial_id': req['trial_id'], 'status': 'VALID'}
            store.write(dest / 'result.json', result)
            return result

        with patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), \
             patch.object(backend.codex, 'call', side_effect=succeed) as second_invoke:
            recovered = backend.run_codex(self.root, folder, [req], self.config)
        second_invoke.assert_called_once()
        self.assertEqual(recovered['status'], 'COLLECTED')
        self.assertTrue((folder / 'calls/case/attempt-004/result.json').exists())

    def test_new_unknown_delivery_does_not_stop_fresh_admission(self):
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'max'} for i in range(3)]
        folder = self.root / '02_analysis/02_comparison'
        dest = folder / 'calls/0/attempt-001'
        store.write(dest / 'request.json', requests[0])
        store.write(dest / 'result.json', {'trial_id': '0', 'status': 'VALID'})
        self.config['schedule'] = {'concurrency': 1}
        def call(req, dest, timeout, validator):
            store.write(dest / 'request.json', req)
            result = {'trial_id': req['trial_id'], 'status': 'UNKNOWN_DELIVERY', 'error': 'TIMEOUT'}
            store.write(dest / 'result.json', result)
            return result
        with patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), patch.object(backend.codex, 'call', side_effect=call) as invoke:
            result = backend.run_codex(self.root, folder, requests, self.config)
        self.assertEqual(invoke.call_count, 2)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['unresolved_trial_ids'], ['1', '2'])
        self.assertEqual(result['pending'], 0)

    def test_timeout_refills_100th_slot_before_other_calls_finish(self):
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'low'} for i in range(101)]
        folder = self.root / '02_analysis/02_comparison'
        self.config['schedule'] = {'concurrency': 100}
        initial, replacement = threading.Event(), threading.Event()
        mutex, seen = threading.Lock(), []
        active, replacement_active = 0, []

        def call(req, dest, timeout, validator):
            nonlocal active
            with mutex:
                active += 1
                seen.append(req['trial_id'])
                if len(seen) == 100:
                    initial.set()
                if req['trial_id'] == '100':
                    replacement_active.append(active)
                    replacement.set()
            if req['trial_id'] == '0':
                if not initial.wait(10):
                    raise RuntimeError('Initial concurrency not reached')
                result = {'trial_id': '0', 'status': 'UNKNOWN_DELIVERY', 'error': 'TIMEOUT'}
            else:
                if not replacement.wait(10):
                    raise RuntimeError('Failed slot was not refilled')
                result = {'trial_id': req['trial_id'], 'status': 'VALID'}
            store.write(dest / 'request.json', req)
            store.write(dest / 'result.json', result)
            with mutex:
                active -= 1
            return result

        with patch.object(backend.codex, 'preflight', return_value={}), \
             patch.object(backend, 'mark_running'), patch.object(backend.codex, 'call', side_effect=call):
            state = backend.run_codex(self.root, folder, requests, self.config)
        self.assertEqual(replacement_active, [100])
        self.assertEqual(len(seen), 101)
        self.assertEqual(state['valid'], 100)
        self.assertEqual(state['pending'], 0)
        self.assertEqual(store.read(self.root / '02_analysis/scheduler.json')['deferred_failure_count'], 1)

    def test_slow_result_aggregation_does_not_delay_new_admission(self):
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'low'} for i in range(3)]
        folder = self.root / '02_analysis/02_comparison'
        self.config['schedule'] = {'concurrency': 1}
        aggregation_started, third_started = threading.Event(), threading.Event()
        original = backend.write_state
        writes = []
        def persist(*args):
            writes.append(1)
            if len(writes) == 1:
                aggregation_started.set()
                self.assertTrue(third_started.wait(5), 'Aggregation prevented refill')
            return original(*args)
        def call(req, dest, timeout, validator):
            if req['trial_id'] == '1':
                self.assertTrue(aggregation_started.wait(5))
            if req['trial_id'] == '2':
                third_started.set()
            store.write(dest / 'request.json', req)
            result = {'trial_id': req['trial_id'], 'status': 'VALID'}
            store.write(dest / 'result.json', result)
            return result
        with patch.object(backend.codex, 'preflight', return_value={}), patch.object(backend, 'mark_running'), \
             patch.object(backend.codex, 'call', side_effect=call), patch.object(backend, 'write_state', side_effect=persist):
            state = backend.run_codex(self.root, folder, requests, self.config)
        self.assertEqual(state['status'], 'COLLECTED')
        self.assertTrue(third_started.is_set())

    def test_account_block_stops_new_admission(self):
        requests = [{'trial_id': str(i), 'model': 'fixture', 'reasoning_effort': 'low'} for i in range(3)]
        folder = self.root / '02_analysis/02_comparison'
        self.config['schedule'] = {'concurrency': 1}
        def call(req, dest, timeout, validator):
            store.write(dest / 'request.json', req)
            result = {'trial_id': req['trial_id'], 'status': 'QUOTA_EXHAUSTED'}
            store.write(dest / 'result.json', result)
            return result
        with patch.object(backend.codex, 'preflight', return_value={}), patch.object(backend, 'mark_running'), \
             patch.object(backend.codex, 'call', side_effect=call) as invoke:
            state = backend.run_codex(self.root, folder, requests, self.config)
        invoke.assert_called_once()
        self.assertEqual(state['reason'], 'QUOTA_EXHAUSTED')
        self.assertEqual(state['pending'], 2)


if __name__ == '__main__':
    unittest.main()
