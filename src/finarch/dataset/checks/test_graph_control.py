"""Concrete-path expansion checked against independent Python execution."""
import copy
import unittest
from finarch.dataset.shared.calculation.python_graph import compile_graph, evaluate


def program(code, values=(10,20,30)):
    names=['x','y','z'][:len(values)]
    context='; '.join(f'{name} = {value}' for name,value in zip(names,values))
    facts={}
    for name,value in zip(names,values):
        start=context.index(f'{name} = ')+len(name)+3
        facts[name]={'text':str(value),'value':str(value),'span':[start,start+len(str(value))],'unit':None}
    return {'code':code,'context':context,'facts':facts}


class GraphControlChecks(unittest.TestCase):
    def check(self, code, values=(10,20,30)):
        p=program(code,values);namespace={'fact':lambda name:float(p['facts'][name]['value'])}
        exec(code,namespace,namespace)  # Only the hard-coded local test programs.
        graph,value,_=compile_graph(p)
        self.assertEqual(value,namespace['answer'])
        evaluated,by_id=evaluate(graph)
        self.assertEqual(evaluated,value)
        for name,key in graph['variables'].items():self.assertEqual(by_id[key],namespace[name])
        return graph

    def test_for_and_reassignment(self):
        g=self.check('x=fact("x")\ny=fact("y")\nz=fact("z")\ntotal=0\nfor value in [x,y,z]:\n total += value\nanswer=total')
        self.assertEqual(next(e['iterations'] for e in g['control_flow']['events'] if e['kind']=='for'),3)

    def test_while_and_break_continue(self):
        self.check('x=fact("x")\ny=fact("y")\nanswer=0\nwhile x<y:\n x+=1\n if x==12:\n  continue\n answer+=x\n if x==15:\n  break', (10,20))

    def test_if_untaken_branch_not_executed_and_path_guard(self):
        code='x=fact("x")\nif x>0:\n answer=x*2\nelse:\n answer=1/0'
        g=self.check(code,(10,))
        changed=copy.deepcopy(g)
        next(n for n in changed['nodes'] if n['kind']=='fact')['value']='-10.0'
        with self.assertRaisesRegex(ValueError,'CONTROL_PATH_CHANGED'):evaluate(changed)
        same=copy.deepcopy(g);next(n for n in same['nodes'] if n['kind']=='fact')['value']='11.0'
        self.assertEqual(evaluate(same)[0],22)

    def test_comprehensions_zip_enumerate_range(self):
        self.check('x=fact("x")\ny=fact("y")\nz=fact("z")\nitems=[v*i for i,v in zip(range(1,4),[x,y,z])]\nanswer=sum(v for i,v in enumerate(items) if i>=0)')

    def test_statistics_import_alias(self):
        self.check('from statistics import mean as avg\nx=fact("x")\ny=fact("y")\nz=fact("z")\nanswer=avg([x,y,z])')

    def test_aggregate_and_sorted_selection_guards(self):
        g=self.check('x=fact("x")\ny=fact("y")\nz=fact("z")\nordered=sorted([x,y,z])\nanswer=sum(ordered)/len(ordered)')
        changed=copy.deepcopy(g);next(n for n in changed['nodes'] if n.get('fact_id')=='x')['value']='100.0'
        with self.assertRaisesRegex(ValueError,'CONTROL_PATH_CHANGED'):evaluate(changed)

    def test_nested_function_lexical_scope_and_repeated_calls(self):
        self.check('x=fact("x")\ndef outer(a):\n def inner(b):\n  return a*b\n return inner(2)+inner(3)\nanswer=outer(x)',(10,))

    def test_while_termination_is_guarded(self):
        g=self.check('x=fact("x")\nanswer=0\nwhile x>0:\n answer+=x\n x-=5',(10,))
        changed=copy.deepcopy(g);next(n for n in changed['nodes'] if n['kind']=='fact')['value']='20.0'
        with self.assertRaisesRegex(ValueError,'CONTROL_PATH_CHANGED'):evaluate(changed)

    def test_while_boolean_conditions_and_shared_zero_keep_replay_checks(self):
        code='x=fact("x")\ny=fact("y")\nremaining=x\ntotal=0\nwhile remaining>0:\n paid=min(remaining,y)\n total+=paid\n remaining-=paid\nanswer=total'
        graph=self.check(code,(30,10))
        self.assertFalse(any(n.get('operator')=='not' for n in graph['nodes']))
        zero=[n for n in graph['nodes'] if n['kind']=='constant' and n['value_type']=='int' and n['value']=='0']
        self.assertEqual(len(zero),1)
        self.assertEqual({p['line'] for p in zero[0]['source_locations']},{4,5})
        conditions=[e for e in graph['control_flow']['events'] if e.get('control')=='while']
        self.assertEqual([e['observed'] for e in conditions],[True,True,True,False])
        self.assertEqual([e['iteration'] for e in conditions],[1,2,3,4])
        self.assertEqual(len(graph['control_flow']['guards']),4)
        by_id={n['id']:n for n in graph['nodes']}
        self.assertTrue(all(by_id[key]['control_internal'] for key in graph['control_flow']['guards']))
        self.assertFalse(by_id[graph['control_flow']['display_output']].get('control_internal',False))
        changed=copy.deepcopy(graph)
        next(n for n in changed['nodes'] if n.get('fact_id')=='x')['value']='40.0'
        with self.assertRaisesRegex(ValueError,'CONTROL_PATH_CHANGED'):evaluate(changed)
        same=copy.deepcopy(graph)
        next(n for n in same['nodes'] if n.get('fact_id')=='x')['value']='25.0'
        self.assertEqual(evaluate(same)[0],25)

    def test_numeric_truthiness_and_explicit_not_are_preserved(self):
        graph=self.check('x=fact("x")\nanswer=0\nwhile x:\n answer+=x\n x-=1',(2,))
        normalization=[n for n in graph['nodes'] if n.get('operator')=='not']
        self.assertTrue(normalization)
        self.assertTrue(all(n.get('control_internal') for n in normalization))
        explicit=self.check('x=fact("x")\nif not x:\n answer=x+1\nelse:\n answer=x',(0,))
        self.assertTrue(any(n.get('operator')=='not' and not n.get('control_internal') for n in explicit['nodes']))

    def test_control_links_connect_each_iteration_and_exit_without_numeric_operands(self):
        graph=self.check('x=fact("x")\ny=fact("y")\nremaining=x\ntotal=0\nwhile remaining>0:\n paid=min(remaining,y)\n total+=paid\n remaining-=paid\nanswer=total',(30,10))
        nodes={n['id']:n for n in graph['nodes']}
        links=graph['control_flow']['links']
        self.assertEqual(len(links),4)
        self.assertEqual([nodes[e['to']].get('operator',nodes[e['to']].get('variable')) for e in links],['min','min','min','answer'])
        self.assertEqual([e['target_kind'] for e in links],['body','body','body','continuation'])
        for edge in links:
            self.assertNotIn(edge['from'],nodes[edge['to']]['inputs'])
            self.assertLess(int(edge['from'][1:]),int(edge['to'][1:]))
        self.assertFalse(any(k.startswith('_') for e in graph['control_flow']['events'] for k in e))

    def test_if_links_cover_independent_selected_calculations(self):
        code='x=fact("x")\nif x>0:\n a=x+1\n b=x*2\nelse:\n a=x-1\n b=x/2\nanswer=a+b'
        for value,operators in [(10,{'+','*'}),(-10,{'-','/'})]:
            graph=self.check(code,(value,));nodes={n['id']:n for n in graph['nodes']}
            links=graph['control_flow']['links']
            self.assertEqual({nodes[e['to']]['operator'] for e in links},operators)
            self.assertTrue(all(e['target_kind']=='body' for e in links))

    def test_zero_iterations_exit_to_loop_else_then_next_calculation(self):
        graph=self.check('x=fact("x")\nwhile x>0:\n x-=1\nelse:\n x+=2\nanswer=x',(0,))
        links=graph['control_flow']['links'];nodes={n['id']:n for n in graph['nodes']}
        self.assertEqual(len(links),1)
        self.assertEqual(nodes[links[0]['to']]['operator'],'+')
        self.assertEqual(nodes[links[0]['to']]['code_line'],5)
        self.assertEqual(links[0]['target_kind'],'continuation')

    def test_condition_at_end_does_not_link_back_to_previous_answer(self):
        graph=self.check('x=fact("x")\nanswer=x\nwhile x>0:\n x-=1',(0,))
        self.assertEqual(graph['control_flow']['links'][0]['to'],None)
        self.assertEqual(graph['control_flow']['links'][0]['target_kind'],'end')

    def test_break_and_return_do_not_invent_false_loop_exits(self):
        graph=self.check('x=fact("x")\nwhile x>0:\n if x>0:\n  break\nelse:\n x+=100\nanswer=x+1',(2,))
        nodes={n['id']:n for n in graph['nodes']}
        self.assertFalse(any(e.get('control')=='while' and not e['observed'] for e in graph['control_flow']['events']))
        self.assertFalse(any(n['code_line']==6 for n in graph['nodes']))
        branch=next(e for e in graph['control_flow']['links'] if graph['control_flow']['events'][e['event_index']]['control']=='if')
        self.assertEqual(nodes[branch['to']]['code_line'],7)
        returned=self.check('x=fact("x")\ndef select(a):\n if a>0:\n  return a\n return -a\nanswer=select(x)',(2,))
        nodes={n['id']:n for n in returned['nodes']}
        self.assertEqual(nodes[returned['control_flow']['links'][0]['to']]['variable'],'answer')

    def test_constant_types_and_later_literal_use_are_preserved(self):
        graph=self.check('x=fact("x")\nvalues=[0,0.0,False,0]\nanswer=x+sum(values)',(0,))
        constants=[n for n in graph['nodes'] if n['kind']=='constant']
        self.assertEqual({(n['value_type'],n['value']) for n in constants},
                         {('int','0'),('float','0.0'),('bool','False')})
        self.assertEqual(len(constants),3)
        self.assertEqual(sum(n['kind']=='fact' for n in graph['nodes']),1)
        promoted=self.check('x=fact("x")\nif x>0:\n delta=1\nelse:\n delta=2\nflag=True\nanswer=x+delta+int(flag)',(10,))
        true=[n for n in promoted['nodes'] if n['kind']=='constant' and n['value_type']=='bool' and n['value']=='True']
        self.assertEqual(len(true),1)
        self.assertFalse(true[0]['control_internal'])
        self.assertEqual(true[0]['source_locations'][0]['line'],6)

    def test_short_circuit(self):
        self.check('x=fact("x")\nif x==0 or 1/x>0:\n answer=x\nelse:\n answer=-x',(0,))

    def test_guard_precedes_invalid_changed_branch(self):
        g=self.check('x=fact("x")\nif x!=0:\n answer=1/x\nelse:\n answer=0',(2,))
        next(n for n in g['nodes'] if n['kind']=='fact')['value']='0.0'
        with self.assertRaisesRegex(ValueError,'CONTROL_PATH_CHANGED'):evaluate(g)

    def test_factorial_comb(self):
        self.check('import math\nx=fact("x")\nanswer=math.factorial(int(x))+math.comb(int(x),2)',(5,))

    def test_sum_preserves_python_compensated_float_semantics(self):
        self.check('x=fact("x")\nanswer=sum([x,1.0,-x])',(10000000000000000,))

    def test_resource_limits_and_unsupported_constructs(self):
        examples=[('x=fact("x")\nwhile True:\n x+=1\nanswer=x','GRAPH_EXPANSION_.*_LIMIT'),
                  ('x=fact("x")\ndef f(a):\n return f(a)\nanswer=f(x)','RECURSION'),
                  ('import numpy as np\nx=fact("x")\nanswer=x','IMPORT:numpy'),
                  ('x=fact("x")\na=[x]\na[0]=2\nanswer=a[0]','MUTABLE_ASSIGNMENT')]
        for code,error in examples:
            with self.subTest(error=error),self.assertRaisesRegex(ValueError,error):compile_graph(program(code,(1,)))


if __name__=='__main__':unittest.main()
