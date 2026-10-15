"""Offline QI01 regressions; real counterexamples are immutable text fixtures."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

ea = importlib.import_module('finarch.dataset.02-generation.01-perturbation.ea_plan')
verify = importlib.import_module('finarch.dataset.02-generation.03-validation.stage')
handler = importlib.import_module('finarch.dataset.02-generation.04-exception-handler.stage')
planner = importlib.import_module('finarch.dataset.02-generation.01-perturbation.generation_plan')
first = importlib.import_module('finarch.dataset.02-generation.01-perturbation.stage')
ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()
FIXTURES = json.loads(Path(__file__).with_name('fixtures').joinpath('ea-recovery-v1.json').read_text())
POLICY = {'enabled': True}


def screen(item):
    return ea.screen_recovery(item['observation'], item['target_descriptor'], POLICY)


def source_plan(item):
    return json.loads((ROOT / item['source_path']).read_text())['plan']


class RecoveryChecks(unittest.TestCase):
    def test_actual_0026_subtotal_and_mean(self):
        result = screen(FIXTURES[0])
        self.assertEqual(result['status'], 'RECOVERABLE')
        self.assertEqual(result['witnesses'][0]['recovered_value'], '428501')
        self.assertEqual(result['witnesses'][0]['derived_answer']['value'], '425855')

    def test_actual_0074_earlier_weight(self):
        self.assertEqual(screen(FIXTURES[1])['witnesses'][0]['recovered_value'], '40')

    def test_actual_0074_later_weight(self):
        self.assertEqual(screen(FIXTURES[2])['witnesses'][0]['recovered_value'], '30')

    def test_tax_whitespace_company_and_year_variants(self):
        item = deepcopy(FIXTURES[0])
        item['observation']['context'] = item['observation']['context'].replace('2019', '2025').replace('2018', '2024').replace(
            'The components', "Acme Corp's components").replace(' | ', '  |\t ').replace('Current: ', 'Current:\t').replace('of income', 'of   income')
        item['observation']['question'] = "What is Acme Corp's average current state tax expense between 2024 and 2025?"
        item['target_descriptor'].update(entity='Acme Corp', period='2025')
        result = screen(item)
        self.assertEqual(result['status'], 'RECOVERABLE')
        self.assertEqual(result['witnesses'][0]['derived_answer']['value'], '425855')

    def test_portfolio_whitespace_company_and_asset_name_variants(self):
        for original in FIXTURES[1:]:
            item = deepcopy(original)
            mapping = {'Asset A': 'Equity Fund', 'Asset B': 'Bond Fund', 'Asset C': 'Property Fund'}
            for old, new in mapping.items():
                item['observation']['context'] = item['observation']['context'].replace(old, new)
            item['target_descriptor']['item'] = mapping[item['target_descriptor']['item']]
            item['observation']['context'] = item['observation']['context'].replace('An investor', 'Acme Capital').replace(
                'The investor', 'Acme Capital').replace(' is ', '  is\t').replace(' in ', '\t in  ').replace('three different', '3   different')
            result = screen(item)
            self.assertEqual(result['status'], 'RECOVERABLE', result)
            self.assertEqual(result['witnesses'][0]['recovered_value'], '40' if original is FIXTURES[1] else '30')

    def test_portfolio_owner_mismatch_is_unknown(self):
        item = deepcopy(FIXTURES[1]);item['observation']['context'] = item['observation']['context'].replace('The investor has', 'Another Fund has')
        self.assertEqual(screen(item)['status'], 'UNKNOWN')

    def test_real_source_hashes_and_observations_unchanged(self):
        for item in FIXTURES:
            with self.subTest(item=item['id']):
                raw = (ROOT / item['source_path']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item['source_sha256'])
                self.assertEqual(json.loads(raw)['observation'], item['observation'])

    def test_every_citation_is_nonempty_and_in_final_observation(self):
        for item in FIXTURES:
            result = screen(item)
            for witness in result['witnesses']:
                evidence = witness['evidence'] + witness.get('derived_answer', {}).get('evidence', [])
                for citation in evidence:
                    start, end = citation['span']
                    self.assertTrue(citation['quote'].strip())
                    self.assertEqual(item['observation'][citation['field']][start:end], citation['quote'])
            self.assertEqual(result['full_EA_verdict'], 'NOT_EVALUATED')

    def test_private_values_do_not_affect_screen_or_hash(self):
        for item in FIXTURES:
            changed = deepcopy(item)
            changed['target_descriptor'].update(value='999', gold='-1', computed='123', text='secret')
            changed['observation'].update(gold='888', original_graph={'computed': '777'})
            self.assertEqual(screen(changed), screen(item))

    def test_target_metadata_ignores_changed_hidden_original_amount(self):
        plan = source_plan(FIXTURES[0]);fact = plan['intent']['target_original'];left, right = fact['span']
        context = plan['request']['context']
        changed = context[:left] + '999,999' + context[right:]
        self.assertEqual(ea.recovery_descriptor(context, [left, right], plan['target']),
                         ea.recovery_descriptor(changed, [left, right], plan['target']))

    def test_period_entity_unit_and_item_mismatch_are_unknown(self):
        for key, value in [('period', '2020'), ('unit', 'EUR'), ('entity', 'other company'), ('item', 'Revenue')]:
            with self.subTest(key=key):
                item = deepcopy(FIXTURES[0]);item['target_descriptor'][key] = value
                self.assertEqual(screen(item)['status'], 'UNKNOWN')

    def test_same_number_different_item_does_not_supply_missing_component(self):
        item = deepcopy(FIXTURES[0]);item['observation']['context'] = item['observation']['context'].replace(
            'Current: Federal | $1,139,927', 'Other: Revenue | $1,139,927')
        self.assertEqual(screen(item)['status'], 'UNKNOWN')

    def test_two_missing_cells_and_multiple_tables_are_unknown(self):
        for transform in (lambda s: s.replace('$1,139,927', ''), lambda s: s + '\n' + s):
            item = deepcopy(FIXTURES[0]);item['observation']['context'] = transform(item['observation']['context'])
            self.assertEqual(screen(item)['status'], 'UNKNOWN')

    def test_changed_final_total_changes_witness_and_hash(self):
        item = deepcopy(FIXTURES[0]);item['observation']['context'] = item['observation']['context'].replace('1,568,428', '1,568,430')
        result = screen(item)
        self.assertEqual(result['witnesses'][0]['recovered_value'], '428503')
        self.assertNotEqual(result['observation_sha256'], screen(FIXTURES[0])['observation_sha256'])

    def test_open_portfolio_is_unknown(self):
        item = deepcopy(FIXTURES[1]);item['observation']['context'] = item['observation']['context'].replace(
            'consisting of three different assets:', 'including three different assets:')
        self.assertEqual(screen(item)['status'], 'UNKNOWN')

    def test_approximate_or_cash_portfolio_is_unknown(self):
        for word in ('approximately ', 'rounded ', 'cash '):
            item = deepcopy(FIXTURES[1]);item['observation']['context'] += ' ' + word
            self.assertEqual(screen(item)['status'], 'UNKNOWN')

    def test_extra_assets_and_duplicate_allocations_are_unknown(self):
        for suffix in (', Asset D, Asset E, Asset F, Asset G, Asset H, Asset I', ', Asset D'):
            item = deepcopy(FIXTURES[1]);item['observation']['context'] = item['observation']['context'].replace('Asset C.', 'Asset C' + suffix + '.', 1)
            self.assertEqual(screen(item)['status'], 'UNKNOWN')
        item = deepcopy(FIXTURES[1]);item['observation']['context'] += ' The investor has allocated their portfolio such that 30% in Asset A.'
        self.assertEqual(screen(item)['status'], 'UNKNOWN')

    def test_invalid_percentages_are_unknown(self):
        item = deepcopy(FIXTURES[1]);item['observation']['context'] = item['observation']['context'].replace('30%', '80%')
        self.assertEqual(screen(item)['status'], 'UNKNOWN')

    def test_decimal_precision_cap_and_scale_are_unknown(self):
        for value in ('123456789012345678901234567890', '1,568,428 million'):
            item = deepcopy(FIXTURES[0]);item['observation']['context'] = item['observation']['context'].replace('1,568,428', value)
            self.assertEqual(screen(item)['status'], 'UNKNOWN')

    def test_direct_restatement_is_explicitly_unsupported(self):
        result = ea.screen_recovery({'context': 'Revenue in 2020 is USD 40.', 'question': 'Revenue?'},
                                    {'target_id': 'revenue', 'kind': 'direct'}, POLICY)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertIn('DIRECT_RESTATEMENT_AND_GENERIC_RELATIONS_NOT_IMPLEMENTED', result['unsupported_reasons'])

    def test_policy_off_and_unknown_rule(self):
        item = FIXTURES[0]
        for policy in (None, {}, {'enabled': False}, {'enabled': True, 'rules': ['generic_solver']}):
            result = ea.screen_recovery(item['observation'], item['target_descriptor'], policy)
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertFalse(result['witnesses'])


class GenerationRecoveryChecks(unittest.TestCase):
    def test_mandatory_equation_screen_does_not_use_legacy_enable_flag(self):
        from finarch.dataset.checks.test_generation_python_gates import ea_fixture
        f = ea_fixture(bind=False)
        for config in ({}, {'ea_recovery_policy': {'enabled': False}}):
            ctx = Mock(); result = {'status': 'PASS'}
            verify.gg04_screen_recovery(ctx, config, f[3], f[5], 'EA', result, f[6])
            ctx.save.assert_called_once()
            self.assertEqual(ctx.save.call_args.args[0], '03-validation/05-recovery-screen.json')
            self.assertEqual(result['recovery_screen']['status'], 'NOT_EVALUATED')
            self.assertEqual(result['status'], 'PASS')
        ctx = Mock(); result = {'status': 'PASS'}
        verify.gg04_screen_recovery(ctx, {}, {}, {}, 'IC_VALUE', result)
        ctx.save.assert_not_called()
        self.assertEqual(result, {'status': 'PASS'})

    def test_final_screen_annotates_and_preserves_audit_pass(self):
        from finarch.dataset.checks.test_generation_python_gates import ea_fixture
        f = ea_fixture(); ctx = Mock()
        audit = {'status': 'PASS', 'full_EA_verdict': 'NOT_EVALUATED', 'findings': ['PASS'] * 3}
        result = {};audit_one = Mock(return_value=deepcopy(audit))
        verify.run(ctx, {}, f[0], f[3], f[3]['request'], f[4], f[5], f[6],
                   'EA', 'EA_01', 5, {}, result, lambda x: 'hash', audit_one, Mock(return_value={'path': 'test-annotation'}))
        self.assertEqual(result['audit'], audit)
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(result['recovery_screen']['affects_quality_status'])
        self.assertNotIn('perturbation_validity', result['recovery_screen'])
        self.assertEqual(result['recovery_screen']['witnesses'][0]['recovered_value'], '8')
        self.assertIn('03-validation/05-recovery-screen.json', [c.args[0] for c in ctx.save.call_args_list])

    def test_not_evaluated_preserves_existing_verdict_and_reason(self):
        from finarch.dataset.checks.test_generation_python_gates import ea_fixture
        f = ea_fixture(bind=False)
        for status in ('PASS', 'FAIL'):
            result = {'status': status, 'reason': 'Existing semantic verdict'}
            verify.gg04_screen_recovery(Mock(), {}, f[3], f[5], 'EA', result, f[6])
            self.assertEqual(result['status'], status)
            self.assertEqual(result['reason'], 'Existing semantic verdict')
            self.assertEqual(result['recovery_screen']['status'], 'NOT_EVALUATED')
            self.assertIn('NO_EXPLICIT_INDEPENDENT_RHS_BINDING', result['recovery_screen']['unsupported_reasons'])
            self.assertNotIn('perturbation_validity', result['recovery_screen'])

    def test_python_handler_never_calls_llm_or_overwrites_nonretryable(self):
        for reason in ('EA_RECOVERABLE_TARGET', 'EA_RECOVERY_UNKNOWN'):
            item = {'round': '01-round', 'label': 'EA_01', 'axis': 'EA', 'reason': reason, 'retryable': False}
            with patch.object(handler, 'gg02_llm_diagnose', side_effect=AssertionError('API forbidden')) as llm:
                result = handler.run(Mock(), {}, item, 'test-0026')
            llm.assert_not_called()
            self.assertFalse(result['retryable'])
            self.assertEqual(result['target_reselection'], 'NOT_IMPLEMENTED')

    def test_generation_build_default_compatibility_and_preview(self):
        from finarch.dataset.shared.calculation.python_graph import compile_graph
        context = ('An investor is managing a diversified portfolio consisting of three different assets: '
                   'Asset A, Asset B, and Asset C. The investor has allocated their portfolio such that '
                   '40% is invested in Asset A, 30% in Asset B, and 30% in Asset C.')
        facts = {}
        for key, text in [('a', '40%'), ('b', '30%')]:
            start = context.index(text)
            facts[key] = {'text': text, 'value': text[:-1], 'unit': '%', 'span': [start, start + len(text)]}
        program = {'code': 'a=fact("a")\nb=fact("b")\nanswer=a+b', 'context': context, 'facts': facts}
        sample = {'context': context, 'question': 'What is the weight sum?', 'reference_answer': '70',
                  'reference_answer_type': 'integer', 'reference_precision': 0}
        graph, _, _ = compile_graph(program)
        for index in (5, 6):
            old = planner.build(sample, program, graph, index)
            self.assertEqual(old, planner.build(sample, program, graph, index, policy={'enabled': False}))
            enabled = planner.build(sample, program, graph, index, policy=POLICY)
            preview = enabled.pop('recovery_preview');enabled.pop('recovery_target_descriptor')
            self.assertEqual(old, enabled)
            self.assertEqual(preview['status'], 'RECOVERABLE')
            self.assertEqual(preview['witnesses'][0]['recovered_value'], '40' if index == 5 else '30')

    def test_enabled_policy_rebuilds_instead_of_inheriting_stale_plan(self):
        from contextlib import nullcontext
        ctx = Mock();ctx.trace.span.return_value = nullcontext()
        builder = Mock(return_value={'graph': {}, 'execution': {}})
        prior = {5: {'plan': {'stale': True}, 'restart': '03-validation'}}
        first.run(ctx, {}, {}, {}, 5, prior, builder, policy=POLICY)
        builder.assert_called_once_with({}, {}, {}, 5, policy=POLICY)


if __name__ == '__main__':
    unittest.main()
