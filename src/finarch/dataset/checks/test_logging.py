"""Per-problem logging checks; local Python and explicit model doubles only."""
import json
import os
import selectors
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

Journal = __import__('finarch.shared.run_logging.logging', fromlist=['Journal']).Journal
read_summary = __import__('finarch.shared.run_logging.logging', fromlist=['read_summary']).read_summary
record_usage = __import__('finarch.shared.run_logging.logging', fromlist=['record_usage']).record_usage
traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
estimate_cost = __import__('finarch.shared.run_logging.logging', fromlist=['estimate_cost']).estimate_cost
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
StepStopped = __import__('finarch.dataset.90-operations.staging', fromlist=['StepStopped']).StepStopped
cli = __import__('finarch.shared.providers.cli', fromlist=['*'])


class LoggingChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='finarch-log-check-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def context(self):
        return RunContext(self.root/'run', {}, case_id='local-test')

    def test_start_is_durable_before_work_and_nested_parent_is_linked(self):
        ctx = self.context()
        @traced()
        def child():
            events = [json.loads(x) for x in ctx.trace.path.read_text().splitlines()]
            self.assertEqual(events[-1]['phase'], 'START')
            self.assertEqual(events[-1]['problem_id'], 'local-test')
        def handler(payload):
            child()
            return StepResult('PASS', 'local test', {})
        ctx.invoke('test', 'work', 'python.check', {}, local=handler)
        events = ctx.events
        starts = [e for e in events if e['phase']=='START']
        self.assertEqual(starts[1]['parent_call_id'], starts[0]['call_id'])
        self.assertEqual([e['sequence'] for e in events], list(range(1,len(events)+1)))
        for e in events:
            if e['phase']=='END':
                self.assertGreaterEqual(e['elapsed_seconds'], 0)
                self.assertIn('started_at', e)
                self.assertIn('ended_at', e)
        self.assertEqual(ctx.trace.summary()['pending_call_ids'], [])

    def test_error_interruption_and_request_save_error_keep_start_and_end(self):
        for mode in ('error','interrupt','save'):
            ctx=RunContext(self.root/mode, {}, case_id='local-test')
            def handler(payload):
                if mode=='interrupt': raise KeyboardInterrupt()
                raise ValueError('local test')
            if mode=='save':
                with patch.object(ctx,'save',side_effect=OSError('local disk test')):
                    with self.assertRaises(OSError):ctx.invoke('test','work','python.check',{},local=handler)
            else:
                with self.assertRaises(KeyboardInterrupt if mode=='interrupt' else StepStopped):
                    ctx.invoke('test','work','python.check',{},local=handler)
            self.assertEqual(ctx.events[0]['phase'],'START')
            self.assertEqual(ctx.events[-1]['phase'],'END')
            self.assertEqual(ctx.events[-1]['status'],'CANCELLED' if mode=='interrupt' else 'FAIL')

    def test_start_log_failure_prevents_handler_and_reuse_does_not_overwrite(self):
        ctx=self.context();calls=[]
        with patch.object(ctx.trace,'emit',side_effect=OSError('local log failure')):
            with self.assertRaises(OSError):
                ctx.invoke('test','work','python.check',{},local=lambda p:calls.append(p))
        self.assertEqual(calls,[])
        with self.assertRaises(FileExistsError):self.context()

    def test_hard_kill_retains_start_without_fake_end(self):
        code="""import sys,time
from pathlib import Path
Journal = __import__('finarch.shared.run_logging.logging', fromlist=['Journal']).Journal
root=Path(sys.argv[1]); journal=Journal(root,'local-test')
with journal.activate(), journal.span('hard-kill-check'):
 print('started',flush=True)
 time.sleep(20)
"""
        process=subprocess.Popen([sys.executable,'-c',code,str(self.root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                self.assertTrue(selector.select(5),'child failed to start')
                self.assertEqual(process.stdout.readline().strip(),'started')
            process.kill();process.communicate(timeout=5)
        finally:
            if process.poll() is None:process.kill();process.communicate(timeout=5)
        report=read_summary(self.root/'events.jsonl')
        self.assertEqual(len(report['pending_call_ids']),1)
        self.assertFalse(report['invocation_count_complete'])
        with (self.root/'events.jsonl').open('a') as f:f.write('{"partial":')
        self.assertEqual(read_summary(self.root/'events.jsonl')['damaged_lines'],[2])

    def test_cli_interrupt_returns_partial_artifacts_and_kills_child(self):
        with patch.object(cli.time,'sleep',side_effect=KeyboardInterrupt), patch.object(__import__('finarch.shared.run_logging.logging', fromlist=['*']), 'record_cli'):
            result=cli.run_process([sys.executable,'-c',"import time; time.sleep(10)"],
                                   '',self.root,5,self.root/'audit.jsonl')
        self.assertEqual(result['state'],'CANCELLED')
        self.assertIsNotNone(result['exit_code'])
        self.assertIn('stdout',result)
        self.assertIn('stderr',result)

    def test_condition_is_evaluated_after_start(self):
        ctx=self.context()
        def condition():
            self.assertTrue(any(e['phase']=='START' and e['step']=='condition' for e in ctx.events))
            self.assertFalse(any(e['phase']=='END' and e['step']=='condition' for e in ctx.events))
            raise ZeroDivisionError()
        with self.assertRaises(StepStopped):ctx.check('test','condition',{},condition,'test')
        self.assertEqual(ctx.events[-1]['status'],'FAIL')

    def test_usage_unknown_is_not_zero_and_known_currency_totals(self):
        ctx=self.context()
        with ctx.trace.activate(),ctx.trace.span('cli'):
            record_usage(role='test',model='test',provider='test',usage={'input_tokens':4},reason='test',estimated_cost=0.25,currency='USD',price_basis='test only')
        self.assertEqual(ctx.trace.summary()['estimated_cost'],0.25)
        with ctx.trace.activate(),ctx.trace.span('cli'):
            record_usage(role='test',model='test',provider='test',usage=None,reason='No reported usage')
        summary=ctx.trace.summary()
        self.assertIsNone(summary['estimated_cost'])
        self.assertIsNone(summary['actual_billed_cost'])
        self.assertEqual(summary['cli_invocations'],2)

    def test_cost_requires_documented_rates_and_accounts_for_cache(self):
        price={'source':'LOCAL_TEST_ONLY','as_of':'test-date','currency':'USD',
               'input_per_million':2,'output_per_million':8,'cached_input_per_million':1}
        usage={'input_tokens':1000,'output_tokens':200,'cached_input_tokens':400}
        self.assertAlmostEqual(estimate_cost(usage,price)['estimated_cost'],0.0032)
        self.assertIsNone(estimate_cost(usage,None)['estimated_cost'])
        self.assertIsNone(estimate_cost({'input_tokens':1000},price)['estimated_cost'])
        self.assertIsNone(estimate_cost(usage,{**price,'source':''})['estimated_cost'])
        self.assertIsNone(estimate_cost(usage,{**price,'cached_input_per_million':None})['estimated_cost'])

    def test_cli_failure_usage_is_linked_before_response_rejection(self):
        ctx=self.context();config=self.root/'config.json'
        config.write_text(json.dumps({'provider':'codex','execution_enabled':True,
          'roles':{'dtt.answer':{'model':'local-test','effort':'low'}},'cli_limits':{'timeout_seconds':1},
          'capabilities':{'dtt.answer':{'tools':[],'skills':[]}}}))
        output=json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'output_tokens':2}})
        result={'state':'TIMEOUT','exit_code':-9,'stdout':output,'stderr':'','started_at':'test','ended_at':'test','elapsed_seconds':1}
        with ctx.trace.activate(),ctx.trace.span('local-model-double',kind='llm'):
            with patch.object(cli,'inspect_runtime',return_value={'executable':'local-only','native_tool_enforcement':'VERIFIED'}),patch.object(cli,'run_process',return_value=result):
                response=cli.call(config,'dtt.answer',{'context':'test','question':'test'},save=lambda k,v:ctx.save('call/'+k,v))
        self.assertEqual(response.status,'FAIL')
        usage=ctx.trace.summary()['usage_records']
        self.assertEqual(len(usage),1)
        self.assertEqual(usage[0]['reported_usage']['input_tokens'],7)
        self.assertIsNotNone(usage[0]['call_id'])
        self.assertTrue((ctx.root/'call/03-result/usage.json').exists())
        self.assertTrue(any(e.get('path')=='call/03-result/usage.json' for e in ctx.events))
        self.assertEqual(ctx.trace.summary()['pending_call_ids'],[])



if __name__=='__main__':unittest.main()
