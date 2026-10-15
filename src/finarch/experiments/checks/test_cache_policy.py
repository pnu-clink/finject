"""Offline checks that forbidden caching cannot silently dispatch or score."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
codex_cli = __import__('finarch.experiments.01-evaluation.03-execution.codex_cli', fromlist=['*'])
gemini_batch = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
test_pipeline = __import__('finarch.experiments.checks.test_pipeline', fromlist=['*'])


class CacheUsageTest(unittest.TestCase):
    def test_codex_uses_its_actual_write_counter_not_anthropic_field(self):
        cases = [({'cached_input_tokens': 0, 'cache_write_input_tokens': 0}, 'VERIFIED_ZERO', 0),
                 ({'cached_input_tokens': 0, 'cache_write_input_tokens': 5}, 'CACHE_POLICY_VIOLATION', 5),
                 ({'cached_input_tokens': 8960, 'cache_write_input_tokens': 0}, 'CACHE_POLICY_VIOLATION', 0),
                 ({'cached_input_tokens': 0, 'cache_creation_input_tokens': 0}, 'CACHE_USAGE_UNVERIFIED', None),
                 ({'cached_input_tokens': 0, 'cache_write_input_tokens': False}, 'CACHE_USAGE_UNVERIFIED', False),
                 ({'cached_input_tokens': 0, 'cache_write_input_tokens': -1}, 'CACHE_USAGE_UNVERIFIED', -1)]
        for usage, expected, written in cases:
            with self.subTest(usage=usage):
                check = cache_policy.usage_check('codex_cli', usage)
                self.assertEqual(check['status'], expected)
                self.assertEqual(check['cache_write_tokens'], written)

    def test_positive_or_missing_counters_never_become_zero(self):
        cases = [({'cache_read_input_tokens': 1, 'cache_creation_input_tokens': 0}, 'CACHE_POLICY_VIOLATION'),
                 ({'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 1}, 'CACHE_POLICY_VIOLATION'),
                 ({'cache_read_input_tokens': 0}, 'CACHE_USAGE_UNVERIFIED'),
                 ({'cache_read_input_tokens': False, 'cache_creation_input_tokens': 0}, 'CACHE_USAGE_UNVERIFIED'),
                 (None, 'CACHE_USAGE_UNVERIFIED'),
                 ({'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}, 'VERIFIED_ZERO')]
        for usage, status in cases:
            with self.subTest(usage=usage):
                self.assertEqual(cache_policy.usage_check('claude_code', usage)['status'], status)
        self.assertEqual(cache_policy.usage_check('codex_cli', {'cached_input_tokens': 12})['status'], 'CACHE_POLICY_VIOLATION')
        self.assertEqual(cache_policy.usage_check('codex_cli', {'cached_input_tokens': 0})['status'], 'CACHE_USAGE_UNVERIFIED')

    def test_direct_transports_block_before_credentials_or_network(self):
        with patch.object(__import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*']), 'credential') as key, \
             patch.object(__import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*']).urllib.request, 'urlopen') as url, \
             patch.object(__import__('finarch.experiments.01-evaluation.03-execution.codex_cli', fromlist=['*']).subprocess, 'run') as process:
            for transport in ('codex_cli', 'gemini_free_api', 'gemini_paid_api', 'gemini_batch'):
                with self.assertRaises(cache_policy.CachePolicyError):
                    providers.preflight({'transport': transport})
            with self.assertRaises(cache_policy.CachePolicyError):
                codex_cli.call({'transport': 'codex_cli'}, {}, Path('/unused'), 1)
            with self.assertRaises(cache_policy.CachePolicyError):
                providers.gemini_call({'transport': 'gemini_free_api'}, {}, Path('/unused'), 1)
            with self.assertRaises(cache_policy.CachePolicyError):
                gemini_batch.http({'transport': 'gemini_batch'}, 'models/model:batchGenerateContent', body={})
        key.assert_not_called()
        url.assert_not_called()
        process.assert_not_called()

    def test_claude_environment_disables_cache_even_if_parent_enables_it(self):
        with patch.dict('os.environ', {'DISABLE_PROMPT_CACHING': '0'}):
            self.assertEqual(providers.subscription_environment()['DISABLE_PROMPT_CACHING'], '1')


class CacheDispatchTest(unittest.TestCase):
    def setUp(self):
        self.fixture = test_pipeline.ExperimentsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def prepare(self, transport):
        config = self.fixture.config
        if transport == 'codex_cli':
            config['models'] = [{'key': 'codex-luna', 'model': 'gpt-5.6-luna', 'transport': transport,
                                 'reasoning_efforts': {'off': 'none', 'on': 'medium'}}]
        else:
            config['models'][0]['transport'] = transport
        write(self.fixture.root / 'config.json', {'experiments': config})
        root = self.fixture.prepare()
        model = read(root / 'config.json')['models'][0]
        return root, model

    def test_all_entry_points_block_with_zero_attempts(self):
        for transport in ('codex_cli', 'gemini_free_api', 'gemini_paid_api', 'gemini_batch'):
            with self.subTest(transport=transport):
                # Omitting the policy from configuration cannot waive the global prohibition.
                self.fixture.config.pop('cache_policy', None)
                if transport != 'codex_cli':
                    self.fixture.config['models'] = [{'key': 'gemini-test', 'model': 'gemini-2.5-flash',
                                                       'key_variable': 'UNUSED_KEY', 'transport': transport}]
                root, model = self.prepare(transport)
                with patch.object(__import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*']), 'call') as call, patch.object(__import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['*']), 'http') as http:
                    summary = pipeline.run(root)
                    pipeline.run(root)
                call.assert_not_called()
                http.assert_not_called()
                self.assertEqual(summary['status'], 'CACHE_POLICY_BLOCKED')
                self.assertEqual(summary['models'][0]['attempts'], 0)
                self.assertEqual(summary['models'][0]['statuses'], {'NOT_RUN': 8})
                self.assertEqual(summary['models'][0]['cache_verification']['status'], 'NOT_CALLED')
                self.assertEqual(read(root / model['key'] / 'cache-preflight.json')['delivery_status'], 'NOT_SENT')
                self.assertFalse(list(root.rglob('started.json')))

    def test_received_cached_response_is_preserved_but_not_valid(self):
        root, model = self.prepare('claude_code')
        request = rows(root / model['key'] / '01-requests/manifest.jsonl')[0]
        response = {'status': 'answered', 'answer': '12', 'answer_meta': {'negative': False, 'scale': 'one'},
                    'explanation': '10 + 2 = 12.', 'evidence': []}
        for counter, expected in [(None, 'CACHE_USAGE_UNVERIFIED'), (1, 'CACHE_POLICY_VIOLATION'), (0, 'VALID')]:
            usage = {'input_tokens': 1, 'output_tokens': 1, 'cache_read_input_tokens': 0}
            if counter is not None:
                usage['cache_creation_input_tokens'] = counter
            reply = {'status': 'RECEIVED', 'text': json.dumps(response), 'usage': usage}
            with patch.object(__import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*']), 'claude_call', return_value=reply):
                result = providers.call(model, request, root / ('response-' + str(counter)), 1)
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['response'], response)
            self.assertEqual(result['usage'], usage)

    def test_local_scheduler_stops_on_first_cache_violation(self):
        self.fixture.config['schedule'].update(initial_concurrency=1, monitor_interval_seconds=3,
            cpu_threshold_percent=50, increase_by=1, memory_threshold_percent=85,
            minimum_available_memory_gb=2)
        root, model = self.prepare('codex_cli')
        def fake(model, request, folder, timeout):
            result = {'status': 'CACHE_POLICY_VIOLATION', 'error': 'CACHE_POLICY_VIOLATION',
                      'usage': {'input_tokens': 2, 'cached_input_tokens': 1, 'output_tokens': 1}}
            write(folder / 'result.json', result)
            return result
        with patch.object(__import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*']), 'preflight', return_value={'status': 'READY'}), \
             patch.object(__import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*']), 'call', side_effect=fake) as call:
            summary = pipeline.run(root)
            pipeline.run(root)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(summary['models'][0]['statuses'], {'CACHE_POLICY_VIOLATION': 1, 'NOT_RUN': 7})
        self.assertNotEqual(summary['status'], 'FINISHED')


if __name__ == '__main__':
    unittest.main()
