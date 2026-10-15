"""The release label requires saved use, necessity, and a passed verdict."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path


exporter = __import__('finarch.dataset.03-release.export_run_results', fromlist=['*'])
knowledge = __import__('finarch.dataset.03-release.external_knowledge', fromlist=['*'])
viewer = __import__('finarch.dataset.viewer.server', fromlist=['result_external_index'])


class ExternalKnowledgeExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name) / 'test-run'
        self.sample = {'id': 'test-0001', 'question': 'What is the ratio?',
                       'context': 'The input is 10.', 'reference_answer': '2',
                       'reference_answer_type': 'integer', 'reference_precision': 0}
        self.row = {'id': 'test-0001', 'status': 'PASS', 'round': '01-round',
                    'input': self.sample, 'source': '01-preparation/test-0001/01-round/data.json'}
        self.case = self.run / '01-preparation/test-0001'
        self.round = self.case / '01-round'
        exporter.save(self.case / 'run.json', {'status': 'PASS', 'active_round': '01-round'})
        exporter.save(self.round / 'data.json', self.sample)
        self.program = {'calculation_input_sources': ['IN_CONTEXT_DATA', 'EXTERNAL_RULE'],
                        'source_usage': [{'id': 'given', 'kind': 'IN_CONTEXT_DATA', 'acquisition': 'SUPPLIED'},
                                         {'id': 'rule', 'kind': 'EXTERNAL_RULE', 'acquisition': 'MODEL_KNOWLEDGE'}]}
        self.verdict = {'status': 'PASS', 'cohort': 'EXTERNAL',
                        'required_external_sources': ['EXTERNAL_RULE']}
        self.write_evidence()

    def write_evidence(self):
        root = self.round
        exporter.save(root / '03-calculation/05-record-calculation-artifacts/03-program.json', self.program)
        exporter.save(root / '03-calculation/05-record-calculation-artifacts/01-stage-output.json',
                      {'sample': self.sample, 'program': self.program})
        exporter.save(root / '04-graph/04-trace-answer-dependencies/01-result.json',
                      {'calculation_input_sources': self.program['calculation_input_sources'],
                       'source_usage': self.program['source_usage']})
        exporter.save(root / '05-verification/05-build-verification-request/01-input.json',
                      {'sample': self.sample})
        exporter.save(root / '05-verification/08-record-verdict/01-result.json', self.verdict)

    def test_confirmed_and_unconfirmed_usage_remain_distinct(self):
        result, _ = knowledge.classify(self.run, self.row)
        self.assertEqual(result, {'used': True, 'used_types': ['EXTERNAL_RULE']})
        self.verdict = {'status': 'PASS', 'cohort': 'INTERNAL', 'required_external_sources': []}
        self.write_evidence()
        self.assertEqual(knowledge.classify(self.run, self.row)[0], {'used': False, 'used_types': []})
        self.verdict = {'status': 'FAIL', 'cohort': 'EXTERNAL',
                        'required_external_sources': ['EXTERNAL_RULE']}
        self.write_evidence()
        self.assertEqual(knowledge.classify(self.run, self.row)[0], {'used': False, 'used_types': []})
        self.verdict = {'status': 'PASS', 'cohort': 'EXTERNAL',
                        'required_external_sources': ['EXTERNAL_DATA']}
        self.write_evidence()
        self.assertEqual(knowledge.classify(self.run, self.row)[0], {'used': False, 'used_types': []})
        self.verdict = {'status': 'PASS', 'cohort': 'EXTERNAL',
                        'required_external_sources': ['EXTERNAL_RULE']}
        self.program['source_usage'][1]['acquisition'] = 'UNAVAILABLE'
        self.write_evidence()
        self.assertEqual(knowledge.classify(self.run, self.row)[0], {'used': False, 'used_types': []})

    def test_final_failure_does_not_expose_prior_external_use(self):
        failed = {**self.row, 'status': 'FAIL'}
        exporter.save(self.case / 'run.json', {'status': 'FAIL', 'active_round': '01-round'})
        self.assertEqual(knowledge.classify(self.run, failed)[0], {'used': False, 'used_types': []})

    def test_saved_question_and_context_must_match(self):
        stale = copy.deepcopy(self.row)
        stale['input']['question'] = 'Another question?'
        with self.assertRaisesRegex(ValueError, 'EXTERNAL_KNOWLEDGE_QC_MISMATCH'):
            knowledge.classify(self.run, stale)

    def test_export_and_backfill_share_label_and_preserve_previous_bytes(self):
        exporter.save(self.run / 'input.json', [self.sample])
        exporter.save(self.run / 'input-selection.json',
                      {'input_path': str(self.run / 'input.json'), 'cases': ['test-0001']})
        exporter.save(self.run / '02-generation/result-report.json', {'rows': []})
        exporter.export(self.run)
        output = self.run / 'results'
        original = exporter.read(output / '00-input.json')
        self.assertEqual(original[0]['external_knowledge'], {'used': True, 'used_types': ['EXTERNAL_RULE']})
        self.assertEqual(exporter.read(output / 'export-log.json')['external_knowledge_counts']['true'], 1)
        variant_hashes = {folder: exporter.sha(output / (folder + '.json')) for _, folder in exporter.TYPES}
        original[0].pop('external_knowledge')
        exporter.save(output / '00-input.json', original)
        manifest = exporter.read(output / 'manifest.json')
        manifest['files']['00-input.json']['sha256'] = exporter.sha(output / '00-input.json')
        exporter.save(output / 'manifest.json', manifest)
        previous = (output / '00-input.json').read_bytes()
        first = exporter.enrich_external_existing(self.run)
        self.assertTrue(first['changed'])
        self.assertEqual(exporter.read(output / '00-input.json')[0]['external_knowledge'],
                         {'used': True, 'used_types': ['EXTERNAL_RULE']})
        self.assertEqual(viewer.result_external_index(self.run)['test-0001'],
                         {'used': True, 'used_types': ['EXTERNAL_RULE']})
        self.assertEqual(exporter.read(output / 'manifest.json')['files']['00-input.json']['sha256'],
                         exporter.sha(output / '00-input.json'))
        for folder, old_hash in variant_hashes.items():
            self.assertEqual(exporter.sha(output / (folder + '.json')), old_hash)
        revision = exporter.read(output / 'export-log.json')['external_knowledge_revisions'][-1]
        self.assertEqual(revision['files']['00-input.json']['before_sha256'], hashlib.sha256(previous).hexdigest())
        self.assertIn('03-program.json', next(path for path in revision['sources']['test-0001']['sources']
                                              if path.endswith('03-program.json')))
        self.assertFalse(exporter.enrich_external_existing(self.run)['changed'])


if __name__ == '__main__':
    unittest.main()
