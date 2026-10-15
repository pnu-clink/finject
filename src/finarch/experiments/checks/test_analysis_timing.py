"""Check wall-time accounting, failure preservation and interrupted-run boundaries."""
from datetime import datetime, timezone
import importlib
from pathlib import Path
import tempfile
import unittest

timing = importlib.import_module('finarch.experiments.02-analysis.timing')


def event(identity, start, end=None, step='model_call'):
    def stamp(seconds):
        return datetime.fromtimestamp(seconds, timezone.utc).isoformat()
    row = {'span_id': identity, 'pid': 1, 'step': step, 'event': 'START', 'started_at': stamp(start)}
    if end is not None:
        row.update(event='END', ended_at=stamp(end), elapsed_seconds=end-start, status='COMPLETED')
    return row


class AnalysisTimingTest(unittest.TestCase):
    def test_parallel_calls_do_not_multiply_wall_time(self):
        value = timing.summarize([event('a', 0, 10), event('b', 5, 15)],
                                 now=datetime.fromtimestamp(15, timezone.utc))
        row = value['steps'][0]
        self.assertEqual(row['completed_call_seconds_sum'], 20)
        self.assertEqual(row['occupied_wall_seconds'], 15)
        self.assertEqual(row['p95_seconds'], 10)

    def test_nested_calls_are_not_added_to_bottleneck_denominator(self):
        value = timing.summarize([event('all', 0, 25, 'analysis_total'),
            event('model', 0, 20, 'comparison_models'), event('call', 0, 20),
            event('save', 20, 25, 'comparison_collection')])
        self.assertEqual(value['bottleneck']['share_of_measured_analysis_steps'], .8)

    def test_dead_process_does_not_accumulate_downtime(self):
        value = timing.summarize([event('a', 0)], now=datetime.fromtimestamp(100, timezone.utc),
                                 is_alive=lambda pid: False)
        self.assertEqual(value['status'], 'INTERRUPTED')
        self.assertEqual(value['steps'][0]['occupied_wall_seconds'], 0)
        self.assertEqual(value['steps'][0]['interrupted'], 1)
        self.assertEqual(value['active'], [])

    def test_running_call_remains_provisional(self):
        value = timing.summarize([event('a', 5, step='comparison_models')],
            now=datetime.fromtimestamp(15, timezone.utc), is_alive=lambda pid: True)
        self.assertEqual(value['active'][0]['elapsed_seconds'], 10)
        self.assertTrue(value['bottleneck']['provisional'])
        self.assertIsNone(value['steps'][0]['p50_seconds'])

    def test_failure_keeps_start_end_and_automatic_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'fixture failure'):
                with timing.measure(root, 'analysis_total'):
                    raise ValueError('fixture failure')
            rows = timing.store.rows(root / '02_analysis/timing-events.jsonl')
            self.assertEqual([row['event'] for row in rows], ['START', 'END'])
            self.assertEqual(rows[-1]['status'], 'FAILED')
            self.assertEqual(rows[-1]['error_type'], 'ValueError')
            self.assertGreaterEqual(rows[-1]['elapsed_seconds'], 0)
            self.assertTrue((root / '02_analysis/timing.md').is_file())


if __name__ == '__main__':
    unittest.main()
