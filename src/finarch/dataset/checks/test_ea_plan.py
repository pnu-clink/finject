import copy
import unittest

build = __import__('finarch.dataset.02-generation.01-perturbation.ea_plan', fromlist=['build']).build
evaluate_available = __import__('finarch.dataset.02-generation.01-perturbation.ea_plan', fromlist=['evaluate_available']).evaluate_available
from finarch.dataset.shared.calculation.python_graph import compile_graph, compile_structure


class EAGraphChecks(unittest.TestCase):
    def program(self,code='A=fact("A")\nB=fact("B")\nC=A+B\nanswer=C'):
        return {'context':'60 40','code':code,'facts':{
            'A':{'value':'60','text':'60','span':[0,2],'unit':'dollars'},
            'B':{'value':'40','text':'40','span':[3,5],'unit':'dollars'}}}

    def test_missing_value_graph_preserves_connections_without_numeric_execution(self):
        p=self.program();before=copy.deepcopy(p);original,value,_=compile_graph(p)
        graph,inputs,_=build(p,'A')
        self.assertEqual(p,before);self.assertEqual(value,100)
        self.assertEqual(graph['edges'],original['edges']);self.assertEqual(inputs['code'],p['code'])
        self.assertNotIn('A',inputs['facts'])
        self.assertFalse(any(n.get(k) in ('60','60.0') for n in graph['nodes'] for k in ('value','computed','text')))
        by={n['id']:n for n in graph['nodes']}
        self.assertEqual(by[graph['variables']['B']]['computed'],'40.0')
        self.assertEqual(by[graph['output']]['evaluation']['state'],'BLOCKED')
        for n in graph['nodes']:
            if n['evaluation']['state']!='KNOWN':self.assertNotIn('computed',n);self.assertNotIn('value',n)

    def test_structure_can_be_built_even_when_numeric_evaluation_fails(self):
        p=self.program('A=fact("A")\nB=fact("B")\nzero=0\nanswer=(A+B)/zero')
        graph,_=compile_structure(p)
        self.assertTrue(any(n.get('operator')=='/' for n in graph['nodes']))
        self.assertTrue(all('computed' not in n for n in graph['nodes']))
        with self.assertRaises(ZeroDivisionError):compile_graph(p)
        with self.assertRaisesRegex(ValueError,'ZERO_DENOMINATOR'):build(p,'A')

    def test_typos_and_bad_syntax_are_errors_not_missing_evidence(self):
        with self.assertRaisesRegex(ValueError,'INVALID_FACT_CALL'):build(self.program('A=fact("TYPO")\nB=fact("B")\nanswer=A+B'),'A')
        with self.assertRaises(SyntaxError):build(self.program('answer=('),'A')
        with self.assertRaisesRegex(ValueError,'UNKNOWN_DELETION_TARGET'):build(self.program(),'TYPO')

    def test_disconnected_input_is_not_a_deletion_candidate(self):
        with self.assertRaisesRegex(ValueError,'FACT_NOT_CONNECTED'):build(self.program('A=fact("A")\nB=fact("B")\nanswer=B'),'A')

    def test_repeated_fact_reads_all_become_missing_and_independent_work_remains(self):
        p=self.program('A=fact("A")\nagain=fact("A")\nB=fact("B")\ntwo=2\nknown=B*two\nanswer=A+again+known')
        graph,_,_=build(p,'A');by={n['id']:n for n in graph['nodes']}
        self.assertEqual(sum(n.get('availability')=='MISSING' for n in graph['nodes']),2)
        self.assertEqual(by[graph['variables']['known']]['computed'],'80.0')

    def test_missing_output_does_not_claim_mathematical_nonuniqueness(self):
        graph,_,_=build(self.program('A=fact("A")\nB=fact("B")\nzero=A-A\nanswer=zero+B'),'A')
        self.assertEqual(graph['nodes'][-1]['evaluation']['state'],'BLOCKED')
        self.assertNotIn('nonunique',graph)

    def test_unknown_operator_and_stale_deleted_value_are_rejected(self):
        graph,_,_=build(self.program(),'A')
        bad=copy.deepcopy(graph);next(n for n in bad['nodes'] if n['kind']=='operation')['operator']='unknown'
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_GRAPH_OPERATOR'):evaluate_available(bad)
        bad=copy.deepcopy(graph);next(n for n in bad['nodes'] if n.get('availability')=='MISSING')['value']='60'
        with self.assertRaisesRegex(ValueError,'INVALID_MISSING_FACT_NODE'):evaluate_available(bad)

    def test_normal_numeric_graph_still_supports_power_round_and_repeated_edges(self):
        p=self.program('A=fact("A")\nB=fact("B")\ns=A+B\ntwo=2\nanswer=round(s**two)')
        graph,value,_=compile_graph(p)
        self.assertEqual(value,10000);self.assertTrue(all('computed' in n for n in graph['nodes']))


if __name__=='__main__':unittest.main()
