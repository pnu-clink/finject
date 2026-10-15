"""Blinding, evidence, immutable assessment references, and paired denominators."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

fixture = __import__('finarch.experiments.checks.test_openai_batch', fromlist=['*'])
review = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_review', fromlist=['*'])
contract = review.contract
store = review.store


class SemanticReviewTest(unittest.TestCase):
    def setUp(self):
        selected = {'enabled': True, 'backend': 'api', 'backends': {'api': {'model': 'gpt-6-luna', 'reasoning_effort': 'max'}}}
        config_patch = patch.object(review.run_layout, 'analysis_config', return_value=selected)
        config_patch.start()
        self.addCleanup(config_patch.stop)
        self.fixture = fixture.NativeBatchTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.input_folder = review.prepare_input(self.root)
        self.requests = store.rows(self.input_folder / 'manifest.jsonl')
        self.assessment = {'classification': 'ANSWERABLE', 'justified_answer': 12, 'conditional_answers': [],
            'reasoning': '10 + 2 = 12.', 'evidence': [{'source': 'context', 'quote': 'Amount A is 10.'}],
            'external_rules': [], 'requires_external_data': False, 'confidence': 'HIGH', 'unresolved_reason': None}

    def collect_input(self):
        results = [{'item_id': r['item_id'], 'status': 'VALID', 'response': self.assessment} for r in self.requests]
        store.write_rows(self.input_folder / 'results.jsonl', results)
        store.write(self.input_folder / 'state.json', {'status': 'COLLECTED',
            'output_hashes': {'results.jsonl': store.file_hash(self.input_folder / 'results.jsonl')}})

    def collect_solver(self):
        self.fixture.remote.update(status='completed', output_file_id='file-output')
        with patch.object(fixture.batch, 'http', side_effect=self.fixture.http):
            fixture.pipeline.run(self.root)

    def test_input_assessor_cannot_see_solver_identity_gold_or_responses(self):
        self.assertEqual(len(self.requests), 2)
        for request in self.requests:
            self.assertEqual(set(request['input']), {'question', 'context', 'answer_format'})
            body = review.body_for(self.fixture.model, request)
            data = json.loads(body['input'][0]['content'][0]['text'])
            self.assertEqual(data, request['input'])
            self.assertNotIn('item_id', data)
            self.assertEqual(body['reasoning']['effort'], 'max')
            self.assertEqual(body['prompt_cache_options'], {'mode': 'explicit'})

    def test_false_quotations_and_inconsistent_answerability_fail_local_gate(self):
        request = self.requests[0]
        self.assertEqual(contract.validate(self.assessment, request), [])
        bad = copy.deepcopy(self.assessment)
        bad['evidence'][0]['quote'] = 'fabricated fact'
        self.assertTrue(contract.validate(bad, request))
        bad = copy.deepcopy(self.assessment)
        bad['classification'] = 'CONFLICT'
        self.assertTrue(contract.validate(bad, request))

    def test_response_payload_blinds_conditions_and_keeps_link_only_in_manifest(self):
        self.collect_solver()
        self.collect_input()
        folder = review.prepare_response(self.root)
        requests = store.rows(folder / 'manifest.jsonl')
        self.assertEqual(sum(len(r['identity_map']) for r in requests), 8)
        for request in requests:
            data = json.loads(review.body_for(self.fixture.model, request)['input'][0]['content'][0]['text'])
            self.assertEqual(set(data), {'question', 'context', 'answer_format', 'input_assessment', 'responses'})
            self.assertNotIn('identity_map', data)
            self.assertTrue(all(set(row) == {'response_id', 'response'} for row in data['responses']))
        store.write_text(self.input_folder / 'results.jsonl', '{}\n')
        with self.assertRaisesRegex(ValueError, 'REVIEW_SOURCE_CHANGED'):
            review.checked_results(self.input_folder)

    def test_paired_metrics_keep_missing_and_cluster_by_original(self):
        rows = []
        for case in ('a', 'b'):
            for variant in ('x', 'y'):
                for prompt in ('P0', 'P1'):
                    rows.append({'trial_id': case + variant + prompt, 'case': case, 'variant': variant,
                        'prompt_condition': prompt, 'reasoning': 'off', 'semantic_assessed': not (case == 'b' and variant == 'y' and prompt == 'P1'),
                        'appropriate': prompt == 'P1'})
        result = review.paired(rows, 'prompt_condition', 'P0', 'P1')
        self.assertEqual(result['planned_pairs'], 4)
        self.assertEqual(result['assessed_pairs'], 3)
        self.assertEqual(result['unassessed_pairs'], 1)
        self.assertEqual(result['original_clusters'], 2)
        self.assertEqual(result['transitions'], {'0->1': 3})
        self.assertEqual(result['cluster_bootstrap_95'], [1, 1])

    def test_technical_recovery_is_bounded_and_does_not_repeat_valid_judgments(self):
        self.collect_input()
        original = store.rows(self.input_folder / 'results.jsonl')
        for row, request in zip(original, self.requests):
            row['trial_id'] = request['trial_id']
        original[0]['status'] = 'OUTPUT_TRUNCATED'
        store.write_rows(self.input_folder / 'results.jsonl', original)
        store.write(self.input_folder / 'state.json', {'status': 'COLLECTED', 'output_hashes': {'results.jsonl': store.file_hash(self.input_folder / 'results.jsonl')}})
        before = store.file_hash(self.input_folder / 'results.jsonl')
        with patch.object(review, 'run_stage', return_value={'status': 'BATCH_PENDING'}):
            review.recover_stage(self.root, self.input_folder)
            review.recover_stage(self.root, self.input_folder)
        retry = store.rows(self.input_folder / 'retry-001/manifest.jsonl')
        self.assertEqual(len(retry), 1)
        self.assertEqual(retry[0]['retry_of'], original[0]['trial_id'])
        self.assertEqual(retry[0]['prompt'], self.requests[0]['prompt'])
        self.assertEqual(retry[0]['input'], self.requests[0]['input'])
        self.assertEqual(before, store.file_hash(self.input_folder / 'results.jsonl'))

    def test_failed_solver_payloads_remain_unassessed_instead_of_crashing_analysis(self):
        self.collect_solver()
        self.collect_input()
        path = self.root / 'luna-batch/03-results/results.jsonl'
        rows = store.rows(path)
        for row, payload in zip(rows, (None, ['not', 'an', 'object'], {'explanation': 42})):
            row['status'] = 'INVALID_RESPONSE'
            store.write(self.root / row['result_path'], {'status': 'INVALID_RESPONSE', 'response': payload})
        store.write_rows(path, rows)
        result = review.rows_for(self.root)
        self.assertEqual(len(result), 8)
        self.assertTrue(all(r['appropriate'] is None for r in result))
        self.assertEqual(review.cell(result)['unassessed'], 8)

    def test_cross_round_pairs_do_not_drop_condition_identity_or_missing_pairs(self):
        study = __import__('finarch.experiments.90-operations.three_rounds', fromlist=['*'])
        first, second = self.root / 'first', self.root / 'second'
        rows = [{'case': 'a', 'variant': 'x', 'prompt_condition': 'P1', 'reasoning': 'off',
                 'trial_id': 'one', 'semantic_assessed': True, 'appropriate': False},
                {'case': 'b', 'variant': 'x', 'prompt_condition': 'P1', 'reasoning': 'off',
                 'trial_id': 'two', 'semantic_assessed': True, 'appropriate': True}]
        store.write_rows(first / '02_analysis/02_comparison/rows.jsonl', rows)
        changed = copy.deepcopy(rows)
        changed[0]['appropriate'] = True
        changed[1]['semantic_assessed'] = False
        store.write_rows(second / '02_analysis/02_comparison/rows.jsonl', changed)
        result = next(r for r in study.round_pairs(first, second) if r['prompt'] == 'P1' and r['reasoning'] == 'off')
        self.assertEqual((result['planned_pairs'], result['assessed_pairs'], result['unassessed_pairs']), (2, 1, 1))
        self.assertEqual(result['transitions'], {'0->1': 1})

    def test_p1_mode_contradiction_is_separate_from_valid_schema_and_semantic_score(self):
        self.collect_solver()
        self.collect_input()
        result_file = self.root / 'luna-batch/03-results/results.jsonl'
        original = store.rows(result_file)
        target = next(r for r in original if r['prompt_condition'] == 'guided')
        payload = store.read(self.root / target['result_path'])
        payload['response'].update(answer=None, answer_meta={'negative': None, 'scale': None},
            explanation='Classification: ANSWERABLE; Response: ANSWER. The required value is absent.')
        store.write(self.root / target['result_path'], payload)
        observed = review.rows_for(self.root)
        row = next(r for r in observed if r['trial_id'] == target['trial_id'])
        self.assertEqual(row['status'], 'VALID')
        self.assertFalse(row['guided_mode_answer_consistent'])
        self.assertIsNone(row['appropriate'])
        self.assertIsNone(row['guided_mode_behavior_matches'])
        self.assertEqual(review.cell(observed)['guided_mode_answer_mismatches'], 1)
        self.assertEqual(store.rows(result_file), original)

    def test_next_paid_round_requires_actual_critical_review_and_stops_after_three(self):
        study = __import__('finarch.experiments.90-operations.three_rounds', fromlist=['*'])
        config = store.read(self.root / 'config.json')
        config['improvement'] = {'campaign': study.CAMPAIGN, 'round': 2, 'previous_run': self.root.name}
        path = self.root / 'next-config.json'
        store.write(path, {'experiments': config})
        with patch.object(study, 'runs', return_value=[(1, self.root, config)]), patch.object(study.pipeline, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'PREVIOUS_ANALYSIS_REQUIRED'):
                study.prepare_next(path)
            store.write(self.root / '02_analysis/02_comparison/summary.json', {})
            with self.assertRaisesRegex(ValueError, 'PREVIOUS_CRITICAL_REVIEW_REQUIRED'):
                study.prepare_next(path)
            prepare.assert_not_called()

        with patch.object(study, 'runs', return_value=[(3, self.root, config)]), patch.object(study.pipeline, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'AUTHORIZED_THREE_ROUNDS_ALREADY_PREPARED'):
                study.prepare_next(path)
            prepare.assert_not_called()

    def test_research_judgment_must_reference_supplied_evidence(self):
        request = {'stage': 'research', 'response_schema': contract.RESEARCH_SCHEMA,
                   'input': {'evidence': [{'trial_id': 'real-trial'}]}}
        value = {'overall_assessment': 'Pilot evidence only.', 'findings': [{
            'title': 'Conditional arithmetic', 'observation': 'A branch is wrong.',
            'evidence_trial_ids': ['real-trial'], 'alternative_explanation': 'The review may be wrong.',
            'limitation': 'One observed response.'}], 'recommendations': [],
            'unresolved_questions': [], 'paper_claims_not_supported': ['Population superiority.']}
        self.assertEqual(contract.validate(value, request), [])
        value['findings'][0]['evidence_trial_ids'] = ['invented-trial']
        self.assertIn('RESEARCH_REFERENCES_UNSUPPLIED_TRIAL', str(contract.validate(value, request)))


class OriginalControlsTest(unittest.TestCase):
    def row(self, model, prompt, variant='ORIGINAL', numeric=True, reasoning='off'):
        return {'model': model, 'case': 'case-a', 'prompt_condition': prompt, 'reasoning': reasoning,
                'variant': variant, 'experiment': 1 if variant == 'ORIGINAL' else 2,
                'trial_id': f'{model}-{prompt}-{reasoning}-{variant}', 'status': 'VALID',
                'semantic_assessed': True, 'appropriate': True, 'audit_disagreement': False,
                'original_numeric_match': numeric, 'audit': None,
                'review': {'outcome': 'SUPPORTED_ANSWER', 'behavior': 'ANSWER'}}

    def build(self, rows):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        with patch.object(review, 'rows_for', return_value=rows), patch.object(review, 'render_readme'), \
                patch.object(review.run_layout, 'analysis_config', return_value={}):
            summary = review.build(root)
        return summary, store.rows(root / '02_analysis/02_comparison/rows.jsonl')

    def test_original_control_keeps_model_prompt_and_reasoning(self):
        rows = []
        for model in ('model-a', 'model-b'):
            for prompt in ('P0', 'P1'):
                for reasoning in ('off', 'on'):
                    match = (model == 'model-a') ^ (prompt == 'P1') ^ (reasoning == 'on')
                    rows += [self.row(model, prompt, numeric=match, reasoning=reasoning),
                             self.row(model, prompt, 'EA', reasoning=reasoning)]
        summary, stored = self.build(rows)
        self.assertEqual(len(summary['matrix']), 16)
        self.assertEqual(summary['original_control_coverage']['missing_same_condition'], 0)
        self.assertNotIn('NO_GUIDED_ORIGINAL_CONTROL', summary['limitations'])
        for row in (r for r in stored if r['experiment'] == 2):
            original = next(r for r in stored if r['trial_id'] == row['original_trial_id'])
            for key in ('model', 'case', 'prompt_condition', 'reasoning'):
                self.assertEqual(original[key], row[key])
            self.assertEqual(row['original_control_numeric_match'], original['original_numeric_match'])
        self.assertEqual({r['model'] for r in summary['original_variant_relations']}, {'model-a', 'model-b'})
        self.assertTrue(all(p['fixed_conditions'].get('model') for p in summary['paired']))

    def test_legacy_missing_p1_original_is_not_replaced_with_p0(self):
        summary, rows = self.build([self.row('a', 'P0'), self.row('a', 'P0', 'EA'), self.row('a', 'P1', 'EA')])
        guided = next(r for r in rows if r['variant'] == 'EA' and r['prompt_condition'] == 'P1')
        self.assertIsNone(guided['original_trial_id'])
        self.assertIsNone(guided['original_control_numeric_match'])
        self.assertEqual(guided['original_control_status'], 'MISSING_SAME_CONDITION')
        self.assertEqual(summary['original_control_coverage']['missing_same_condition'], 1)
        self.assertIn('NO_GUIDED_ORIGINAL_CONTROL', summary['limitations'])

    def test_pairing_does_not_overwrite_models_or_discard_missing_sides(self):
        rows = [self.row(model, prompt, 'EA') for model in ('a', 'b') for prompt in ('P0', 'P1')]
        rows.append(self.row('c', 'P0', 'EA'))
        result = review.paired(rows, 'prompt_condition', 'P0', 'P1')
        self.assertEqual((result['planned_pairs'], result['assessed_pairs'], result['unassessed_pairs']), (3, 2, 1))
        self.assertEqual({pair['model'] for pair in result['pairs']}, {'a', 'b'})

    def test_duplicate_original_condition_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_ORIGINAL_CONTROL_CONDITION'):
            self.build([self.row('a', 'P0'), self.row('a', 'P0')])


if __name__ == '__main__':
    unittest.main()
