import unittest
import json
import hashlib
from importlib import import_module
from pathlib import Path
import tempfile
from unittest.mock import patch
relation = import_module('finarch.dataset.02-generation.01-perturbation.relation_plan')
make_branches = relation.make_branches
create = relation.create
from finarch.dataset.shared.calculation.python_graph import compile_graph
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.dataset.shared.calculation.validation_gate import record_gate
from finarch.shared.reference import Reference, compare
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext

class RelationPlanChecks(unittest.TestCase):
    def example(self):
        return {'code':'a = fact("a")\nb = fact("b")\nanswer = a + b',
                'facts':{'a':{'span':[0,2],'text':'80','value':'80','unit':'dollars'},'b':{'span':[3,5],'text':'45','value':'45','unit':'dollars'}}}
    def test_both_relation_directions_keep_original(self):
        p=self.example();branches=make_branches(p,'80 45','a','b','2',directions=('B','C'))
        self.assertEqual(p['facts']['a']['value'],'80')
        self.assertEqual(p['facts']['b']['value'],'45')
        self.assertEqual([compile_graph(b['program'])[1] for b in branches.values()],[135,120])
        for b in branches.values():self.assertTrue(b['question_calculation_unchanged'])
    def test_default_is_one_direction(self):
        self.assertEqual(list(make_branches(self.example(),'80 45','a','b','2')),['B'])
    def test_no_conflict_rejected(self):
        p=self.example();p['facts']['a']['value']='90'
        with self.assertRaisesRegex(ValueError,'ALREADY_CONSISTENT'):make_branches(p,'90 45','a','b','2')
    def test_zero_negative_invalid_ratio(self):
        for k in ['0','-2','NaN','Infinity']:
            with self.subTest(k=k),self.assertRaises(ValueError):make_branches(self.example(),'80 45','a','b',k)
    def test_unit_mismatch(self):
        p=self.example();p['facts']['b']['unit']='percent'
        with self.assertRaisesRegex(ValueError,'SAME_UNIT'):make_branches(p,'80 45','a','b','2')
    def test_interleaved_inputs_unsupported(self):
        p=self.example();p['code']='a = fact("a")\nx = a + 1\nb = fact("b")\nanswer = x + b'
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_INPUT'):make_branches(p,'80 45','a','b','2')
    def test_same_fact_is_not_a_relation(self):
        with self.assertRaisesRegex(ValueError,'TWO_DISTINCT_FACTS_REQUIRED'):
            make_branches(self.example(),'80 45','a','a','2')
    def test_unknown_fact_rejected(self):
        with self.assertRaisesRegex(ValueError,'TWO_DISTINCT_FACTS_REQUIRED'):
            make_branches(self.example(),'80 45','a','missing','2')
    def test_existing_rounding_is_preserved(self):
        p=self.example();p['code']=p['code'].replace('answer = a + b','total = a + b\nanswer = round(total, 1)')
        branch=make_branches(p,'80 45','a','b','2')['B']
        self.assertTrue(branch['question_calculation_unchanged'])
        self.assertEqual(branch['program']['code'].count('round('),1)
        self.assertEqual(compile_graph(branch['program'])[1],135)
    def test_same_final_answer_is_not_registered(self):
        # [RP01] Exercise the legacy entry point without depending on archived runs.
        context = 'Fees were 80 dollars and commissions were 45 dollars.'
        program = {'context': context, 'facts': {}, 'code':
                   'service_fee_income = fact("service_fee_income")\n'
                   'commission_income = fact("commission_income")\n'
                   'total = service_fee_income + commission_income\nanswer = round(total, 0)'}
        for name, text in [('service_fee_income', '80'), ('commission_income', '45')]:
            start = context.index(text)
            program['facts'][name] = {'span': [start, start+len(text)],
                                     'text': text, 'value': text, 'unit': 'dollars'}
        # The old entry point requires this raw ID; these are synthetic test inputs.
        sample = {'raw_id': 'finance-test-489', 'context': context,
                  'question': 'What is the total fee and commission income, rounded to a dollar?',
                  'reference_answer': '125', 'reference_answer_type': 'integer', 'reference_precision': 0}
        with tempfile.TemporaryDirectory() as temp:
            ctx = RunContext(Path(temp)/'test-local', {}, 'test-local'); case = ctx.root
            with ctx.trace.activate(), ctx.trace.span('test.prepare_relation_fixture'):
                ctx.save('run.json', {'status': 'PASS', 'fixture': True})
                ctx.save('00-data-preparation/01-select-input/01-input.json', sample)
                ctx.save('02-calculation/02-prepare-code/03-program.json', program)
                execution = execute(program)
                self.assertEqual(execution.status, 'PASS', execution.reason)
                ctx.save('02-calculation/03-execute-python/03-result.json', {'data': execution.data})
                comparison = compare(execution.data['exact_value'], Reference('125', 'integer', 0))
                self.assertTrue(comparison['matches'])
                ctx.save('02-calculation/04-compare-answer/01-comparison.json', comparison)
                record_gate(ctx, comparison, program)
                graph, _, _ = compile_graph(program)
                graph_path = '03-graph/04-save-graph/01-graph.json'
                ctx.save(graph_path, graph)
                ctx.save('03-graph/04-save-graph/03-disposition.json', {
                    'status': 'PASS', 'allow_next_stage': True,
                    'graph_sha256': hashlib.sha256((case/graph_path).read_bytes()).hexdigest(),
                    'code_sha256': graph['code_sha256']})
            index = case/'04-perturbation/05-list-candidates/03-result.json'
            index.parent.mkdir(parents=True, exist_ok=True)
            index.write_text('[]')
            branches=make_branches(program,context,'service_fee_income','commission_income','1.78')
            self.assertEqual(compile_graph(branches['B']['program'])[1],125)
            # Only the proposed multiplier is controlled; production Python execution and gate run normally.
            with patch.object(relation, 'make_branches', return_value=branches):
                with self.assertRaisesRegex(ValueError,'FINAL_ANSWER_UNCHANGED'):create(case)
            self.assertEqual(json.loads(index.read_text()),[])
            base=case/'04-perturbation/03-plan-ic-relation'
            self.assertFalse((base/'04-plan.json').exists())
            self.assertEqual(json.loads((base/'03-result/failure.json').read_text())['reason'],'FINAL_ANSWER_UNCHANGED')
