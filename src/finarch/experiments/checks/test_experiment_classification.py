"""Offline checks for explicit classifications, neutral controls, and frozen runs."""
import copy
import json
import unittest
from unittest.mock import patch
from finarch.experiments import assets

fixtures = __import__('finarch.experiments.checks.test_openai_batch', fromlist=['*'])
pipeline = fixtures.pipeline
store = fixtures.storage
layout = pipeline.run_layout
contract = pipeline.answer_format.answer_contract
review = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_review', fromlist=['*'])
contract_view = __import__('finarch.experiments.viewer.contract_view', fromlist=['*'])


class ExplicitClassificationTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NativeBatchTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        config = copy.deepcopy(self.fixture.fixture.config)
        config.update(definition_source_run=None, response_contract=contract.CLASSIFIED_TITLE)
        source = self.fixture.fixture.root / 'classified-config.json'
        store.write(source, {'evaluation': config, 'analysis': {'enabled': False}})
        self.root = pipeline.prepare(source)
        self.model = self.fixture.model
        self.requests = store.rows(layout.requests(self.root, self.model['key']))
        self.p0 = next(r for r in self.requests if r['prompt_condition'] == 'unguided')
        self.p1 = next(r for r in self.requests if r['prompt_condition'] == 'guided')
        self.answer = {'answer': 12, 'answer_meta': {'negative': False, 'scale': 'one'},
                       'classification': 'ANSWERABLE', 'explanation': '10 + 2 = 12.',
                       'evidence': ['Amount A is 10.']}

    def errors(self, response, request=None):
        return pipeline.answer_format.response_errors(response, request or self.p1)

    def test_shared_wire_schema_has_field_but_no_classification_cues(self):
        self.assertEqual(len(self.requests), 8)
        self.assertEqual(self.p0['response_schema'], self.p1['response_schema'])
        for request in self.requests:
            body = fixtures.batch.api.body_for(self.model, request)
            schema = body['text']['format']['schema']
            self.assertEqual(schema['properties']['classification'], {'type': ['string', 'null']})
            self.assertIn('classification', schema['required'])
            self.assertEqual(set(json.loads(body['input'][0]['content'][0]['text'])),
                             {'question', 'context', 'answer_format'})
            for label in contract.CLASSIFICATIONS:
                self.assertNotIn(label, json.dumps(schema))
                if request['prompt_condition'] == 'unguided':
                    self.assertNotIn(label, body['instructions'])
        self.assertEqual(self.errors({**self.answer, 'classification': None}, self.p0), [])
        self.assertTrue(self.errors(self.answer, self.p0))
        self.assertEqual(self.errors(self.answer), [])

    def test_permitted_labels_and_number_null_combinations_are_checked(self):
        empty = {**self.answer, 'answer': None, 'answer_meta': {'negative': None, 'scale': None}}
        for label in contract.CLASSIFICATIONS[1:]:
            self.assertEqual(self.errors({**empty, 'classification': label}), [], label)
            self.assertTrue(self.errors({**self.answer, 'classification': label}), label)
        self.assertTrue(self.errors(empty))
        for invalid in (None, '', 'ANSWER', 'CONDITIONAL', 'answerable', 'UNKNOWN'):
            self.assertTrue(self.errors({**self.answer, 'classification': invalid}), str(invalid))
        missing = dict(self.answer)
        del missing['classification']
        self.assertTrue(self.errors(missing))
        self.assertTrue(self.errors({**self.answer, 'response_mode': 'ANSWER'}))
        self.assertTrue(self.errors({**self.answer, 'answer': 12.123}))

    def test_new_names_are_frozen_and_legacy_definition_stays_readable(self):
        for condition, name in layout.PROMPT_FILES.items():
            self.assertEqual(layout.prompt_file(layout.definition(self.root), condition).name, name)
            self.assertEqual((layout.definition(self.root) / name).read_bytes(),
                             assets.prompt_path('solver_' + condition).read_bytes())
            self.assertFalse((layout.definition(self.root) / layout.LEGACY_PROMPT_FILES[condition]).exists())
        self.assertEqual((layout.definition(self.root) / 'common.md').read_bytes(),
                         assets.prompt_path('solver_common').read_bytes())
        self.assertEqual(store.read(layout.definition(self.root) / 'response.schema.json'),
                         assets.schema('solver_response'))
        old = pipeline.PROJECT / 'src/finarch/experiments/checks/fixtures/experiment-v6/00-definition'
        self.assertEqual(layout.prompt_file(old, 'P1').name, 'p1-abstention-aware.md')
        pipeline.verify(self.root)
        pipeline.verify(self.fixture.root)

    def test_field_precedes_legacy_prefix_and_null_never_becomes_abstention(self):
        value = {**self.answer, 'explanation': 'Classification: CONFLICT; Response: CONDITIONAL. Old text.'}
        self.assertEqual(contract.declaration(value),
                         {'classification': 'ANSWERABLE', 'mode': None, 'source': 'JSON_FIELD'})
        self.assertIsNone(contract.declaration({**value, 'classification': None})['classification'])
        del value['classification']
        self.assertEqual(contract.declaration(value),
                         {'classification': 'CONFLICT', 'mode': 'CONDITIONAL', 'source': 'LEGACY_EXPLANATION_PREFIX'})
        self.assertIsNone(contract.declaration({'answer': None, 'explanation': 'No completed result.'})['classification'])

    def test_analysis_collects_explicit_labels_without_inventing_response_modes(self):
        self.fixture.requests = self.requests
        original_wire = self.fixture.wire_output

        def wire(request):
            result = original_wire(request)
            content = result['response']['body']['output'][0]['content'][0]
            response = json.loads(content['text'])
            response['classification'] = 'ANSWERABLE' if request['prompt_condition'] == 'guided' else None
            content['text'] = json.dumps(response)
            return result

        self.fixture.remote.update(status='completed', output_file_id='file-output')
        with patch.object(self.fixture, 'wire_output', side_effect=wire), patch.object(fixtures.batch, 'http', side_effect=self.fixture.http):
            pipeline.run(self.root)
        folder = self.root / review.ROOT / '01-LLM-input'
        assessment = {'classification': 'ANSWERABLE', 'justified_answer': 12, 'conditional_answers': [],
                      'reasoning': '10 + 2 = 12.', 'evidence': [{'source': 'context', 'quote': 'Amount A is 10.'}],
                      'external_rules': [], 'requires_external_data': False, 'confidence': 'HIGH', 'unresolved_reason': None}
        store.write_rows(folder / 'results.jsonl', [{'item_id': item_id, 'status': 'VALID', 'response': assessment}
                                                  for item_id in {r['item_id'] for r in self.requests}])
        store.write(folder / 'state.json', {'status': 'COLLECTED',
                    'output_hashes': {'results.jsonl': store.file_hash(folder / 'results.jsonl')}})
        observed = review.rows_for(self.root)
        guided = [r for r in observed if r['prompt_condition'] == 'guided']
        self.assertTrue(all(r['stated_classification'] == 'ANSWERABLE' and r['stated_mode'] is None for r in guided))
        self.assertTrue(all(r['guided_label_present'] and r['guided_classification_answer_consistent'] for r in guided))
        self.assertTrue(all(r['appropriate'] is None for r in observed))
        self.assertEqual(review.cell(observed)['guided_stated_classifications'], {'ANSWERABLE': len(guided)})
        self.assertEqual(review.cell(observed)['guided_mode_answer_checked'], 0)
        target = guided[0]
        path = self.root / target['result_path']
        result = store.read(path)
        result['response'].update(classification='ABSTAIN', answer=None,
                                  answer_meta={'negative': None, 'scale': None})
        store.write(path, result)
        changed = next(r for r in review.rows_for(self.root) if r['trial_id'] == target['trial_id'])
        self.assertIsNone(changed['guided_classification_matches_input'])
        self.assertTrue(changed['guided_classification_answer_consistent'])

    def test_contract_view_reads_new_files_and_hash_bound_translations(self):
        bundle = contract_view.read_contract(pipeline.PROJECT)
        self.assertEqual(bundle['title'], contract.CLASSIFIED_TITLE)
        self.assertTrue(bundle['files']['guided']['path'].endswith('01-evaluation.02-request.guided.md'))
        self.assertTrue(bundle['files']['unguided']['path'].endswith('01-evaluation.02-request.unguided.md'))
        for key in ('common', 'unguided', 'guided'):
            self.assertEqual(bundle['files'][key]['translation']['status'], 'AVAILABLE')


if __name__ == '__main__':
    unittest.main()
