import unittest
name_constants = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['name_constants']).name_constants
review = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['review']).review
from finarch.dataset.shared.calculation.python_runtime import execute


class StepwiseChecks(unittest.TestCase):
    def test_constants_named_without_changing_python_result_or_original(self):
        code='x=fact("x")\ny=1+x\nz=y*100\nanswer=round(z,2)\n'
        original={'code':code,'context':'2','facts':{'x':{'text':'2','value':'2','span':[0,1],'unit':None}}}
        prepared,audit=name_constants(original)
        self.assertEqual(original['code'],code)
        self.assertEqual(audit['review']['status'],'PASS')
        self.assertEqual(execute(original).data['exact_value'],execute(prepared).data['exact_value'])
        self.assertEqual(name_constants(prepared)[0],prepared)

    def test_name_collisions_and_multibyte_identifiers_preserve_values(self):
        program={'code':'합계_constant_1=7\n합계=x*100\n'}
        prepared,audit=name_constants(program)
        scope={'x':2};exec(prepared['code'],scope)
        self.assertEqual(scope['합계_constant_1'],7)
        self.assertEqual(scope['합계'],200)
        self.assertEqual(audit['review']['status'],'PASS')

    def test_nested_expression_is_not_falsely_marked_ready(self):
        prepared,audit=name_constants({'code':'answer=(x+1)*100\n'})
        self.assertEqual(audit['review']['status'],'FAIL')
        self.assertTrue(audit['review']['nested_operation_lines'])

    def test_provenance_lines_follow_rewritten_assignments(self):
        import ast
        program={'code':'x=fact("x")\nanswer=x*100\n','source_usage':[{
            'id':'rule','code_lines':[2],'output_variables':['answer']}]}
        changed,audit=name_constants(program)
        answer_line=next(n.lineno for n in ast.walk(ast.parse(changed['code']))
                         if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) and n.id=='answer')
        self.assertEqual(changed['source_usage'][0]['code_lines'],[answer_line])
        self.assertEqual(program['source_usage'][0]['code_lines'],[2])
        self.assertTrue(audit['provenance_changes'])

    def test_question_fact_is_validated_against_question(self):
        program={'code':'answer=fact("q")','question':'3','context':'2',
                 'facts':{'q':{'text':'3','value':'3','span':[0,1],'unit':None,'origin':'QUESTION'}}}
        result=execute(program)
        self.assertEqual(result.status,'PASS')
        self.assertEqual(result.data['exact_value'],'3')
