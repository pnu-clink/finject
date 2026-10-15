import contextlib
import io
import unittest

from finarch.dataset.shared.calculation.standalone import render_standalone


class StandaloneChecks(unittest.TestCase):
    def program(self):
        return {'code': 'amount = fact("fee")\nanswer = round(amount / 2)',
                'facts': {'fee': {'value': '80,000', 'text': '80,000', 'span': [0, 6], 'unit': '$'}}}

    def test_complete_program_runs_without_finarch_imports_or_files(self):
        original = self.program()
        rendered = render_standalone(original)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile(rendered['code'], '<standalone>', 'exec'), {})
        self.assertEqual(output.getvalue().strip(), '40000')
        self.assertEqual(original['facts']['fee']['value'], '80,000')
        lines = rendered['code'].splitlines()
        self.assertEqual(lines[rendered['original_start_line'] - 1], 'amount = fact("fee")')

    def test_uses_saved_normalized_values_and_rejects_wrong_record(self):
        program = self.program()
        audit = {'status': 'PASS', 'facts': [{'fact_id': 'fee', 'original_value': '80,000', 'python_value': '80000'}]}
        self.assertEqual(render_standalone(program, audit)['fact_values']['fee'], '80000')
        audit['facts'][0]['original_value'] = '90,000'
        with self.assertRaisesRegex(ValueError, 'NORMALIZATION_VALUE_MISMATCH'):
            render_standalone(program, audit)

    def test_original_model_code_is_included_without_repairs(self):
        program = self.program()
        program['code'] = 'answer = (fact("fee")'
        self.assertIn(program['code'], render_standalone(program)['code'])
