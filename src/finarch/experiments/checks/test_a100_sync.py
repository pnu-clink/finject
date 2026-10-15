"""Local synchronization boundaries; no model/server requests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from finarch.experiments.a100.sync_protocol import code_manifest, digest, differences, safe, sha, public_input_manifest
from finarch.experiments.a100.sync_agent import publish_release, publish_inputs, publish_control, outputs, write
from finarch.experiments.a100.sync_gate import verify
from finarch.experiments.a100.worker import call


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def public_run(self, root):
        files = {'config.json': '{}', '00_input/public.jsonl': '{}\n',
                 '00_input/private.jsonl': 'DO_NOT_TRANSFER',
                 '01_evaluation/02_request/model/manifest.jsonl': '{}\n'}
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        write(root / 'manifest.json', {name: sha(root / name) for name in files})
        return root

    def test_public_input_excludes_private_and_rejects_drift(self):
        run = self.public_run(self.root)
        selected = public_input_manifest(run)
        self.assertNotIn('00_input/private.jsonl', selected)
        (run / '00_input/public.jsonl').write_text('CHANGED')
        with self.assertRaisesRegex(ValueError, 'FROZEN_INPUT_CHANGED'):
            public_input_manifest(run)

    def test_paths_reject_traversal_and_links(self):
        for name in ('../secret', '/etc/passwd', 'a/../../b', 'a\\b'):
            with self.assertRaises(ValueError):
                safe(self.root, name)
        (self.root / 'escape').symlink_to('/tmp')
        with self.assertRaises(ValueError):
            safe(self.root, 'escape/example')

    def test_release_verified_before_current_switch_and_drift_gate(self):
        project = self.root / 'pc'
        (project / 'src/finarch').mkdir(parents=True)
        (project / 'src/finarch/pipeline.py').write_text('value = 1\n')
        files = code_manifest(project)
        release = digest(files)
        import shutil
        target = self.root / 'remote/releases' / release
        shutil.copytree(project, target)
        write(target / 'sync-release.json', {'release': release, 'files': files})
        (self.root / 'remote/reports').mkdir()
        result = publish_release(self.root / 'remote', release)
        self.assertEqual(result['status'], 'VERIFIED')
        run = self.public_run(self.root / 'run')
        selected = public_input_manifest(run)
        write(run / 'sync-input.json', {'run_id': '20261003-example', 'code_release': release, 'files': selected})
        self.assertEqual(verify(run, target)['status'], 'VERIFIED')
        (target / 'src/finarch/pipeline.py').write_text('value = 2\n')
        with self.assertRaisesRegex(ValueError, 'EXECUTION_CODE_DRIFT'):
            verify(run, target)
        with self.assertRaisesRegex(ValueError, 'RELEASE_NOT_VERIFIED'):
            publish_release(self.root / 'remote', release)

    def test_existing_input_conflict_is_not_overwritten(self):
        remote = self.root / 'remote'
        run_id = '20261003-example'
        incoming = self.public_run(remote / '.sync/incoming' / run_id)
        files = public_input_manifest(incoming)
        write(incoming / 'sync-input.json', {'files': files, 'code_release': 'example'})
        write(incoming / 'pc-state.json', {'execution_control': {'evaluation': {'paused': True}}})
        publish_inputs(remote, run_id)
        dest = remote / 'reports/experiments-run' / run_id
        self.assertFalse((dest / '00_input/private.jsonl').exists())
        (dest / '00_input/public.jsonl').write_text('PRESERVED_CONFLICT')
        with self.assertRaisesRegex(ValueError, 'FROZEN_REMOTE_INPUT_CONFLICT'):
            publish_inputs(remote, run_id)
        self.assertEqual((dest / '00_input/public.jsonl').read_text(), 'PRESERVED_CONFLICT')

    def test_only_terminal_responses_are_published_and_hash_is_checked(self):
        for trial, status in [('one', 'RECEIVED'), ('two', 'SENDING')]:
            folder = self.root / 'remote-results' / trial
            folder.mkdir(parents=True)
            (folder / 'raw-response.json').write_text('{}')
            write(folder / 'delivery.json', {'status': status, 'response_sha256': sha(folder / 'raw-response.json')})
        result = outputs(self.root)
        self.assertEqual(result['pending_unpublished'], 1)
        self.assertEqual(len(result['files']), 2)
        (self.root / 'remote-results/one/raw-response.json').write_text('{"tampered":true}')
        with self.assertRaisesRegex(ValueError, 'RAW_RESPONSE_HASH_MISMATCH'):
            outputs(self.root, force=True)

    def test_pause_control_updates_without_changing_frozen_inputs(self):
        remote = self.root / 'remote'
        run_id = '20261003-example'
        incoming = self.public_run(remote / '.sync/incoming' / run_id)
        files = public_input_manifest(incoming)
        write(incoming / 'sync-input.json', {'files': files, 'code_release': 'example'})
        write(incoming / 'pc-state.json', {'execution_control': {'evaluation': {'paused': False}}})
        publish_inputs(remote, run_id)
        state = {'execution_control': {'evaluation': {'paused': True}}}
        write(incoming / 'pc-state.json', state)
        result = publish_control(remote, run_id)
        target = remote / 'reports/experiments-run' / run_id
        self.assertEqual(json.loads((target / 'pc-state.json').read_text()), state)
        self.assertEqual({name: sha(target / name) for name in files}, files)
        self.assertEqual(result['new_model_calls'], 0)

    def test_diff_distinguishes_missing_changed_and_extra(self):
        self.assertEqual(differences({'a': '1', 'b': '2'}, {'b': '3', 'c': '4'}),
                         {'missing': ['a'], 'changed': ['b'], 'extra': ['c']})

    def test_inventory_cache_is_separate_from_historical_source(self):
        source = self.root / 'history'
        folder = source / 'remote-results/one'
        folder.mkdir(parents=True)
        write(folder / 'delivery.json', {'status': 'RECEIVED'})
        cache = self.root / 'managed/.sync/output-cache'
        first = outputs(source, cache_dir=cache)
        second = outputs(source, cache_dir=cache)
        self.assertEqual(second['inventory_verification'], 'UNCHANGED_EXECUTION_PUBLISHED_HASHES')
        self.assertEqual(first['files'], second['files'])
        self.assertFalse((source / '.sync-hash-cache.json').exists())
        self.assertTrue((cache / '.sync-published.json').exists())

    def test_wire_failure_remains_unknown_and_existing_attempt_never_retries(self):
        request = {'trial_id': 'example', 'model': 'local', 'reasoning': 'on',
                   'prompt': 'Return JSON.', 'input': {}, 'max_output_tokens': 10,
                   'response_schema': {'type': 'object', 'properties': {'answer': {'type': 'number'}}}}
        runtime = {'sampling': {'on': {'temperature': .6, 'top_p': .95}}, 'top_k': 20, 'min_p': 0, 'seed': 1}
        with patch('urllib.request.urlopen', side_effect=TimeoutError('simulated transport failure')) as provider:
            self.assertEqual(call(self.root, request, runtime, 'http://127.0.0.1:1'), 'UNKNOWN_DELIVERY')
            self.assertEqual(provider.call_count, 1)
            with self.assertRaises(FileExistsError):
                call(self.root, request, runtime, 'http://127.0.0.1:1')
            self.assertEqual(provider.call_count, 1)
        self.assertTrue(json.loads((self.root / 'remote-results/example/provider-request.json').read_text())['chat_template_kwargs']['enable_thinking'])


if __name__ == '__main__':
    unittest.main()
