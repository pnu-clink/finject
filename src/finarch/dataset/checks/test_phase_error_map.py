import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from finarch.dataset.viewer.reports.phase_report import build, source_signature


class PhaseMapTests(unittest.TestCase):
    def test_observed_failure_not_feedback_target_and_carried_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = '02-generation/01-round/test-0001/01-ic-value-before/run.json'
            p = root / source
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'status': 'FAIL', 'restart': '01-perturbation',
                                    'recovery': {'target_step': '02-generate-text'}}))
            row = {'case': 'test-0001', 'type': 'IC_VALUE', 'variant': '01-ic-value-before',
                   'rounds': [{'status': 'FAIL', 'source': source, 'reason': 'PLAN_ERROR', 'carried': True}]}
            snapshot = {'generation': {'rows': [row], 'rounds': []}}
            with patch('finarch.dataset.viewer.reports.phase_report.snapshot', return_value=snapshot), \
                 patch('finarch.dataset.viewer.reports.phase_report.token_usage', return_value={'generated_at': 'test'}):
                result = build(root, 'generation')
            self.assertEqual(result['maps'][0]['error_stage'], '01')
            self.assertEqual(result['maps'][0]['round'], '01-round')
            self.assertEqual(result['stage_columns'], ['01', '02', '03', '04'])
            before = source_signature(root, 'generation')
            p.write_text('{"status":"PASS"}')
            self.assertNotEqual(before, source_signature(root, 'generation'))

    def test_not_evaluated_is_neither_pass_nor_error(self):
        row = {'case': 'test-0001', 'type': 'ANSWER',
               'rounds': [{'status': 'NOT_EVALUATED', 'reason': 'NO_RESULT', 'source': None}]}
        with tempfile.TemporaryDirectory() as tmp, \
             patch('finarch.dataset.viewer.reports.phase_report.snapshot', return_value={'preparation': {'rows': [row], 'rounds': []}}), \
             patch('finarch.dataset.viewer.reports.phase_report.token_usage', return_value={'generated_at': 'test'}):
            result = build(tmp, 'preparation')
        self.assertEqual(result['summary'][0]['NOT_EVALUATED'], 1)
        self.assertEqual(result['summary'][0]['PASS'], 0)
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['stage_columns']), 7)
