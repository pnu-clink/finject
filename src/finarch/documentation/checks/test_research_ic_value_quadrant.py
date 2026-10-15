"""Regression checks for dataset identity, denominator and repeat handling."""
import copy
import unittest

from finarch.documentation import research_ic_value_quadrant as view


def fixture(feature=view.FEATURE, choice='A'):
    matrix, pairs = [], []
    for reasoning in ('off', 'on'):
        endpoints = {}
        for prompt in ('unguided', 'guided'):
            rows = [{'case': case, 'prompt_condition': prompt, 'reasoning': reasoning,
                     'choice': choice if case == 'one' else 'FORMAT_OR_EXECUTION_FAILED',
                     'response_id': f'{prompt}/{reasoning}/{case}'} for case in ('one', 'two')]
            endpoints[prompt] = rows
            matrix.append({'model': 'demo', 'variant': feature, 'prompt_condition': prompt,
                           'reasoning': reasoning, 'planned': 2, 'collected': 1,
                           'numeric_candidate_choices': {choice: 1, 'FORMAT_OR_EXECUTION_FAILED': 1},
                           'statuses': {'VALID': 1, 'OUTPUT_TRUNCATED': 1},
                           'response_ids': [row['response_id'] for row in rows]})
        pairs.append({'model': 'demo', 'variant': feature, 'axis': 'PROMPT',
                      'pairs': [{'left': left, 'right': right} for left, right in zip(endpoints['unguided'], endpoints['guided'])]})
    return matrix, pairs


class CohortTests(unittest.TestCase):
    def test_variant_selection_does_not_mix_saved_results(self):
        before_matrix, before_pairs = fixture()
        after_matrix, after_pairs = fixture('IC_VALUE_01_AFTER', 'B')
        combined_matrix = before_matrix + after_matrix
        combined_pairs = before_pairs + after_pairs
        before = view.normalize_cells(combined_matrix, 'demo', ['one', 'two'], combined_pairs)
        after = view.normalize_cells(combined_matrix, 'demo', ['one', 'two'], combined_pairs, 'IC_VALUE_01_AFTER')
        self.assertEqual(before['unguided/off']['counts']['A'], 1)
        self.assertEqual(before['unguided/off']['counts']['B'], 0)
        self.assertEqual(after['unguided/off']['counts']['A'], 0)
        self.assertEqual(after['unguided/off']['counts']['B'], 1)

    def test_ea_keeps_original_value_without_an_added_candidate(self):
        matrix, pairs = fixture('EA_01', 'ORIGINAL_VALUE')
        cells = view.normalize_cells(matrix, 'demo', ['one', 'two'], pairs, 'EA_01')
        for cell in cells.values():
            self.assertEqual(cell['counts']['ORIGINAL_VALUE'], 1)
            self.assertNotIn('B', cell['counts'])
            self.assertEqual(cell['total'], 2)

    def test_ea_cannot_silently_drop_unsupported_category(self):
        matrix, pairs = fixture('EA_02', 'B')
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_ANSWER_CATEGORY'):
            view.normalize_cells(matrix, 'demo', ['one', 'two'], pairs, 'EA_02')

    def test_truncated_response_remains_in_denominator(self):
        matrix, pairs = fixture()
        cells = view.normalize_cells(matrix, 'demo', ['one', 'two'], pairs)
        for cell in cells.values():
            self.assertEqual(cell['total'], 2)
            self.assertEqual(cell['collected'], 1)
            self.assertEqual(cell['counts']['FORMAT_OR_EXECUTION_FAILED'], 1)

    def test_missing_or_changed_case_is_not_same_cohort(self):
        matrix, pairs = fixture()
        pairs[0]['pairs'][0]['left']['case'] = 'different'
        with self.assertRaisesRegex(ValueError, 'CASE_SET_MISMATCH'):
            view.normalize_cells(matrix, 'demo', ['one', 'two'], pairs)

    def test_matrix_cannot_disagree_with_saved_pairs(self):
        matrix, pairs = fixture()
        matrix[0]['numeric_candidate_choices'] = {'B': 1, 'FORMAT_OR_EXECUTION_FAILED': 1}
        with self.assertRaisesRegex(ValueError, 'PAIR_MATRIX_MISMATCH'):
            view.normalize_cells(matrix, 'demo', ['one', 'two'], pairs)

    def test_invalid_denominator_is_rejected(self):
        matrix, pairs = fixture()
        matrix[0]['planned'] = 3
        with self.assertRaisesRegex(ValueError, 'DENOMINATOR_MISMATCH'):
            view.normalize_cells(matrix, 'demo', ['one', 'two'], pairs)

    def test_input_candidate_and_case_changes_separate_groups(self):
        args = ['FinanceReasoning', 'run', 'input', 'cases', 'candidates']
        baseline = view.cohort_identity(*args)
        for position in range(len(args)):
            changed = args.copy()
            changed[position] += '-different'
            self.assertNotEqual(baseline, view.cohort_identity(*changed))

    def test_provenance_controls_dataset_family(self):
        self.assertEqual(view.dataset_family(['FinanceReasoning-embedded', 'FinanceReasoning-native']), 'FinanceReasoning')
        self.assertEqual(view.dataset_family(['TAT-QA']), 'TAT-QA')
        with self.assertRaisesRegex(ValueError, 'MIXED_OR_MISSING'):
            view.dataset_family(['TAT-QA', 'FinanceReasoning-native'])

    def test_repeat_is_latest_saved_run_not_sum(self):
        earlier = {'key': 'model', 'label': 'Model', 'order': 0, 'protocol_label': 'v1',
                   'series_signature': 'same', 'generated_at': '2026-09-27T00:00:00+00:00', 'run': 'old'}
        later = {**earlier, 'generated_at': '2026-09-28T00:00:00+00:00', 'run': 'new'}
        changed = {**later, 'series_signature': 'different', 'protocol_label': 'v2', 'run': 'other'}
        result = view.latest_series(copy.deepcopy([earlier, later, changed]))
        self.assertEqual(len(result), 2)
        self.assertEqual(next(model for model in result if model['run'] == 'new')['previous_runs'], ['old'])
        self.assertEqual(len({model['key'] for model in result}), 2)


if __name__ == '__main__':
    unittest.main()
