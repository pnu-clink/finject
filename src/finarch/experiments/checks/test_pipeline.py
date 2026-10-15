"""Offline regression checks: isolation, selection, costs, and safe resume."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

dataset = __import__('finarch.experiments.00-input.dataset', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])
allocate = __import__('finarch.experiments.90-operations.storage', fromlist=['allocate']).allocate
encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_rows = __import__('finarch.experiments.90-operations.storage', fromlist=['write_rows']).write_rows
request_order = __import__('finarch.experiments.01-evaluation.02-request.request_order', fromlist=['*'])


class ExperimentsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.original = {'id': 'test-0001', 'question': 'What is 10 plus 2?', 'context': 'Amount A is 10. Amount B is 2.',
                         'reference_answer': '12', 'reference_answer_type': 'integer', 'reference_precision': 0}
        write(self.root / 'input.json', [self.original])
        prep = {'input_id': 'test-0001', 'status': 'PASS', 'human_decision': 'PENDING'}
        write(self.source / '01-preparation/summary.json', {'results': [prep]})
        write(self.source / '01-preparation/test-0001/run.json', prep)
        observation = {'question': self.original['question'], 'context': self.original['context'] + ' Amount A is 11.'}
        folder = self.source / '02-generation/01-round/test-0001/01-value'
        item = {'label': 'IC_VALUE_01_BEFORE', 'status': 'PASS', 'path': str(folder.relative_to(self.source))}
        write(folder / 'run.json', item)
        write(folder / '02-generate-text/04-observation.json', observation)
        write(folder / '03-validation/03-result.json', {'status': 'PASS', 'human_decision': 'PENDING',
            'observation_sha256': hashlib.sha256(json.dumps(observation, sort_keys=True, separators=(',', ':')).encode()).hexdigest()})
        write(folder / '03-validation/04-comparison.json', {'working': observation, 'reference': dataset.qc(self.original)})
        write(self.source / '02-generation/summary.json', {'latest': {'test-0001': {'0': item}}})
        config = pipeline.settings.load(read(pipeline.PROJECT / 'config/hyperparameter.json'))[0]
        self.config = copy.deepcopy(config)
        self.config['definition_source_run'] = str(pipeline.PROJECT / 'src/finarch/experiments/checks/fixtures/experiment-v4')
        self.config['response_contract'] = 'FinancialAnswerMagnitudeV4'
        self.config['dataset'].pop('reuse_input_run', None)
        self.config['dataset'].pop('require_collected_results', None)
        self.config['dataset'].pop('require_generated', None)
        self.config['dataset'].pop('generated_path', None)
        self.config.update(max_output_tokens=8192, thinking_budget=2048, billing={})
        self.config['models'] = [{'key': 'gemini-test', 'model': 'gemini-2.5-flash', 'transport': 'gemini_free_api',
            'key_variable': 'GEMINI_API_KEY_TEST', 'key_file': str(self.root / 'nonexistent.env'),
            'reference_price_per_million': {'input': .15, 'output': 1.25, 'cached_input': .03}}]
        self.config['dataset'].update(source_run=str(self.source), input_path=str(self.root / 'input.json'), count=1,
                                      require_all_variants_pass=False)
        self.config.update(output_root=str(self.root / 'runs'))
        self.config['models'] = self.config['models'][:1]
        self.config['models'][0]['transport'] = 'gemini_free_api'
        self.config['schedule'].update(concurrency=3, fallback_group_size=1, retry_delay_seconds=0,
                                       timeout_seconds=300, max_rate_limit_attempts=2)
        write(self.root / 'config.json', {'experiments': self.config})

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self):
        return pipeline.prepare(self.root / 'config.json')

    def test_selection_includes_automatic_pending_but_never_rejected(self):
        public, private, selection = dataset.select(self.config['dataset'])
        self.assertEqual(selection['variants'], 1)
        self.assertEqual(set(public[0]), {'item_id', 'question', 'context', 'answer_format'})
        self.assertTrue(all(row['answer_format'] == {'decimal_places': 0} for row in public))
        self.assertEqual(len(selection['exclusions']), 6)
        self.assertEqual(private[0]['reference']['reference_answer'], '12')
        p = self.source / '01-preparation/test-0001/run.json'
        write(p, {**read(p), 'human_decision': 'REJECTED'})
        with self.assertRaisesRegex(ValueError, 'INSUFFICIENT'):
            dataset.select(self.config['dataset'])

    def test_collected_results_keep_types_aligned_and_detect_tampering(self):
        root = self.source / 'results'
        prepared = {**self.original, 'question': 'What is the prepared amount?'}
        originals = [{'id': 'test-0001', 'status': 'PASS', 'input': prepared}]
        files = {}
        write(root / '00-input.json', originals)
        files['00-input.json'] = {'sha256': dataset.file_hash(root / '00-input.json')}
        for label, filename in zip(dataset.LABELS, dataset.RESULT_FILES):
            source = '02-generation/01-round/test-0001/01-value'
            record = {'id': 'test-0001', 'type': label, 'status': 'NOT_RUN', 'result': None}
            if label == dataset.LABELS[0]:
                record.update(status='PASS', result=source, question=self.original['question'],
                              context=self.original['context'] + ' Amount A is 11.')
            write(root / filename, [record])
            files[filename] = {'sha256': dataset.file_hash(root / filename)}
        write(root / 'manifest.json', {'source_run': self.source.name,
                                      'selected_count': 1, 'files': files})
        self.assertEqual(dataset.collected_results(self.source)[0], [prepared])
        self.config['dataset']['require_collected_results'] = True
        public, private, selection = dataset.select(self.config['dataset'])
        self.assertEqual(selection['variants'], 1)
        self.assertEqual(public[0]['question'], prepared['question'])
        self.assertEqual(public[1]['context'], self.original['context'] + ' Amount A is 11.')
        summary_path = self.source / '02-generation/summary.json'
        saved_summary = read(summary_path)
        changed_summary = copy.deepcopy(saved_summary)
        changed_summary['latest']['test-0001']['0']['status'] = 'FAIL'
        write(summary_path, changed_summary)
        with self.assertRaisesRegex(ValueError, 'RESULTS_GENERATION_STATUS_CHANGED'):
            dataset.select(self.config['dataset'])
        write(summary_path, saved_summary)
        write(root / dataset.RESULT_FILES[0], [{'id': 'test-0002', 'type': dataset.LABELS[0]}])
        with self.assertRaisesRegex(ValueError, 'RESULTS_FILE_HASH_MISMATCH'):
            dataset.collected_results(self.source)

    def test_required_collected_results_cannot_fall_back_or_reuse_old_input(self):
        self.config['dataset']['require_collected_results'] = True
        with self.assertRaisesRegex(ValueError, 'CONSOLIDATED_RESULTS_REQUIRED'):
            dataset.select(self.config['dataset'])
        self.config['dataset']['reuse_input_run'] = 'reports/experiments-run/old'
        write(self.root / 'config.json', {'experiments': self.config})
        with self.assertRaisesRegex(ValueError, 'CONSOLIDATED_RESULTS_CANNOT_REUSE'):
            self.prepare()

    def test_empty_schema_and_private_leak_fail_before_call(self):
        root = self.prepare()
        request = rows(root / self.config['models'][0]['key'] / '01-requests/manifest.jsonl')[0]
        self.assertEqual(len(rows(root / self.config['models'][0]['key'] / '01-requests/manifest.jsonl')), 8)
        with self.assertRaisesRegex(ValueError, 'SCHEMA'):
            providers.validate_request({**request, 'response_schema': {}})

        with self.assertRaisesRegex(ValueError, 'PRIVATE'):
            providers.validate_request({**request, 'input': {**request['input'], 'reference_answer': '12'}})
        for mode, expected in [('off', 0), ('on', 2048)]:
            self.assertEqual(providers.gemini_body({**request, 'reasoning': mode})['generationConfig']['thinkingConfig']['thinkingBudget'], expected)
        command = providers.claude_command(request)
        schema = json.loads(command[command.index('--json-schema') + 1])
        self.assertNotIn('$schema', schema)
        self.assertEqual(schema['properties'], request['response_schema']['properties'])

    def test_request_uses_complete_public_even_without_private_reference(self):
        public, private, selection = dataset.select(self.config['dataset'])
        for row in public:
            row['answer_format'] = {'decimal_places': 2}
        for row in private:
            row.pop('reference')
        with patch.object(dataset, 'select', return_value=(public, private, selection)):
            root = self.prepare()
        expected = {row['item_id']: {k: v for k, v in row.items() if k != 'item_id'} for row in public}
        requests = rows(root / self.config['models'][0]['key'] / '01-requests/manifest.jsonl')
        for request in requests:
            self.assertEqual(request['input'], expected[request['item_id']])
            wire = providers.gemini_body(request)
            self.assertEqual(json.loads(wire['contents'][0]['parts'][0]['text']), expected[request['item_id']])

    def test_model_manifests_replace_selection_file_and_keep_audit_log(self):
        self.config['models'].append({**self.config['models'][0], 'key': 'second-model'})
        write(self.root / 'config.json', {'experiments': self.config})
        root = self.prepare()
        self.assertFalse((root / 'input-selection.json').exists())
        self.assertNotIn('input-selection.json', read(root / 'manifest.json'))
        audit = [row for row in rows(root / 'events.jsonl') if row['event'] == 'INPUT_SELECTION']
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]['case_ids'], ['test-0001'])
        self.assertEqual(len(audit[0]['exclusions']), 6)
        self.assertIn('input_sha256', audit[0])
        self.assertNotIn('items', audit[0])
        summary = request_order.selection_from_manifests(root, public=rows(root / '01-input/public.jsonl'), require_same_items=True)
        self.assertEqual((summary['originals'], summary['variants']), (1, 1))
        self.assertEqual(len(summary['items']), 2)
        self.assertEqual(len(summary['manifest_files']), 2)
        self.assertEqual([len(rows(root / p)) for p in summary['manifest_files']], [8, 8])
        report = reporting.build(root)
        self.assertEqual((report['originals'], report['variants']), (1, 1))
        pipeline.verify(root)

    def test_reuse_recovers_all_items_from_manifests_without_selection_file(self):
        summary_path = self.source / '02-generation/summary.json'
        summary = read(summary_path)
        item = summary['latest']['test-0001']['0']
        summary['latest']['test-0001'] = {str(i): dict(item, label=label) for i, label in enumerate(dataset.LABELS)}
        write(summary_path, summary)
        self.config['dataset']['require_all_variants_pass'] = True
        write(self.root / 'config.json', {'experiments': self.config})
        source = self.prepare()
        before = {p: pipeline.file_hash(source / p) for p in read(source / 'manifest.json')}
        self.config['dataset']['reuse_input_run'] = str(source)
        write(self.root / 'config.json', {'experiments': self.config})
        with patch.object(dataset, 'select', side_effect=AssertionError('Dataset selection must not run during reuse')):
            target = self.prepare()
        self.assertFalse((source / 'input-selection.json').exists())
        self.assertFalse((target / 'input-selection.json').exists())
        model = self.config['models'][0]['key']
        self.assertEqual(rows(source / model / '01-requests/manifest.jsonl'), rows(target / model / '01-requests/manifest.jsonl'))
        self.assertEqual(before, {p: pipeline.file_hash(source / p) for p in before})
        self.assertEqual((read(target / 'summary.json')['originals'], read(target / 'summary.json')['variants']), (1, 7))

    def test_manifest_conflicts_and_missing_models_cannot_silently_change_cohort(self):
        root = self.prepare()
        model = self.config['models'][0]['key']
        manifest = root / model / '01-requests/manifest.jsonl'
        original = rows(manifest)
        changed = copy.deepcopy(original)
        changed[1]['case'] = 'wrong-case'
        write_rows(manifest, changed)
        with self.assertRaisesRegex(ValueError, 'MANIFEST_ITEM_IDENTITY_CONFLICT'):
            request_order.selection_from_manifests(root)
        changed = copy.deepcopy(original)
        changed[1]['input']['context'] = 'Changed source text.'
        write_rows(manifest, changed)
        with self.assertRaisesRegex(ValueError, 'MANIFEST_ITEM_INPUT_CONFLICT'):
            request_order.selection_from_manifests(root)
        write_rows(manifest, original)
        public = rows(root / '01-input/public.jsonl')
        public[0]['answer_format']['decimal_places'] = 3
        with self.assertRaisesRegex(ValueError, 'PUBLIC_MANIFEST_INPUT_MISMATCH'):
            request_order.selection_from_manifests(root, public=public)
        config = read(root / 'config.json')
        config['models'].append({**config['models'][0], 'key': 'second-model'})
        write(root / 'config.json', config)
        with self.assertRaisesRegex(ValueError, 'REQUEST_MANIFEST_REQUIRED'):
            request_order.selection_from_manifests(root)
        write_rows(root / 'second-model/01-requests/manifest.jsonl', [row for row in original if row['experiment'] == 1])
        with self.assertRaisesRegex(ValueError, 'MODEL_MANIFEST_COHORT_MISMATCH'):
            request_order.selection_from_manifests(root, require_same_items=True)

    def test_missing_public_precision_cannot_fall_back_to_private(self):
        public, private, selection = dataset.select(self.config['dataset'])
        for row in public:
            row.pop('answer_format')
        self.assertIn('reference_precision', private[0]['reference'])
        with patch.object(dataset, 'select', return_value=(public, private, selection)):
            with self.assertRaisesRegex(ValueError, 'PUBLIC_ANSWER_FORMAT_REQUIRED'):
                self.prepare()

    def test_public_precision_is_required_valid_metadata_at_dataset_handoff(self):
        for precision in [True, -1, 101, '2', None]:
            with self.assertRaisesRegex(ValueError, 'INVALID_PUBLIC_DECIMAL_PLACES'):
                dataset.public_input(self.original, precision)

    def test_complete_cohort_requires_all_seven_and_respects_rejection(self):
        settings = dict(self.config['dataset'], require_all_variants_pass=True)
        with self.assertRaisesRegex(ValueError, 'INSUFFICIENT'):
            dataset.select(settings)
        summary_path = self.source / '02-generation/summary.json'
        summary = read(summary_path)
        original_item = summary['latest']['test-0001']['0']
        summary['latest']['test-0001'] = {str(i): dict(original_item, label=label)
                                         for i, label in enumerate(dataset.LABELS)}
        write(summary_path, summary)
        public, private, selected = dataset.select(settings)
        self.assertEqual(selected['variants'], 7)
        self.assertEqual(len(public), 8)
        self.assertEqual(selected['policy'], 'ALL_SEVEN_PASS_IN_INPUT_ORDER')
        folder = self.source / original_item['path']
        write(folder / '05-human-review/01-result.json', {'decision': 'REJECTED'})
        with self.assertRaisesRegex(ValueError, 'COMPLETE_COHORT_REJECTED'):
            dataset.select(settings)

    def test_currency_sign_is_preserved_in_numeric_screen(self):
        reference = {'reference_answer': '-35', 'reference_answer_type': 'integer', 'reference_precision': 0}
        for answer in ['-$35 million', '- $35 million', '−$35 million', '$-35 million']:
            checked = reporting.screen({'answer': answer, 'evidence': []},
                                       {'question': '', 'context': ''},
                                       {'experiment': 1, 'reference': reference})
            self.assertTrue(checked['numeric_comparison']['matches'], answer)
        checked = reporting.screen({'answer': '$35 million', 'evidence': []},
                                   {'question': '', 'context': ''},
                                   {'experiment': 1, 'reference': reference})
        self.assertFalse(checked['numeric_comparison']['matches'])

    def test_resume_never_repeats_success_and_manifest_is_frozen(self):
        root = self.prepare()
        calls = []
        def fake(model, request, folder, timeout):
            calls.append(request['trial_id'])
            result = {'status': 'VALID', 'response': {'status': 'answered', 'answer': '12', 'answer_meta': {'negative': False, 'scale': 'one'}, 'explanation': '10 + 2 = 12.', 'evidence': ['Amount A is 10.']},
                      'usage': {'promptTokenCount': 100, 'candidatesTokenCount': 20, 'thoughtsTokenCount': 5}}
            write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), patch.object(providers, 'call', side_effect=fake):
            pipeline.run(root, max_new=1)
            pipeline.run(root)
            pipeline.run(root)
        self.assertEqual(len(calls), 8)
        self.assertEqual(len(set(calls)), 8)
        summary = reporting.build(root)['models'][0]
        self.assertEqual(summary['output_tokens_including_thinking'], 200)
        self.assertAlmostEqual(summary['api_equivalent_usd'], 0.00016)
        self.assertIsNone(summary['billed_cost_usd'])
        write(root / 'config.json', {})
        with self.assertRaisesRegex(ValueError, 'FROZEN'):
            pipeline.verify(root)

    def test_quota_stops_and_unknown_delivery_is_not_retried(self):
        root = self.prepare()
        def fake(model, request, folder, timeout):
            result = {'status': 'QUOTA_EXHAUSTED', 'usage': None}
            write(folder / 'result.json', result)
            return result
        with patch.object(providers, 'preflight', return_value={'status': 'READY'}), patch.object(providers, 'call', side_effect=fake) as call:
            pipeline.run(root)
            pipeline.run(root)
            self.assertEqual(call.call_count, 1)
        summary = read(root / 'summary.json')['models'][0]
        self.assertEqual(summary['statuses']['NOT_RUN'], 7)
        self.assertEqual(summary['attempts_without_usage'], 1)
        self.assertEqual(summary['provider_state']['concurrency'], 1)

    def test_credential_reader_never_executes_shell(self):
        p = self.root / 'keys'
        p.write_text('export GEMINI_API_KEY_FREE="test-value"\nexport GEMINI_API_KEY_PAID="other-value"\n')
        self.assertEqual(providers.credential({'key_variable': 'GEMINI_API_KEY_FREE', 'key_file': str(p)}), 'test-value')
        p.write_text('export GEMINI_API_KEY_FREE="$(touch stolen)"\n')
        with self.assertRaises(ValueError):
            providers.credential({'key_variable': 'GEMINI_API_KEY_FREE', 'key_file': str(p)})

    def test_cli_envelope_recognizes_subscription_block_without_retry(self):
        raw = [{'type': 'system', 'subtype': 'init'}, {'type': 'result', 'is_error': True,
                'result': 'Your organization has disabled Claude subscription access for Claude Code',
                'usage': {'input_tokens': 0, 'output_tokens': 0}, 'total_cost_usd': 0}]
        result = providers.parse_claude_response(json.dumps(raw))
        self.assertEqual(result['status'], 'AUTH_BLOCKED')
        self.assertEqual(result['usage']['input_tokens'], 0)

    def test_batch_matches_opaque_ids_and_collects_thinking_usage(self):
        make_jobs = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['make_jobs']).make_jobs
        collect = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['collect']).collect
        root = self.prepare()
        model = {**self.config['models'][0], 'transport': 'gemini_batch'}
        folders = make_jobs(root, model)
        trials = read(folders[0] / 'trials.json')
        responses = []
        for trial in reversed(trials):
            responses.append({'metadata': {'key': trial['request']['trial_id']}, 'response': {
                'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
                    {'text': 'private analysis', 'thought': True}, {'text': json.dumps({'status': 'answered', 'answer': '12', 'answer_meta': {'negative': False, 'scale': 'one'}, 'explanation': '10 + 2', 'evidence': []})}]}}],
                'usageMetadata': {'promptTokenCount': 100, 'candidatesTokenCount': 20, 'thoughtsTokenCount': 10}}})
        operation = {'name': 'batches/example', 'done': True, 'response': {'inlinedResponses': {'inlinedResponses': responses}}}
        self.assertEqual(collect(root, model, folders[0], operation), 8)
        summary = reporting.build(root)['models'][0]
        self.assertEqual(summary['statuses']['CACHE_USAGE_UNVERIFIED'], 8)
        prices = model['reference_price_per_million']
        self.assertAlmostEqual(summary['paid_batch_usage_cost_estimate_usd'],
                               8 * (100 * prices['input'] + 30 * prices['output']) / 1e6)
        operation['response']['inlinedResponses']['inlinedResponses'][0]['metadata']['key'] = 'unexpected'
        with self.assertRaisesRegex(ValueError, 'ID_SET_MISMATCH'):
            collect(root, model, folders[0], operation)

    def test_batch_resume_does_not_duplicate_submission(self):
        make_jobs = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['make_jobs']).make_jobs
        process = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['process']).process
        root = self.prepare()
        model = {**self.config['models'][0], 'transport': 'gemini_batch'}
        folder = make_jobs(root, model)[0]
        state = read(root / 'state.json')
        trials = read(folder / 'trials.json')
        reply = {'name': 'batches/example', 'done': True, 'response': {'inlinedResponses': {'inlinedResponses': [
            {'metadata': {'key': t['request']['trial_id']}, 'response': {
                'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(
                    {'status': 'answered', 'answer': '12', 'answer_meta': {'negative': False, 'scale': 'one'}, 'explanation': '10 + 2', 'evidence': []})}]}}],
                'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 10}}} for t in trials]}}}
        # This isolates legacy batch resume behavior; strict dispatch rejection is tested separately.
        with patch.object(__import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*']), 'require_control'), patch.object(__import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['*']), 'http', side_effect=[(200, {'name': 'batches/example'}), (200, reply)]) as http:
            process(root, model, state, reporting.build, poll_seconds=0)
            process(root, model, state, reporting.build, poll_seconds=0)
        self.assertEqual(http.call_count, 2)
        self.assertEqual(read(folder / 'job.json')['status'], 'COLLECTED')
        state['models'][model['key']]['status'] = 'PENDING'
        write(folder / 'job.json', {'status': 'UNKNOWN_SUBMISSION'})
        with patch.object(__import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*']), 'require_control'), patch.object(__import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['*']), 'http') as http:
            with self.assertRaisesRegex(ValueError, 'RECONCILIATION'):
                process(root, model, state, reporting.build, poll_seconds=0)
        http.assert_not_called()

    def test_sequence_and_ambiguous_answer_remains_unscored(self):
        a, b = allocate(self.root / 'runs'), allocate(self.root / 'runs')
        self.assertTrue(a.name.endswith('exp-001'))
        self.assertTrue(b.name.endswith('exp-002'))
        checked = reporting.screen({'answer': 'Either 12 or 13', 'explanation': '', 'evidence': ['invented']},
                                   dataset.qc(self.original), {'experiment': 1, 'reference': {k: self.original[k] for k in ['reference_answer', 'reference_answer_type', 'reference_precision']}})
        self.assertEqual(checked['numeric_comparison_status'], 'NOT_EVALUATED')
        self.assertFalse(checked['all_quotes_present'])


if __name__ == '__main__':
    unittest.main()
