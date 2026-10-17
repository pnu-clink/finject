import copy
import unittest
compose_pair = __import__('finarch.dataset.02-generation.01-perturbation.value_positions', fromlist=['compose_pair']).compose_pair


class ValuePositionChecks(unittest.TestCase):
    def payload(self, context='Intro. A is 80,000. End.'):
        start = context.index('80,000'); first = context.index(' A'); last = context.index('.', start)+1
        return {'axis': 'IC_VALUE', 'original_context': context, 'question': 'Total?', 'source_conditions': [],
            'target': {'original_span': [start, start+6], 'original_text': '80,000',
                       'nearby_sentence': {'span': [first, last], 'text': context[first:last]}},
            'python': {'code': 'answer=A+B'}, 'graph_binding': {'original_node_ids': ['n1']},
            'conditional_answers': {'A': {'computed': '170000'}, 'B': {'computed': '180000'}}}

    def test_same_statement_with_opposite_placement_and_original_preservation(self):
        payload = self.payload(); original = copy.deepcopy(payload)
        before, after = compose_pair(payload, 'A is 90,000.', 'pair-1')
        self.assertEqual(before['preview_context'], 'Intro. A is 90,000. A is 80,000. End.')
        self.assertEqual(after['preview_context'], 'Intro. A is 80,000. A is 90,000. End.')
        self.assertEqual(before['claim_order'], ['B', 'A']); self.assertEqual(after['claim_order'], ['A', 'B'])
        self.assertEqual(before['perturb_sentence'], after['perturb_sentence'])
        self.assertEqual(payload, original)

    def test_unicode_positions_and_sentence_at_document_end(self):
        payload = self.payload('\uc740\ud589 🙂. A is 80,000.')
        for p in compose_pair(payload, 'A is 90,000.', 'pair-2'):
            self.assertEqual(p['preview_context'][slice(*p['perturb_sentence_span'])], 'A is 90,000.')
            self.assertEqual(p['preview_context'][slice(*p['target_sentence']['preview_span'])], 'A is 80,000.')

    def test_mismatched_sentence_anchor_is_rejected(self):
        payload = self.payload(); payload['target']['nearby_sentence']['span'][0] += 1
        with self.assertRaisesRegex(ValueError, 'ANCHOR_MISMATCH'):
            compose_pair(payload, 'A is 90,000.', 'pair-3')

    def test_source_condition_and_blank_statement_are_rejected(self):
        payload = self.payload(); payload['source_conditions'] = [{'side': 'A'}]
        with self.assertRaisesRegex(ValueError, 'WITHOUT_SOURCE'):
            compose_pair(payload, 'A is 90,000.', 'pair-4')
        with self.assertRaisesRegex(ValueError, 'NONEMPTY'):
            compose_pair(self.payload(), ' ', 'pair-5')


if __name__ == '__main__':
    unittest.main()
