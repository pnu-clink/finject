"""Verify Analysis-only sequencing and honest completion/failure publication."""
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sequence = importlib.import_module('finarch.experiments.90-operations.analysis_sequence')
store = sequence.store


class SequenceTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.roots = [Path(tmp.name).resolve() / name for name in ('first', 'second')]
        for root in self.roots:
            store.write(root / 'state.json', {'models': {'solver': {'status': 'FINISHED'}},
                        'execution_control': {'evaluation': {'paused': True}, 'analysis': {'paused': False}}})

    def test_finished_evaluation_stays_paused_and_analysis_completes_in_order(self):
        with patch.object(sequence.analysis, 'run', return_value={'status': 'COLLECTED'}) as run:
            sequence.run(self.roots, interval=0)
        self.assertEqual([call.args[0] for call in run.call_args_list], self.roots)
        for root in self.roots:
            saved = store.read(root / 'state.json')
            self.assertTrue(saved['execution_control']['evaluation']['paused'])
            self.assertEqual(saved['full_pipeline']['status'], 'COMPLETE')
            self.assertEqual(saved['full_pipeline']['execution_scope'], 'ANALYSIS_ONLY')
        first = store.read(self.roots[0] / 'state.json')['queued_execution']
        second = store.read(self.roots[1] / 'state.json')['queued_execution']
        self.assertIsNone(first['after_run'])
        self.assertEqual(second['after_run'], self.roots[0].name)
        self.assertEqual(first['queue_pid'], second['queue_pid'])

    def test_needs_review_prevents_following_run(self):
        with patch.object(sequence.analysis, 'run', return_value={'status': 'NEEDS_REVIEW'}) as run:
            sequence.run(self.roots, interval=0)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(store.read(self.roots[0] / 'state.json')['full_pipeline']['status'], 'NEEDS_REVIEW')
        self.assertNotIn('full_pipeline', store.read(self.roots[1] / 'state.json'))

    def test_no_patterns_is_not_published_as_regular_complete(self):
        with patch.object(sequence.analysis, 'run', return_value={'status': 'ASSESSMENTS_COLLECTED_NO_PATTERNS'}):
            sequence.run(self.roots[:1], interval=0)
        self.assertEqual(store.read(self.roots[0] / 'state.json')['full_pipeline']['status'], 'COMPLETE_NO_PATTERN_FINDINGS')

    def test_queue_waits_for_both_analysis_and_full_pipeline_completion(self):
        parent = self.roots[0].parent / 'preceding'
        store.write(parent / 'state.json', {'analysis': {'status': 'COMPLETE'}, 'full_pipeline': {'status': 'RUNNING'}})
        def finish(_):
            self.assertEqual(store.read(self.roots[0] / 'state.json')['queued_execution']['status'], 'WAITING_FOR_ANALYSIS')
            store.write(parent / 'state.json', {'analysis': {'status': 'COMPLETE'}, 'full_pipeline': {'status': 'COMPLETE'}})
        with patch.object(sequence.time, 'sleep', side_effect=finish) as wait, \
             patch.object(sequence.analysis, 'run', return_value={'status': 'COLLECTED'}) as run:
            sequence.run(self.roots, interval=0, after_run=parent)
        wait.assert_called_once()
        self.assertEqual([call.args[0] for call in run.call_args_list], self.roots)
        self.assertEqual(store.read(self.roots[0] / 'state.json')['queued_execution']['status'], 'STARTED')

    def test_unresolved_predecessor_does_not_dispatch_any_following_calls(self):
        parent = self.roots[0].parent / 'preceding'
        store.write(parent / 'state.json', {'analysis': {'status': 'BLOCKED'}, 'full_pipeline': {'status': 'NEEDS_REVIEW'}})
        def pause(_):
            saved = store.read(self.roots[0] / 'state.json')
            saved['execution_control']['analysis']['paused'] = True
            store.write(self.roots[0] / 'state.json', saved)
        with patch.object(sequence.time, 'sleep', side_effect=pause), patch.object(sequence.analysis, 'run') as run:
            sequence.run(self.roots, interval=0, after_run=parent)
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
