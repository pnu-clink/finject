"""No live calls: verify the EA annotation boundary and saved evidence display."""
from copy import deepcopy
from importlib import import_module
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError
from finarch.dataset.schemas.ea_inverse_review import ROLE
from finarch.dataset.schemas.registry import CONTRACTS, require_llm_schema
from finarch.dataset.schemas.validation import validate
from finarch.shared.providers.cli import prepare_instruction
from finarch.shared.providers.structured import complete
from finarch.shared.providers.roles import normalize_config

inverse = import_module('finarch.dataset.02-generation.03-validation.ea_inverse_review')
verify = import_module('finarch.dataset.02-generation.03-validation.stage')
g05 = import_module('finarch.dataset.02-generation.05-human-review.stage')
ops = import_module('finarch.dataset.90-operations.staging')
feedback = import_module('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context')

QC = {'question': 'What is A?', 'context': 'A and B are the only components. Total is 100. B is 40.'}


def response(possible=True):
    evidence = []
    for quote in ('100', '40'):
        start = QC['context'].index(quote)
        evidence.append({'field': 'context', 'start': start, 'end': start+len(quote), 'quote': quote})
    return {'inverse_review': {'inverse_possible': possible, 'missing_quantity': 'Component A',
            'reason': 'The total and the only other component remain.' if possible else 'Required operands are absent.',
            'evidence': evidence if possible else [], 'formula': 'A = 100 - 40 = 60' if possible else None}}


class InverseReviewTests(unittest.TestCase):
    def test_boolean_and_witness_contract(self):
        for possible in (True, False):
            validate(ROLE+'.response', response(possible))
        for edits in ({'inverse_possible': 'true'}, {'evidence': []}, {'formula': None}, {'extra': 1}):
            value = response(); value['inverse_review'].update(edits)
            with self.assertRaises(ValidationError): validate(ROLE+'.response', value)
        value = response(False); value['inverse_review']['formula'] = 'A=60'
        with self.assertRaises(ValidationError): validate(ROLE+'.response', value)
        for key in ('gold', 'original_context', 'target', 'feedback', 'graph'):
            with self.assertRaises(ValidationError): validate(ROLE+'.request', {**QC, key: 'PRIVATE'})

    def test_prompt_isolated_from_feedback(self):
        token = feedback._ACTIVE.set({(ROLE, 'ANSWER'): [{'guidance': 'PRIVATE_DELETED_VALUE', 'version': 1, 'file': 'private'}]})
        try:
            instruction, meta = prepare_instruction(ROLE, QC)
        finally:
            feedback._ACTIVE.reset(token)
        self.assertNotIn('PRIVATE_DELETED_VALUE', instruction)
        self.assertTrue(instruction.startswith('MANDATORY Q/C SCOPE BOUNDARY'))
        self.assertIn('annotation only', instruction)
        self.assertTrue(any(p['file'].endswith('ea-recoverability-review.md') for p in meta['parts']))

    def test_dedicated_review_purpose_and_legacy_config(self):
        config = {'roles': {'dtt.audit': {'profile_id': 'luna-low-api'}},
                  'capabilities': {'dtt.audit': {'tools': [], 'skills': []}}}
        normalized = normalize_config(config)
        self.assertEqual(normalized['roles'][ROLE], {'profile_id': 'luna-low-api'})
        self.assertEqual(normalized['capabilities'][ROLE], {'tools': [], 'skills': []})
        from finarch.shared.providers.profiles import purpose_for_role
        self.assertEqual(purpose_for_role(ROLE, phase='generation'), 'ea_inverse_review')

    def test_selected_model_and_call_use_same_profile(self):
        project = Path(__file__).resolve().parents[4]
        config = project/'config/llm.json'
        from finarch.shared.providers.profiles import DEFAULT, selected_profile
        for phase in (None, 'generation'):
            selected = selected_profile(DEFAULT, ROLE, phase=phase)
            self.assertEqual((selected['id'], selected['model'], selected['effort']),
                             ('sol61-high-api', 'gpt-6.1-sol', 'high'))
            self.assertEqual(selected['purpose'], 'ea_inverse_review')
        with tempfile.TemporaryDirectory() as tmp:
            ctx = ops.RunContext(Path(tmp)/'variant', {}, 'test-local')
            with patch.object(inverse, 'call', return_value=ops.StepResult('PASS', 'Test', response())) as transport:
                ref = inverse.review(ctx, config, QC)
            record = inverse.verify_reference(ctx.root, ref, QC)
            self.assertEqual(record['status'], 'COMPLETED')
            self.assertEqual((record['model']['model'], record['model']['effort']),
                             ('gpt-6.1-sol', 'high'))
            self.assertEqual(transport.call_args.kwargs['profile_id'], 'sol61-high-api')
            self.assertEqual(transport.call_args.args[2], QC)

    def test_schema_missing_prevents_transport(self):
        calls, files = [], {}
        with patch.dict(CONTRACTS, {k: v for k, v in CONTRACTS.items() if k != ROLE+'.response'}, clear=True):
            result = complete(ROLE, QC, transport=lambda **kw: calls.append(kw),
                              save=lambda k, v: files.__setitem__(k, v), schema_mode='native')
        self.assertEqual(result.reason, 'MISSING_LLM_SCHEMA'); self.assertFalse(calls)

    def test_api_request_uses_sol61_high_and_qc_only(self):
        from finarch.shared.providers import api
        project = Path(__file__).resolve().parents[4]
        envelope = {'status': 'completed', 'usage': {'input_tokens': 12, 'output_tokens': 4},
                    'output': [{'type': 'message', 'content': [
                        {'type': 'output_text', 'text': json.dumps(response())}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            ctx = ops.RunContext(Path(tmp)/'variant', {}, 'test-local')
            with patch.object(api, 'api_key', return_value='test-only'), \
                    patch.object(api, 'record_usage'), \
                    patch.object(api, '_post', side_effect=[json.dumps({'input_tokens': 12}),
                                                          json.dumps(envelope)]) as http:
                ref = inverse.review(ctx, project/'config/llm.json', QC)
            record = inverse.verify_reference(ctx.root, ref, QC)
            self.assertEqual(record['status'], 'COMPLETED')
            body = http.call_args.args[1]
            self.assertEqual((body['model'], body['reasoning']['effort']), ('gpt-6.1-sol', 'high'))
            self.assertEqual(json.loads(body['input']), QC)
            self.assertEqual(body['max_output_tokens'], 32768)
            self.assertTrue(body['text']['format']['strict'])
            self.assertEqual(body['tools'], [])

    def test_saved_profile_selection_without_new_key_keeps_verification(self):
        from finarch.shared.providers.profiles import DEFAULT, selected_profile
        with tempfile.TemporaryDirectory() as tmp:
            profiles = Path(tmp)/'profiles.toml'
            text = DEFAULT.read_text().replace('ea_inverse_review = "sol61-high-api"\n', '')
            text = text.replace('verification = "luna-max-api"', 'verification = "luna-low-api"')
            profiles.write_text(text)
            selected = selected_profile(profiles, ROLE)
            self.assertEqual(selected['id'], 'luna-low-api')

    def test_schema_sent_raw_preserved_before_validation(self):
        calls, files = [], {}
        raw = json.dumps(response())
        def transport(**kw): calls.append(kw); return raw
        result = complete(ROLE, QC, transport=transport, save=lambda k, v: files.__setitem__(k, v), schema_mode='native')
        self.assertEqual(result.status, 'PASS')
        self.assertEqual(calls[0]['payload'], QC)
        self.assertEqual(calls[0]['response_schema'], require_llm_schema(ROLE)['schema'])
        self.assertEqual(files['02-raw-response.json']['text'], raw)

    def test_unique_coordinate_repair_not_semantic_repair(self):
        value = response(); value['inverse_review']['evidence'][0].update(start=0, end=1)
        value['inverse_review']['formula'] = 'A = 100 - 40 = 999'
        original = deepcopy(value)
        display = inverse.evidence_display_check(QC, value['inverse_review']['evidence'])
        self.assertEqual(display['checks'][0]['status'], 'UNIQUE_QUOTE_MATCH')
        self.assertEqual(value, original)
        self.assertEqual(display['status'], 'PASS')

    def test_duplicate_or_absent_quote_is_not_guessed(self):
        qc = {**QC, 'context': '100 or 100'}
        evidence = [{'field': 'context', 'start': 1, 'end': 2, 'quote': quote} for quote in ('100', '40')]
        display = inverse.evidence_display_check(qc, evidence)
        self.assertEqual([p['status'] for p in display['checks']], ['AMBIGUOUS_QUOTE', 'QUOTE_NOT_FOUND'])
        self.assertEqual(display['resolved_evidence'], [])

    def test_true_false_and_failure_preserve_quality_verdict(self):
        from finarch.dataset.checks.test_generation_python_gates import ea_fixture
        f = ea_fixture()
        for auto in ('PASS', 'FAIL'):
            for value in (response(), response(False), {'wrong': 'shape'}):
                with tempfile.TemporaryDirectory() as tmp:
                    ctx = ops.RunContext(Path(tmp)/'variant', {}, 'test-local')
                    audit = {'status': auto, 'reason': 'Existing audit'}
                    result = {}
                    def annotate(ctx, config, observation, **kwargs):
                        return inverse.review(ctx, config, observation, **kwargs,
                            local=lambda payload, response_schema: ops.StepResult('PASS', 'Test response', value))
                    verify.run(ctx, {}, f[0], f[3], f[3]['request'], f[4], f[5], f[6], 'EA',
                        'EA_01', 5, {}, result, lambda x: 'private_plan_hash', Mock(return_value=audit), annotate)
                    self.assertEqual((result['status'], result['reason']), (auto, 'Existing audit'))
                    self.assertNotIn('perturbation_validity', result['recovery_screen'])
                    record = inverse.verify_reference(ctx.root, result['inverse_review_ref'], f[5])
                    self.assertEqual(record['status'], 'RESPONSE_INVALID' if 'wrong' in value else 'COMPLETED')
                    self.assertEqual(record['inverse_review'], None if 'wrong' in value else value['inverse_review'])

    def test_call_failure_is_null_and_not_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = ops.RunContext(Path(tmp)/'variant', {}, 'test-local')
            ref = inverse.review(ctx, {}, QC, local=lambda payload, response_schema: ops.StepResult('FAIL', 'API_HTTP_503'))
            record = inverse.verify_reference(ctx.root, ref, QC)
            self.assertEqual(record['status'], 'CALL_FAILED')
            self.assertIsNone(record['inverse_review'])

    def test_preflight_failure_no_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = ops.RunContext(Path(tmp)/'variant', {}, 'test-local')
            with patch.object(inverse, 'read_settings', side_effect=ValueError('Bad config')), patch.object(inverse, 'call') as transport:
                ref = inverse.review(ctx, {}, QC)
            self.assertEqual(inverse.verify_reference(ctx.root, ref, QC)['status'], 'NOT_RUN')
            transport.assert_not_called()

    def test_immutable_attempts_private_ref_not_in_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = ops.RunContext(Path(tmp)/'variant', {}, 'test-local')
            requests = []
            def local(payload, response_schema): requests.append(payload); return ops.StepResult('PASS', 'Test', response())
            ref1 = inverse.review(ctx, {}, QC, private_ref={'deleted_value': 'PRIVATE_VALUE'}, local=local)
            old = (ctx.root/ref1['path']).read_bytes()
            ref2 = inverse.review(ctx, {}, QC, local=local)
            self.assertNotEqual(ref1['path'], ref2['path'])
            self.assertEqual((ctx.root/ref1['path']).read_bytes(), old)
            self.assertEqual(requests, [QC, QC])
            for path in ctx.root.rglob('handler-input.json'):
                self.assertNotIn('PRIVATE_VALUE', path.read_text())
            self.assertEqual(json.loads((ctx.root/inverse.BASE/'latest.ref.json').read_text()), ref2)
            with self.assertRaises(ValueError): inverse.verify_reference(ctx.root, ref1, {**QC, 'context': 'Changed'})
            with self.assertRaises(ValueError): inverse.verify_reference(ctx.root, {**ref1, 'sha256': 'wrong'}, QC)

    def test_g05_uses_only_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp); ref = {'path': 'a.json', 'sha256': 'h', 'observation_sha256': 'q'}
            item = {'path': 'variant', 'status': 'PASS', 'observation': QC, 'inverse_review_ref': ref}
            g05.run(bundle, item)
            record = json.loads((bundle/'variant/05-human-review/01-result.json').read_text())
            self.assertEqual(record['inverse_review_ref'], ref)
            self.assertNotIn('inverse_review', record)

    def test_export_keeps_private_reference_and_public_input_is_clean(self):
        export = import_module('finarch.dataset.03-release.export_run_results')
        public_input = import_module('finarch.experiments.00-input.dataset').public_input
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)/'run'; bundle.mkdir()
            original = {**QC, 'id': 'test-local'}
            inputs = bundle/'inputs.json'
            export.save(inputs, [original])
            export.save(bundle/'input-selection.json', {'input_path': str(inputs), 'cases': ['test-local']})
            export.save(bundle/'01-preparation/test-local/run.json', {'status': 'UNKNOWN'})
            relative = '02-generation/01-round/test-local/06-ea-earlier-input'
            ctx = ops.RunContext(bundle/relative, {}, 'test-local')
            ref = inverse.review(ctx, {}, QC,
                local=lambda payload, response_schema: ops.StepResult('PASS', 'Test', response()))
            export.save(ctx.root/'run.json', {'status': 'PASS', 'inverse_review_ref': ref})
            export.save(ctx.root/'02-generate-text/04-observation.json', QC)
            export.save(bundle/'02-generation/result-report.json', {'rows': [
                {'case': 'test-local', 'type': 'EA_01', 'status': 'PASS', 'origin': relative}]})
            with patch.object(export, 'edit_record', return_value={'status': 'NOT_TESTED'}), \
                    patch.object(export, 'external_records', side_effect=lambda run, rows:
                        ([{**row, 'external_knowledge': {'used': False, 'used_types': []}} for row in rows], {})):
                export.export(bundle)
                row = json.loads((bundle/'results/06-ea-earlier-input.json').read_text())[0]
                self.assertEqual(row['inverse_review_ref'], {**ref, 'path': relative+'/'+ref['path']})
                self.assertNotIn('inverse_review', row)
                self.assertNotIn('inverse_possible', row)
                self.assertEqual(public_input(row, 0), {**QC, 'answer_format': {'decimal_places': 0}})
                export.save(ctx.root/'02-generate-text/04-observation.json', {**QC, 'context': 'Changed'})
                with self.assertRaisesRegex(ValueError, 'OBSERVATION_MISMATCH'):
                    export.export(bundle)

    def test_non_ea_never_calls(self):
        fn = Mock(side_effect=AssertionError('EA only'))
        result = {}
        verify.gg06_record_inverse_review(Mock(), {}, QC, 'IC_VALUE', result, 'hash', fn)
        fn.assert_not_called(); self.assertEqual(result, {})


if __name__ == '__main__': unittest.main()
