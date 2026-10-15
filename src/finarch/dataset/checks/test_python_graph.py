import copy
import tempfile
import unittest
from pathlib import Path
from finarch.dataset.shared.calculation.python_graph import compile_graph, evaluate
from finarch.dataset.shared.calculation.python_runtime import execute
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext


class PythonGraphChecks(unittest.TestCase):
    def program(self,code):return {'code':code,'context':'2','facts':{'x':{'text':'2','value':'2','span':[0,1],'unit':None}}}

    def test_min_max_preserve_python_values_and_all_dependencies(self):
        for expr in ('max(x, 0)', 'min(x, -3, 9)', 'max(-x, 0)',
                     'min(max(x, 0), 1)', 'max(2, x)', 'max(x, 2)'):
            with self.subTest(expr=expr):
                p=self.program('x=fact("x")\nanswer='+expr)
                graph,value,_=compile_graph(p)
                actual=execute(p)
                self.assertEqual(actual.status,'PASS')
                self.assertEqual(str(value),actual.data['exact_value'])
                for node in graph['nodes']:
                    if node['kind']=='variable':
                        self.assertEqual(node['computed'],actual.data['trace'][node['variable']])
                    if node.get('operator') in ('min','max'):
                        self.assertEqual(len(node['inputs']),len([e for e in graph['edges'] if e['to']==node['id']]))

    def test_min_max_unsupported_forms_are_not_silently_changed(self):
        for expr in ('min()', 'max(x)', 'max(x, 0, key=abs)'):
            with self.subTest(expr=expr),self.assertRaises(ValueError):
                compile_graph(self.program('x=fact("x")\nanswer='+expr))

    def test_erf_matches_python_for_both_signs_and_zero(self):
        for expression in ('-x','x-x','x'):
            with self.subTest(expression=expression):
                p=self.program('import math\nx=fact("x")\ny='+expression+'\nanswer=math.erf(y)')
                graph,value,_=compile_graph(p)
                actual=execute(p)
                self.assertEqual(actual.status,'PASS')
                self.assertEqual(str(value),actual.data['exact_value'])
                self.assertTrue(all(n['computed']==actual.data['trace'][n['variable']] for n in graph['nodes'] if n['kind']=='variable'))

    def test_power_function_and_type_sensitive_round_match_python(self):
        p=self.program('import math\nx=fact("x")\na=x**3\nb=math.pow(a,x)\ndigits=1\nanswer=round(b,digits)')
        graph,value,_=compile_graph(p);actual=execute(p).data
        self.assertEqual(str(value),actual['exact_value'])
        self.assertTrue(all(n['computed']==actual['trace'][n['variable']] for n in graph['nodes'] if n['kind']=='variable'))
        self.assertEqual(graph['nodes'][0]['span'],[0,1])
        self.assertTrue(all('code_line' in n for n in graph['nodes']))

    def test_alias_and_repeated_operand_edges_preserve_input_order(self):
        graph,value,_=compile_graph(self.program('from math import pow as power\nx=fact("x")\na=x+x\nanswer=power(a,x)'))
        self.assertEqual(value,16)
        addition=next(n for n in graph['nodes'] if n.get('operator')=='+')
        self.assertEqual(addition['inputs'][0],addition['inputs'][1])
        self.assertEqual(len([e for e in graph['edges'] if e['to']==addition['id']]),2)

    def test_bad_edges_duplicates_cycles_and_operators_fail(self):
        graph,_,_=compile_graph(self.program('x=fact("x")\nanswer=x+x'))
        bad=copy.deepcopy(graph);bad['nodes'].append(copy.deepcopy(bad['nodes'][0]))
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):evaluate(bad)
        bad=copy.deepcopy(graph);bad['edges'].pop()
        with self.assertRaisesRegex(ValueError,'EDGE'):evaluate(bad)
        bad=copy.deepcopy(graph);bad['nodes'][-1]['inputs']=[bad['output']]
        bad['edges']=[{'from':p,'to':n['id'],'input_index':i} for n in bad['nodes'] for i,p in enumerate(n['inputs'])]
        with self.assertRaisesRegex(ValueError,'CYCLE'):evaluate(bad)
        bad=copy.deepcopy(graph);next(n for n in bad['nodes'] if n['kind']=='operation')['operator']='unknown'
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED'):evaluate(bad)

    def test_unrepresented_control_flow_and_disconnected_facts_fail(self):
        self.assertEqual(compile_graph(self.program('x=fact("x")\nif x:\n answer=x'))[1],2)
        with self.assertRaisesRegex(ValueError,'NOT_CONNECTED'):compile_graph(self.program('x=fact("x")\nanswer=3'))

    def test_journal_continuation_preserves_prior_artifacts_and_sequence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'case';ctx=RunContext(root,{},case_id='case')
            with ctx.trace.activate(),ctx.trace.span('first'):ctx.save('run.json',{'status':'PASS'})
            before=(root/'events.jsonl').read_bytes()
            resumed=RunContext.resume(root,{},'case')
            with resumed.trace.activate(),resumed.trace.span('second'):resumed.save('03-graph/check.json',{'status':'PASS'})
            self.assertTrue((root/'events.jsonl').read_bytes().startswith(before))
            self.assertEqual([e['sequence'] for e in resumed.events],list(range(1,len(resumed.events)+1)))
            with self.assertRaises(FileExistsError):resumed.save('run.json',{})

class SavedGraphChecks(unittest.TestCase):
    def test_saved_graph_edit_is_blocked_before_next_stage(self):
        import json
        import hashlib
        from finarch.dataset.shared.calculation.python_graph import load_graph
        from finarch.dataset.shared.calculation.validation_gate import record_gate
        from finarch.shared.reference import compare, Reference
        with tempfile.TemporaryDirectory() as d:
            ctx=RunContext(Path(d)/'case',{},case_id='case')
            p={'code':'x=fact("x")\nanswer=x','context':'2','facts':{'x':{'text':'2','value':'2','span':[0,1],'unit':None}}}
            graph,value,_=compile_graph(p);comparison=compare(str(value),Reference('2','integer',0))
            ctx.save('02-calculation/02-prepare-code/03-program.json',p);ctx.save('02-calculation/04-compare-answer/01-comparison.json',comparison)
            record_gate(ctx,comparison,p);ctx.save('02-calculation/03-execute-python/03-result.json',{'data':{'exact_value':str(value)}})
            ctx.save('03-graph/04-save-graph/01-graph.json',graph)
            raw=(ctx.root/'03-graph/04-save-graph/01-graph.json').read_bytes()
            ctx.save('03-graph/04-save-graph/03-disposition.json',{'status':'PASS','allow_next_stage':True,
                     'graph_sha256':hashlib.sha256(raw).hexdigest(),'code_sha256':graph['code_sha256']})
            self.assertEqual(load_graph(ctx.root),graph)
            (ctx.root/'03-graph/04-save-graph/01-graph.json').write_bytes(raw+b' ')
            with self.assertRaisesRegex(ValueError,'ORIGINAL_GRAPH_CHANGED'):load_graph(ctx.root)
