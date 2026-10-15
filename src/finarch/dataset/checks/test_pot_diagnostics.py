"""POT diagnostics preserve failures without promoting them; no provider calls."""
import importlib
import json
import unittest
from unittest.mock import patch

from finarch.shared.providers.structured import complete
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult

d = importlib.import_module('finarch.dataset.01-preparation.03-calculation.diagnostics')


class DiagnosticsChecks(unittest.TestCase):
    def response(self):
        return {'code': "answer = fact('n')", 'facts': [
            {'id': 'n', 'span': [0, 1], 'text': '2', 'value': '2', 'unit': None}],
            'grounding': 'Use the supplied number.', 'external_evidence': [],
            'calculation_input_sources': ['IN_CONTEXT_DATA'], 'source_usage': [
                {'id': 'instruction', 'kind': 'IN_CONTEXT_DATA', 'description': 'Question instruction',
                 'fact_ids': [], 'evidence_ids': [], 'acquisition': 'SUPPLIED',
                 'source_title': None, 'source_url': None, 'locator': None, 'quote': 'Round.',
                 'applicability': 'Final answer', 'code_lines': [1], 'output_variables': ['answer']} ]}

    def test_invalid_provenance_still_executes_and_is_rejected(self):
        saved = {}; events = []
        def save(name, value):
            saved[name] = value
        def diagnose(value):
            events.append('diagnose')
            d.preserve_and_execute(value, '2', save, save)
        def transport(**kwargs):
            events.append('transport')
            return json.dumps(self.response())
        with patch.object(d, 'execute', return_value=StepResult('PASS', 'Executed', {'exact_value': '2'})) as execute:
            result = complete('01-preparation.03-calculation.pot', {'context': '2', 'question': 'Round.',
                              'reference_answer_type':'integer', 'reference_precision':0,
                              'answer_metadata':{'scale':None}},
                              transport=transport, save=save, schema_mode='native', before_validate=diagnose)
        execute.assert_called_once()
        self.assertEqual(events, ['transport', 'diagnose'])
        self.assertEqual(result.status, 'FAIL')
        self.assertEqual(saved['02-program.py'], self.response()['code'])
        self.assertEqual(saved['06-summary.json']['execution']['status'], 'PASS')
        self.assertEqual(saved['06-summary.json']['response_check']['status'], 'FAIL')
        self.assertFalse(saved['06-summary.json']['accepted'])

    def test_execution_error_does_not_hide_response_check(self):
        saved = {}
        with patch.object(d, 'execute', side_effect=ValueError('NUMERIC_ANSWER_REQUIRED')):
            d.preserve_and_execute(self.response(), '2', lambda n,v:saved.update({n:v}), lambda n,v:saved.update({n:v}))
        self.assertEqual(saved['06-summary.json']['execution']['status'], 'FAIL')
        self.assertEqual(saved['06-summary.json']['response_check']['status'], 'FAIL')

    def test_malformed_execution_fields_never_execute(self):
        saved = {}; value = self.response(); value['facts'][0]['value'] = {'bad': 1}
        with patch.object(d, 'execute') as execute:
            d.preserve_and_execute(value, '2', lambda n,v:saved.update({n:v}), lambda n,v:saved.update({n:v}))
        execute.assert_not_called()
        self.assertIn('02-program.py', saved)
        self.assertEqual(saved['04-execution/result.json']['status'], 'FAIL')
