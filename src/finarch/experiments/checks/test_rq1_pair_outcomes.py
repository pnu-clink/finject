"""Verify four quadrant orientation and preservation of unknown planned pairs."""
import importlib
import unittest

pairs = importlib.import_module('finarch.experiments.02-analysis.02-comparison.pair_outcomes')


class PairOutcomeTest(unittest.TestCase):
    def test_axes_and_counterclockwise_numbering(self):
        self.assertEqual([pairs.quadrant(x, y) for x, y in
                          [(True, True), (False, True), (False, False), (True, False)]], [1, 2, 3, 4])
        for x, y in [(None, True), (False, None), (None, None), (1, True)]:
            self.assertIsNone(pairs.quadrant(x, y))

    def test_unavailable_pairs_remain_in_denominator(self):
        rows = [{'quadrant': q, 'placement_status': 'PLACED' if q else 'VARIANT_UNAVAILABLE',
                 'original_item_id': 'one-original', 'variant_answer_shape': 'UNAVAILABLE' if q is None else 'NULL',
                 'classification_display': 'NOT_REQUESTED'} for q in [1, 2, 3, 4, None, None]]
        result = pairs.aggregate(rows)
        self.assertEqual(result['planned_pairs'], 6)
        self.assertEqual(result['original_cases'], 1)
        self.assertEqual(result['placed_pairs'], 4)
        self.assertEqual(result['unplaced_pairs'], 2)
        for q in range(1, 5):
            self.assertEqual(result['quadrants'][str(q)]['count'], 1)
            self.assertAlmostEqual(result['quadrants'][str(q)]['ratio_of_planned'], 1 / 6)

    def test_no_judgments_does_not_create_failure_quadrant(self):
        rows = [{'quadrant': None, 'placement_status': 'SEMANTIC_NOT_REVIEWED',
                 'original_item_id': 'original', 'variant_answer_shape': 'NULL',
                 'classification_display': 'CONFLICT'}]
        result = pairs.aggregate(rows)
        self.assertEqual(result['placed_pairs'], 0)
        self.assertEqual(result['unplaced_pairs'], 1)
        self.assertTrue(all(c['count'] == 0 for c in result['quadrants'].values()))


if __name__ == '__main__':
    unittest.main()
