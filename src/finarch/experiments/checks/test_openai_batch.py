"""Offline checks for native Batch submission, recovery and exact result joins."""
import copy
import json
import unittest
from unittest.mock import patch

fixture_module = __import__('finarch.experiments.checks.test_pipeline', fromlist=['*'])
batch = __import__('finarch.experiments.01-evaluation.03-execution.openai_batch', fromlist=['*'])
pipeline = fixture_module.pipeline
storage = batch.storage


class NativeBatchTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.ExperimentsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.model = {'key': 'luna-batch', 'model': 'gpt-6-luna', 'transport': 'openai_batch',
            'reasoning_efforts': {'off': 'none', 'on': 'medium'},
            'reference_price_per_million': {'input': .05, 'output': .25, 'cached_input': .005, 'cache_write_input': .0625},
            'price_source': 'https://developers.openai.com/api/docs/models/gpt-6-luna'}
        self.fixture.config.update(models=[self.model],
            definition_source_run=str(pipeline.PROJECT / 'src/finarch/experiments/checks/fixtures/experiment-v6'),
            response_contract='FinancialAnswerV6')
        storage.write(self.fixture.root / 'config.json', {'experiments': self.fixture.config})
        self.root = self.fixture.prepare()
        self.requests = storage.rows(self.root / 'luna-batch/01-requests/manifest.jsonl')
        self.folder = self.root / 'luna-batch/02-batches/batch-001'
        self.posts = []
        self.remote = {'id': 'batch-test', 'input_file_id': 'file-input', 'status': 'in_progress',
                       'output_file_id': None, 'error_file_id': None, 'request_counts': {'total': 8, 'completed': 0, 'failed': 0}}

    def wire_output(self, request):
        answer = {'answer': 12, 'answer_meta': {'negative': False, 'scale': 'one'},
                  'explanation': '10 + 2 = 12.', 'evidence': ['Amount A is 10.']}
        return {'custom_id': request['trial_id'], 'error': None, 'response': {'status_code': 200, 'request_id': 'req-test',
            'body': {'id': request['trial_id'], 'status': 'completed', 'model': 'gpt-6-luna',
                'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(answer)}]}],
                'usage': {'input_tokens': 100, 'output_tokens': 40,
                          'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                          'output_tokens_details': {'reasoning_tokens': 10}}}}}

    def http(self, model, suffix, **kwargs):
        if kwargs.get('body') is not None:
            self.posts.append(suffix)
        if suffix == 'files':
            return {'id': 'file-input'}
        if suffix in ('batches', 'batches/batch-test'):
            return copy.deepcopy(self.remote)
        if suffix == 'files/file-output/content':
            return ''.join(json.dumps(self.wire_output(request)) + '\n' for request in reversed(self.requests))
        if suffix == 'batches?limit=100':
            return {'data': [copy.deepcopy(self.remote)], 'has_more': False}
        raise AssertionError(suffix)

    def test_native_submission_is_not_repeated_and_collects_by_custom_id(self):
        with patch.object(batch, 'http', side_effect=self.http):
            pipeline.run(self.root)
            self.assertEqual(storage.read(self.root / 'state.json')['status'], 'BATCH_PENDING')
            self.remote.update(status='completed', output_file_id='file-output')
            pipeline.run(self.root)
            pipeline.run(self.root)
        self.assertEqual(self.posts, ['files', 'batches'])
        summary = storage.read(self.root / 'summary.json')['models'][0]
        self.assertEqual(summary['statuses'], {'VALID': 8})
        self.assertEqual(summary['attempts'], 8)
        self.assertEqual(summary['input_tokens'], 800)
        self.assertEqual(summary['output_tokens_including_thinking'], 320)
        self.assertAlmostEqual(summary['paid_batch_usage_cost_estimate_usd'], 8 * (100 * .05 + 40 * .25) / 1e6)
        self.assertEqual(summary['paid_api_usage_cost_estimate_usd'], 0)
        self.assertIsNone(summary['billed_cost_usd'])
        self.assertEqual(storage.read(self.folder / 'job.json')['status'], 'COLLECTED')

    def test_unknown_create_is_reconciled_without_another_paid_submission(self):
        manifest = self.root / 'luna-batch/01-requests/manifest.jsonl'
        job = batch.prepare_job(self.model, manifest, self.folder, self.requests, batch.api.body_for)
        storage.write(self.folder / 'job.json', {**job, 'status': 'UNKNOWN_SUBMISSION', 'input_file_id': 'file-input'})
        with patch.object(batch, 'http', side_effect=self.http):
            result = batch.submit(self.model, self.folder)
        self.assertEqual(result['batch_id'], 'batch-test')
        self.assertEqual(self.posts, [])

    def test_partitioned_jobs_collect_every_request_once(self):
        chunks = batch.split_requests(self.model, self.requests, max_count=3)
        self.assertEqual([len(c) for c in chunks], [3, 3, 2])
        remotes, file_chunks, posts = {}, {}, []
        def http(model, suffix, **kwargs):
            body = kwargs.get('body')
            if body is not None:
                posts.append(suffix)
            if suffix == 'files':
                key = f'file-{len(file_chunks)+1}'
                file_chunks[key] = chunks[len(file_chunks)]
                return {'id': key}
            if suffix == 'batches':
                key = f'batch-{len(remotes)+1}'
                remote = {'id': key, 'input_file_id': body['input_file_id'], 'status':'completed',
                          'output_file_id': key+'-output', 'error_file_id': None,
                          'request_counts': {'total':len(file_chunks[body['input_file_id']]),
                            'completed':len(file_chunks[body['input_file_id']]), 'failed':0}}
                remotes[key] = remote
                return remote
            if suffix.startswith('batches/'):
                return remotes[suffix.split('/')[1]]
            if suffix.startswith('files/'):
                remote = remotes[suffix.split('/')[1].removesuffix('-output')]
                return ''.join(json.dumps(self.wire_output(req))+'\n' for req in file_chunks[remote['input_file_id']])
            raise AssertionError(suffix)
        with patch.object(batch,'split_requests',return_value=chunks), patch.object(batch,'http',side_effect=http):
            pipeline.run(self.root)
            pipeline.run(self.root)
        self.assertEqual(len(posts),6)
        state=storage.read(self.root/'state.json')
        self.assertEqual(state['status'],'FINISHED')
        self.assertEqual(state['models'][self.model['key']]['request_counts']['completed'],8)
        self.assertEqual(storage.read(self.root/'summary.json')['models'][0]['attempts'],8)

    def test_unknown_result_ids_and_changed_wire_are_rejected(self):
        manifest = self.root / 'luna-batch/01-requests/manifest.jsonl'
        batch.prepare_job(self.model, manifest, self.folder, self.requests, batch.api.body_for)
        record = self.wire_output(self.requests[0])
        record['custom_id'] = 'not-planned'
        storage.write_rows(self.folder / 'output.jsonl', [record])
        with self.assertRaisesRegex(ValueError, 'BATCH_CUSTOM_ID_SET_MISMATCH'):
            batch.outputs(self.folder, {r['trial_id'] for r in self.requests})
        storage.write_text(self.folder / 'input.jsonl', '{}\n')
        with self.assertRaisesRegex(ValueError, 'FROZEN_BATCH_INPUT_CHANGED'):
            batch.prepare_job(self.model, manifest, self.folder, self.requests, batch.api.body_for)

    def test_nonzero_cache_and_missing_cache_counts_are_never_scored_valid(self):
        record = self.wire_output(self.requests[0])
        record['response']['body']['usage']['input_tokens_details']['cached_tokens'] = 5
        result = batch.interpret(self.model, self.requests[0], record, batch.answer_format.response_errors)
        self.assertEqual(result['status'], 'CACHE_POLICY_VIOLATION')
        del record['response']['body']['usage']['input_tokens_details']['cache_write_tokens']
        record['response']['body']['usage']['input_tokens_details']['cached_tokens'] = 0
        result = batch.interpret(self.model, self.requests[0], record, batch.answer_format.response_errors)
        self.assertEqual(result['status'], 'CACHE_USAGE_UNVERIFIED')
        self.assertIsNone(result['token_cost_estimate_usd'])

    def test_auxiliary_message_never_corrupts_final_phase_json(self):
        record = self.wire_output(self.requests[0])
        message = record['response']['body']['output'][0]
        message['phase'] = 'final_answer'
        record['response']['body']['output'].insert(0, {'type': 'message', 'phase': 'commentary',
            'content': [{'type': 'output_text', 'text': 'Intermediate commentary is not final JSON.'}]})
        result = batch.interpret(self.model, self.requests[0], record, batch.answer_format.response_errors)
        self.assertEqual(result['status'], 'VALID')
        self.assertEqual(result['response']['answer'], 12)
        self.assertEqual(json.loads(batch.layout.response_text(record))['answer'], 12)


if __name__ == '__main__':
    unittest.main()
