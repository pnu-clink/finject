"""Relation scope, numeric leakage and resume checks; no model calls."""
from copy import deepcopy
from importlib import import_module
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

planner = import_module('finarch.dataset.02-generation.01-perturbation.generation_plan')
scope = import_module('finarch.dataset.02-generation.01-perturbation.relation_scope')
g01 = import_module('finarch.dataset.02-generation.01-perturbation.stage')
realize = import_module('finarch.dataset.02-generation.02-generate-text.dtt_realize')
driver = import_module('finarch.dataset.02-generation.generate_run')
from finarch.dataset.shared.calculation.python_graph import compile_graph
from finarch.dataset.schemas.validation import validate

ROOT = Path(__file__).resolve().parents[4]


def saved(case):
    path = ROOT / f'reports/run/20260917-002/02-generation/01-round/{case}/05-ic-relation/01-perturbation/01-input.json'
    value = json.loads(path.read_text())
    return value['sample'], value['program'], value['graph']


def fixture(markdown=False, same_year=False):
    raw = json.dumps({'Assets -- Property, plant, and equipment': {'2019': 140, '2018': 160},
                      'Assets -- Total assets': {'2019': 180, '2018': 200}})
    if same_year:
        raw = json.dumps({'Assets -- Property, plant, and equipment': {'2018': 160},
                          'Assets -- Total assets': {'2018': 200}})
    context = import_module('finarch.dataset.00-input.json_context').assemble_json(raw)['context'] if markdown else raw
    facts = {}
    for cell in scope.source_cells(context):
        if cell['period'] == '2018':
            key = 'total' if scope.total(cell) else 'ppe'
            facts[key] = {k: cell[k] for k in ('span', 'text', 'value')}
            facts[key]['unit'] = 'USD'
    program = {'code': 'ppe=fact("ppe")\ntotal=fact("total")\nanswer=round(ppe/total*100,2)',
               'facts': facts, 'context': context}
    graph, _, _ = compile_graph(program)
    sample = {'id': 'test-local', 'context': context, 'question': 'What percentage was PPE in 2018? Answer to two decimal places.',
              'reference_answer': '80.00', 'reference_answer_type': 'float', 'reference_precision': 2}
    return sample, program, graph


def response(request, sentence):
    slot = request['edit_slots'][0]
    if slot['required_prefix']:
        sentence = slot['required_prefix'] + sentence.lstrip()
        if slot['end'] < len(request['context']):
            sentence += '\n'
    return {'patches': [{k: slot[k] for k in ('start', 'end', 'before', 'element_ids')} | {'text': sentence}]}


class RelationScopeTests(unittest.TestCase):
    def test_date_with_comma_is_not_a_numeric_table_cell(self):
        context = '| Period | Date | Amount |\n|---|---|---|\n| Tax | December 28, 2018 | 1,609,000 |'
        cells = scope.source_cells(context)
        self.assertEqual([c['value'] for c in cells], ['1609000'])
        self.assertEqual(context[cells[0]['span'][0]:cells[0]['span'][1]], '1,609,000')

    def test_malformed_numeric_commas_remain_an_error(self):
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_COMMA_FORMAT'):
            scope.numeric('16,09,000', scope.load_rules()[0])

    def test_thousands_fact_values_use_registered_rules_in_relation_plan(self):
        context = '| Item | 2019 | 2018 |\n|---|---|---|\n| Income tax expense | 1,609,000 | 1,164,000 |'
        facts = {}
        for year, raw in (('2019', '1,609,000'), ('2018', '1,164,000')):
            start = context.index(raw)
            facts['tax_' + year] = {'value': raw, 'text': raw, 'span': [start, start + len(raw)], 'unit': 'USD'}
        program = {'code': 'a=fact("tax_2019")\nb=fact("tax_2018")\nanswer=round((a-b)/b*100,2)',
                   'facts': facts, 'context': context}
        graph, _, _ = compile_graph(program)
        sample = {'id': 'test-numeric', 'context': context, 'question': 'What was the percentage increase in income tax expense?',
                  'reference_answer': '38.23', 'reference_answer_type': 'float', 'reference_precision': 2}
        before = deepcopy(program)
        plan = planner.build(sample, program, graph, 4)
        self.assertEqual(program, before)
        self.assertEqual(plan['execution']['exact_value'], '100.0')
        evidence = plan['number_normalization']['facts']['operand']
        self.assertEqual((evidence['original'], evidence['normalized']), ('1,164,000', '1164000'))
        self.assertIn('remove_thousands_commas', evidence['applied_rules'])
        self.assertEqual(plan['request']['edit_slots'][0]['start'], len(context))

    def test_tax_balance_omits_left_amount_and_permits_right_amount(self):
        args = saved('test-0025'); before = deepcopy(args)
        plan = planner.build(*args, 4); request = plan['request']
        self.assertEqual(args, before)
        self.assertEqual(plan['target'], 'f_end_2015')
        self.assertEqual(plan['intent']['relation']['operand_period'], '2014')
        self.assertEqual(set(request['edit_slots'][0]['allowed_numbers']), {'2', '1171', '31', '2015', '2014'})
        text = ' The 2015 balance of unrecognized tax benefits was twice the 2014 balance of $1,171 million.'
        observation, _ = realize.check_response(request, response(request, text))
        self.assertEqual(observation['question'], args[0]['question'])
        self.assertEqual(observation['context'].count('1,136'), args[0]['context'].count('1,136'))
        wrong = text.replace('benefits was', 'benefits, $1,136 million, was')
        with self.assertRaisesRegex(ValueError, 'UNPLANNED_NUMERIC_CONTENT'):
            realize.check_response(request, response(request, wrong))

    def test_assets_choose_total_left_cross_year_and_bind_unused_reference(self):
        args = saved('test-0254'); before = deepcopy(args)
        plan = planner.build(*args, 4); relation = plan['intent']['relation']
        self.assertEqual(args, before)
        self.assertEqual(plan['target'], 'total_assets_2018')
        self.assertEqual((relation['target_period'], relation['operand_period']), ('2018', '2019'))
        self.assertEqual(relation['target_aggregation_role'], 'TOTAL')
        self.assertEqual(relation['operand']['value'], '2235')
        self.assertEqual(plan['execution']['exact_value'], '59.08')
        self.assertEqual(len(plan['selection']['additional_facts']), 1)
        reference = next(iter(plan['selection']['additional_facts']))
        self.assertTrue(any(n.get('fact_id') == reference for n in plan['graph']['nodes']))
        reasons = {t.get('reason') for t in plan['selection']['attempts']}
        self.assertIn('RELATION_COMPONENT_EXCEEDS_TOTAL', reasons)
        self.assertIn('RELATION_TOTAL_MUST_BE_LEFT', reasons)
        self.assertEqual(compile_graph(plan['program'])[1], 59.08)
        validate('02-generation.02-generate-text.realization.request', plan['request'])
        self.assertNotIn('reference_answer', plan['request'])

    def test_same_contract_works_after_json_adapter_conversion(self):
        for markdown in (False, True):
            with self.subTest(markdown=markdown):
                args = fixture(markdown)
                plan = planner.build(*args, 4)
                self.assertEqual(plan['target'], 'total')
                self.assertEqual(plan['intent']['relation']['operand_period'], '2019')
                self.assertEqual(plan['execution']['exact_value'], '57.14')
                self.assertEqual(plan['request']['context'], args[0]['context'])

    def test_same_year_is_valid_fallback_without_other_year(self):
        plan = planner.build(*fixture(same_year=True), 4)
        self.assertEqual(plan['target'], 'total')
        self.assertEqual(plan['intent']['relation']['operand_period'], '2018')
        self.assertEqual(plan['execution']['exact_value'], '50.0')

    def test_original_balance_cell_is_not_added_again_due_to_currency_prefix(self):
        args = saved('test-0025')
        original, inventory, _ = scope.descriptors(args[0]['context'], args[1])
        self.assertEqual(len(original), 2)
        self.assertEqual(len(inventory), 3)
        self.assertEqual([d['period'] for d in inventory], ['2015', '2014', '2013'])

    def test_target_amount_cannot_leak_through_another_context_number(self):
        plan = planner.build(*saved('test-0025'), 4)
        for amount in ('1136', '759', '1701', '2342'):
            with self.subTest(amount=amount), self.assertRaisesRegex(ValueError, 'UNPLANNED_NUMERIC_CONTENT'):
                realize.check_response(plan['request'], response(plan['request'], f' The 2015 balance was twice {amount}.'))

    def test_incompatible_units_are_not_selected(self):
        args = fixture(same_year=True); args[1]['facts']['ppe']['unit'] = 'shares'
        with self.assertRaisesRegex(ValueError, 'NO_SOURCE_SCOPED_RELATION'):
            planner.build(*args, 4)

    def test_single_input_cannot_create_self_reference(self):
        sample, program, _ = fixture()
        program['facts'] = {'x': {'span': [0, 2], 'text': '80', 'value': '80', 'unit': 'USD'}}
        program.update(context='80', code='x=fact("x")\nanswer=x')
        sample['context'] = '80'
        graph, _, _ = compile_graph(program)
        with self.assertRaisesRegex(ValueError, 'NO_SOURCE_SCOPED_RELATION'):
            planner.build(sample, program, graph, 4)

    def test_selector_retries_when_first_relation_does_not_affect_answer(self):
        context = '80 45'
        program = {'context': context, 'code': 'x=fact("x")\ny=fact("y")\nanswer=x-x+y',
                   'facts': {'x': {'span': [0, 2], 'text': '80', 'value': '80', 'unit': 'USD'},
                             'y': {'span': [3, 5], 'text': '45', 'value': '45', 'unit': 'USD'}}}
        sample = {'context': context, 'question': 'What is the amount?', 'reference_answer': '45',
                  'reference_answer_type': 'integer', 'reference_precision': 0}
        graph, _, _ = compile_graph(program)
        plan = planner.build(sample, program, graph, 4)
        self.assertEqual(plan['target'], 'y')
        self.assertEqual(plan['selection']['attempts'][0]['reason'], 'RELATION_ANSWER_UNCHANGED')

    def test_old_relation_plan_is_rebuilt_current_plan_reused(self):
        old = {'path': 'old', 'plan': {'target': 'ppe'}}
        self.assertIsNone(g01.gg01_select_prior_plan(4, {4: old}))
        new = {'path': 'new', 'plan': planner.build(*fixture(), 4)}
        self.assertIs(g01.gg01_select_prior_plan(4, {4: new}), new)
        stale = deepcopy(new)
        stale['plan'].pop('relation_placement_version')
        self.assertIsNone(g01.gg01_select_prior_plan(4, {4: stale}))
        self.assertIs(g01.gg01_select_prior_plan(0, {0: old}), old)

    def test_reported_table_cases_place_relation_after_final_row(self):
        for case in ('test-0100', 'test-0105'):
            with self.subTest(case=case):
                root = ROOT / f'reports/run/20261003-concat-001/02-generation/01-round/{case}/05-ic-relation'
                inputs = json.loads((root / '01-perturbation/01-input.json').read_text())
                args = tuple(inputs[k] for k in ('sample', 'program', 'graph'))
                before = deepcopy(args)
                plan = planner.build(*args, 4)
                request = plan['request']; spec = request['edit_slots'][0]
                self.assertEqual(spec['start'], len(args[0]['context']))
                self.assertEqual(spec['required_prefix'], '\n\n')
                saved = json.loads((root / '02-generate-text/05-patches.json').read_text())[0]
                observation, _ = realize.check_response(request, response(request, saved['text']))
                self.assertEqual(observation['context'], args[0]['context'] + '\n\n' + saved['text'].strip())
                self.assertEqual(observation['question'], args[0]['question'])
                self.assertEqual(args, before)
                with self.assertRaisesRegex(ValueError, 'RELATION_PARAGRAPH_SEPARATOR_REQUIRED'):
                    raw = response(request, saved['text'])
                    raw['patches'][0]['text'] = saved['text']
                    realize.check_response(request, raw)

    def test_changed_relation_plan_does_not_reuse_old_generated_text(self):
        sample, program, graph = fixture(); plan = planner.build(sample, program, graph, 4)
        prior = {'path': 'old', 'plan': {'target': 'ppe'}, 'recovery': {'target_step': '03-validation'},
                 'generation_request': {}, 'generation_response': {}, 'observation': {}, 'patches': []}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'prepared'
            for relative, value in [('data.json', sample), ('03-calculation/02-prepare-code/03-program.json', program),
                                    ('04-graph/04-save-graph/01-graph.json', graph)]:
                path = source / relative; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            with patch.object(driver.g01_perturbation, 'run', return_value=plan), \
                 patch.object(driver.g02_generate_text, 'run', return_value=(plan['request'], {}, {}, [])) as generate, \
                 patch.object(driver.g03_verification, 'run'):
                result = driver._process_attempt(root, root / '02-generation/02-round', 'test-local', 4, {},
                                                 {'test-local': {'case_path': 'prepared'}}, {4: prior})
            self.assertNotEqual(result['status'], 'FAIL', result)
            generate.assert_called_once()

    def test_active_prompt_and_audit_request_use_current_relation_rules(self):
        from finarch.shared.providers.cli import prepare_instruction
        from finarch.dataset.schemas.registry import describe
        for role, expected in [('02-generation.02-generate-text.realization', 'Never repeat its observed'),
                               ('shared.01-02.02-03.review-and-validation', 'Reject repetition of its observed')]:
            instruction, selection = prepare_instruction(role, {'axis': 'IC_RELATION'})
            self.assertIn(expected, instruction)
            self.assertEqual(selection['version'], 4)
            self.assertTrue(describe(role + '.response')['schema'])
        plan = planner.build(*saved('test-0025'), 4)
        raw = response(plan['request'], ' The 2015 balance was twice the 2014 balance of $1,171 million.')
        observation, _ = realize.check_response(plan['request'], raw)
        g03 = import_module('finarch.dataset.02-generation.03-validation.stage')
        request = g03.gg01_build_verification_request(plan, plan['request'], raw, observation, 'IC_RELATION')
        validate('shared.01-02.02-03.review-and-validation.request', request)
        self.assertIn('each operand', ' '.join(request['intent']['verification_requirements']))


if __name__ == '__main__':
    unittest.main()
