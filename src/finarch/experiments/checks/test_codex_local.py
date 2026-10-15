"""Offline Codex envelope, resource thresholds and subscription checks."""
import json
import os
import unittest
from unittest.mock import patch

environment = __import__('finarch.experiments.01-evaluation.03-execution.codex_cli', fromlist=['environment']).environment
parse = __import__('finarch.experiments.01-evaluation.03-execution.codex_cli', fromlist=['parse']).parse
next_limit = __import__('finarch.experiments.01-evaluation.03-execution.local_schedule', fromlist=['next_limit']).next_limit
precision_conflict = __import__('finarch.experiments.01-evaluation.04-validation.numeric_analysis', fromlist=['precision_conflict']).precision_conflict
response_diagnostics = __import__('finarch.experiments.01-evaluation.04-validation.numeric_analysis', fromlist=['response_diagnostics']).response_diagnostics


class CodexLocalTest(unittest.TestCase):
    def test_threshold_and_memory_block(self):
        settings = {'concurrency': 200, 'increase_by': 50, 'cpu_threshold_percent': 50,
                    'memory_threshold_percent': 85, 'minimum_available_memory_gb': 2}
        sample = {'cpu_percent': 49, 'memory_percent': 60, 'available_memory_bytes': 4 * 1024 ** 3}
        self.assertEqual(next_limit(50, sample, settings), (100, False))
        self.assertEqual(next_limit(150, sample, settings), (200, False))
        self.assertEqual(next_limit(200, sample, settings), (200, False))
        self.assertEqual(next_limit(50, dict(sample, cpu_percent=50), settings), (50, False))
        self.assertEqual(next_limit(100, dict(sample, memory_percent=85), settings), (50, True))
        self.assertEqual(next_limit(50, dict(sample, available_memory_bytes=1024 ** 3), settings), (1, True))

    def test_subscription_environment_removes_api_keys(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test', 'CODEX_API_KEY': 'test'}):
            self.assertNotIn('OPENAI_API_KEY', environment())
            self.assertNotIn('CODEX_API_KEY', environment())

    def test_events_preserve_usage_and_last_response(self):
        body = {'status': 'answered', 'answer': '12.6', 'answer_meta': {'negative': True, 'scale': 'million'},
                'explanation': 'The difference is negative.', 'evidence': []}
        events = [{'type': 'thread.started', 'thread_id': 'test'}, {'type': 'turn.started'},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(body)}},
                  {'type': 'turn.completed', 'usage': {'input_tokens': 100, 'cached_input_tokens': 20, 'output_tokens': 30}}]
        raw = '\n'.join(json.dumps(e) for e in events)
        result = parse(raw)
        self.assertEqual(result['status'], 'RECEIVED')
        self.assertEqual(result['usage']['cached_input_tokens'], 20)
        self.assertEqual(json.loads(result['text']), body)
        events.insert(2, {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'cat private'}})
        self.assertEqual(parse('\n'.join(json.dumps(e) for e in events))['status'], 'TRANSPORT_ERROR')

    def test_provider_limits_and_unsupported_configuration(self):
        for message, expected in [('You have hit your usage limit', 'QUOTA_EXHAUSTED'),
                                  ('Too many requests: 429', 'RATE_LIMITED'),
                                  ('Reasoning effort none is not supported', 'LOCAL_PREFLIGHT_REJECTED')]:
            result = parse(json.dumps({'type': 'turn.failed', 'error': {'message': message}}), returncode=1)
            self.assertEqual(result['status'], expected)

    def test_failure_diagnostics_do_not_change_scoring_status(self):
        row = {'experiment': 1, 'status': 'INVALID_RESPONSE'}
        result = {'response': {'status': 'answered', 'answer': '40.0',
                              'answer_meta': {'negative': True, 'scale': 'million'}},
                  'schema_errors': [{'message': 'Use an unsigned decimal string with exactly 2 decimal places; no symbols or separators.'}]}
        tags, relaxed = response_diagnostics(row, result, {'reference_answer': '-40'})
        self.assertIn('DECIMAL_PLACES_MISMATCH', tags)
        self.assertIn('INVALID_FORMAT_BUT_EQUAL_NUMERIC_VALUE', tags)
        self.assertTrue(relaxed['matches'])
        self.assertFalse(relaxed['changes_score'])
        self.assertEqual(row['status'], 'INVALID_RESPONSE')

    def test_explicit_question_precision_is_audited_without_rewriting_input(self):
        request = {'input': {'question': 'Calculate the value. Answer to three decimal places.',
                             'answer_format': {'decimal_places': 1}}}
        diagnostic = precision_conflict(request)
        self.assertEqual(diagnostic['question_decimal_places'], [3])
        self.assertEqual(diagnostic['supplied_decimal_places'], 1)
        self.assertEqual(request['input']['answer_format']['decimal_places'], 1)
        request['input']['question'] = 'How much?'
        self.assertIsNone(precision_conflict(request))
        request['input']['question'] = 'Answer to one decimal place.'
        self.assertIsNone(precision_conflict(request))


class CodexScheduleTest(unittest.TestCase):
    def setUp(self):
        from finarch.experiments.checks.test_pipeline import ExperimentsTest
        write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
        self.fixture = ExperimentsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        config = self.fixture.config
        config['models'] = [{'key': 'codex-luna', 'model': 'gpt-5.6-luna', 'transport': 'codex_cli',
                             'reasoning_efforts': {'off': 'none', 'on': 'medium'}}]
        config['schedule'].update(initial_concurrency=2, monitor_interval_seconds=3,
            cpu_threshold_percent=50, increase_by=50, memory_threshold_percent=85,
            minimum_available_memory_gb=2)
        write(self.fixture.root / 'config.json', {'experiments': config})
        self.root = self.fixture.prepare()

    def test_reporting_distinguishes_codex_zero_writes_from_missing_usage(self):
        call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
        reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])
        rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
        write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
        base = self.root / 'codex-luna'
        request = rows(base / '01-requests/manifest.jsonl')[0]
        for written, expected, records in [(None, None, 0), (0, 0, 1), (7, 7, 1)]:
            with self.subTest(written=written):
                usage = {'input_tokens': 100, 'cached_input_tokens': 20, 'output_tokens': 30}
                if written is not None:
                    usage['cache_write_input_tokens'] = written
                write(call_layout.attempt_path(base, request, 1) / 'result.json',
                      {'status': 'INVALID_RESPONSE', 'transport': 'codex_cli', 'usage': usage})
                summary = reporting.build(self.root)['models'][0]
                self.assertEqual(summary['cache_creation_tokens'], expected)
                self.assertEqual(summary['attempts_with_cache_write_usage'], records)
                self.assertEqual(summary['input_tokens'], 100)
                self.assertEqual(summary['cache_read_tokens'], 20)

    def test_local_resume_preserves_completed_calls_and_cached_usage(self):
        pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
        providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
        read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
        write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
        called = []

        def fake(model, request, folder, timeout):
            called.append(request['trial_id'])
            result = {'status': 'VALID', 'transport': 'codex_cli', 'billing_mode': 'CODEX_SUBSCRIPTION',
                      'response': {'status': 'answered', 'answer': '12', 'answer_meta': {'negative': False, 'scale': 'one'},
                                   'explanation': '10 + 2 = 12.', 'evidence': []},
                      'usage': {'input_tokens': 100, 'cached_input_tokens': 20, 'output_tokens': 30}}
            write(folder / 'result.json', result)
            return result

        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), patch.object(providers, 'call', side_effect=fake):
            pipeline.run(self.root, max_new=1)
            pipeline.run(self.root)
            pipeline.run(self.root)
        summary = read(self.root / 'summary.json')
        self.assertEqual(summary['status'], 'FINISHED')
        self.assertEqual(len(called), 8)
        self.assertEqual(len(set(called)), 8)
        model = summary['models'][0]
        self.assertEqual(model['input_tokens'], 800)
        self.assertEqual(model['cache_read_tokens'], 160)
        self.assertEqual(model['output_tokens_including_thinking'], 240)
        self.assertEqual(model['incremental_api_charge_usd'], 0)
        self.assertIsNone(model['api_equivalent_usd'])
        self.assertTrue((self.root / 'ANALYSIS.md').exists())

    def test_local_quota_stops_without_repeating_uncertain_delivery(self):
        pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
        providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
        call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
        read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
        rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
        write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
        base = self.root / 'codex-luna'
        request = rows(base / '01-requests/manifest.jsonl')[0]
        write(call_layout.attempt_path(base, request, 1) / 'started.json', {'transport': 'codex_cli'})

        def fake(model, request, folder, timeout):
            result = {'status': 'QUOTA_EXHAUSTED', 'usage': None}
            write(folder / 'result.json', result)
            return result

        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), patch.object(providers, 'call', side_effect=fake) as call:
            pipeline.run(self.root)
            pipeline.run(self.root)
        self.assertEqual(call.call_count, 1)
        model = read(self.root / 'state.json')['models']['codex-luna']
        self.assertEqual(model['status'], 'QUOTA_EXHAUSTED')
        self.assertEqual(model['unresolved_trial_ids'], [request['trial_id']])


if __name__ == '__main__':
    unittest.main()
