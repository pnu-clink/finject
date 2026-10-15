"""Offline stage refactor regressions: boundaries, artifacts and compatibility."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def prep(name):
    return importlib.import_module('finarch.dataset.01-preparation.' + name)


def gen(name):
    return importlib.import_module('finarch.dataset.02-generation.' + name)


class OrderedStages(unittest.TestCase):
    def test_stage_folders_own_the_implementation(self):
        for package, name in [(prep, '01-source.stage'), (prep, '02-review.stage'),
                              (prep, '03-calculation.stage'), (prep, '04-graph.stage'),
                              (gen, '02-generate-text.stage'), (gen, '03-validation.stage')]:
            implementation = package(name)
            self.assertEqual(Path(implementation.__file__).parent.name, name.split('.')[0])
            self.assertNotIn('sys.modules[__name__]', Path(implementation.__file__).read_text())

    def test_source_only_preserves_files_and_stops_before_review(self):
        class Inputs:
            def case(self, name):
                return {'sample': {'question': 'Q', 'context': 'C'},
                        'comparison': {'status': 'PASS'}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'case'
            with patch.object(prep('02-review.stage'), 'run', side_effect=AssertionError('Unexpected review')):
                result = prep('prepare_run').run(Inputs(), 'case', root, None, only_stage='01-source')
            self.assertEqual(result['status'], 'PAUSED')
            self.assertFalse(result['allow_next_stage'])
            self.assertEqual(json.loads((root/'01-source/01-receive-input/01-input.json').read_text()), Inputs().case('case')['sample'])
            self.assertTrue((root/'01-source/02-record-source/01-provenance.json').exists())
            self.assertTrue((root/'01-source/03-compare-source/01-result.json').exists())
            self.assertTrue((root/'README.md').exists())

    def test_pot_request_preserves_metadata_but_excludes_gold(self):
        sample = {'context': 'The amount is 2.', 'question': 'What is the amount?',
                  'raw_id': 'x', 'reference_answer': '2', 'reference_answer_type': 'integer',
                  'reference_precision': 0, 'answer_metadata': {'scale': None, 'negative': False}}
        request = prep('03-calculation.stage').pp01_build_pot_request(sample)
        self.assertNotIn('reference_answer', request)
        self.assertEqual(request['reference_precision'], 0)
        self.assertEqual(request['answer_metadata'], sample['answer_metadata'])

    def test_graph_mismatch_does_not_publish_accepted_graph(self):
        class Context:
            def __init__(self): self.saved = {}
            def save(self, name, value): self.saved[name] = value
            def invoke(self, *args, **kwargs):
                return {'graph': {'nodes': [], 'variables': {}}, 'exact_value': '9'}
        ctx = Context()
        with self.assertRaisesRegex(ValueError, 'PYTHON_GRAPH_MISMATCH'):
            prep('04-graph.stage').run(ctx, {'context': '2'}, {}, {'exact_value': '2', 'trace': {}}, {})
        self.assertEqual(ctx.saved['04-graph/03-compare-calculation/01-result.json']['status'], 'FAIL')
        self.assertNotIn('04-graph/04-save-graph/01-graph.json', ctx.saved)

    def test_inherited_plan_is_copied_without_rebuilding(self):
        class Context:
            def save(self, name, value): self.saved = (name, value)
        ctx = Context()
        old = {'plan': {'graph': []}, 'restart': '02-generate-text', 'path': 'previous'}
        def forbidden(*args): raise AssertionError('Unexpected rebuild')
        result = gen('01-perturbation.stage').run(ctx, {}, {}, {}, 0, {0: old}, forbidden)
        result['graph'].append('new')
        self.assertEqual(old['plan']['graph'], [])
        self.assertEqual(ctx.saved[0], '01-perturbation/01-inherited-plan.json')

    def test_paired_sentence_uses_no_llm_and_keeps_artifact(self):
        class Context:
            def save(self, name, value): self.saved = (name, value)
        ctx = Context()
        slot = {'start': 0, 'end': 0, 'before': '', 'element_ids': ['a']}
        def forbidden(*args): raise AssertionError('Unexpected LLM')
        result = gen('02-generate-text.stage').gg02_llm_generate_text(
            ctx, None, None, None, 'case', 1, {'context': 'abc'}, {'anchor': [0, 3]},
            {0: {'patches': [{'text': ' paired '}], 'path': 'prior'}}, None, forbidden,
            {'edit_slots': [slot]})
        self.assertEqual(result['patches'][0]['text'], ' paired')
        self.assertEqual(ctx.saved[1]['new_model_calls'], 0)


if __name__ == '__main__':
    unittest.main()
