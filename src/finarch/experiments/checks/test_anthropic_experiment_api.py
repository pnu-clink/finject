"""Local request-contract checks; no provider call or credentials required."""

import json
from copy import deepcopy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
body_for = __import__('finarch.experiments.01-evaluation.03-execution.anthropic_api', fromlist=['body_for']).body_for
transport_schema = __import__('finarch.experiments.01-evaluation.03-execution.anthropic_api', fromlist=['transport_schema']).transport_schema
batch = __import__('finarch.experiments.01-evaluation.03-execution.anthropic_batch', fromlist=['*'])
prepare_requests = __import__('finarch.experiments.01-evaluation.02-request.prepare', fromlist=['*']).prepare
store = batch.storage
layout = batch.run_layout


ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()


class AnthropicExperimentApiTests(unittest.TestCase):
    def setUp(self):
        manifest = ROOT / 'reports/experiments-run/20260923-exp-009/luna-api/01-requests/manifest.jsonl'
        self.request = json.loads(manifest.read_text().splitlines()[0])
        self.request['model'] = 'claude-haiku-4-5-20251001'
        self.request['reasoning'] = 'off'
        self.model = {'model': self.request['model'], 'transport': 'anthropic_api'}

    def test_prompt_schema_and_public_input_are_sent_together(self):
        body = body_for(self.model, self.request)
        self.assertEqual(body['system'], self.request['prompt'])
        self.assertEqual(json.loads(body['messages'][0]['content']), self.request['input'])
        self.assertEqual(body['output_config']['format']['type'], 'json_schema')
        self.assertNotIn('cache_control', json.dumps(body))
        self.assertEqual(cache_policy.control(self.model)['status'], 'READY')

    def test_unsupported_provider_constraints_stay_in_local_schema(self):
        local = self.request['response_schema']
        wire = transport_schema(local)
        self.assertIn('maxLength', local['properties']['explanation'])
        self.assertNotIn('maxLength', wire['properties']['explanation'])
        self.assertIn('maxLength=2000', wire['properties']['explanation']['description'])

    def test_nullable_enum_uses_provider_anyof_without_changing_local_contract(self):
        local = self.request['response_schema']
        wire = transport_schema(local)
        scale = wire['properties']['answer_meta']['properties']['scale']
        self.assertEqual(scale['anyOf'], [
            {'type': 'string', 'enum': ['one', 'hundred', 'thousand', 'million',
                                       'billion', 'trillion', 'percent']},
            {'type': 'null'},
        ])
        self.assertEqual(local['properties']['answer_meta']['properties']['scale']['type'],
                         ['string', 'null'])
        self.assertEqual(wire['properties']['answer']['anyOf'],
                         [{'type': 'number'}, {'type': 'null'}])

    def haiku55(self, mode='on', effort='max'):
        request = deepcopy(self.request)
        request.pop('thinking_budget', None)
        request.update(model='claude-haiku-5-5', reasoning=mode, reasoning_effort=effort,
                       thinking_type='adaptive' if mode == 'on' else 'disabled',
                       max_output_tokens=128000)
        model = {'model': request['model'], 'transport': 'anthropic_batch',
                 'reasoning_efforts': {mode: effort}, 'reference_price_per_million': {'input': .05, 'output': .25}}
        return model, request

    def test_haiku55_max_is_sent_with_adaptive_thinking_and_the_json_schema(self):
        model, request = self.haiku55()
        before = deepcopy(request)
        body = body_for(model, request)
        self.assertEqual(body['output_config']['effort'], 'max')
        self.assertEqual(body['thinking'], {'type': 'adaptive'})
        self.assertEqual(body['max_tokens'], 128000)
        self.assertEqual(body['output_config']['format']['type'], 'json_schema')
        self.assertNotIn('budget_tokens', json.dumps(body))
        self.assertEqual(request, before)

    def test_haiku55_off_is_explicit_and_rejects_unsupported_efforts(self):
        model, request = self.haiku55('off', 'high')
        self.assertEqual(body_for(model, request)['thinking'], {'type': 'disabled'})
        for effort in ('xhigh', 'max'):
            model, request = self.haiku55('off', effort)
            with self.assertRaisesRegex(ValueError, 'REASONING_OFF_UNSUPPORTED'):
                body_for(model, request)

    def test_haiku55_missing_or_mismatched_effort_and_old_budget_are_rejected(self):
        model, request = self.haiku55()
        request.pop('reasoning_effort')
        with self.assertRaisesRegex(ValueError, 'SUPPORTED_EFFORT_REQUIRED'):
            body_for(model, request)
        model, request = self.haiku55()
        model['reasoning_efforts']['on'] = 'medium'
        with self.assertRaisesRegex(ValueError, 'EFFORT_MISMATCH'):
            body_for(model, request)
        model, request = self.haiku55()
        request['thinking_budget'] = 1024
        with self.assertRaisesRegex(ValueError, 'NOT_THINKING_BUDGET'):
            body_for(model, request)

    def test_haiku45_keeps_the_original_budget_transport(self):
        self.request.update(reasoning='on', thinking_budget=1024, max_output_tokens=8192)
        body = body_for(self.model, self.request)
        self.assertEqual(body['thinking'], {'type': 'enabled', 'budget_tokens': 1024})
        self.assertNotIn('effort', body['output_config'])

    def prepared_haiku55(self, root):
        config = store.read(ROOT / 'config/experiments/finject-haiku5.5-max.json')['evaluation']
        store.write(root / 'config.json', {'layout_version': 2, 'evaluation': config, 'analysis': {'enabled': False}})
        public = {'item_id': self.request['item_id'], **self.request['input']}
        item = {key: self.request[key] for key in ('item_id', 'case', 'experiment', 'variant')}
        prepare_requests(root, config, [public], {'items': [item]})
        model = config['models'][0]
        return model, store.rows(layout.requests(root, model['key']))

    def test_e02_freezes_effort_and_only_the_supported_conditions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model, requests = self.prepared_haiku55(root)
            self.assertEqual(len(requests), 2)
            self.assertEqual({r['prompt_condition'] for r in requests}, {'unguided', 'guided'})
            for request in requests:
                self.assertEqual(request['reasoning'], 'on')
                self.assertEqual(request['reasoning_effort'], 'max')
                self.assertNotIn('thinking_budget', request)
                self.assertEqual(body_for(model, request)['output_config']['effort'], 'max')
            self.assertEqual(len(batch.split_requests(model, requests)[0]), 2)
            with self.assertRaisesRegex(ValueError, 'CONDITION_BATCH_PILOT_REQUIRED'):
                batch.split_requests(model, requests[:1])

    def test_two_condition_pilot_failure_preserves_responses_and_blocks_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model, requests = self.prepared_haiku55(root)
            folder = layout.batches(root, model['key']) / 'batch-001'
            job = {'status': 'SUBMITTED', 'batch_id': 'msgbatch-offline-test',
                   'provider': {'processing_status': 'ended', 'request_counts': {'succeeded': 2}}}
            store.write(folder / 'job.json', job)
            records = {}
            for request in requests:
                record = {'custom_id': request['trial_id'], 'result': {'type': 'succeeded', 'message': {
                    'id': 'msg-offline-test', 'model': model['model'], 'stop_reason': 'end_turn',
                    'content': [{'type': 'text', 'text': '{}'}],
                    'usage': {'input_tokens': 10, 'output_tokens': 2, 'cache_read_input_tokens': 0,
                              'cache_creation_input_tokens': 0}}}}
                records[request['trial_id']] = (record, json.dumps(record))
            state = {'models': {model['key']: {}}}
            with patch.object(batch, 'prepare_job', return_value=job), patch.object(batch, 'submit', return_value=job), \
                    patch.object(batch, 'poll', return_value=job), patch.object(batch, 'result_records', return_value=records), \
                    patch.object(batch.layout, 'publish'):
                result = batch.process_chunk(root, model, state, requests, folder, pilot=True)
            self.assertEqual(result['result_status'], 'PILOT_INVALID')
            self.assertEqual(len(list(root.rglob('raw-response.json'))), 2)
            for saved in root.rglob('result.json'):
                self.assertEqual(store.read(saved)['reasoning_effort_requested'], 'max')

    def test_haiku45_batch_keeps_the_four_condition_pilot(self):
        requests = []
        for prompt in ('unguided', 'guided'):
            for reasoning in ('off', 'on'):
                request = deepcopy(self.request)
                request.update(prompt_condition=prompt, reasoning=reasoning, thinking_budget=1024,
                               trial_id=f'{prompt}-{reasoning}')
                requests.append(request)
        self.assertEqual(len(batch.split_requests(self.model, requests)[0]), 4)


if __name__ == '__main__':
    unittest.main()
