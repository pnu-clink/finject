"""Offline checks for failed-only same-run execution; no model calls."""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
recheck = __import__('finarch.dataset.90-operations.failed_recheck', fromlist=['*'])
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write

class FailedRecheckTests(unittest.TestCase):
    def test_latest_failed_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp)
            for name,status in [('test-0001','PASS'),('test-0002','FAIL')]:
                write(b/'01-preparation'/name/'run.json',{'status':status,'active_round':'02-round','stopped_at':'05-verification'})
            self.assertEqual([x['case'] for x in recheck.targets(b,'preparation')],['test-0002'])
            write(b/'02-generation/01-round/test-0001/a/run.json',{'status':'FAIL'})
            write(b/'02-generation/02-round/test-0001/a/run.json',{'status':'PASS'})
            write(b/'02-generation/01-round/test-0002/b/run.json',{'status':'FAIL'})
            self.assertEqual([(x['case'],x['variant']) for x in recheck.targets(b,'generation')],[('test-0002','b')])
    def test_recheck_preserves_population_and_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);phase=b/'01-preparation'
            for name,status in [('test-0001','PASS'),('test-0002','FAIL')]:
                write(phase/name/'run.json',{'input_id':name,'status':status,'active_round':'01-round','stopped_at':'05-verification','rounds':[{'round':'01-round','status':status}]})
            untouched=(phase/'test-0001/run.json').read_bytes()
            target=recheck.targets(b,'preparation')
            job={'id':'001-preparation','phase':'preparation','status':'QUEUED','planned':1,'completed':0,'passed':0,'failed':0,'not_evaluated':1,'targets':target,'results':[]}
            write(b/'retry-history/001-preparation/job.json',job)
            write(b/'input-selection.json',{'cases':['test-0001','test-0002'],'input_path':'unused'})
            write(phase/'summary.json',{'results':[]})
            runner=importlib.import_module('finarch.dataset.01-preparation.prepare_run')
            def run(*args,**kwargs):
                self.assertEqual(kwargs['start_stage'],'05-verification')
                return {'input_id':'test-0002','status':'PASS','stopped_at':'07-human-review'}
            def scheduler(items,worker,**kwargs):
                for item in items:yield item,worker(item)
            with patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'evaluate'),patch.object(__import__('finarch.dataset.90-operations.staging', fromlist=['*']), 'PreparedInputs'),patch.object(runner,'run',side_effect=run),patch.object(__import__('finarch.dataset.90-operations.adaptive_schedule', fromlist=['*']), 'run',side_effect=scheduler),patch.object(__import__('finarch.dataset.90-operations.schedule_settings', fromlist=['*']), 'for_config',return_value={}),patch('finarch.dataset.viewer.reports.completion_report.build'),patch.object(importlib.import_module('finarch.shared.run_logging.api_usage'),'summarize_run'):
                result=recheck.execute(b,'001-preparation','preparation')
            self.assertEqual(result['passed'],1)
            self.assertEqual(result['targets'][0]['previous']['status'],'FAIL')
            self.assertEqual((phase/'test-0001/run.json').read_bytes(),untouched)
            self.assertEqual(len(read(phase/'summary.json')['results']),2)
            self.assertEqual(read(phase/'test-0002/run.json')['status'],'PASS')
    def test_generation_rechecks_only_selected_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);driver=importlib.import_module('finarch.dataset.02-generation.generate_run')
            folder=driver.TYPES[4][0];root=b/'02-generation/01-round/test-0001'/folder
            write(root/'run.json',{'status':'FAIL','restart':'03-validation'})
            target=recheck.targets(b,'generation')
            write(b/'retry-history/001-generation/job.json',{'id':'001-generation','phase':'generation','status':'QUEUED','planned':1,'targets':target,'results':[]})
            def run(*args,**kwargs):
                self.assertEqual(kwargs['approved'],{'test-0001':{}});self.assertEqual(kwargs['indices'],[4]);self.assertEqual(kwargs['start_stage'],'03-validation')
                value={'status':'PASS','path':str(root.relative_to(b))};write(root/'run.json',value)
                return {'results':[value]}
            def scheduler(items,worker,**kwargs):
                for item in items:yield item,worker(item)
            with patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'require_generation_inputs',return_value={'test-0001':{}}) as gate,patch.object(driver,'run',side_effect=run),patch.object(__import__('finarch.dataset.90-operations.adaptive_schedule', fromlist=['*']), 'run',side_effect=scheduler),patch.object(__import__('finarch.dataset.90-operations.schedule_settings', fromlist=['*']), 'for_config',return_value={}),patch('finarch.dataset.viewer.reports.completion_report.build'),patch.object(importlib.import_module('finarch.shared.run_logging.api_usage'),'summarize_run'):
                result=recheck.execute(b,'001-generation','generation')
            self.assertEqual(result['passed'],1)
            self.assertEqual(read(b/'02-generation/summary.json')['latest']['test-0001']['4']['status'],'PASS')

    def test_restart_archives_old_handler_without_touching_graph(self):
        begin = __import__('finarch.dataset.90-operations.stage_range', fromlist=['begin']).begin
        PREPARATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['PREPARATION']).PREPARATION
        RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'case';ctx=RunContext(root,{},'test-0001')
            ctx.trace.emit(event='START',function='test',status='RUNNING')
            ctx.save('run.json',{'status':'FAIL'})
            ctx.save('04-graph/sentinel.json',{'preserve':True})
            ctx.save('05-verification/old.json',{'status':'FAIL'})
            ctx.save('06-exception-handler/old.json',{'status':'FAIL'})
            graph=(root/'04-graph/sentinel.json').read_bytes()
            ctx=begin(root,PREPARATION,('05-verification','07-human-review'),'test-0001')
            self.assertFalse((root/'06-exception-handler').exists())
            self.assertEqual((root/'04-graph/sentinel.json').read_bytes(),graph)
            self.assertEqual(len(list((root/'stage-history').glob('*/06-exception-handler/old.json'))),1)
            ctx.save('06-exception-handler/old.json',{'status':'NEW'})

    def test_in_progress_launch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);write(b/'retry-history/001-preparation/job.json',{'status':'RUNNING'})
            with self.assertRaisesRegex(ValueError,'RECHECK_ALREADY_RUNNING'):recheck.launch(b,'preparation')

if __name__=='__main__':unittest.main()
