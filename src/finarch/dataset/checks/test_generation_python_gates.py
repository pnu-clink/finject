"""Narrow offline checks for mandatory generation Python gates; no model calls."""
import ast
from copy import deepcopy
from importlib import import_module
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from finarch.dataset.shared.review.dtt_audit import observation_hash
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext

planner = import_module('finarch.dataset.02-generation.01-perturbation.generation_plan')
realize = import_module('finarch.dataset.02-generation.02-generate-text.dtt_realize')
source = import_module('finarch.dataset.02-generation.03-validation.source_validation')
verify = import_module('finarch.dataset.02-generation.03-validation.stage')
handler = import_module('finarch.dataset.02-generation.04-exception-handler.stage')


def source_fixture(after=False):
    original = 'Revenue is 100.'
    sample = {'context': original, 'question': 'What is revenue?'}
    text = ' Revenue is 110.' if after else 'Revenue is 110. '
    start = len(original) if after else 0
    plan = {'label': 'IC_SOURCE_B_ONLY' if after else 'IC_SOURCE_A_ONLY', 'request': sample,
            'intent': {'target_original': {'span': [11, 14]}, 'value_pair': ['100', '110']}}
    base = {'status': 'PASS', 'label': 'IC_VALUE_01_AFTER' if after else 'IC_VALUE_01_BEFORE',
            'path': '02-generation/01-round/test-local/' + ('02-ic-value-after' if after else '01-ic-value-before'),
            'patches': [{'start': start, 'end': start, 'text': text, 'element_ids': ['n1']}],
            'observation': {**sample, 'context': original+text if after else text+original}}
    request = planner.source_request(plan, base)
    spec = request['edit_slots'][0]
    response = {'patches': [{k: spec[k] for k in ('start', 'end', 'before', 'element_ids')} |
                            {'text': ' (according to the analyst)'}]}
    observation, patches = realize.check_response(request, response)
    dependency = {'source': base['path'], 'observation_sha256': observation_hash(base['observation'])}
    return [plan, request, response, observation, patches, base, dependency, 3 if after else 2]


class SourceExactTests(unittest.TestCase):
    def test_normal_a_b_actual_generation_contract(self):
        for after in (False, True):
            self.assertEqual(source.validate(*source_fixture(after))['status'], 'PASS')

    def test_tampering(self):
        mutations = {
            'question': lambda f: f[3].update(question='Changed?'),
            'other_body': lambda f: f[3].update(context=f[3]['context']+' Changed.'),
            'patch_text': lambda f: f[4][0].update(text=' (another text)'),
            'patch_position': lambda f: f[4][0].update(start=0, end=0),
            'base_body': lambda f: f[5]['observation'].update(context='Changed base'),
            'base_path': lambda f: f[5].update(path='other-case/value'),
            'hash': lambda f: f[6].update(observation_sha256='wrong'),
            'base_label': lambda f: f[5].update(label='IC_VALUE_01_AFTER'),
            'base_status': lambda f: f[5].update(status='FAIL'),
            'missing_binding': lambda f: f[6].clear(),
            'response_patch': lambda f: f[2]['patches'][0].update(text=' wrong'),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                fixture = source_fixture(); mutate(fixture)
                self.assertEqual(source.validate(*fixture)['status'], 'FAIL')

    def test_coordinated_wrong_position_is_blocked(self):
        f = source_fixture(); text = f[4][0]['text']
        for p in (f[4][0], f[2]['patches'][0], f[1]['edit_slots'][0]): p.update(start=0, end=0)
        f[3]['context'] = text+f[5]['observation']['context']
        report = source.validate(*f)
        self.assertFalse(report['checks']['assigned_position'])

    def test_remove_only_stored_occurrence(self):
        f = source_fixture(); text = f[4][0]['text']
        f[3]['context'] += text
        self.assertEqual(source.validate(*f)['status'], 'FAIL')

    def test_g03_sidecar_and_python_handler(self):
        for after in (False, True):
            f = source_fixture(after)
            for corrupt in (False, True):
                with tempfile.TemporaryDirectory() as tmp:
                    ctx = RunContext(Path(tmp)/'variant', {}, 'test-local')
                    ctx.save('02-generate-text/00-value-dependency.json', f[6] if not corrupt else {})
                    result = {}; audit = Mock(return_value={'status': 'PASS', 'reason': 'Offline stub'})
                    verify.run(ctx, {}, f[0]['request'], f[0], f[1], f[2], f[3], f[4],
                               'IC_SOURCE', f[0]['label'], f[7], {1 if after else 0: f[5]}, result, lambda x: 'test', audit)
                    self.assertEqual(result['status'], 'FAIL' if corrupt else 'PASS')
                    self.assertTrue((ctx.root/'03-validation/06-source-exact.json').exists())
                    if corrupt:
                        result.update(round='01-round', axis='IC_SOURCE', label=f[0]['label'])
                        with patch.object(handler, 'gg02_llm_diagnose', side_effect=AssertionError('No API')):
                            self.assertFalse(handler.run(ctx, {}, result, 'test-local')['retryable'])


inversion = import_module('finarch.dataset.02-generation.01-perturbation.ea_inversion')


def ea_fixture(expression='x+y', rhs='11', bind=True, field='context'):
    from finarch.dataset.shared.calculation.python_graph import compile_graph
    context = 'X is 8. Y is 3. Total is ' + rhs + '.'
    question = 'What is the total?'
    if field == 'question':
        context = 'X is 8. Y is 3.'
        question = 'Given total ' + rhs + ', what is X?'
    program = {'code': 'x=fact("x")\ny=fact("y")\ntotal='+expression+'\nanswer=total',
               'context': context, 'question': question,
               'facts': {'x': {'span': [5, 6], 'text': '8', 'value': '8'},
                         'y': {'span': [13, 14], 'text': '3', 'value': '3'}}}
    used = {node.id for node in ast.walk(ast.parse(expression, mode='eval')) if isinstance(node, ast.Name)}
    program['facts'] = {key: fact for key, fact in program['facts'].items() if key in used}
    program['code'] = ''.join(f'{key}=fact("{key}")\n' for key in program['facts']) + 'total='+expression+'\nanswer=total'
    if bind:
        raw = context if field == 'context' else question
        start = raw.index(rhs, 15 if field == 'context' else 0)
        program['recovery_bindings'] = [{'variable': 'total', 'field': field,
                                         'span': [start, start+len(rhs)], 'text': rhs}]
    sample = {'context': context, 'question': question, 'reference_answer': '11',
              'reference_answer_type': 'integer', 'reference_precision': 0}
    graph, _, _ = compile_graph(program)
    plan = planner.build(sample, program, graph, 5)
    spec = plan['request']['edit_slots'][0]
    response = {'patches': [{k: spec[k] for k in ('start', 'end', 'before', 'element_ids')} |
                            {'text': 'X is reported.'}]}
    observation, patches = realize.check_response(plan['request'], response)
    return sample, program, graph, plan, response, observation, patches


def screen_ea(f):
    return inversion.screen(f[5], f[3]['request'], f[6], f[3]['graph'], 'x', f[3]['recovery_inputs'])


class EaInversionTests(unittest.TestCase):
    def test_operations_and_side_specific_inversion(self):
        for expression, rhs in [('x+y', '11'), ('y+x', '11'), ('x-y', '5'), ('y-x', '-5'),
                                ('x*y', '24'), ('y*x', '24'), ('x/y', '8'), ('y/x', '0.375'),
                                ('(x+y)*2', '22')]:
            with self.subTest(expression=expression):
                result = screen_ea(ea_fixture(expression, rhs))
                self.assertEqual(result['status'], 'RECOVERABLE', result)
                expected = '24' if expression == 'x/y' else '8'
                self.assertEqual(result['witnesses'][0]['recovered_value'], expected)
                for cite in result['witnesses'][0]['evidence']:
                    self.assertTrue(cite['quote'])

    def test_question_rhs_and_registered_number_rules(self):
        for rhs, expression, field in [('11', 'x+y', 'question'), ('$1,100', 'x+y', 'context'),
                                       ('11%', 'x+y', 'context')]:
            result = screen_ea(ea_fixture(expression, rhs, field=field))
            self.assertEqual(result['status'], 'RECOVERABLE', result)
            self.assertTrue(result['number_rules_sha256'])
            self.assertTrue(result['number_normalization'])

    def test_no_binding_is_not_evaluated_even_equal_output_fact(self):
        f = ea_fixture(bind=False)
        for node in f[3]['graph']['nodes']:
            node['computed'] = '3'; node['value'] = '3'
        result = screen_ea(f)
        self.assertEqual(result['status'], 'NOT_EVALUATED')
        self.assertIn('NO_EXPLICIT_INDEPENDENT_RHS_BINDING', result['unsupported_reasons'])

    def test_private_values_never_supply_evidence(self):
        f = ea_fixture(); before = screen_ea(f)
        for node in f[3]['graph']['nodes']:
            node.update(computed='999999', value='777777', evaluation={'value': '666'})
        f[3]['intent']['target_original'].update(value='888', text='secret')
        f[3]['program'].update(gold='999', exact_value='999')
        f[5].update(gold='999', reference_answer='999')
        # The full observation fingerprint changes; recovery evidence and values must not.
        after = screen_ea(f)
        self.assertEqual(after['observation_sha256'], observation_hash(f[5]))
        self.assertEqual({k:v for k,v in after.items() if k != 'observation_sha256'},
                         {k:v for k,v in before.items() if k != 'observation_sha256'})

    def test_unsupported_zero_and_repeated_unknown(self):
        for expression, rhs in [('x*0', '0'), ('0/x', '0'), ('x+x', '16'),
                                ('x**2', '64'), ('round(x/y)', '3'), ('abs(x)', '8')]:
            with self.subTest(expression=expression):
                self.assertEqual(screen_ea(ea_fixture(expression, rhs))['status'], 'NOT_EVALUATED')
        f = ea_fixture('x/y', '8')
        # Change the surviving Q/C binding itself to zero; no stale graph numeric fields are used.
        for container in (f[3]['request'], f[5]): container['context'] = container['context'].replace('Y is 3', 'Y is 0')
        f[3]['recovery_inputs']['facts']['y']['text'] = '0'
        result = screen_ea(f)
        self.assertEqual(result['status'], 'NOT_EVALUATED')
        self.assertIn('DIVISION_BY_ZERO', result['unsupported_reasons'])

    def test_overlapping_or_wrong_rhs_binding_is_not_evaluated(self):
        for update in ({'span': [5, 6], 'text': '8'}, {'text': '999'}, {'variable': 'not_a_variable'},
                       {'span': [1, 1]}):
            f = ea_fixture(); f[3]['recovery_inputs']['bindings'][0].update(update)
            self.assertEqual(screen_ea(f)['status'], 'NOT_EVALUATED')

    def test_g03_mandatory_no_policy_and_audit_preservation(self):
        for bind in (False, True):
            f = ea_fixture(bind=bind)
            for settings in ({}, {'ea_recovery_policy': {'enabled': False}}):
                with tempfile.TemporaryDirectory() as tmp:
                    ctx = RunContext(Path(tmp)/'variant', {}, 'test-local')
                    result = {}; audit = {'status': 'PASS', 'reason': 'Offline stub'}
                    verify.run(ctx, settings, f[0], f[3], f[3]['request'], f[4], f[5], f[6], 'EA',
                               'EA_01', 5, {}, result, lambda x: 'test', Mock(return_value=audit))
                    self.assertEqual(result['status'], 'PASS')
                    self.assertEqual(result['audit'], audit)
                    self.assertFalse(result['recovery_screen']['affects_quality_status'])
                    self.assertTrue((ctx.root/'03-validation/05-recovery-screen.json').exists())

    def test_actual_driver_loads_explicit_private_bindings(self):
        driver = import_module('finarch.dataset.02-generation.generate_run')
        for bind in (False, True):
            f = ea_fixture(bind=bind)
            with tempfile.TemporaryDirectory() as tmp:
                bundle = Path(tmp); prep = bundle/'01-preparation/test-local'
                for relative, data in [('data.json', f[0]), ('03-calculation/02-prepare-code/03-program.json', f[1]),
                                       ('04-graph/04-save-graph/01-graph.json', f[2])]:
                    path = prep/relative; path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(data))
                with patch.object(driver, 'invoke', return_value=f[4]) as generation, \
                     patch.object(driver, 'audit_one', return_value={'status': 'PASS', 'reason': 'Offline stub'}) as audit, \
                     patch.object(handler, 'gg02_llm_diagnose', side_effect=AssertionError('No API')):
                    result = driver.process(bundle, bundle/'02-generation/01-round', 'test-local', 5, {},
                                            {'test-local': {'case_path': '01-preparation/test-local'}}, {})
                generation.assert_called_once(); audit.assert_called_once()
                self.assertEqual(result['status'], 'PASS', result)
                self.assertEqual(result['recovery_screen']['status'], 'RECOVERABLE' if bind else 'NOT_EVALUATED')
                self.assertNotIn('recovery', result)


if __name__ == '__main__':
    unittest.main()
