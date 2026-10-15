"""Offline end-to-end checks for phase paths and independent analysis dispatch."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

fixture_module = __import__('finarch.experiments.checks.test_openai_batch', fromlist=['*'])
review = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_review', fromlist=['*'])
layout = review.run_layout
store = review.store
pipeline = fixture_module.pipeline


class OrderedRunTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.NativeBatchTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.analysis = {'enabled': True, 'backend': 'codex', 'schedule': {'concurrency': 1},
                         'backends': {'codex': {'model': 'gpt-6-sol', 'reasoning_effort': 'max'},
                                      'api': {'model': 'gpt-6-luna', 'reasoning_effort': 'high'}}}
        config = self.fixture.fixture.root / 'new-config.json'
        store.write(config, {'evaluation': self.fixture.fixture.config, 'analysis': self.analysis})
        self.root = pipeline.prepare(config)

    def test_phase_paths_and_private_boundary(self):
        key = self.fixture.model['key']
        self.assertTrue((self.root / '00_input/public.jsonl').exists())
        self.assertTrue((self.root / '01_evaluation/02_request/common.md').exists())
        self.assertTrue((self.root / '01_evaluation/01_preparation/run-readme-template.md').exists())
        self.assertFalse((self.root / '00-definition').exists())
        self.assertFalse((self.root / '01-input').exists())
        self.assertFalse((self.root / key).exists())
        requests = store.rows(layout.requests(self.root, key))
        public = {r['item_id']: {k: v for k, v in r.items() if k != 'item_id'}
                  for r in store.rows(layout.inputs(self.root) / 'public.jsonl')}
        self.assertEqual(len(requests), 8)
        self.assertTrue(all(r['input'] == public[r['item_id']] for r in requests))
        pipeline.verify(self.root)

    def test_collect_then_numeric_analysis_has_separate_files(self):
        key = self.fixture.model['key']
        self.fixture.requests = store.rows(layout.requests(self.root, key))
        self.fixture.remote.update(status='completed', output_file_id='file-output')
        with patch.object(fixture_module.batch, 'http', side_effect=self.fixture.http):
            pipeline.run(self.root)
        rows = store.rows(layout.validation(self.root, key) / 'results.jsonl')
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(r['status'] == 'VALID' for r in rows))
        self.assertTrue(all(r['result_path'].startswith('01_evaluation/03_execution/') for r in rows))
        self.assertTrue(all('numeric_comparison' not in r['checks'] for r in rows))
        diagnostics = store.rows(layout.validation(self.root) / 'numeric-comparisons.jsonl')
        self.assertEqual(sum(bool(r['numeric_comparison']) for r in diagnostics), 4)
        self.assertFalse((self.root / 'analysis').exists())
        pipeline.verify(self.root)

    def test_analysis_model_never_inherits_solver(self):
        folder = review.prepare_input(self.root)
        requests = store.rows(folder / 'manifest.jsonl')
        self.assertTrue(all(r['model'] == 'gpt-6-sol' and r['reasoning_effort'] == 'max' for r in requests))
        self.assertTrue(all(set(r['input']) == {'question', 'context', 'answer_format'} for r in requests))
        runner = __import__('finarch.experiments.02-analysis.legacy.content-analysis.codex_review', fromlist=['*'])
        with patch.object(runner, 'run', return_value={'status': 'COLLECTED'}) as codex, patch.object(review.batch, 'submit') as api:
            review.run_stage(self.root, folder)
        codex.assert_called_once()
        api.assert_not_called()

    def test_api_selection_is_explicit_and_invalid_selection_fails(self):
        raw = store.read(self.root / 'config.json')
        raw['analysis']['backend'] = 'api'
        store.write(self.root / 'config.json', raw)
        self.assertEqual(review.model_for(self.root)['transport'], 'openai_batch')
        self.assertEqual(review.model_for(self.root)['model'], 'gpt-6-luna')
        raw['analysis']['backend'] = 'unknown'
        store.write(self.root / 'config.json', raw)
        with self.assertRaisesRegex(ValueError, 'BACKEND'):
            review.model_for(self.root)

    def test_profile_limit_reaches_frozen_request_and_api_body(self):
        source = store.read(pipeline.PROJECT / 'config/hyperparameter.json')
        source['evaluation']['run']['definition_source_run'] = None
        source['evaluation']['schedule']['dataset'] = {'generated_path': 'mock-generated', 'count': 1}
        selected = pipeline.dataset.select(self.fixture.fixture.config['dataset'])
        config = self.fixture.fixture.root / 'profile-config.json'
        store.write(config, source)
        destination = self.fixture.fixture.root / 'profile-run'
        destination.mkdir()
        with patch.object(pipeline.dataset, 'select', return_value=selected), patch.object(pipeline, 'allocate', return_value=destination):
            root = pipeline.prepare(config)
        model = store.configuration(root)['models'][0]
        requests = store.rows(layout.requests(root, model['key']))
        self.assertEqual(len(requests), 8)
        expected = {(prompt, reasoning) for prompt in ('unguided', 'guided') for reasoning in ('off', 'on')}
        for experiment in (1, 2):
            self.assertEqual({(r['prompt_condition'], r['reasoning']) for r in requests
                              if r['experiment'] == experiment}, expected)
        plan = store.read(layout.plan(root))['models'][0]
        self.assertEqual((plan['experiment1'], plan['experiment2'], plan['requests']), (4, 4, 8))
        for request in requests:
            self.assertNotIn('thinking_budget', request)
            body = fixture_module.batch.api.body_for(model, request)
            self.assertEqual(body['max_output_tokens'], 65536)
            self.assertEqual(body['reasoning']['effort'], 'none' if request['reasoning'] == 'off' else 'medium')
        pipeline.verify(root)


if __name__ == '__main__':
    unittest.main()
