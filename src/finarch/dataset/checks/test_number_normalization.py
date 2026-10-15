"""Number-format conversion preserves source and chains registered methods in order."""
import copy
import unittest
from unittest.mock import patch

from finarch.dataset.shared.calculation.number_normalization import load_rules, normalize_number, prepare_numeric_values, validate_rules
from finarch.dataset.shared.calculation.python_runtime import execute


class NumberNormalizationChecks(unittest.TestCase):
    def test_adjacent_dollar_citation_is_repaired_before_source_check(self):
        program = self.program('80,000')
        program['context'] = '$80,000'
        program['facts']['x'].update(span=[1, 7], text='$80,000', value='80000', unit='$')
        original = copy.deepcopy(program)
        saved = {}
        result = execute(program, save=lambda name, data: saved.update({name: data}))
        self.assertEqual(result.status, 'PASS')
        self.assertEqual(float(result.data['exact_value']), 80000)
        self.assertEqual(program, original)
        entry = saved['number-normalization.json']['facts'][0]
        self.assertEqual(entry['source_text'], '$80,000')
        self.assertEqual(entry['validated_source_text'], '80,000')
        self.assertEqual(entry['source_applied_rules'], ['align_adjacent_dollar_citation'])

    def test_dollar_rule_does_not_hide_wrong_digits_or_wrong_source(self):
        for context, span, text in [('$80,000', [1, 7], '$90,000'),
                                    ('€80,000', [1, 7], '$80,000'),
                                    ('80,000', [0, 6], '$80,000')]:
            program = self.program('80000')
            program['context'] = context
            program['facts']['x'].update(span=span, text=text)
            with patch('finarch.dataset.shared.calculation.python_runtime.subprocess.Popen') as worker:
                with self.assertRaisesRegex(ValueError, 'FACT_TEXT_MISMATCH'):
                    execute(program)
            worker.assert_not_called()

    def test_repaired_citation_still_checks_numeric_value(self):
        program = self.program('90000')
        program['context'] = '$80,000'
        program['facts']['x'].update(span=[1, 7], text='$80,000')
        with self.assertRaisesRegex(ValueError, 'FACT_VALUE_MISMATCH'):
            execute(program)

    def test_grouped_commas_preserve_sign_decimal_and_value(self):
        rules, _ = load_rules()
        for source, expected in [('80,000', '80000'), ('-1,234,567.50', '-1234567.50'),
                                 ('+12,345.67', '+12345.67'), ('100', '100')]:
            with self.subTest(source=source):
                value, applied = normalize_number(source, rules)
                self.assertEqual(value, expected)
                self.assertEqual(bool(applied), ',' in source)

    def test_multiple_methods_chain_in_declared_order(self):
        comma = next(r for r in load_rules()[0]['rules'] if r['id']=='remove_thousands_commas')
        rules = {'version': 1, 'rules': [
            {'id': 'currency', 'kind': 'literal_replace', 'from': '$', 'to': '', 'enabled': True},
            {'id': 'spaces', 'kind': 'strip_whitespace', 'enabled': True}, comma]}
        validate_rules(rules)
        steps = []
        value, applied = normalize_number('$ 80,000 ', rules, steps)
        self.assertEqual(value, '80000')
        self.assertEqual(applied, ['currency', 'spaces', 'remove_thousands_commas'])
        self.assertEqual([(s['before'], s['after']) for s in steps],
                         [('$ 80,000 ', ' 80,000 '), (' 80,000 ', '80,000'), ('80,000', '80000')])
        # The regex runs too early in reverse order: order is observable, not cosmetic.
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_COMMA_FORMAT'):
            normalize_number('$ 80,000 ', {'rules': list(reversed(rules['rules']))})

    def test_disabled_and_nonmatching_rules_do_not_change_values(self):
        rules = copy.deepcopy(load_rules()[0])
        rules['rules'].insert(0, {'id': 'disabled', 'kind': 'literal_replace',
                                  'from': '8', 'to': '9', 'enabled': False})
        steps = []
        self.assertEqual(normalize_number('80', rules, steps), ('80', []))
        self.assertEqual(len(steps), sum(r['enabled'] for r in rules['rules']))
        self.assertFalse(steps[0]['changed'])

    def test_percent_suffix_preserves_percent_magnitude(self):
        rules=load_rules()[0]
        self.assertEqual(normalize_number('25%',rules)[0],'25')
        self.assertEqual(normalize_number('1,000%',rules)[0],'1000')
        self.assertEqual(normalize_number('0.25',rules)[0],'0.25')

    def test_unknown_method_is_rejected(self):
        rules = {'version': 1, 'rules': [{'id': 'x', 'kind': 'eval', 'enabled': True}]}
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_NUMBER_TRANSFORM'):
            validate_rules(rules)

    def test_unrecognized_comma_format_never_reaches_worker(self):
        for value in ['1,5', '12,34', '80,000,']:
            program = self.program(value)
            saved = {}
            with patch('finarch.dataset.shared.calculation.python_runtime.subprocess.Popen') as worker:
                result = execute(program, save=lambda name, data: saved.update({name: data}))
            worker.assert_not_called()
            self.assertEqual(result.status, 'FAIL')
            self.assertEqual(saved['number-normalization.json']['facts'][0]['error'], 'UNSUPPORTED_COMMA_FORMAT')

    def program(self, value):
        return {'context': value, 'code': 'answer=fact("x")',
                'facts': {'x': {'span': [0, len(value)], 'text': value, 'value': value, 'unit': None}}}

    def test_source_and_code_unchanged_and_runtime_gets_converted_value(self):
        program = self.program('80,000')
        original = copy.deepcopy(program)
        prepared, audit, _ = prepare_numeric_values(program)
        self.assertEqual(program, original)
        self.assertEqual(prepared['code'], original['code'])
        self.assertEqual(prepared['facts']['x']['text'], '80,000')
        self.assertEqual(prepared['facts']['x']['value'], '80000')
        self.assertEqual(audit['facts'][0]['original_value'], '80,000')
        saved = {}
        result = execute(program, save=lambda name, data: saved.update({name: data}))
        self.assertEqual(result.status, 'PASS')
        self.assertEqual(float(result.data['exact_value']), 80000)
        self.assertEqual(program, original)
        self.assertEqual(saved['number-normalization.json'], audit)


if __name__ == '__main__':
    unittest.main()
