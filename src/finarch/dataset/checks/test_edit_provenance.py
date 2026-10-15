"""Offline checks for staged edits, missing history, and unchanged dataset payloads."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

edits = __import__('finarch.dataset.03-release.edit_provenance', fromlist=['*'])
exporter = __import__('finarch.dataset.03-release.export_run_results', fromlist=['*'])


def patch(start, end, before, text, kind='VALUE'):
    return {'start': start, 'end': end, 'before': before, 'text': text,
            'element_ids': ['number-a'], 'segments': [{'kind': kind, 'text': text}],
            'purpose': 'Preserve the saved edit.'}


class EditProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.base = {'question': 'What is the amount?', 'context': '😀 A=10.'}
        self.value = patch(len(self.base['context']), len(self.base['context']), '', '\nB=20.')
        self.middle = self.base['context'] + self.value['text']
        self.source = patch(self.middle.index('20'), self.middle.index('20'), '', '(source) ', 'SOURCE_B')
        self.final = {**self.base, 'context': self.middle.replace('20', '(source) 20')}
        self.comparison = {'reference': self.base, 'working': self.final,
                           'value_dependency': [self.value], 'patches': [self.source]}

    def test_source_replays_unicode_parent_before_nested_child(self):
        record = edits.build('test-1', 'IC_SOURCE_B_ONLY', self.base, self.final, self.comparison)
        self.assertEqual(record['status'], 'VERIFIED')
        self.assertEqual([step['variant'] for step in record['steps']],
                         ['IC_VALUE_01_AFTER', 'IC_SOURCE_B_ONLY'])
        self.assertEqual(record['steps'][0]['patches'], [self.value])
        self.assertEqual(record['steps'][1]['input_context_sha256'], edits.text_sha(self.middle))
        self.assertEqual(edits.checked(record, 'test-1', 'IC_SOURCE_B_ONLY', self.base, self.final), record)
        self.assertNotEqual(self.source['start'], len(self.middle[:self.source['start']].encode('utf-16-le')) // 2)

    def test_same_stage_offsets_use_pre_edit_context_and_deletion_is_retained(self):
        before = 'A 10; B 20'
        patches = [patch(2, 4, '10', '100'), patch(8, 10, '20', '', 'EA')]
        after = edits.apply_patches(before, patches)
        self.assertEqual(after, 'A 100; B ')
        base, final = {**self.base, 'context': before}, {**self.base, 'context': after}
        record = edits.build('test-1', 'EA_02', base, final,
                             {'reference': base, 'working': final, 'patches': patches})
        self.assertEqual(record['status'], 'VERIFIED')
        self.assertEqual(record['steps'][0]['patches'][1]['before'], '20')
        self.assertNotIn('20', final['context'])

    def test_missing_history_is_not_no_changes(self):
        self.assertEqual(edits.build('test-1', 'IC_SOURCE_B_ONLY', self.base, self.final)['status'], 'UNAVAILABLE')
        record = edits.build('test-1', 'IC_SOURCE_B_ONLY', self.base, self.final,
                             {**self.comparison, 'value_dependency': None})
        self.assertEqual(record['status'], 'UNAVAILABLE')
        self.assertEqual(record['reason'], 'NO_SAVED_PATCHES')

    def test_wrong_before_overlapping_edits_and_false_segments_are_rejected(self):
        for patches, reason in [([patch(0, 1, 'X', 'Y')], 'PATCH_BEFORE_MISMATCH'),
                                ([patch(0, 1, 'A', 'Y'), patch(0, 0, '', 'Z')], 'PATCH_OVERLAP'),
                                ([{**patch(0, 1, 'A', 'Y'), 'segments': [{'kind': 'VALUE', 'text': 'Z'}]}],
                                 'PATCH_SEGMENTS_MISMATCH')]:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                edits.apply_patches('ABC', patches)

    def test_changed_question_and_stale_baseline_are_not_verified(self):
        for base, final in [({**self.base, 'context': 'changed'}, self.final),
                            (self.base, {**self.final, 'question': 'Changed question?'})]:
            self.assertEqual(edits.build('test-1', 'IC_SOURCE_B_ONLY', base, final, self.comparison)['status'], 'MISMATCH')

    def test_binding_detects_wrong_hash_order_and_request_context(self):
        original = edits.build('test-1', 'IC_SOURCE_B_ONLY', self.base, self.final, self.comparison)
        bad = copy.deepcopy(original)
        bad['steps'][0]['output_context_sha256'] = 'bad'
        self.assertEqual(edits.checked(bad, 'test-1', 'IC_SOURCE_B_ONLY', self.base, self.final)['reason'],
                         'EDIT_OUTPUT_HASH_MISMATCH')
        bad = copy.deepcopy(original)
        bad['steps'].reverse()
        self.assertEqual(edits.checked(bad, 'test-1', 'IC_SOURCE_B_ONLY', self.base, self.final)['reason'],
                         'EDIT_STEP_ORDER_MISMATCH')
        self.assertEqual(edits.checked(original, 'test-1', 'IC_SOURCE_B_ONLY', self.base,
                                       {**self.final, 'context': 'different request'})['reason'],
                         'EXPERIMENT_FINAL_MISMATCH')

    def test_original_is_explicit_empty_chain(self):
        original = edits.build('test-1', 'ORIGINAL', self.base, self.base)
        self.assertEqual(original['status'], 'VERIFIED')
        self.assertEqual(original['steps'], [])
        self.assertEqual(edits.build('test-1', 'ORIGINAL', self.base, self.final)['status'], 'MISMATCH')

    def test_enrich_existing_preserves_every_original_field_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exporter.save(root / 'results/00-input.json', [{'id': 'test-1', 'status': 'PASS', 'input': self.base}])
            filenames = ['00-input.json']
            for label, folder in exporter.TYPES:
                filenames.append(folder + '.json')
                exporter.save(root / 'results' / filenames[-1], [
                    {'id': 'test-1', 'type': label, 'status': 'NOT_RUN', 'question': None,
                     'context': None, 'result': None}])
            old_rows = {name: exporter.read(root / 'results' / name) for name in filenames}
            exporter.save(root / 'results/manifest.json', {'source_run': root.name, 'selected_count': 1,
                'files': {name: {'sha256': exporter.sha(root / 'results' / name), 'count': 1} for name in filenames}})
            first = exporter.enrich_existing(root)
            self.assertTrue(first['changed'])
            self.assertEqual(first['edit_provenance_counts']['00-input.json'], {'VERIFIED': 1})
            for name in filenames:
                now = exporter.read(root / 'results' / name)
                self.assertEqual([{k: v for k, v in row.items() if k != 'edit_provenance'} for row in now], old_rows[name])
                self.assertEqual(exporter.read(root / 'results/manifest.json')['files'][name]['sha256'],
                                 exporter.sha(root / 'results' / name))
            before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'results').iterdir()}
            self.assertFalse(exporter.enrich_existing(root)['changed'])
            self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'results').iterdir()})
            (root / 'results/00-input.json').write_text('[]')
            with self.assertRaisesRegex(ValueError, 'RESULTS_FILE_HASH_MISMATCH'):
                exporter.enrich_existing(root)

    def test_new_exports_include_provenance_without_changing_original_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = {'id': 'test-1', **self.base, 'reference_precision': 0, 'reference_answer': '10'}
            exporter.save(root / 'input.json', [original])
            exporter.save(root / 'input-selection.json', {'input_path': str(root / 'input.json'), 'cases': ['test-1']})
            exporter.save(root / '02-generation/result-report.json', {'rows': []})
            files = exporter.export(root)
            self.assertEqual(len(files), 8)
            saved = exporter.read(root / 'results/00-input.json')[0]
            self.assertEqual(saved['input'], original)
            self.assertEqual(saved['edit_provenance']['status'], 'VERIFIED')
            for _, folder in exporter.TYPES:
                variant = exporter.read(root / 'results' / (folder + '.json'))[0]
                self.assertEqual(variant['status'], 'NOT_RUN')
                self.assertEqual(variant['edit_provenance']['status'], 'UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
