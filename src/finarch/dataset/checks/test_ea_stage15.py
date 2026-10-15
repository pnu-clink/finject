"""EA15 regression cases for direct residue and the two observed-input deletions."""
import copy
import unittest

from finarch.dataset.checks.review_ea_stage15 import occurrences
build = __import__('finarch.dataset.02-generation.01-perturbation.ea_plan', fromlist=['build']).build
compose_ea = __import__('finarch.dataset.02-generation.02-generate-text.text_preview', fromlist=['compose_ea']).compose_ea


class EAStage15Checks(unittest.TestCase):
    def fixture(self, key):
        context = 'Service fees totaling 80,000, commissions reaching 45,000.'
        facts = {}
        for name, text in [('service_fee_income', '80,000'), ('commission_income', '45,000')]:
            start = context.index(text)
            facts[name] = {'span': [start, start + len(text)], 'text': text,
                           'value': text.replace(',', ''), 'unit': 'dollars'}
        program = {'context': context, 'facts': facts,
                   'code': 'A=fact("service_fee_income")\nB=fact("commission_income")\nanswer=A+B'}
        graph, _, _ = build(program, key)
        plan = {'axis': 'EA', 'method': 'missing-input-dag-v1', 'fact_id': key,
                'deletion': {'span': facts[key]['span'], 'before': facts[key]['text']},
                'graphs': {'EA': graph}, 'result': {'answer': None, 'missing_facts': [key]}}
        return {'context': context, 'question': 'What is the total?'}, program, plan

    def test_both_input_choices_preserve_the_other_amount(self):
        for key, removed, retained in [('service_fee_income', '80,000', '45,000'),
                                       ('commission_income', '45,000', '80,000')]:
            with self.subTest(key=key):
                sample, program, plan = self.fixture(key)
                preview = compose_ea(sample, plan, program)
                self.assertNotIn(removed, preview['preview_context'])
                self.assertIn(retained, preview['preview_context'])
                self.assertNotIn('[EA_DELETE:', preview['preview_context'])
                self.assertEqual(preview['question'], sample['question'])
                self.assertIsNone(preview['calculation_result']['answer'])

    def test_wrong_span_or_overlapping_other_input_is_rejected(self):
        sample, program, plan = self.fixture('service_fee_income')
        wrong = copy.deepcopy(plan); wrong['deletion']['span'][0] += 1
        with self.assertRaisesRegex(ValueError, 'EVIDENCE_MISMATCH'):
            compose_ea(sample, wrong, program)
        overlap = copy.deepcopy(program)
        overlap['facts']['commission_income']['span'] = program['facts']['service_fee_income']['span']
        with self.assertRaisesRegex(ValueError, 'DELETES_OTHER_FACT'):
            compose_ea(sample, plan, overlap)

    def test_same_number_in_other_notation_is_found_without_substring_matches(self):
        matches = occurrences('80,000 / 80000 / 80000.0 / 180000 / 80,000%', '80000')
        self.assertEqual([m['text'] for m in matches], ['80,000', '80000', '80000.0'])
        self.assertEqual(occurrences('45,000', '80000'), [])


if __name__ == '__main__':
    unittest.main()
