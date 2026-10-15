"""Check experiment profiles, wire limits, and backwards-compatible snapshots."""
from copy import deepcopy
import unittest

settings = __import__('finarch.experiments.90-operations.settings', fromlist=['*'])
api = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['*'])
store = settings.store


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.source = store.read(store.PROJECT / 'config/hyperparameter.json')

    def test_shared_shape_and_actual_output_limit(self):
        evaluation, analysis = settings.load(self.source)
        for phase in ('evaluation', 'analysis'):
            self.assertEqual(set(self.source[phase]), {'schedule', 'run'})
        self.assertNotIn('thinking_budget', evaluation)
        self.assertNotIn('prompt_conditions', evaluation)
        self.assertNotIn('prompt_conditions', self.source['evaluation']['run'])
        self.assertEqual(evaluation['models'][0]['output_limits'], {'off': 65536, 'on': 65536})
        self.assertEqual(evaluation['models'][0]['reasoning_efforts'], {'off': 'none', 'on': 'medium'})
        self.assertEqual(analysis['backends']['codex']['model'], 'gpt-6.1-sol')
        self.assertEqual(analysis['backends']['codex']['reasoning_effort'], 'low')
        self.assertEqual(analysis['schedule']['concurrency'], 100)
        self.assertFalse(analysis['schedule']['adaptive']['enabled'])
        self.assertEqual(settings.DEFAULT_CONFIG, store.PROJECT / 'config/hyperparameter.json')
        self.assertNotIn('max_output_tokens', analysis['backends']['codex'])
        forbidden = ('reference_price_per_million', 'price_source', 'prices_checked_on', 'key_file', 'billing')
        for key in forbidden:
            self.assertNotIn('"' + key + '"', store.encoded(self.source).decode())

    def test_selecting_api_uses_independent_sol_profile(self):
        self.source['analysis']['run']['backend'] = 'api'
        _, analysis = settings.load(self.source)
        self.assertEqual(analysis['backends']['api']['max_output_tokens'], 65536)
        self.assertEqual(analysis['backends']['api']['model'], 'gpt-6.1-sol')

    def test_evaluation_defaults_to_batch_and_rejects_synchronous_api(self):
        self.source['evaluation']['run'].pop('transport', None)
        self.assertEqual(settings.load(self.source)[0]['models'][0]['transport'], 'openai_batch')
        self.source['evaluation']['run']['transport'] = 'api'
        with self.assertRaisesRegex(ValueError, 'REQUIRES_BATCH'):
            settings.load(self.source)

    def test_wrong_backend_or_off_profile_is_rejected(self):
        self.source['analysis']['run']['models']['codex'] = 'sol6-max-api'
        with self.assertRaisesRegex(ValueError, 'BACKEND_MISMATCH'):
            settings.load(self.source)
        self.setUp()
        self.source['evaluation']['run']['models']['luna-api']['off'] = 'luna6-medium-api'
        with self.assertRaisesRegex(ValueError, 'OFF_REQUIRES_NONE'):
            settings.load(self.source)

    def test_frozen_expanded_config_does_not_read_changed_profiles(self):
        saved = {'layout_version': 2, 'evaluation': {'models': [{'model': 'saved-model'}], 'max_output_tokens': 8192},
                 'analysis': {'enabled': True, 'backend': 'codex'}}
        expected = deepcopy(saved)
        evaluation, analysis = settings.load(saved, profile_path='/missing/profiles.toml')
        self.assertEqual(evaluation, saved['evaluation'])
        self.assertEqual(analysis, saved['analysis'])
        self.assertEqual(saved, expected)

    def test_cost_is_report_metadata_not_a_request_control(self):
        model = settings.load(self.source)[0]['models'][0]
        self.assertNotIn('reference_price_per_million', model)
        rates, _ = api.accounting(model)
        self.assertEqual(rates['input'], .05)
        self.assertEqual(rates['output'], .25)
        self.assertEqual(api.accounting({**model, 'model': 'unknown'}), (None, None))

    def test_haiku55_max_configuration_is_native_batch_and_on_only(self):
        source = store.read(store.PROJECT / 'config/experiments/finject-haiku5.5-max.json')
        evaluation, analysis = settings.load(source)
        self.assertEqual(evaluation['reasoning_modes'], ['on'])
        self.assertEqual(evaluation['models'][0]['reasoning_efforts'], {'on': 'max'})
        self.assertEqual(evaluation['models'][0]['transport'], 'anthropic_batch')
        self.assertFalse(analysis['enabled'])
        source['evaluation']['reasoning_modes'].append('off')
        source['evaluation']['models'][0]['reasoning_efforts']['off'] = 'max'
        source['evaluation']['models'][0]['output_limits']['off'] = 128000
        with self.assertRaisesRegex(ValueError, 'REASONING_OFF_UNSUPPORTED'):
            settings.load(source)

    def test_haiku55_old_thinking_budget_is_rejected_before_preparation(self):
        source = store.read(store.PROJECT / 'config/experiments/finject-haiku5.5-max.json')
        source['evaluation']['models'][0]['thinking_budget'] = 1024
        with self.assertRaisesRegex(ValueError, 'NOT_THINKING_BUDGET'):
            settings.load(source)



if __name__ == '__main__':
    unittest.main()
