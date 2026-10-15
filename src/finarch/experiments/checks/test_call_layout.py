"""Offline checks for stable call identities, migration integrity and resume."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
gemini_batch = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])
consolidate_root = __import__('finarch.experiments.01-evaluation.03-execution.organize_calls', fromlist=['consolidate_root']).consolidate_root
organize = __import__('finarch.experiments.01-evaluation.03-execution.organize_calls', fromlist=['organize']).organize
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_rows = __import__('finarch.experiments.90-operations.storage', fromlist=['write_rows']).write_rows


class CallLayoutTest(unittest.TestCase):
    def test_frozen_readme_is_preserved_when_result_navigation_is_generated(self):
        self.seed_legacy_run()
        frozen = (self.root / 'README.md').read_bytes()
        manifest = read(self.root / 'manifest.json')
        manifest['README.md'] = file_hash(self.root / 'README.md')
        write(self.root / 'manifest.json', manifest)
        reporting.build(self.root)
        self.assertEqual((self.root / 'README.md').read_bytes(), frozen)
        self.assertTrue((self.root / 'EVALUATION.md').is_file())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / 'model'
        self.request = {'trial_id': 'opaque-hash', 'case': 'test-0001', 'variant': 'ORIGINAL',
                        'prompt_condition': 'P0', 'reasoning': 'off', 'experiment': 1,
                        'item_id': 'original', 'input': {'question': 'What is 1 + 2?', 'context': 'A is 1. B is 2.'},
                        'prompt': 'Calculate the answer.', 'response_schema': {'type': 'object'}}

    def seed_legacy_run(self):
        model = {'key': 'model', 'transport': 'gemini_batch'}
        write(self.root / 'config.json', {'models': [model]})
        write(self.root / 'input-selection.json', {'originals': 1, 'variants': 0})
        write(self.root / 'state.json', {'status': 'FINISHED', 'models': {'model': {'status': 'FINISHED'}}})
        write_rows(self.root / '01-input/public.jsonl', [dict(self.request['input'], item_id='original')])
        write_rows(self.root / '01-input/private.jsonl', [{'item_id': 'original', 'case': 'test-0001',
                   'experiment': 1, 'variant': 'ORIGINAL', 'reference': {'reference_answer': '3',
                   'reference_answer_type': 'integer', 'reference_precision': 0}}])
        requests = [self.request, dict(self.request, reasoning='on', trial_id='other-hash')]
        write_rows(self.base / '01-requests/manifest.jsonl', requests)
        for request in requests:
            folder = self.base / '02-calls' / request['trial_id'] / 'attempt-001'
            write(folder / 'request.json', request)
            write(folder / 'result.json', {'status': 'VALID', 'response': {'answer': '3', 'evidence': [], 'explanation': '1 + 2 = 3.'},
                 'transport': 'gemini_batch', 'billing_mode': 'PAID_BATCH', 'usage': {'promptTokenCount': 100, 'candidatesTokenCount': 10}})
            (folder / 'raw-response.json').write_bytes(b'{"original_bytes": true}\n')
        tracked = [self.root / 'config.json', self.base / '01-requests/manifest.jsonl']
        write(self.root / 'manifest.json', {str(p.relative_to(self.root)): file_hash(p) for p in tracked})
        reporting.build(self.root)

    def test_legacy_matrix_keeps_thirty_human_readable_paths(self):
        paths = []
        for variant in call_layout.TYPE_FOLDERS:
            for prompt in ('P0',) if variant == 'ORIGINAL' else ('P0', 'P1'):
                for reasoning in ('off', 'on'):
                    request = dict(self.request, variant=variant, prompt_condition=prompt, reasoning=reasoning)
                    paths.append(call_layout.call_path(self.base, request))
        self.assertEqual(len(set(paths)), 30)
        self.assertEqual(paths[0].relative_to(self.base).as_posix(), 'calls/test-0001/00-Original/test-0001-P0-R-off.json')
        self.assertEqual(paths[-1].name, 'test-0001-P1-R-on.json')
        self.assertEqual(paths[-1].parent.name, '07-EA-02')
        for field, value in [('case', '../unsafe'), ('reasoning', 'unknown'), ('prompt_condition', 'R1')]:
            with self.assertRaises(ValueError):
                call_layout.call_path(self.base, dict(self.request, **{field: value}))
        with self.assertRaisesRegex(ValueError, 'COLLISION'):
            call_layout.check_manifest(self.base, [self.request, dict(self.request, trial_id='different')])

    def test_current_matrix_has_four_conditions_for_every_type(self):
        requests = [dict(self.request, variant=variant, prompt_condition=prompt, reasoning=reasoning,
                         trial_id=f'{variant}-{prompt}-{reasoning}')
                    for variant in call_layout.TYPE_FOLDERS for prompt in ('unguided', 'guided')
                    for reasoning in ('off', 'on')]
        call_layout.check_manifest(self.base, requests)
        paths = [call_layout.call_path(self.base, request) for request in requests]
        self.assertEqual(len(set(paths)), 32)
        self.assertEqual(sum(request['variant'] == 'ORIGINAL' for request in requests), 4)
        self.assertEqual(paths[0].name, 'test-0001-unguided-R-off.json')
        self.assertEqual(paths[3].name, 'test-0001-guided-R-on.json')

    def test_migration_preserves_bytes_metrics_and_is_idempotent(self):
        self.seed_legacy_run()
        result = organize(self.root)
        self.assertEqual(result['readable_call_files'], 2)
        self.assertFalse((self.base / '02-calls').exists())
        self.assertEqual(result['preserved_files'], 6)
        actual = read(call_layout.call_path(self.base, self.request))
        self.assertEqual(actual['response']['answer'], '3')
        self.assertEqual(actual['request'], self.request)
        self.assertEqual(organize(self.root)['preserved_files'], 6)
        for record in rows(self.root / 'layout/record-hashes.jsonl'):
            self.assertEqual(file_hash(self.root / record['new']), record['sha256'])
        with patch.object(gemini_batch, 'http') as http:
            self.assertEqual(gemini_batch.make_jobs(self.root, {'key': 'model'}), [])
        http.assert_not_called()

    def test_interrupted_migration_can_resume(self):
        self.seed_legacy_run()
        rename = Path.rename
        count = 0
        def interrupted(path, target):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('simulated interruption')
            return rename(path, target)
        with patch.object(Path, 'rename', interrupted):
            with self.assertRaises(OSError):
                organize(self.root)
        self.assertEqual(organize(self.root)['status'], 'VERIFIED')

    def test_ambiguous_or_changed_record_blocks_before_overwrite(self):
        self.seed_legacy_run()
        call_layout.record_dir(self.base, self.request).mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'DESTINATION_EXISTS'):
            organize(self.root)
        self.assertTrue((self.base / '02-calls/opaque-hash/attempt-001/raw-response.json').exists())
        call_layout.record_dir(self.base, self.request).rmdir()
        organize(self.root)
        raw = call_layout.record_dir(self.base, self.request) / 'attempt-001/raw-response.json'
        raw.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'MIGRATION_RECORD_CHANGED'):
            organize(self.root)

    def test_all_attempts_remain_visible_and_unknown_is_not_resubmitted(self):
        base = call_layout.record_dir(self.base, self.request)
        write_rows(self.base / '01-requests/manifest.jsonl', [self.request])
        write(base / 'attempt-001/result.json', {'status': 'RATE_LIMITED', 'usage': None})
        write(base / 'attempt-002/request.json', self.request)
        with self.assertRaisesRegex(ValueError, 'RECONCILE_UNKNOWN'):
            gemini_batch.make_jobs(self.root, {'key': 'model'})
        path = call_layout.publish(self.root, self.base, self.request, {})
        payload = read(self.root / path)
        self.assertEqual(payload['status'], 'UNKNOWN_DELIVERY')
        self.assertIsNone(payload['records']['attempts'][-1]['result_path'])
        broken = '{"answer": "unfinished'
        write(base / 'attempt-002/raw-response.json', {'response': {'candidates': [{'content': {'parts': [{'text': broken}]}}]}})
        write(base / 'attempt-002/result.json', {'status': 'OUTPUT_TRUNCATED', 'usage': {}})
        call_layout.publish(self.root, self.base, self.request, {})
        payload = read(self.root / path)
        self.assertEqual(payload['response_text'], broken)
        self.assertIsNone(payload['response'])
        self.assertEqual(len(payload['records']['attempts']), 2)
        self.assertEqual(gemini_batch.make_jobs(self.root, {'key': 'model'}), [])

    def test_root_consolidation_preserves_bytes_and_refuses_collision(self):
        source = self.root / 'report/experiments-run'
        target = self.root / 'reports/experiments-run'
        path = source / '20260920-exp-001/model/raw.json'
        write(path, {'saved': True})
        original = path.read_bytes()
        target.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'COLLISION'):
            consolidate_root(source, target)
        target.rmdir()
        self.assertEqual(consolidate_root(source, target)['status'], 'VERIFIED')
        self.assertFalse((self.root / 'report').exists())
        self.assertEqual((target / '20260920-exp-001/model/raw.json').read_bytes(), original)
        self.assertEqual(consolidate_root(source, target)['status'], 'VERIFIED')

    def test_unfinished_retry_is_not_reported_as_the_previous_success(self):
        self.seed_legacy_run()
        folder = self.base / '02-calls/opaque-hash/attempt-002'
        write(folder / 'request.json', self.request)
        summary = reporting.build(self.root)['models'][0]
        entry = next(r for r in rows(self.base / '03-results/results.jsonl') if r['trial_id'] == 'opaque-hash')
        self.assertEqual(summary['statuses']['UNKNOWN_DELIVERY'], 1)
        self.assertEqual(summary['attempts'], 3)
        self.assertEqual(entry['status'], 'UNKNOWN_DELIVERY')
        self.assertIsNone(entry['result_path'])
        self.assertNotIn('checks', entry)
        self.assertEqual(read(self.root / entry['call_path'])['status'], 'UNKNOWN_DELIVERY')


if __name__ == '__main__':
    unittest.main()
