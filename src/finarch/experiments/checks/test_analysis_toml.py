"""Verify TOML dispatch, immutable snapshots, and paused runs without providers."""
import importlib
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

settings = importlib.import_module('finarch.experiments.90-operations.settings')
configuration = importlib.import_module('finarch.experiments.02-analysis.configuration')
backend = importlib.import_module('finarch.experiments.02-analysis.llm_backend')
runner = importlib.import_module('finarch.experiments.pipeline')
fixture = importlib.import_module('finarch.experiments.checks.test_evaluation_analysis_layout')
store = settings.store


class AnalysisTomlTest(unittest.TestCase):
    def setUp(self):
        prepared = fixture.OrderedRunTest()
        prepared.setUp()
        self.addCleanup(prepared.doCleanups)
        self.root = prepared.root
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'config.toml'
        self.path.write_bytes(settings.DEFAULT_CONFIG.read_bytes())

    def select(self, backend_name):
        text = settings.DEFAULT_CONFIG.read_text().replace('backend = "codex"', f'backend = "{backend_name}"')
        self.path.write_text(text)

    def test_toml_resolves_both_backends_and_api_output_limit(self):
        evaluation, codex = settings.load_file(self.path)
        self.assertEqual(codex['backend'], 'codex')
        self.assertEqual(set(codex['backends']), {'api', 'codex'})
        self.select('api')
        same_evaluation, api = settings.load_file(self.path)
        self.assertEqual(api['backend'], 'api')
        self.assertEqual(api['backends']['api']['transport'], 'openai_batch')
        self.assertEqual(api['backends']['api']['max_output_tokens'], 65536)
        self.assertEqual(evaluation['models'][0]['model'], same_evaluation['models'][0]['model'])
        self.assertEqual(evaluation['dataset'], same_evaluation['dataset'])

    def test_snapshot_is_stable_and_preserves_evaluation_and_pause(self):
        saved = (self.root / 'config.json').read_bytes()
        state = store.read(self.root / 'state.json')
        state['execution_control'] = {'analysis': {'paused': True}}
        store.write(self.root / 'state.json', state)
        frozen = configuration.freeze(self.root, self.path)
        self.assertEqual(frozen, configuration.freeze(self.root, self.path))
        self.select('api')
        self.assertEqual(configuration.read(self.root)['backend'], 'codex')
        with self.assertRaisesRegex(ValueError, 'FROZEN_ANALYSIS_CONFIGURATION_MISMATCH'):
            configuration.freeze(self.root, self.path)
        self.assertEqual((self.root / 'config.json').read_bytes(), saved)
        self.assertTrue(store.read(self.root / 'state.json')['execution_control']['analysis']['paused'])
        store.verify(self.root)

    def test_started_analysis_cannot_receive_new_settings(self):
        store.write_rows(self.root / '02_analysis/02_comparison/manifest.jsonl', [])
        with self.assertRaisesRegex(ValueError, 'ANALYSIS_ALREADY_STARTED'):
            configuration.freeze(self.root, self.path)

    def test_operational_schedule_changes_preserve_frozen_requests(self):
        configuration.freeze(self.root, self.path)
        request = backend.request(self.root, '03_research', 'example', 'Analyze saved results.',
                                  backend.contracts.FINDINGS, {'run': self.root.name, 'interpretations': []})
        backend.freeze(self.root, '03_research', [request])
        before = (self.root / '02_analysis/config.json').read_bytes()
        self.path.write_text(re.sub(r'^concurrency = \d+$', 'concurrency = 30', self.path.read_text(), count=1, flags=re.MULTILINE))
        configuration.configure_schedule(self.root, self.path)
        self.assertEqual(backend.scheduler.policy(self.root, configuration.read(self.root))['concurrency'], 30)
        self.assertEqual((self.root / '02_analysis/config.json').read_bytes(), before)
        self.assertEqual(request, backend.request(self.root, '03_research', 'example', 'Analyze saved results.',
            backend.contracts.FINDINGS, {'run': self.root.name, 'interpretations': []}))
        store.verify(self.root)

    def test_tampered_snapshot_is_rejected(self):
        snapshot = configuration.freeze(self.root, self.path)
        snapshot['analysis']['backend'] = 'api'
        store.write(self.root / '02_analysis/config.json', snapshot)
        with self.assertRaisesRegex(ValueError, 'ANALYSIS_CONFIGURATION_CHANGED'):
            configuration.read(self.root)

    def test_api_selection_dispatches_without_codex_fallback(self):
        self.select('api')
        configuration.freeze(self.root, self.path)
        request = backend.request(self.root, '03_research', 'example', 'Analyze saved results.',
                                  backend.contracts.FINDINGS, {'run': self.root.name, 'interpretations': []})
        with patch.object(backend, 'run_api', return_value={'status': 'RUNNING'}) as api, patch.object(backend, 'run_codex') as codex:
            backend.run(self.root, '03_research', [request])
        api.assert_called_once()
        codex.assert_not_called()
        self.assertEqual(api.call_args.args[-1]['transport'], 'openai_batch')

    def test_paused_entrypoints_make_no_provider_calls(self):
        state = store.read(self.root / 'state.json')
        state['execution_control'] = {name: {'paused': True} for name in ('evaluation', 'analysis')}
        store.write(self.root / 'state.json', state)
        with patch.object(backend.batch, 'http') as http, patch.object(backend.codex, 'call') as codex, patch.object(runner, 'collect_when_ready') as collect:
            self.assertEqual(runner.evaluation.run(self.root)['status'], 'PAUSED_BY_USER')
            self.assertEqual(runner.analysis.run(self.root)['status'], 'PAUSED_BY_USER')
            self.assertEqual(backend.run(self.root, '03_research', [])['status'], 'PAUSED_BY_USER')
            self.assertEqual(runner.run(self.root)['status'], 'PAUSED_BY_USER')
        http.assert_not_called()
        codex.assert_not_called()
        collect.assert_not_called()

    def test_codex_toml_overrides_reach_command(self):
        self.path.write_text(self.path.read_text().replace('"--skip-git-repo-check"', '"-c", "model_verbosity=low", "--skip-git-repo-check"'))
        configuration.freeze(self.root, self.path)
        request = backend.request(self.root, '03_research', 'example', 'Analyze saved results.',
                                  backend.contracts.FINDINGS, {'run': self.root.name, 'interpretations': []})
        process = {'stdout': '', 'stderr': '', 'state': 'TIMED_OUT', 'elapsed_seconds': 1, 'exit_code': None}
        with patch.object(backend.codex.shutil, 'which', return_value='/fake/codex'), patch('finarch.shared.providers.cli.run_process', return_value=process) as call:
            result = backend.codex.call(request, self.root / 'offline-analysis-call', 1)
        command = call.call_args.args[0]
        self.assertIn('model_verbosity="low"', command)
        self.assertEqual(command[command.index('-m') + 1], request['model'])
        self.assertEqual(result['status'], 'UNKNOWN_DELIVERY')


class SourceDocumentationTest(unittest.TestCase):
    def test_source_migration_and_indexed_toml_are_readable(self):
        documentation = importlib.import_module('finarch.dataset.viewer.reports.documentation')
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            bundle = project / 'reports/run/source-layout'
            readme = 'src/finarch/experiments/README.md'
            config = 'config/experiments/config.toml'
            store.write_text(project / readme, '# Source layout\n')
            store.write_text(project / config, '[analysis.run]\nbackend="api"\n')
            store.write_text(bundle / 'README.md', '# Work log\n')
            store.write(bundle / 'migration.json', {'files': [{'old': readme, 'new': readme,
                'archive': 'archive/20260927-experiment-source-layout/README.md'}]})
            store.write(bundle / 'documentation.json', {'kind': 'PIPELINE_DOCUMENTATION',
                'title': 'Source layout', 'documents': [{'path': readme, 'title': 'Source layout'}],
                'reference_files': [config]})
            with patch.object(documentation, 'PROJECT', project), patch.object(documentation, 'ALIASES_PATH', project/'missing.json'):
                value = documentation.view(bundle)
                self.assertEqual(value['batch']['documentation']['documents'][0]['path'], readme)
                self.assertIn('backend="api"', documentation.read_document(bundle, config)['content'])
                with self.assertRaisesRegex(ValueError, 'DOCUMENT_NOT_IN_INDEX'):
                    documentation.read_document(bundle, '.env')


if __name__ == '__main__':
    unittest.main()
