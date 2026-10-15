"""Analysis relationships must not become new Evaluation judgments or calls."""
import copy
import importlib
import json
import tempfile
import unittest
from pathlib import Path

a01 = importlib.import_module('finarch.experiments.02-analysis.01-results.results')
a02 = importlib.import_module('finarch.experiments.02-analysis.02-comparison.comparison')
contracts = importlib.import_module('finarch.experiments.02-analysis.contracts')
pipeline = importlib.import_module('finarch.experiments.01-evaluation.pipeline')


def row(answer=None, variant='IC_VALUE_01_BEFORE', **extra):
    return dict(model='m', trial_id='t', response_id='m:t', case='c', item_id='i',
        variant=variant, prompt_condition='unguided', reasoning='on', status='VALID',
        original_result='NOT_ORIGINAL', response={'answer': answer, 'classification': None},
        reference={'reference_answer': 10}, alternative_answer=20) | extra


class RelationshipTests(unittest.TestCase):
    def test_candidate_and_position_are_not_correctness(self):
        self.assertEqual(a02.choice(row(10)), 'A')
        self.assertEqual(a02.position(row(10)), 'UNKNOWN')
        self.assertEqual(a02.position(row(10, verified_candidate_positions={'A': 'BACK'})), 'BACK')
        self.assertEqual(a02.position(row(10, 'IC_VALUE_01_AFTER')), 'UNKNOWN')
        self.assertEqual(a02.choice(row(15)), 'OTHER')
        self.assertEqual(a02.choice(row(10, alternative_answer=10)), 'BOTH')
        self.assertEqual(a02.position(row(None)), 'NULL')
        self.assertEqual(a02.choice(row(10, status='INVALID_RESPONSE')), 'FORMAT_OR_EXECUTION_FAILED')

    def test_missing_pair_and_unguided_null_remain_distinct(self):
        self.assertEqual(a02.outcome(row()), 'UNGUIDED_NULL')
        self.assertEqual(a02.outcome(row(prompt_condition='guided')), 'CLASSIFICATION_MISSING')
        missing = a02.pair(row(10), None, 'PROMPT')
        self.assertFalse(missing['format_comparable'])
        group = a02.group_pairs([missing])[0]
        self.assertEqual((group['planned_pairs'], group['comparable_pairs'], group['missing_pairs']), (1, 0, 1))
        self.assertEqual(group['choice_transitions'], {})

    def test_analysis_only_run_is_rejected_before_any_evaluation(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p/'config.json').write_text('{"run_kind":"ANALYSIS_ONLY"}')
            with self.assertRaisesRegex(ValueError, 'ANALYSIS_ONLY_RUN_CANNOT_EXECUTE_EVALUATION'):
                pipeline.run(p, preflight=lambda: self.fail('Provider preflight must not run'))
            self.assertFalse((p/'.pipeline.lock').exists())

    def test_unknown_and_invented_evidence_rejected(self):
        r = row(10); r['response']['explanation'] = 'I used the table.'
        text = dict(title='t', observation='o', interpretation='i', limitation='l')
        item = dict(id='O01', category='RESPONSE_ELEMENTS', tags=['T'], response_ids=['m:t'],
                    excerpts=[dict(response_id='m:t', field='explanation', quote='the table')],
                    display_ko=text, **text)
        self.assertTrue(contracts.validate_interpretations([item], {'m:t': r}))
        fabricated = copy.deepcopy(item); fabricated['excerpts'][0]['quote'] = 'I verified the gold.'
        with self.assertRaisesRegex(ValueError, 'EXCERPT_NOT_IN_SAVED_RESPONSE'):
            contracts.validate_interpretations([fabricated], {'m:t': r})
        wrong = copy.deepcopy(item); wrong['response_ids'] = ['unknown']
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_RESPONSE_REFERENCE'):
            contracts.validate_interpretations([wrong], {'m:t': r})


if __name__ == '__main__':
    unittest.main()
