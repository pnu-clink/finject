"""Offline execution checks for explicit cap changes and safe Evaluation resume."""
import copy
import unittest
from unittest.mock import patch

base = __import__('finarch.experiments.checks.test_orca_experiment_api', fromlist=['*'])
budget = __import__('finarch.experiments.01-evaluation.03-execution.output_budget', fromlist=['*'])
runner = __import__('finarch.experiments.pipeline', fromlist=['*'])
store, layout, pipeline, orca = base.store, base.layout, base.pipeline, base.orca
calls = pipeline.call_layout


class OutputBudgetTest(unittest.TestCase):
    def setUp(self):
        fixture = base.fixtures.ExperimentsTest()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        model = copy.deepcopy(base.MODEL)
        model['output_limits'] = {'off': 65536, 'on': 65536}
        fixture.config.update(models=[model], reasoning_modes=['off', 'on'], max_output_tokens=65536)
        store.write(fixture.root / 'config.json', {'experiments': fixture.config})
        self.root = fixture.prepare()
        self.requests = store.rows(layout.requests(self.root, model['key']))
        self.key = model['key']
        self.execution = layout.execution(self.root, self.key)
        base.policy.authorize_orca(self.root, self.key, 'User approved this offline fixture.')

    def configure(self, maximum=384000, probed=True):
        value = budget.configure(self.root, self.key, 'Use 8194 tokens; increase only truncated requests.', maximum=maximum)
        if probed:
            state = store.read(self.root / 'state.json')
            state['models'][self.key].update(first_call_checked=True, validated_reasoning_modes=['off', 'on'])
            store.write(self.root / 'state.json', state)
        return value

    def seed(self, index, result):
        folder = calls.attempt_path(self.execution, self.requests[index], 1)
        store.write(folder / 'request.json', self.requests[index])
        store.write(folder / 'started.json', {'at': store.now()})
        store.write(folder / 'result.json', result)
        return folder

    def received(self, request, finish='stop'):
        raw = base.envelope(10 if request['reasoning'] == 'on' else 0)
        raw['choices'][0]['finish_reason'] = finish
        return raw

    def execute(self, finish_for=None, **kwargs):
        seen = []
        def transport(model, request, folder, timeout):
            wire = orca.body_for(model, request)
            seen.append((request['trial_id'], wire['max_tokens']))
            result = finish_for(request, folder) if finish_for else 'stop'
            if isinstance(result, dict):
                return result
            raw = self.received(request, result)
            store.write(folder / 'provider-request-wire.json', wire)
            store.write(folder / 'raw-response.json', raw)
            return orca.parse_response(raw, 200, {}, request)
        with patch.object(base.providers, 'preflight', return_value={'status': 'READY'}), \
                patch.object(orca, 'call', side_effect=transport):
            summary = pipeline.run(self.root, **kwargs)
        return seen, summary

    def test_only_length_retries_increase_cap_and_preserve_frozen_and_prior_bytes(self):
        self.configure()
        trial = self.requests[0]['trial_id']
        frozen_hash = store.file_hash(layout.requests(self.root, self.key))
        seen, summary = self.execute(lambda request, folder: 'length' if request['trial_id'] == trial and folder.name == 'attempt-001' else 'stop')
        self.assertEqual([cap for identity, cap in seen if identity == trial], [8194, 16388])
        self.assertTrue(all(cap == 8194 for identity, cap in seen if identity != trial))
        self.assertEqual(summary['models'][0]['statuses'], {'VALID': 8})
        self.assertEqual(store.read(self.root / 'state.json')['models'][self.key]['concurrency'], 3)
        attempts = calls.attempt_dirs(self.execution, self.requests[0])
        hashes = {str(path): store.file_hash(path) for path in attempts[0].iterdir() if path.is_file()}
        derived = store.read(attempts[1] / 'request.json')
        derived.pop('output_budget')
        derived['max_output_tokens'] = self.requests[0]['max_output_tokens']
        self.assertEqual(derived, self.requests[0])
        self.execute()
        self.assertEqual(hashes, {str(path): store.file_hash(path) for path in attempts[0].iterdir() if path.is_file()})
        self.assertEqual(frozen_hash, store.file_hash(layout.requests(self.root, self.key)))
        store.verify(self.root)

    def test_existing_65536_length_result_gets_131072_without_rewriting_attempt(self):
        old = self.seed(0, {'status': 'OUTPUT_TRUNCATED', 'finish_reason': 'length', 'http_status': 200,
                            'delivery_status': 'RECEIVED', 'usage': None})
        before = {str(p): store.file_hash(p) for p in old.iterdir()}
        self.configure()
        seen, _ = self.execute()
        self.assertEqual([cap for trial, cap in seen if trial == self.requests[0]['trial_id']], [131072])
        self.assertEqual(before, {str(p): store.file_hash(p) for p in old.iterdir()})

    def test_format_failures_and_uncertain_deliveries_are_never_replayed(self):
        for index, result in enumerate([
                {'status': 'INVALID_RESPONSE', 'finish_reason': 'stop', 'usage': None},
                {'status': 'UNKNOWN_DELIVERY', 'delivery_status': 'UNKNOWN', 'usage': None},
                {'status': 'LOCAL_ERROR', 'error_type': 'ConnectionResetError', 'usage': None},
                {'status': 'AUTH_BLOCKED', 'delivery_status': 'UNKNOWN', 'error': 'uncertain', 'usage': None}]):
            self.seed(index, result)
        self.configure()
        seen, _ = self.execute(resume_limits=True)
        self.assertEqual({trial for trial, _ in seen}, {r['trial_id'] for r in self.requests[4:]})
        self.assertTrue(all(cap == 8194 for _, cap in seen))
        self.assertTrue(all(len(calls.attempt_dirs(self.execution, r)) == 1 for r in self.requests[:4]))

    def test_explicit_auth_rejection_requires_resume_and_uses_new_base(self):
        self.seed(0, {'status': 'AUTH_BLOCKED', 'delivery_status': 'REJECTED', 'error': 'key limit', 'usage': None})
        self.configure()
        seen, _ = self.execute()
        self.assertEqual(seen, [])
        seen, _ = self.execute(resume_limits=True)
        self.assertEqual(dict(seen)[self.requests[0]['trial_id']], 8194)

    def test_escalated_limit_survives_restart_and_rejected_attempt(self):
        self.configure()
        seen, _ = self.execute(lambda request, folder: 'length', max_new=1)
        self.assertEqual(seen[0][1], 8194)
        rejected = {'status': 'AUTH_BLOCKED', 'delivery_status': 'REJECTED', 'error': 'key limit', 'usage': None}
        seen, _ = self.execute(lambda request, folder: rejected, max_new=1)
        self.assertEqual(seen[0][1], 16388)
        seen, summary = self.execute(resume_limits=True)
        self.assertEqual(dict(seen)[self.requests[0]['trial_id']], 16388)
        self.assertEqual(summary['models'][0]['statuses'], {'VALID': 8})

    def test_maximum_stops_length_retries_with_final_failure_visible(self):
        self.configure(maximum=16388)
        trial = self.requests[0]['trial_id']
        seen, summary = self.execute(lambda request, folder: 'length' if request['trial_id'] == trial else 'stop')
        self.assertEqual([cap for identity, cap in seen if identity == trial], [8194, 16388])
        self.assertEqual(summary['models'][0]['statuses'], {'OUTPUT_TRUNCATED': 1, 'VALID': 7})
        seen, _ = self.execute()
        self.assertEqual(seen, [])

    def test_length_probe_can_retry_before_broad_wave(self):
        self.configure(probed=False)
        trial = self.requests[0]['trial_id']
        seen, summary = self.execute(lambda request, folder: 'length' if request['trial_id'] == trial and folder.name == 'attempt-001' else 'stop')
        self.assertEqual(seen[:2], [(trial, 8194), (trial, 16388)])
        self.assertEqual(summary['models'][0]['statuses'], {'VALID': 8})
        self.assertEqual(store.read(self.root / 'state.json')['models'][self.key]['validated_reasoning_modes'], ['off', 'on'])

    def test_policy_requires_authorization_and_cannot_widen_silently(self):
        with self.assertRaisesRegex(ValueError, 'AUTHORIZATION_REQUIRED'):
            budget.configure(self.root, self.key, '')
        self.assertFalse((self.root / 'runtime-overrides.json').exists())
        self.configure(maximum=16388)
        with self.assertRaisesRegex(ValueError, 'DIFFERENT_LIMITS'):
            budget.configure(self.root, self.key, 'Same user request.', maximum=32776)

    def test_root_resume_runs_evaluation_only_and_records_actual_coordinator(self):
        self.seed(0, {'status': 'AUTH_BLOCKED', 'delivery_status': 'REJECTED', 'error': 'key limit', 'usage': None})
        self.configure()
        state = store.read(self.root / 'state.json')
        state['status'] = 'INCOMPLETE'
        store.write(self.root / 'state.json', state)
        def transport(model, request, folder, timeout):
            self.assertEqual(orca.body_for(model, request)['max_tokens'], 8194)
            return orca.parse_response(self.received(request), 200, {}, request)
        numeric = __import__('finarch.experiments.01-evaluation.04-validation.numeric_validation', fromlist=['*'])
        with patch.object(base.providers, 'preflight', return_value={'status': 'READY'}), \
                patch.object(orca, 'call', side_effect=transport), patch.object(runner.analysis, 'run') as analyze, \
                patch.object(numeric, 'build'), patch.object(runner, 'next_run') as next_run:
            with self.assertRaisesRegex(ValueError, 'EVALUATION_REQUIRES_REVIEW'):
                runner.collect_when_ready(self.root)
            runner.run(self.root, evaluation_only=True, resume_limits=True)
        analyze.assert_not_called()
        next_run.assert_not_called()
        saved = store.read(self.root / 'state.json')
        self.assertEqual(saved['full_pipeline']['status'], 'EVALUATION_COMPLETE')
        self.assertEqual(saved['queued_execution']['pid'], runner.os.getpid())
        self.assertGreater(saved['queued_execution']['process_started_at'], 0)


if __name__ == '__main__':
    unittest.main()
