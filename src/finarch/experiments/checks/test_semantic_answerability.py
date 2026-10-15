"""Offline classification, evidence binding, and preservation regression checks."""
import copy
from importlib import import_module
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

m = import_module('finarch.experiments.02-analysis.05-outcomes.semantic_answerability')
pipeline = import_module('finarch.experiments.02-analysis.pipeline')


class OutcomeTests(unittest.TestCase):
    def outcome(self, action, arv, dg, match=None, item=None, status='COMPLETED'):
        return m.classify(action, status, arv, dg, match, item)

    def test_supported_answer_and_abstention(self):
        answer = self.outcome('N', 'NOT_APPLICABLE', 'SUPPORTED')
        abstention = self.outcome('A', 'SUPPORTED', 'SUPPORTED')
        self.assertEqual(answer['semantic_answerability'], 'SUPPORTED_ANSWER')
        self.assertEqual(answer['item_answerability'], 'ANSWERABLE')
        self.assertEqual(abstention['semantic_answerability'], 'SUPPORTED_ABSTENTION')
        self.assertEqual(abstention['item_answerability'], 'UNANSWERABLE')
        self.assertEqual(answer['item_answerability_basis'], 'RESPONSE_REVIEW_INFERENCE')

    def test_unsupported_is_not_false_positive_or_false_negative(self):
        for match in (True, False, None):
            row = self.outcome('N', 'NOT_APPLICABLE', 'UNSUPPORTED', match)
            self.assertEqual(row['semantic_answerability'], 'UNCLASSIFIED')
            self.assertEqual(row['item_answerability'], 'UNDETERMINED')
        for arv, dg in (('SUPPORTED', 'UNSUPPORTED'), ('UNSUPPORTED', 'SUPPORTED'),
                        ('UNSUPPORTED', 'UNSUPPORTED'), ('UNDETERMINED', 'UNSUPPORTED'),
                        ('UNSUPPORTED', 'UNDETERMINED')):
            self.assertEqual(self.outcome('A', arv, dg)['semantic_answerability'], 'UNCLASSIFIED')

    def test_independent_evidence_needed_for_failure_action(self):
        self.assertEqual(self.outcome('A', 'UNSUPPORTED', 'UNSUPPORTED', item='ANSWERABLE')['semantic_answerability'], 'UNNECESSARY_ABSTENTION')
        self.assertEqual(self.outcome('N', 'NOT_APPLICABLE', 'UNSUPPORTED', item='UNANSWERABLE')['semantic_answerability'], 'MISSED_ABSTENTION')
        self.assertEqual(self.outcome('N', 'NOT_APPLICABLE', 'UNSUPPORTED', item='ANSWERABLE')['semantic_answerability'], 'UNCLASSIFIED')
        self.assertEqual(self.outcome('A', 'UNSUPPORTED', 'UNSUPPORTED', item='UNANSWERABLE')['semantic_answerability'], 'UNCLASSIFIED')

    def test_conflicting_or_missing_judgments_are_not_forced(self):
        for action, arv, dg, item in (('N', 'NOT_APPLICABLE', 'SUPPORTED', 'UNANSWERABLE'),
                                      ('A', 'SUPPORTED', 'SUPPORTED', 'ANSWERABLE')):
            row = self.outcome(action, arv, dg, item=item)
            self.assertEqual(row['classification_reason'], 'ITEM_AND_RESPONSE_REVIEW_DISAGREE')
            self.assertEqual(row['semantic_answerability'], 'UNCLASSIFIED')
        for status in ('REVIEW_FAILED', 'NOT_REVIEWABLE', 'NOT_RUN', 'STALE_TARGET', 'STALE_INPUT'):
            self.assertEqual(self.outcome('N', None, 'SUPPORTED', item='UNANSWERABLE', status=status)['semantic_answerability'], 'UNCLASSIFIED')

    def test_undetermined_and_invalid_verdicts(self):
        self.assertEqual(self.outcome('N', 'NOT_APPLICABLE', 'UNDETERMINED')['nasu'], 'ND')
        self.assertEqual(self.outcome('A', 'SUPPORTED', 'UNDETERMINED')['nasu'], 'AD')
        self.assertEqual(self.outcome('A', None, 'SUPPORTED')['nasu'], 'F')

    def test_item_evidence_is_input_bound(self):
        public = {'v': {'question': 'What is revenue?', 'context': 'Revenue is 12.'}}
        good = {'item_id': 'v', 'basis': 'INDEPENDENT_ITEM_REVIEW', 'status': 'VERIFIED',
                'value': 'ANSWERABLE', 'reviewer': 'human-example', 'reason': 'The requested value is explicit.',
                'public_input_sha256': m.store.digest(public['v']),
                'citations': [{'source': 'context', 'quote': 'Revenue is 12.'}]}
        self.assertEqual(m.item_reviews([good], public)['v'], good)
        for change in ({'basis': 'NASU'}, {'public_input_sha256': 'stale'}, {'citations': []},
                       {'citations': [{'source': 'context', 'quote': 'Invented'}]}):
            with self.assertRaises(ValueError):
                m.item_reviews([good | change], public)

    def test_snapshot_detects_missing_source_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'missing.json'
            snap = m.Snapshot()
            self.assertIsNone(snap.read(path))
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                snap.verify()

    def test_pipeline_final_hook_does_not_call_models_itself(self):
        summary = {'schema_version': m.VERSION, 'scopes': {'variants': {'total': 7}}}
        with patch.object(pipeline.a04, 'run', return_value={'status': 'COLLECTED'}), patch.object(pipeline.outcomes, 'build', return_value=summary) as build:
            value = pipeline.finish_postprocessing(Path('fixture'))
            build.assert_called_once()
            self.assertEqual(value['semantic_response_outcomes']['new_model_calls'], 0)
        with patch.object(pipeline.a04, 'run', return_value={'status': 'PARTIAL'}), patch.object(pipeline.outcomes, 'build') as build:
            pipeline.finish_postprocessing(Path('fixture'))
            build.assert_not_called()

    def test_build_preserves_inputs_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source.json'
            source.write_text('{"frozen": true}')
            before = source.read_bytes()
            snap = m.Snapshot()
            snap.read(source)
            rows = [{'run': root.name, 'variant': 'EA_01', 'model': 'example', 'dataset': 'test',
                     'prompt_condition': 'guided', 'reasoning': 'off', 'independent_item_review': None, 'review_status': 'COMPLETED',
                     **m.classify('A', 'COMPLETED', 'SUPPORTED', 'SUPPORTED')}]
            with patch.object(m, 'extract', return_value=(rows, snap)):
                first = m.build(root)
                second = m.build(root)
            self.assertEqual(first, second)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(sum(first['scopes']['variants'][c] for c in m.CATEGORIES), 1)
            self.assertEqual(first['scopes']['h1']['SUPPORTED_ABSTENTION'], 1)
            self.assertFalse((root / m.OUTPUT / 'history').exists())

    def test_changing_run_reports_previous_snapshot_as_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'run'
            output = root / m.OUTPUT
            m.store.write_rows(output / 'responses.jsonl', [])
            previous = {'schema_version': m.VERSION, 'run': root.name, 'generated_at': 'saved-time',
                        'groups': [], 'scopes': {'variants': m.counts([])},
                        'output_hashes': {'responses.jsonl': m.store.file_hash(output / 'responses.jsonl')}}
            m.store.write(output / 'summary.json', previous)
            report = Path(temp) / 'models.md'
            with patch.object(m, 'build', side_effect=ValueError('SOURCE_CHANGED')), patch('sys.argv',
                    ['outcomes', '--run', str(root), '--report', str(report)]), patch('builtins.print'):
                with self.assertRaises(SystemExit) as error:
                    m.main()
            self.assertEqual(error.exception.code, 1)
            result = m.store.read(report.with_suffix('.json'))
            self.assertEqual(result['runs'][0]['snapshot_status'], 'PREVIOUS_SNAPSHOT_NOT_REFRESHED')
            self.assertEqual(result['not_published'][0]['reason'], 'SOURCE_CHANGED')
            self.assertEqual(m.store.read(output / 'summary.json'), previous)


if __name__ == '__main__':
    unittest.main()
