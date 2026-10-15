"""Offline export and experiment handoff checks for explicit human rejection."""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

export = importlib.import_module('finarch.dataset.03-release.export_run_results')
policy = importlib.import_module('finarch.dataset.03-release.export_policy')
dataset = importlib.import_module('finarch.experiments.00-input.dataset')


class ExportRejectionChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name) / 'export-check'
        self.ids = [f'test-{number:04d}' for number in range(1, 5)]
        originals, prep, reports, latest = [], [], [], {}
        for case in self.ids:
            sample = {'id': case, 'question': 'What is the sum?', 'context': 'A is 10. B is 2.',
                      'reference_answer': '12', 'reference_answer_type': 'integer', 'reference_precision': 0}
            originals.append(sample)
            state = {'input_id': case, 'status': 'FAIL' if case == self.ids[3] else 'PASS',
                     'active_round': '01-round', 'human_decision': 'PENDING'}
            if case == self.ids[2]:
                state['human_decision'] = 'REJECTED'
            root = self.run / '01-preparation' / case
            export.save(root / 'run.json', state)
            export.save(root / '01-round/data.json', sample)
            prep.append(state)
            latest[case] = {}
            if state['status'] != 'PASS':
                continue
            for index, (label, name) in enumerate(export.TYPES):
                folder = self.run / '02-generation/01-round' / case / name
                relative = str(folder.relative_to(self.run))
                current = {'label': label, 'status': 'PASS', 'path': relative, 'human_decision': 'PENDING'}
                export.save(folder / 'run.json', current)
                observation = {'question': sample['question'], 'context': sample['context'] + ' A is 11.'}
                export.save(folder / '02-generate-text/04-observation.json', observation)
                export.save(folder / '03-validation/03-result.json', {'status': 'PASS'})
                export.save(folder / '03-validation/04-comparison.json',
                            {'working': observation, 'reference': dataset.qc(sample)})
                reports.append({'case': case, 'type': label, 'origin': relative, 'status': 'PASS'})
                latest[case][str(index)] = current
        export.save(self.run / 'input.json', originals)
        export.save(self.run / 'input-selection.json',
                    {'input_path': str(self.run / 'input.json'), 'cases': self.ids})
        export.save(self.run / '01-preparation/summary.json', {'results': prep})
        export.save(self.run / '02-generation/summary.json', {'latest': latest})
        export.save(self.run / '02-generation/result-report.json', {'rows': reports})
        self.prep_reject = self.run / '01-preparation' / self.ids[1] / '01-round/07-human-review/03-record-decision/decision.json'
        export.save(self.prep_reject, {'decision': 'REJECTED', 'reason': 'Review found invalid input.'})
        export.save(self.run / '01-preparation' / self.ids[2] / '01-round/07-human-review/03-record-decision/decision.json',
                    {'decision': 'APPROVED', 'reason': ''})
        self.variant_reject = self.run / '02-generation/01-round' / self.ids[0] / export.TYPES[0][1] / '05-human-review/02-record-decision/decision.json'
        export.save(self.variant_reject, {'decision': 'reject', 'reason': 'Review found an invalid edit.'})
        self.settings = {'source_run': str(self.run), 'input_path': str(self.run / 'input.json'),
                         'count': 1, 'require_all_variants_pass': True, 'require_collected_results': True}

    def collect(self):
        # Source classification has separate real-evidence regression coverage.
        def labels(run, rows):
            return ([{**row, 'external_knowledge': {'used': False, 'used_types': []}} for row in rows], {})
        with patch.object(export, 'external_records', side_effect=labels):
            return export.export(self.run)

    def update_result(self, name, rows):
        root = self.run / 'results'
        export.save(root / name, rows)
        manifest = export.read(root / 'manifest.json')
        manifest['files'][name].update(sha256=export.sha(root / name), count=len(rows))
        export.save(root / 'manifest.json', manifest)

    def test_export_filters_current_decisions_and_preserves_source_files(self):
        before = {path: path.read_bytes() for path in self.run.rglob('*.json')}
        files = self.collect()
        root = self.run / 'results'
        self.assertEqual([r['id'] for r in export.read(root / '00-input.json')], [self.ids[0], self.ids[2], self.ids[3]])
        for index, (_, name) in enumerate(export.TYPES):
            ids = [r['id'] for r in export.read(root / (name + '.json'))]
            expected = [self.ids[2], self.ids[3]] if index == 0 else [self.ids[0], self.ids[2], self.ids[3]]
            self.assertEqual(ids, expected)
            self.assertEqual(files[name + '.json']['count'], len(expected))
        original_rows = export.read(root / '00-input.json')
        self.assertEqual(original_rows[1]['human_decision'], 'APPROVED')
        self.assertEqual(original_rows[2]['status'], 'FAIL')
        self.assertEqual(export.read(root / '02-ic-value-after.json')[0]['human_decision'], 'PENDING')
        manifest = export.read(root / 'manifest.json')
        self.assertEqual((manifest['source_input_count'], manifest['selected_count']), (4, 3))
        self.assertEqual(manifest['selection_policy'], policy.POLICY)
        self.assertEqual({entry['scope'] for entry in manifest['exclusions']}, {'original', 'variant'})
        for entry in manifest['exclusions']:
            self.assertEqual(entry['source_sha256'], export.sha(self.run / entry['source']))
        log = export.read(root / 'export-log.json')
        self.assertEqual(log['model_calls'], 0)
        self.assertEqual(log['exclusions'], manifest['exclusions'])
        self.assertEqual(log['excluded_count'], 2)
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw)

    def test_handoff_joins_sparse_variants_by_id_and_skips_incomplete_cohort(self):
        self.collect()
        rows, variants, _, _ = dataset.collected_results(self.run)
        self.assertEqual([r['id'] for r in rows], [self.ids[0], self.ids[2], self.ids[3]])
        self.assertNotIn(self.ids[0], variants[dataset.LABELS[0]])
        public, private, selection = dataset.select(self.settings)
        self.assertEqual(selection['case_ids'], [self.ids[2]])
        self.assertEqual(selection['variants'], 7)
        self.assertEqual(len(public), 8)
        self.assertEqual(private[0]['human_decision'], 'APPROVED')
        self.assertTrue(any(r['reason'] == 'INCOMPLETE_SEVEN_VARIANT_SET' for r in selection['exclusions']))

    def test_handoff_detects_changed_rejection_after_export(self):
        self.collect()
        export.save(self.variant_reject, {'decision': 'APPROVED'})
        with self.assertRaisesRegex(ValueError, 'RESULTS_REJECTION_STATUS_CHANGED'):
            dataset.select(self.settings)

    def test_handoff_excludes_current_rejection_added_after_export(self):
        self.collect()
        self.settings['require_all_variants_pass'] = False
        self.settings['excluded_ids'] = [self.ids[0]]
        folder = self.run / '02-generation/01-round' / self.ids[2] / export.TYPES[1][1]
        export.save(folder / '05-human-review/02-record-decision/decision.json', {'decision': 'REJECTED'})
        _, _, selection = dataset.select(self.settings)
        self.assertEqual(selection['variants'], 6)
        self.assertTrue(any(r.get('variant') == dataset.LABELS[1] and r['reason'] == 'EXPLICIT_REJECTION'
                            for r in selection['exclusions']))

    def test_missing_variant_requires_declared_rejection(self):
        self.collect()
        filename = dataset.RESULT_FILES[1]
        rows = export.read(self.run / 'results' / filename)
        self.update_result(filename, rows[1:])
        with self.assertRaisesRegex(ValueError, 'RESULTS_REJECTION_EXCLUSIONS_MISMATCH'):
            dataset.collected_results(self.run)

    def test_orphans_duplicates_and_wrong_order_are_rejected(self):
        for changed in ('orphan', 'duplicate', 'order'):
            with self.subTest(changed=changed):
                self.collect()
                filename = dataset.RESULT_FILES[1]
                rows = export.read(self.run / 'results' / filename)
                if changed == 'orphan':
                    rows[0]['id'] = 'test-9999'
                elif changed == 'duplicate':
                    rows[1]['id'] = rows[0]['id']
                else:
                    rows.reverse()
                self.update_result(filename, rows)
                with self.assertRaisesRegex(ValueError, 'RESULTS_TYPE_ALIGNMENT_MISMATCH'):
                    dataset.collected_results(self.run)

    def test_legacy_manifest_still_requires_full_alignment(self):
        self.collect()
        root = self.run / 'results'
        manifest = export.read(root / 'manifest.json')
        manifest['selection_policy'] = 'ALL_SELECTED_ORIGINALS_WITH_ALL_VARIANT_STATES'
        export.save(root / 'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'RESULTS_TYPE_ALIGNMENT_MISMATCH'):
            dataset.collected_results(self.run)

    def test_legacy_readme_does_not_claim_rejections_were_removed(self):
        text = export.results_readme('legacy-run', 4, 'ALL_SELECTED_ORIGINALS_WITH_ALL_VARIANT_STATES')
        self.assertIn('기존 행이나 Reject 판정을 제외하지 않았습니다', text)
        self.assertNotIn('현재 차수의 명시적', text)

    def test_model_document_is_readable_without_exposing_other_config_files(self):
        docs = importlib.import_module('finarch.dataset.viewer.reports.documentation')
        bundle = self.run / 'docs-check'
        export.save(bundle / 'documentation.json', {'kind': 'PIPELINE_DOCUMENTATION', 'documents': [
            {'path': 'config/MODELS-README.md', 'title': 'Models'},
            {'path': 'config/llm.json', 'title': 'Not an allowed model document'}]})
        export.save(bundle / 'migration.json', [])
        (self.run / 'config').mkdir()
        (self.run / 'config/MODELS-README.md').write_text('# Models\ngpt-6-luna / max\n')
        export.save(self.run / 'config/llm.json', {'private_fixture': True})
        with patch.object(docs, 'PROJECT', self.run):
            self.assertIn('gpt-6-luna', docs.read_document(bundle, 'config/MODELS-README.md')['content'])
            with self.assertRaisesRegex(ValueError, 'INVALID_DOCUMENT_PATH'):
                docs.read_document(bundle, 'config/llm.json')

    def test_current_active_round_and_recorded_decision_take_priority(self):
        root = self.run / '01-preparation' / self.ids[0]
        export.save(root / '00-round/07-human-review/03-record-decision/decision.json', {'decision': 'REJECTED'})
        self.collect()
        self.assertIn(self.ids[0], [r['id'] for r in export.read(self.run / 'results/00-input.json')])
        for value in policy.REJECTED:
            self.assertEqual(policy.current_decision({'human_decision': 'PENDING'}, {'decision': value.lower()}), value)
        self.assertEqual(policy.current_decision({'human_decision': 'REJECTED'}, {'decision': 'PENDING'}), 'PENDING')


if __name__ == '__main__':
    unittest.main()
