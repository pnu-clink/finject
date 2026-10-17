import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
begin = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['begin']).begin
end = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['end']).end
measure = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['measure']).measure
from finarch.dataset.viewer.reports.timing_report import union_seconds, metrics, build


class ExecutionTimingTests(unittest.TestCase):
    def test_preparation_rounds_include_archived_repairs(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp)/'reports/run/example'
            for attempt,relative in enumerate(['repair-history/01-round/test-1','repair-history/02-round/test-1','test-1']):
                case=root/'01-preparation'/relative;case.mkdir(parents=True)
                (case/'run.json').write_text(json.dumps({'input_id':'test-1','repair_attempt':attempt}))
                base={'call_id':str(attempt),'started_at':f'2026-09-10 10:0{attempt}:00+09:00','ended_at':f'2026-09-10 10:0{attempt}:10+09:00'}
                events=[{**base,'phase':'USAGE','cli_invocations':1},{**base,'phase':'END','function':'finarch.shared.providers.cli.CLITransport.__call__'}]
                (case/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            report=build(root)
            self.assertEqual([(r['round'],r['llm_calls']) for r in report['rounds']],[(f'Preparation / {i}\ucc28',1) for i in (1,2,3)])
            self.assertEqual(report['total']['llm_calls'],3)

    def test_api_usage_without_cli_invocation_is_counted(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp)/'reports/run/example'
            case=root/'01-preparation/test-0001/02-round';case.mkdir(parents=True)
            base={'call_id':'api1','function':'finarch.shared.providers.cli.CLITransport.__call__',
                  'started_at':'2026-09-10 10:00:00+09:00','ended_at':'2026-09-10 10:00:10+09:00'}
            events=[{**base,'phase':'START'}, {**base,'phase':'END'},
                    {**base,'phase':'USAGE','provider':'openai','cli_invocations':0,
                     'reported_usage':{'input_tokens':100,'output_tokens':20,'input_tokens_details':{'cached_tokens':40}}}]
            (case/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            result=build(root)
            self.assertEqual(result['calls_without_usage'],0)
            self.assertEqual(result['total']['llm_calls'],1)
            self.assertEqual(result['total']['llm_call_seconds'],10)
            self.assertEqual(result['total']['reported_tokens'],{'input_tokens':100,'output_tokens':20,'cached_input_tokens':40})
            self.assertEqual(result['rounds'][0]['round'],'Preparation / 2\ucc28')

    def test_generation_types_separate_parallel_calls(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp)/'reports/run/example'
            for variant in ['01-ic-value-before','02-ic-value-after']:
                case=root/'02-generation/01-round/test-1'/variant;case.mkdir(parents=True)
                base={'call_id':variant,'started_at':'2026-09-10 10:00:00+09:00','ended_at':'2026-09-10 10:00:10+09:00'}
                events=[{**base,'phase':'USAGE','cli_invocations':1},{**base,'phase':'END','function':'finarch.shared.providers.cli.CLITransport.__call__'}]
                (case/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            report=build(root)
            self.assertEqual(len(report['generation_types']),2)
            self.assertEqual([r['llm_calls'] for r in report['generation_types']],[1,1])
            self.assertEqual(report['total']['llm_active_seconds'],10)
            self.assertEqual(sum(r['llm_call_seconds'] for r in report['generation_types']),20)

    def test_parallel_llm_sum_is_not_wall_time(self):
        self.assertEqual(union_seconds([(0,10),(5,15),(6,8)]),15)
        m=metrics([(0,20)],[(0,10),(5,15)],[{'cli_invocations':1},{'cli_invocations':1}])
        self.assertEqual(m['elapsed_seconds'],20)
        self.assertEqual(m['llm_call_seconds'],20)
        self.assertEqual(m['llm_active_seconds'],15)

    def test_lifecycle_logs_command_and_monotonic_duration(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp)/'reports/run/example'
            with patch.object(__import__('finarch.dataset.90-operations.execution_timing', fromlist=['*']).time, 'monotonic',side_effect=[100,112.5]):
                begin(root,'run',['python','-m','example','--input','a b.json'])
                result=end(root)
            self.assertEqual(result['elapsed_seconds'],12.5)
            self.assertEqual(result['elapsed_display'],'00:00:12')
            self.assertIn("'a b.json'",result['command'])
            records=[json.loads(line) for line in (Path(tmp)/'log/cli.log').read_text().splitlines()]
            self.assertEqual([r['phase'] for r in records],['START','END'])
            self.assertEqual(end(root),result)

    def test_error_is_recorded_not_completed(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp)
            with self.assertRaises(ValueError):
                with measure(root,'run',['example']):raise ValueError('failed')
            result=json.loads((root/'timing.json').read_text())
            self.assertEqual(result['status'],'ERROR')
            self.assertIn('failed',result['reason'])

    def test_actual_transport_only_not_nested_llm_spans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'reports/run/example';case=root/'01-round/test-0001';case.mkdir(parents=True)
            base={'stage':'05-text','step':'01-generate-text','kind':'llm','started_at':'2026-09-10 10:00:00+09:00','ended_at':'2026-09-10 10:00:10+09:00'}
            events=[{**base,'phase':'USAGE','call_id':'actual','cli_invocations':1},
                    {**base,'phase':'END','call_id':'actual','function':'finarch.shared.providers.cli.CLITransport.__call__'},
                    {**base,'phase':'END','call_id':'outer','function':'outer_llm_wrapper'}]
            (case/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            report=build(root)
            self.assertEqual(report['total']['llm_call_seconds'],10)
            self.assertEqual(report['total']['llm_calls'],1)
            self.assertEqual(report['total']['measurement'],'observed_event_window')


if __name__=='__main__':unittest.main()
