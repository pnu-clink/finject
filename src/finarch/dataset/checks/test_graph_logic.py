"""Boolean graph evaluation must follow Python, including skipped operands."""
import unittest
from finarch.dataset.shared.calculation.python_graph import compile_graph
from finarch.dataset.shared.calculation.python_runtime import execute

class LogicTests(unittest.TestCase):
    def test_comparison_boundaries_and_boolean_values(self):
        for expr in ['x if x>0 else 1/0','1/0 if x<0 else x','(x if x==2 else 0) if x>0 else -x','x<2','x<=2','x>2','x>=2','x==2','x!=2','0<=x<3','x>=0 and x<3','x<0 or x==2','not (x<0)','False and 1/0','True or 1/0','3<x<1/0','x and 7','x or 7']:
            with self.subTest(expr=expr):
                p={'context':'2','facts':{'x':{'text':'2','value':'2','span':[0,1],'unit':None}},'code':'x=fact("x")\nv='+expr+'\nanswer=int(v)+int(x-x)'}
                graph,value,_=compile_graph(p);result=execute(p)
                self.assertEqual(result.status,'PASS')
                self.assertEqual(str(value),result.data['exact_value'])
                for node in graph['nodes']:
                    if node['kind']=='variable':self.assertEqual(node['computed'],result.data['trace'][node['variable']])

if __name__=='__main__':unittest.main()
