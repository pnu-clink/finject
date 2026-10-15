"""Preserve request contents and coverage while prioritizing a pilot cohort."""
import copy
import unittest

prioritize_pilot = __import__('finarch.experiments.01-evaluation.02-request.request_order', fromlist=['prioritize_pilot']).prioritize_pilot


class PilotOrderTest(unittest.TestCase):
    def setUp(self):
        self.trials = [
            {'case': case, 'experiment': experiment, 'reasoning': reasoning,
             'trial_id': f'{case}-{experiment}-{reasoning}', 'input': {'question': case}}
            for experiment in (1, 2) for case in ('a', 'b', 'c') for reasoning in ('off', 'on')]

    def test_pilot_includes_both_experiments_before_other_cases_without_mutation(self):
        before = copy.deepcopy(self.trials)
        ordered = prioritize_pilot(self.trials, ['c'])
        self.assertEqual([t['case'] for t in ordered[:4]], ['c'] * 4)
        self.assertEqual([t['experiment'] for t in ordered[:4]], [1, 1, 2, 2])
        self.assertEqual(self.trials, before)
        self.assertCountEqual(ordered, before)
        probes = [next(t for t in ordered if t['experiment'] == 1 and t['reasoning'] == mode)
                  for mode in ('off', 'on')]
        self.assertTrue(all(t['case'] == 'c' for t in probes))

    def test_undeclared_or_duplicate_cases_are_rejected(self):
        for invalid in ([], ['a', 'a'], ['missing'], 'a', [None]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                prioritize_pilot(self.trials, invalid)

    def test_no_pilot_preserves_original_order(self):
        self.assertIs(prioritize_pilot(self.trials, None), self.trials)


if __name__ == '__main__':
    unittest.main()
