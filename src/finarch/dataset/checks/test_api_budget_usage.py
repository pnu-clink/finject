"""No-network regression checks for call purposes, exact token budgets and costs."""
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
api = __import__('finarch.shared.providers.api', fromlist=['*'])
profiles = __import__('finarch.shared.providers.profiles', fromlist=['*'])
from finarch.shared.providers.structured import ProviderFailure

usage = importlib.import_module('finarch.shared.run_logging.api_usage')
POT = '01-preparation.03-calculation.pot'


def envelope(identifier='resp_test', status='completed'):
    return {'id': identifier, 'status': status, 'usage': {
        'input_tokens': 1000, 'input_tokens_details': {'cached_tokens': 200, 'cache_write_tokens': 100},
        'output_tokens': 500, 'output_tokens_details': {'reasoning_tokens': 300}, 'total_tokens': 1500},
        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{}'}]}]}


class BudgetAndUsageChecks(unittest.TestCase):
    def invoke(self, input_count, result=None, role=POT):
        saved = {}
        profile = profiles.read_profile(profiles.DEFAULT, 'sol-medium-api')
        settings = {'execution_enabled': True, 'policy': {'tools': [], 'skills': []},
                    'model': profile['model'], 'effort': profile['effort'], 'profile': profile, 'timeout_seconds': 1}
        replies = [io.BytesIO(json.dumps({'input_tokens': input_count}).encode()),
                   io.BytesIO(json.dumps(result or envelope()).encode())]
        with patch.object(api, 'api_key', return_value='secret-never-save'), patch.object(api.urllib.request, 'urlopen', side_effect=replies) as http:
            error = None
            try:
                api.complete_api(settings=settings, role=role, payload={'question': 'Q', 'context': 'C'},
                    response_schema={'type': 'object', 'properties': {}}, instruction='Solve.',
                    prompt_selection={}, save=lambda n, v: saved.update({n: v}))
            except ProviderFailure as caught:
                error = str(caught)
        self.assertNotIn('secret-never-save', json.dumps(saved))
        return saved, http, error

    def test_input_and_output_fit_500k_including_schema(self):
        saved, http, error = self.invoke(450000)
        self.assertIsNone(error)
        self.assertEqual(http.call_count, 2)
        count_request, generate_request = [call.args[0] for call in http.call_args_list]
        self.assertTrue(count_request.full_url.endswith('/responses/input_tokens'))
        c, g = json.loads(count_request.data), json.loads(generate_request.data)
        for key in ('model', 'instructions', 'input', 'text', 'reasoning', 'tools', 'truncation'):
            self.assertEqual(c[key], g[key])
        self.assertNotIn('max_output_tokens', c)
        self.assertEqual(g['max_output_tokens'], 50000)
        self.assertEqual(saved['03-result/usage.json']['response_id'], 'resp_test')

    def test_model_output_limit_when_input_small(self):
        saved, _, error = self.invoke(1000)
        self.assertIsNone(error)
        self.assertEqual(saved['01-input.json']['request']['max_output_tokens'], 128000)

    def test_no_generation_when_budget_exhausted_or_count_invalid(self):
        for count in (500000, 510000, None, True, -1):
            with self.subTest(count=count):
                saved, http, error = self.invoke(count)
                self.assertIsNotNone(error)
                self.assertEqual(http.call_count, 1)
                self.assertNotIn('01-input/api-start.json', saved)

    def test_incomplete_response_still_has_cost_and_usage(self):
        saved, _, error = self.invoke(1000, envelope(status='incomplete'))
        self.assertEqual(error, 'API_RESPONSE_INCOMPLETE')
        self.assertIsNotNone(saved['03-result/usage.json']['estimated_cost'])

    def test_actual_over_budget_rejected_after_recording(self):
        result = envelope(); result['usage']['input_tokens'] = 500000; result['usage']['total_tokens'] = 500500
        saved, _, error = self.invoke(1000, result)
        self.assertEqual(error, 'API_REPORTED_TOKEN_BUDGET_EXCEEDED')
        self.assertFalse(saved['03-result/usage.json']['token_budget']['actual_within_budget'])

    def test_cache_write_read_reasoning_cost(self):
        result = usage.estimate_api_cost('gpt-5.6-sol', envelope()['usage'])
        # 700 regular, 200 cached, 100 writes at 1.25x, 500 total output.
        self.assertAlmostEqual(result['estimated_cost'], (700*4+200*.4+100*5+500*20)/1e6)
        self.assertEqual(usage.normalize_usage(envelope()['usage'])['total_tokens'], 1500)
        self.assertIsNone(result['actual_billed_cost'])
    def test_new_model_prices_and_historical_rates_remain_separate(self):
        for model, input_rate, cached_rate, output_rate in (
                ('gpt-6-luna', .1, .01, .5), ('gpt-6.1-sol', 2, .1, 10)):
            result = usage.estimate_api_cost(model, envelope()['usage'])
            self.assertAlmostEqual(result['estimated_cost'],
                                   (700*input_rate + 200*cached_rate + 100*input_rate*1.25 + 500*output_rate)/1e6)
            self.assertIsNone(result['actual_billed_cost'])
        self.assertNotEqual(usage.estimate_api_cost('gpt-5.6-sol', envelope()['usage'])['estimated_cost'],
                            usage.estimate_api_cost('gpt-6.1-sol', envelope()['usage'])['estimated_cost'])

    def test_missing_fields_and_inconsistent_counts_are_not_zero(self):
        self.assertIsNone(usage.estimate_api_cost('gpt-5.6-sol', {'input_tokens': 10, 'output_tokens': 3})['estimated_cost'])
        raw = envelope()['usage']; raw['input_tokens_details']['cached_tokens'] = 9999
        self.assertEqual(usage.estimate_api_cost('gpt-5.6-sol', raw)['cost_status'], 'INCONSISTENT_USAGE')

    def test_aggregate_deduplicates_copies_but_includes_failed_retries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = [usage.usage_record(role=POT, purpose='pot_generation', model='gpt-5.6-sol',
                attempt_id='attempt1', envelope=envelope()),
                usage.usage_record(role=POT, purpose='pot_generation', model='gpt-5.6-sol',
                attempt_id='attempt2', envelope=envelope('resp_retry', 'incomplete')),
                usage.usage_record(role=POT, purpose='pot_generation', model='gpt-5.6-sol',
                attempt_id='attempt3', status='connection_failed')]
            for index, record in enumerate([records[0], records[0], records[1], records[2]]):
                path = root/str(index)/'usage.json'; path.parent.mkdir(); path.write_text(json.dumps(record))
            summary = usage.summarize_run(root)
            self.assertEqual(summary['total']['calls'], 3)
            self.assertEqual(summary['total']['missing_usage_calls'], 1)
            self.assertEqual(summary['total']['failed_or_incomplete_or_unknown'], 2)
            self.assertEqual(summary['total']['token_totals_known']['total_tokens'], 3000)
            self.assertEqual(summary['total']['average_context_tokens'], 1000)
            self.assertEqual(len(summary['duplicates']), 1)
            self.assertTrue((root/'api-usage/README.md').is_file())
            self.assertEqual(usage.summarize_run(root)['total']['calls'], 3)

    def test_purpose_profiles_and_legacy_fallback(self):
        mappings = [(POT, 'pot_generation', 'sol-medium-api'),
            ('01-preparation.02-review-and-correct.revision', 'source_review', 'luna-max-api'),
            ('01-preparation.05-verification.semantic', 'verification', 'luna-max-api'),
            ('shared.01-06.02-04.exception-handler', 'exception_feedback', 'luna-max-api'),
            ('02-generation.02-generate-text.realization', 'text_generation', 'luna-max-api')]
        for role, purpose, expected in mappings:
            selected = profiles.selected_profile(profiles.DEFAULT, role)
            self.assertEqual((selected['purpose'], selected['id']), (purpose, expected))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'profiles.toml'
            path.write_text('[selection]\ngeneration="old"\nvalidation="old"\n[profiles.old]\nargv=["-m","gpt-5.6-luna","-c","model_reasoning_effort=low"]\n')
            self.assertEqual(profiles.selected_profile(path, POT)['id'], 'old')
        with patch.object(__import__('finarch.dataset.90-operations.schedule_settings', fromlist=['*']), 'load_run', return_value={'models': {
            'generation_profile': 'luna-medium', 'validation_profile': 'luna-medium',
            'pot_generation': 'sol-medium-api', 'source_review': 'luna-max-api'}}):
            self.assertEqual(profiles.selected_profile(profiles.DEFAULT, POT, phase='preparation')['id'], 'sol-medium-api')
            shared = profiles.selected_profile(profiles.DEFAULT, 'shared.01-02.02-03.review-and-validation', phase='preparation')
            self.assertEqual(shared['purpose'], 'source_review')


if __name__ == '__main__':
    unittest.main()
