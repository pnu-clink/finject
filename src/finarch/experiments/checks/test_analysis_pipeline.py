"""Exercise the full results workflow offline, including restart and API selection."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest
from jsonschema import Draft202012Validator
from finarch.experiments import assets

fixture = importlib.import_module('finarch.experiments.checks.test_evaluation_analysis_layout')
analysis = importlib.import_module('finarch.experiments.02-analysis.pipeline')
backend = analysis.backend
store = analysis.store


def fake_response(req):
    if req['stage'] == '04_quadrant':
        fixture_groups = __import__('finarch.experiments.checks.test_quadrant_findings', fromlist=['*'])
        return fixture_groups.grouped_response(req)
    if req['stage'] == '02_comparison':
        row = req['input']['responses'][0]
        prose = {'title': 'Observed value', 'observation': 'A saved response returns 12.',
                 'interpretation': 'A descriptive observation.', 'limitation': 'One case only.'}
        assessments = []
        for variant in req['input']['responses']:
            if variant['variant'] == 'ORIGINAL':
                continue
            public = req['input']['inputs'][variant['item_id']]['public']
            citations = [{'source': 'question', 'quote': public['question'], 'evidence_index': None},
                {'source': 'explanation', 'quote': variant['response']['explanation'], 'evidence_index': None}]
            assessments.append({'response_id': variant['response_id'], 'review_status': 'COMPLETED',
                'abstention_reason_validity': {'verdict': 'NOT_APPLICABLE', 'reason': 'Numeric fixture answer.', 'citations': []},
                'decision_grounding': {'verdict': 'SUPPORTED', 'reason': 'Offline fixture only.', 'citations': citations}})
        return {'observations': [{'id': 'O1', 'category': 'RESPONSE_ELEMENTS', **prose,
            'display': prose, 'response_ids': [row['response_id']], 'tags': ['DESCRIPTIVE'],
            'excerpts': [{'response_id': row['response_id'], 'field': 'explanation',
                         'quote': row['response']['explanation']}]}], 'coverage_note': 'All supplied rows read.',
            'response_assessments': assessments}
    finding = {'id': 'F1', 'title': 'Description', 'claim': 'Saved relationship.',
               'alternatives': 'Alternative.', 'limitation': 'No causal identification.',
               'decision': 'ACCEPT_DESCRIPTIVE'}
    return {'schema_version': 1, 'run': req['input']['run'], 'findings': [{**finding,
        'interpretation_ids': [req['input']['interpretations'][0]['id']],
        'display_ko': {k:v for k,v in finding.items() if k != 'id'}}],
        'discussion': [{'id': 'D1', 'proposal': 'Discuss next step.', 'reason': 'More data needed.',
            'status': 'NOT_EXECUTED', 'display_ko': {'proposal': '검토', 'reason': '추가 근거'}}]}


class ResponseAssessmentContractTest(unittest.TestCase):
    def setUp(self):
        original = {'response_id': 'original', 'item_id': 'o', 'variant': 'ORIGINAL', 'status': 'VALID',
            'response': {'answer': 12, 'explanation': '12 = 3 * 4.', 'evidence': ['Revenue 12.']}}
        variant = copy.deepcopy(original) | {'response_id': 'variant', 'item_id': 'v', 'variant': 'EA_01'}
        self.req = {'stage': '02_comparison', 'response_schema': assets.schema('comparison_response'),
            'input': {'responses': [original, variant], 'inputs': {k: {'public': {
                'question': 'Compute revenue.', 'context': 'Revenue 12.'}} for k in ('o', 'v')}}}
        self.value = fake_response(self.req)
        self.assessment = self.value['response_assessments'][0]

    def check(self):
        return analysis.contracts.validate_response(self.value, self.req)

    def test_complete_coverage_and_applicability(self):
        self.assertEqual(self.check(), [])
        for replacement in ([], [self.assessment, self.assessment], [self.assessment | {'response_id': 'original'}]):
            with self.subTest(replacement=replacement):
                self.value['response_assessments'] = replacement
                self.assertTrue(self.check())

    def test_zero_observations_requires_complete_assessments_and_coverage_note(self):
        self.value['observations'] = []
        self.value['coverage_note'] = 'All supplied responses reviewed; no cross-response pattern is supported.'
        self.assertEqual(self.check(), [])
        self.value['coverage_note'] = '   '
        self.assertTrue(self.check())
        self.value['coverage_note'] = 'No supported pattern.'
        self.value['response_assessments'] = []
        self.assertTrue(self.check())

    def test_thirteen_distinct_observations_are_not_limited_by_quota(self):
        prototype = self.value['observations'][0]
        self.value['observations'] = []
        for i in range(13):
            row = copy.deepcopy(self.req['input']['responses'][0])
            row['response_id'] = f'original-{i}'
            row['response']['explanation'] = f'Observed calculation {i} + 1 = {i + 1}.'
            self.req['input']['responses'].append(row)
            item = copy.deepcopy(prototype)
            item.update(id=f'O{i}', observation=row['response']['explanation'],
                        response_ids=[row['response_id']], excerpts=[{
                'response_id': row['response_id'], 'field': 'explanation', 'quote': row['response']['explanation']}])
            item['display']['observation'] = item['observation']
            self.value['observations'].append(item)
        self.assertEqual(self.check(), [])
        self.req['response_schema']['properties']['observations']['maxItems'] = 12
        self.assertTrue(self.check())

    def test_null_requires_abstention_review_and_resolved_outcomes(self):
        reviews = importlib.import_module('finarch.experiments.02-analysis.02-comparison.response_assessments')
        response = self.req['input']['responses'][1]['response']
        response['answer'] = None
        self.assertTrue(self.check())
        self.assessment['abstention_reason_validity'] = copy.deepcopy(self.assessment['decision_grounding'])
        self.assertEqual(self.check(), [])
        self.assertIs(reviews.outcome(self.assessment, response), True)
        self.assessment['decision_grounding']['verdict'] = 'UNDETERMINED'
        self.assertIsNone(reviews.outcome(self.assessment, response))
        self.assessment['abstention_reason_validity']['verdict'] = 'UNSUPPORTED'
        self.assertIs(reviews.outcome(self.assessment, response), False)

    def test_missing_or_invalid_is_not_semantic_failure(self):
        for status, change in (('NOT_REVIEWABLE', 'INVALID_RESPONSE'), ('SOURCE_MISSING', 'MISSING_CONTEXT')):
            with self.subTest(status=status):
                self.setUp()
                if change == 'MISSING_CONTEXT':
                    self.req['input']['inputs']['v']['public'].pop('context')
                else:
                    self.req['input']['responses'][1]['status'] = change
                self.assertTrue(self.check())
                self.assessment['review_status'] = status
                for field in ('abstention_reason_validity', 'decision_grounding'):
                    self.assessment[field] = {'verdict': None, 'reason': 'Missing review material.', 'citations': []}
                self.assertEqual(self.check(), [])

    def test_citations_require_exact_sources_and_both_sides(self):
        judgment = self.assessment['decision_grounding']
        original = copy.deepcopy(judgment['citations'])
        for citations in ([original[0]], [original[1]],
            [original[0], original[1] | {'quote': 'Invented text'}],
            [original[0], {'source': 'evidence', 'quote': 'Revenue 12.', 'evidence_index': 5}],
            [original[0] | {'evidence_index': 0}, original[1]]):
            with self.subTest(citations=citations):
                judgment['citations'] = citations
                self.assertTrue(self.check())
        judgment['citations'] = [original[0], {'source': 'evidence', 'quote': 'Revenue 12.', 'evidence_index': 0}]
        self.assertEqual(self.check(), [])

    def test_frozen_legacy_schema_remains_readable(self):
        schema = self.req['response_schema']
        schema['properties'].pop('response_assessments')
        schema['required'].remove('response_assessments')
        item = schema['properties']['observations']['items']
        item['properties']['display_ko'] = item['properties'].pop('display')
        item['required'] = ['display_ko' if k == 'display' else k for k in item['required']]
        self.value.pop('response_assessments')
        for observation in self.value['observations']:
            observation['display_ko'] = observation.pop('display')
        self.assertEqual(self.check(), [])
        self.value['observations'] = []
        self.assertTrue(self.check())


class CandidatePositionEvidenceTest(unittest.TestCase):
    def test_variant_name_does_not_prove_placement_and_replayed_edits_do(self):
        row = {'case': 'c', 'item_id': 'v', 'variant': 'IC_VALUE_01_AFTER', 'status': 'VALID',
               'response': {'answer': 2}, 'reference': {'reference_answer': 1}, 'alternative_answer': 2}
        self.assertEqual(analysis.a02.position(row), 'UNKNOWN')
        original = 'Revenue is 1.'
        inserted = 'Revenue is 2. '
        digest = lambda s: hashlib.sha256(s.encode()).hexdigest()
        public = {'o': {'context': original}, 'v': {'context': inserted + original}}
        private = {'v': {'edit_provenance': {'status': 'VERIFIED', 'steps': [{
            'variant': 'IC_VALUE_01_AFTER', 'input_context_sha256': digest(original),
            'output_context_sha256': digest(inserted + original),
            'patches': [{'start': 0, 'end': 0, 'before': '', 'text': inserted}]}]}}}
        rows = [{'case': 'c', 'item_id': 'o', 'variant': 'ORIGINAL'}, row]
        resolved = analysis.a02.attach_positions(rows, public, private)[1]
        self.assertEqual(analysis.a02.position(resolved), 'FRONT')
        private['v']['edit_provenance']['steps'][0]['patches'][0]['text'] = 'Bad edit'
        self.assertEqual(analysis.a02.position(analysis.a02.attach_positions(rows, public, private)[1]), 'UNKNOWN')


class AnalysisPipelineTest(unittest.TestCase):
    def setUp(self):
        self.f = fixture.OrderedRunTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        self.calls = []
        f = self.f.fixture
        f.requests = store.rows(fixture.layout.requests(self.root, f.model['key']))
        f.remote.update(status='completed', output_file_id='file-output')
        with patch.object(fixture.fixture_module.batch, 'http', side_effect=f.http):
            fixture.pipeline.run(self.root)

    def call(self, req, dest, timeout, validator):
        self.assertEqual(store.read(self.root / 'state.json')['analysis']['status'], 'RUNNING')
        self.calls.append(req)
        response = fake_response(req)
        errors = validator(response, req)
        self.assertEqual(errors, [])
        store.write(dest / 'request.json', req)
        result = {'trial_id': req['trial_id'], 'status': 'VALID', 'response': response, 'usage': {}}
        store.write(dest / 'result.json', result)
        store.write_text(dest / 'raw-response.jsonl', 'offline fixture')
        return result

    def test_full_flow_restarts_without_model_calls_and_detects_changed_evaluation(self):
        with patch.object(backend.codex, 'preflight', return_value={}), patch.object(backend.codex, 'call', side_effect=self.call):
            state = analysis.run(self.root)
            self.assertEqual(state['status'], 'COLLECTED')
            self.assertEqual(len(self.calls), 3)
            first = store.read(self.root / '02_analysis/01_results/state.json')
            self.assertEqual(first['planned'], 8)
            result = store.rows(self.root / '02_analysis/01_results/responses.jsonl')
            self.assertEqual(sum(r['original_result']=='MATCH' for r in result), 4)
            self.assertFalse((self.root / '02_analysis/01_input_review').exists())
            assessments = store.rows(self.root / '02_analysis/02_comparison/response-assessments.jsonl')
            self.assertEqual(len(assessments), 4)
            self.assertTrue(all(r['review_status'] == 'COMPLETED' for r in assessments))
            summary = store.read(self.root / '02_analysis/02_comparison/response-assessment-summary.json')
            self.assertEqual(summary['overall']['planned'], 4)
            self.assertEqual(self.calls[1]['input']['response_assessment_summary'], summary)
            grouped = self.root / '02_analysis/04_quadrant/01_findings/summary.json'
            grouped_hash = store.file_hash(grouped)
            self.assertEqual(self.calls[2]['stage'], '04_quadrant')
            self.assertEqual(set(self.calls[2]['input']), {'run', 'scope', 'findings'})
            pair_folder = self.root / '02_analysis/02_comparison/pair-outcomes'
            pair_hashes = {name: store.file_hash(pair_folder / name)
                           for name in ('pairs.jsonl', 'summary.json')}
            (pair_folder / 'pairs.jsonl').unlink()
            analysis.run(self.root)
            self.assertEqual(len(self.calls), 3)
            self.assertEqual(store.file_hash(pair_folder / 'pairs.jsonl'), pair_hashes['pairs.jsonl'])
            # An intact aggregate is reused on later resumes, including its timestamp.
            summary_hash = store.file_hash(pair_folder / 'summary.json')
            analysis.run_postprocessing(self.root)
            self.assertEqual(store.file_hash(pair_folder / 'summary.json'), summary_hash)
            self.assertEqual(len(self.calls), 3)
            self.assertEqual(store.file_hash(grouped), grouped_hash)
            self.assertTrue(store.read(self.root / '02_analysis/04_quadrant/state.json')['reused'])
            source = self.root / '01_evaluation/04_validation/numeric-comparisons.jsonl'
            source.write_text(source.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'ANALYSIS_SOURCE_CHANGED'):
                analysis.run(self.root)

    def test_zero_patterns_preserve_assessments_and_skip_research_without_fabrication(self):
        original_fake = fake_response
        def no_patterns(req):
            self.assertEqual(req['stage'], '02_comparison')
            value = original_fake(req)
            value['observations'] = []
            value['coverage_note'] = 'No substantive pattern in this fixture.'
            return value
        with patch.object(backend.codex, 'preflight', return_value={}), \
                patch.object(backend.codex, 'call', side_effect=self.call), \
                patch(__name__ + '.fake_response', side_effect=no_patterns):
            result = analysis.run(self.root)
            self.assertEqual(result['status'], 'ASSESSMENTS_COLLECTED_NO_PATTERNS')
            self.assertEqual(len(self.calls), 1)
            analysis.run(self.root)
            self.assertEqual(len(self.calls), 1)
        folder = self.root / '02_analysis'
        self.assertEqual(len(store.rows(folder / '02_comparison/response-assessments.jsonl')), 4)
        coverage = store.read(folder / '02_comparison/coverage.json')['cases'][0]
        self.assertEqual(coverage['coverage_note'], 'No substantive pattern in this fixture.')
        self.assertEqual(coverage['observation_count'], 0)
        self.assertEqual(coverage['comparison_review_completeness'], 'NOT_INDEPENDENTLY_VERIFIED')
        self.assertEqual(store.read(folder / '03_research/state.json')['status'], 'SKIPPED_NO_PATTERN_OBSERVATIONS')
        self.assertFalse((folder / '03_research/manifest.jsonl').exists())
        self.assertFalse((folder / '03_research/findings.json').exists())

    def test_full_request_size_blocks_without_truncation(self):
        analysis.numeric.build(self.root); analysis.a01.build(self.root)
        rows = store.rows(self.root / '02_analysis/01_results/responses.jsonl')
        with patch.object(analysis, 'MAX_COMPARISON_INPUT_BYTES', 1):
            with self.assertRaisesRegex(ValueError, 'A02_PARTITION_REQUIRED'):
                analysis.comparison_requests(self.root, rows)
        with patch.object(analysis, 'MAX_RESEARCH_INPUT_BYTES', 1):
            with self.assertRaisesRegex(ValueError, 'A03_SINGLE_OBSERVATION_EXCEEDS_INPUT_BUDGET'):
                analysis.research_requests(self.root, [{'category': 'RESPONSE_ELEMENTS', 'id': 'I1'}], {})
        self.assertFalse((self.root / '02_analysis/02_comparison/manifest.jsonl').exists())

    def test_research_partitions_include_fixed_payload_and_preserve_all_observations(self):
        items = [{'category': 'RESPONSE_ELEMENTS', 'id': f'I{i}', 'observation': 'x' * 5000} for i in range(3)]
        full = analysis.research_requests(self.root, items, {'fixed': 'y' * 8000})
        budget = len(store.encoded(full[0])) - 4000
        with patch.object(analysis, 'MAX_RESEARCH_INPUT_BYTES', budget):
            split = analysis.research_requests(self.root, items, {'fixed': 'y' * 8000})
        self.assertGreater(len(split), 1)
        self.assertTrue(all(len(store.encoded(r)) <= budget for r in split))
        self.assertEqual([i['id'] for r in split for i in r['input']['interpretations']], ['I0', 'I1', 'I2'])

    def test_fabricated_quote_is_rejected(self):
        analysis.numeric.build(self.root); analysis.a01.build(self.root)
        requests = analysis.comparison_requests(self.root, store.rows(self.root / '02_analysis/01_results/responses.jsonl'))
        value = fake_response(requests[0])
        value['observations'][0]['excerpts'][0]['quote'] = 'fabricated'
        self.assertTrue(analysis.contracts.validate_response(value, requests[0]))

    def test_assessment_collector_preserves_pending_and_failed_calls(self):
        analysis.numeric.build(self.root); analysis.a01.build(self.root)
        requests = analysis.comparison_requests(self.root, store.rows(self.root / '02_analysis/01_results/responses.jsonl'))
        summary = analysis.contracts.collect_assessments(self.root, requests, backend)
        self.assertEqual(summary['overall']['review_status'], {'NOT_REVIEWED': 4})
        folder = backend.freeze(self.root, '02_comparison', requests)
        req = requests[0]
        dest = folder / 'calls' / req['trial_id'] / 'attempt-001'
        store.write(dest / 'request.json', req)
        store.write(dest / 'result.json', {'status': 'UNKNOWN_DELIVERY'})
        summary = analysis.contracts.collect_assessments(self.root, requests, backend)
        self.assertEqual(summary['overall']['review_status'], {'REVIEW_FAILED': 4})
        self.assertEqual(summary['overall']['adaptation_outcome'], {'UNDETERMINED_OR_UNREVIEWED': 4})

    def test_frozen_requests_keep_their_prompt_and_schema(self):
        analysis.numeric.build(self.root); analysis.a01.build(self.root)
        rows = store.rows(self.root / '02_analysis/01_results/responses.jsonl')
        requests = analysis.comparison_requests(self.root, rows)
        folder = backend.freeze(self.root, '02_comparison', requests)
        before = store.file_hash(folder / 'manifest.jsonl')
        with patch.object(analysis, 'COMPARISON_PROMPT', 'Changed prompt must not replace a frozen request.'):
            self.assertEqual(analysis.comparison_requests(self.root, rows), requests)
        self.assertEqual(store.file_hash(folder / 'manifest.jsonl'), before)

    def test_aggregate_only_preserves_blocked_execution_without_model_calls(self):
        analysis.numeric.build(self.root); analysis.a01.build(self.root)
        analysis.a02.build(self.root)
        folder = self.root / '02_analysis/02_comparison'
        stage = {'status': 'BLOCKED', 'requests': 1, 'completed': 1, 'valid': 0,
                 'statuses': {'UNKNOWN_DELIVERY': 1}}
        store.write(folder / 'state.json', stage)
        root_state = store.read(self.root / 'state.json')
        root_state['analysis'] = {**stage, 'stage': 'A02'}
        root_state['full_pipeline'] = {'status': 'NEEDS_REVIEW'}
        store.write(self.root / 'state.json', root_state)
        source_hash = store.file_hash(self.root / '02_analysis/01_results/responses.jsonl')
        with patch.object(backend, 'run') as caller:
            result = analysis.run(self.root, aggregate_only=True)
        caller.assert_not_called()
        self.assertEqual(result['status'], 'AGGREGATES_REFRESHED')
        self.assertEqual(result['new_model_calls'], 0)
        pair_summary = store.read(folder / 'pair-outcomes/summary.json')
        self.assertEqual(pair_summary['new_model_calls'], 0)
        self.assertEqual(pair_summary['overall']['planned_pairs'], 4)
        self.assertEqual(pair_summary['overall']['unplaced_pairs'], 4)
        self.assertEqual(store.read(folder / 'state.json'), stage)
        self.assertEqual(store.read(self.root / 'state.json'), root_state)
        self.assertEqual(store.file_hash(self.root / '02_analysis/01_results/responses.jsonl'), source_hash)
        self.assertEqual(len(list(folder.glob('comparisons-before-refresh-*.json'))), 1)

    def test_stage_named_assets_match_real_analysis_requests_and_index(self):
        analysis.numeric.build(self.root)
        analysis.a01.build(self.root)
        rows = store.rows(self.root / '02_analysis/01_results/responses.jsonl')
        comparison = analysis.comparison_requests(self.root, rows)[0]
        self.assertEqual(comparison['prompt'], assets.prompt_text('comparison_common') + assets.prompt_text('comparison'))
        self.assertEqual(comparison['response_schema'], assets.schema('comparison_response'))
        research = analysis.research_requests(self.root, [{'category': 'RESPONSE_ELEMENTS', 'id': 'I1'}], {})[0]
        self.assertEqual(research['prompt'], assets.prompt_text('analysis_common') + assets.prompt_text('research'))
        self.assertEqual(research['response_schema'], assets.schema('research_response'))
        index = json.loads((assets.ROOT / 'schemas/json/index.json').read_text())
        self.assertEqual({row['file'] for row in index}, set(assets.SCHEMAS.values()))
        for row in index:
            path = assets.ROOT / 'schemas/json' / row['file']
            self.assertEqual(row['schema_id'], row['file'].removesuffix('.schema.json'))
            self.assertEqual(row['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            Draft202012Validator.check_schema(json.loads(path.read_text()))

    def test_unknown_delivery_blocks_without_another_call(self):
        analysis.numeric.build(self.root); analysis.a01.build(self.root)
        requests = analysis.comparison_requests(self.root, store.rows(self.root / '02_analysis/01_results/responses.jsonl'))
        folder = backend.freeze(self.root, '02_comparison', requests)
        dest = folder / 'calls' / requests[0]['trial_id'] / 'attempt-001'
        store.write(dest/'request.json', requests[0]); store.write(dest/'result.json', {'status': 'UNKNOWN_DELIVERY'})
        with patch.object(backend.codex, 'call') as caller:
            state = backend.run(self.root, '02_comparison', requests)
        self.assertEqual(state['status'], 'BLOCKED')
        caller.assert_not_called()

    def test_proven_schema_rejection_retries_with_original_attempt_preserved(self):
        analysis.numeric.build(self.root); analysis.a01.build(self.root)
        requests = analysis.comparison_requests(self.root, store.rows(self.root / '02_analysis/01_results/responses.jsonl'))
        req = requests[0]
        folder = backend.freeze(self.root, '02_comparison', requests)
        dest = folder / 'calls' / req['trial_id'] / 'attempt-001'
        store.write(dest / 'request.json', req)
        store.write(dest / 'provider-request.json', {'response_schema': req['response_schema']})
        store.write(dest / 'result.json', {'status': 'LOCAL_PREFLIGHT_REJECTED',
            'error': "invalid_json_schema: 'uniqueItems' is not permitted."})
        original_hash = store.file_hash(dest / 'result.json')
        with patch.object(backend.codex, 'preflight', return_value={}), patch.object(backend.codex, 'call', side_effect=self.call):
            state = backend.run(self.root, '02_comparison', requests)
        self.assertEqual(state['status'], 'COLLECTED')
        self.assertEqual(store.file_hash(dest / 'result.json'), original_hash)
        self.assertTrue((dest / 'recovery.json').exists())
        self.assertEqual(len(backend.attempts(folder, req)), 2)

    def test_wire_schema_preserves_canonical_uniqueness_checks(self):
        canonical = copy.deepcopy(analysis.contracts.INTERPRETATION_RESPONSE)
        req = backend.request(self.root, '02_comparison', 'offline', 'Analyze saved responses.', canonical, {})
        wire = backend.api_body({}, req)['text']['format']['schema']
        ids = wire['properties']['observations']['items']['properties']['response_ids']
        self.assertNotIn('uniqueItems', ids)
        self.assertIn('unique', ids['description'])
        self.assertEqual(canonical, analysis.contracts.INTERPRETATION_RESPONSE)
        from jsonschema import Draft202012Validator, ValidationError
        ids_contract = canonical['properties']['observations']['items']['properties']['response_ids']
        with self.assertRaises(ValidationError):
            Draft202012Validator(ids_contract).validate(['same', 'same'])
        named = {'type': 'object', 'properties': {'uniqueItems': {'type': 'boolean'}}}
        self.assertEqual(backend.codex.wire_schema.for_openai(named), named)

    def test_wire_schema_adds_provider_type_for_const_without_changing_canonical(self):
        canonical = {'type': 'object', 'properties': {'schema_version': {'const': 1},
                     'status': {'const': 'NOT_EXECUTED'}}}
        wire = backend.codex.wire_schema.for_openai(canonical)
        self.assertEqual(wire['properties']['schema_version'], {'const': 1, 'type': 'integer'})
        self.assertEqual(wire['properties']['status'], {'const': 'NOT_EXECUTED', 'type': 'string'})
        self.assertEqual(canonical['properties']['schema_version'], {'const': 1})

    def test_api_uses_batch_payload_and_never_codex_fallback(self):
        config = store.read(self.root / 'config.json')
        config['analysis']['backend'] = 'api'
        config['analysis']['backends']['api']['max_output_tokens'] = 65536
        store.write(self.root / 'config.json', config)
        req = backend.request(self.root, '03_research', 'category', 'Analyze supplied results.',
                              analysis.contracts.FINDINGS, {'run': self.root.name, 'interpretations': []})
        payload = backend.api_body(config['analysis']['backends']['api'], req)
        self.assertEqual(payload['prompt_cache_options'], {'mode': 'explicit'})
        self.assertEqual(payload['tools'], [])
        with patch.object(backend, 'run_api', return_value={'status':'RUNNING'}) as api, patch.object(backend, 'run_codex') as cli:
            backend.run(self.root, '03_research', [req])
        api.assert_called_once(); cli.assert_not_called()

    def test_native_analysis_batch_round_trip_is_resumable(self):
        analysis.numeric.build(self.root); analysis.a01.build(self.root)
        config = store.read(self.root/'config.json')
        config['analysis']['backend']='api'
        config['analysis']['backends']['api'].update(model='gpt-6-sol', max_output_tokens=65536)
        store.write(self.root/'config.json',config)
        requests = analysis.comparison_requests(self.root,store.rows(self.root/'02_analysis/01_results/responses.jsonl'))
        posts=[]
        remote={'id':'analysis-batch','input_file_id':'analysis-input','status':'in_progress',
                'output_file_id':None,'error_file_id':None}
        def http(model,suffix,**kwargs):
            if kwargs.get('body') is not None:posts.append(suffix)
            if suffix=='files':return {'id':'analysis-input'}
            if suffix in ('batches','batches/analysis-batch'):return dict(remote)
            if suffix=='files/analysis-output/content':
                import json
                return '\n'.join(json.dumps({'custom_id':r['trial_id'],'response':{'status_code':200,
                    'body':{'id':'saved','status':'completed','output':[{'type':'message','content':[
                        {'type':'output_text','text':json.dumps(fake_response(r))}]}],
                        'usage':{'input_tokens':100,'output_tokens':10,'input_tokens_details':{
                            'cached_tokens':0,'cache_write_tokens':0}}}}}) for r in requests)+'\n'
            raise AssertionError(suffix)
        with patch.object(backend.batch,'http',side_effect=http),patch.object(backend.codex,'call') as cli:
            state=backend.run(self.root,'02_comparison',requests)
            self.assertEqual(state['status'],'RUNNING')
            remote.update(status='completed',output_file_id='analysis-output')
            self.assertEqual(backend.run(self.root,'02_comparison',requests)['status'],'COLLECTED')
            self.assertEqual(backend.run(self.root,'02_comparison',requests)['status'],'COLLECTED')
        cli.assert_not_called()
        self.assertEqual(posts,['files','batches'])
        result=backend.latest(self.root/'02_analysis/02_comparison',requests[0])
        self.assertEqual(result['response'],fake_response(requests[0]))

    def test_full_runner_resumes_completed_run_without_evaluation(self):
        runner=importlib.import_module('finarch.experiments.pipeline')
        with patch.object(backend.codex,'preflight',return_value={}),patch.object(backend.codex,'call',side_effect=self.call):
            analysis.run(self.root)
        with patch.object(runner.evaluation,'run') as target,patch.object(runner.analysis,'run') as reviewed:
            runner.run(self.root)
            runner.run(self.root)
        target.assert_not_called();reviewed.assert_not_called()
        self.assertEqual(store.read(self.root/'state.json')['full_pipeline']['status'],'COMPLETE')

    def test_full_runner_closes_assessment_only_run_without_claiming_findings(self):
        runner = importlib.import_module('finarch.experiments.pipeline')
        with patch.object(runner, 'collect_when_ready', return_value=True), \
                patch.object(runner.analysis, 'run', return_value={'status': 'ASSESSMENTS_COLLECTED_NO_PATTERNS'}), \
                patch.object(runner, 'next_run') as next_run:
            runner.run(self.root)
        next_run.assert_not_called()
        self.assertEqual(store.read(self.root / 'state.json')['full_pipeline']['status'], 'COMPLETE_NO_PATTERN_FINDINGS')

    def test_full_runner_does_not_start_next_before_analysis_completes(self):
        runner=importlib.import_module('finarch.experiments.pipeline')
        with patch.object(runner,'collect_when_ready',return_value=True),patch.object(runner.analysis,'run',return_value={'status':'PARTIAL'}),patch.object(runner,'next_run') as next_run:
            runner.run(self.root,following={'source_run':'later','count':1080})
        next_run.assert_not_called()
        self.assertEqual(store.read(self.root/'state.json')['full_pipeline']['status'],'NEEDS_REVIEW')

    def test_user_pause_prevents_any_analysis_invocation(self):
        state = store.read(self.root/'state.json')
        state['execution_control'] = {'analysis': {'paused': True, 'reason': 'User requested code review first.'}}
        store.write(self.root/'state.json', state)
        with patch.object(backend, 'run') as caller, patch.object(analysis.numeric, 'build') as numeric:
            result = analysis.run(self.root)
        self.assertEqual(result['status'], 'PAUSED_BY_USER')
        self.assertEqual(result['new_model_calls'], 0)
        caller.assert_not_called(); numeric.assert_not_called()

    def test_evaluation_only_collects_scores_without_analysis_or_following_run(self):
        runner = importlib.import_module('finarch.experiments.pipeline')
        with patch.object(runner.analysis, 'run') as analyze, patch.object(runner, 'next_run') as next_run:
            runner.run(self.root, evaluation_only=True)
        analyze.assert_not_called(); next_run.assert_not_called()
        self.assertTrue((self.root/'01_evaluation/04_validation/numeric-comparisons.jsonl').is_file())
        self.assertEqual(store.read(self.root/'state.json')['full_pipeline']['status'], 'EVALUATION_COMPLETE')

    def test_seed_suffix_does_not_replace_the_run_sequence_number(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            date = store.now()[:10].replace('-', '')
            (folder/f'{date}-exp-007-20260920').mkdir()
            self.assertEqual(store.allocate(folder, seed=20260921).name, f'{date}-exp-008-20260921')
            self.assertEqual(store.allocate(folder).name, f'{date}-exp-009')


if __name__ == '__main__':
    unittest.main()
