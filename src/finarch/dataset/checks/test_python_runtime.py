"""Ordinary Python computation and OS denial checks; no model calls."""
import tempfile
import unittest
from pathlib import Path
from finarch.dataset.shared.calculation.python_runtime import execute

class PythonRuntimeChecks(unittest.TestCase):
    def program(self,code):
        return {'context':'100','facts':{'x':{'span':[0,3],'text':'100','value':'100','unit':None}},'code':code}

    def test_log_power_and_round_are_executed_by_python(self):
        result=execute(self.program('import math\nx=fact("x")\nanswer=round(math.log10(x)**3,2)'))
        self.assertEqual(result.status,'PASS');self.assertEqual(float(result.data['exact_value']),8)

    def test_declared_decimal_and_fraction_imports_are_available(self):
        for code in ('from decimal import Decimal\nx=Decimal(str(fact("x")))\nanswer=x/Decimal("2")',
                     'from fractions import Fraction\nx=Fraction(str(fact("x")))\nanswer=x/2'):
            result=execute(self.program(code))
            self.assertEqual(result.status,'PASS')
            self.assertEqual(float(result.data['exact_value']),50)

    def test_worker_imports_are_not_implicit_program_globals(self):
        result=execute(self.program('x=fact("x")\nanswer=math.log10(x)'))
        self.assertEqual(result.status,'FAIL')
        self.assertIn('NameError',result.reason)

    def test_private_project_file_read_is_denied(self):
        path=(Path(__file__).resolve().parent / '../../../..').resolve()/'config/llm.json'
        result=execute(self.program('x=fact("x")\nanswer=len(open('+repr(str(path))+').read())'))
        self.assertEqual(result.status,'FAIL');self.assertIn('PermissionError',result.reason)

    def test_network_and_process_spawn_are_denied(self):
        for code in ('import socket\nx=fact("x")\nsocket.create_connection(("127.0.0.1",9),timeout=1)\nanswer=x',
                     'import subprocess\nx=fact("x")\nsubprocess.run(["/bin/echo","test"],check=True)\nanswer=x'):
            result=execute(self.program(code));self.assertEqual(result.status,'FAIL');self.assertIn('PermissionError',result.reason)

    def test_unapproved_file_write_is_denied(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'not-created.txt'
            result=execute(self.program('x=fact("x")\nopen('+repr(str(target))+',"w").write("test")\nanswer=x'))
            self.assertEqual(result.status,'FAIL');self.assertFalse(target.exists())

    def test_source_span_mismatch_is_rejected_before_execution(self):
        program=self.program('answer=fact("x")');program['facts']['x']['text']='200'
        with self.assertRaisesRegex(ValueError,'FACT_TEXT_MISMATCH'):execute(program)

    def test_computation_exception_and_unused_facts_are_not_passed(self):
        self.assertEqual(execute(self.program('answer=fact("x")/0')).status,'FAIL')
        self.assertEqual(execute(self.program('answer=100')).status,'FAIL')

if __name__=='__main__':unittest.main()

class PythonResultBoundaryChecks(unittest.TestCase):
    def test_zero_is_valid_but_missing_null_boolean_and_nonfinite_are_not(self):
        facts={'x':{'text':'1','value':'1','span':[0,1],'unit':None}}
        for tail,passed in [('answer=0',True),('answer=None',False),('answer=True',False),('answer=float("inf")',False),('',False)]:
            result=execute({'context':'1','facts':facts,'code':'x=fact("x")\n'+tail})
            self.assertEqual(result.status=='PASS',passed)

    def test_sleeping_program_stops_at_wall_time_limit(self):
        result=execute({'context':'1','facts':{'x':{'text':'1','value':'1','span':[0,1],'unit':None}},
                        'code':'import time\nx=fact("x")\ntime.sleep(30)\nanswer=x'})
        self.assertEqual(result.status,'FAIL')
        self.assertEqual(result.reason,'PYTHON_TIMEOUT')
