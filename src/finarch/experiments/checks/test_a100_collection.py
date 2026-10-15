import importlib
import json
import unittest

from finarch.experiments.a100.collect import require_complete, response_result
from finarch.experiments import assets

calls = importlib.import_module('finarch.experiments.01-evaluation.03-execution.call_layout')


class GPUCollectionTests(unittest.TestCase):
    def test_completion_requires_manifest_denominator_and_all_delivery(self):
        require_complete({'status': 'EVALUATION_RECEIVED', 'total': 34560,
                          'attempt_records': 34560, 'remaining_unstarted': 0}, 34560)
        require_complete({'status': 'EVALUATION_RECEIVED', 'completed': 17824}, 17824)
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE'):
            require_complete({'status': 'EVALUATION_RECEIVED', 'total': 34560, 'attempt_records': 34559}, 34560)

    def test_local_checks_detect_representation_failures_missed_by_schema(self):
        request = {'response_schema': assets.schema('solver_response'), 'prompt_condition': 'unguided',
                   'input': {'answer_format': {'decimal_places': 2}}}
        answer = {'answer': 1.234, 'answer_meta': {'negative': False, 'scale': 'one'},
                  'classification': 'ANSWERABLE', 'evidence': [], 'explanation': 'A saved explanation.'}
        raw = {'usage': {'prompt_tokens': 10, 'completion_tokens': 20},
               'choices': [{'message': {'content': json.dumps(answer)}}]}
        delivery = {'elapsed_seconds': 1, 'finish_reason': 'stop'}
        checked = response_result(request, raw, delivery, {'status': 'UNKNOWN_NOT_ZERO'})
        self.assertEqual(checked['status'], 'INVALID_RESPONSE')
        self.assertEqual({tuple(x['path']) for x in checked['schema_errors']}, {('answer',), ('classification',)})
        self.assertEqual(json.loads(raw['choices'][0]['message']['content']), answer)

    def test_truncated_chat_text_is_preserved_and_usage_not_filled_with_zero(self):
        raw = {'usage': {'prompt_tokens': 10, 'completion_tokens': 8192},
               'choices': [{'message': {'content': '{"answer":'}}]}
        request = {'response_schema': assets.schema('solver_response'), 'prompt_condition': 'guided'}
        result = response_result(request, raw, {'elapsed_seconds': 1, 'finish_reason': 'length'}, {})
        self.assertEqual(result['status'], 'OUTPUT_TRUNCATED')
        self.assertEqual(calls.response_text(raw), '{"answer":')
        raw['choices'][0]['finish_reason'] = 'length'
        result = response_result(request, raw, {'elapsed_seconds': 1, 'finish_reason': None, 'usage': None}, {})
        self.assertEqual(result['status'], 'OUTPUT_TRUNCATED')
        self.assertEqual(result['usage']['output_tokens'], 8192)
        self.assertEqual(result['delivery_metadata_discrepancies']['finish_reason']['raw_response'], 'length')
        with self.assertRaisesRegex(ValueError, 'USAGE_MISSING'):
            response_result(request, {'usage': None}, {}, {})


if __name__ == '__main__':
    unittest.main()
