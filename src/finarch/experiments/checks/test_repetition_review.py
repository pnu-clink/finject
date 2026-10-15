"""Guard absent/null, sign/scale, request equality, and stable wrong answers."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
repetition_review = __import__('finarch.experiments.02-analysis.legacy.content-analysis.repetition_review', fromlist=['*'])
compare = __import__('finarch.experiments.02-analysis.legacy.content-analysis.repetition_review', fromlist=['compare']).compare
signature = __import__('finarch.experiments.02-analysis.legacy.content-analysis.repetition_review', fromlist=['signature']).signature
summarize = __import__('finarch.experiments.02-analysis.legacy.content-analysis.repetition_review', fromlist=['summarize']).summarize


def row(answer, scale='million', outcome='NUMERIC_MISMATCH'):
    return {'case':'example','variant':'ORIGINAL','prompt_condition':'P0','reasoning':'off',
            'trial_id':'trial','saved_status':'VALID','original_outcome':outcome,'result_path':'result.json',
            'response':{'answer':answer,'answer_meta':{'scale':scale},'evidence':['source']}}


class RepeatReviewTest(unittest.TestCase):
    def test_missing_is_not_explicit_null(self):
        a,b=row(None,None),row(None,None)
        b['response']=None
        self.assertIsNone(signature(b))
        pair=compare(a,b,True,True)
        self.assertIsNone(pair['same_presence'])
        self.assertEqual(summarize([pair])['answer_unassessed_pairs'],1)

    def test_sign_and_scale_are_part_of_numeric_identity(self):
        for other in (row(-12),row(12,'one')):
            pair=compare(row(12),other,True,True)
            self.assertTrue(pair['same_presence'])
            self.assertFalse(pair['same_numeric_and_scale'])

    def test_different_payload_is_not_repeat_evidence(self):
        pair=compare(row(12),row(12),False,True)
        self.assertIsNone(pair['same_answer_and_scale'])
        self.assertEqual(summarize([pair])['eligible_pairs'],0)

    def test_stable_wrong_answer_is_separate_from_correctness(self):
        pair=compare(row(12),row(12.0),True,True)
        result=summarize([pair])
        self.assertEqual(result['same_numeric_and_scale'],1)
        self.assertEqual(result['stable_original_numeric_mismatch'],1)

    def test_signed_zero_is_the_same_numeric_coefficient(self):
        self.assertEqual(signature(row(-0.0)), signature(row(0)))

    def test_saved_wire_bytes_control_repeat_eligibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            template = root/'src/finarch/documentation/templates/experiment-repeat-analysis.md'
            template.parent.mkdir(parents=True)
            template.write_text('{{first_run}} → {{second_run}}')
            folders = []
            for label in ('first', 'second'):
                folder = root/label
                folder.mkdir()
                result = folder/'result.json'
                result.write_text(json.dumps({'model_version': 'test-model'}))
                value = row(12)
                value.update(run_id=label, result_path=str(result.relative_to(root)))
                (folder/'rows.jsonl').write_text(json.dumps(value)+'\n')
                (folder/'provider-request-wire.json').write_bytes(b'{"answer":1,"evidence":2}')
                folders.append(folder)
            with patch.object(repetition_review, 'ROOT', root):
                same = repetition_review.build(*folders, root/'same')
                self.assertEqual(same['overall']['eligible_pairs'], 1)
                self.assertEqual(same['by_original_case'][0]['same_answer_and_scale'], 1)
                # Equivalent JSON objects with a different generation order are not identical conditions.
                (folders[1]/'provider-request-wire.json').write_bytes(b'{"evidence":2,"answer":1}')
                reordered = repetition_review.build(*folders, root/'reordered')
                self.assertEqual(reordered['overall']['eligible_pairs'], 0)
                (folders[1]/'provider-request-wire.json').unlink()
                missing = repetition_review.build(*folders, root/'missing')
                self.assertEqual(missing['overall']['answer_unassessed_pairs'], 1)


if __name__ == '__main__':
    unittest.main()
