"""Offline logging checks; files stay in temporary directories, no LLM calls."""
import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path

Journal = __import__('finarch.shared.run_logging.logging', fromlist=['Journal']).Journal
record_cli = __import__('finarch.shared.run_logging.logging', fromlist=['record_cli']).record_cli
traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs
from finarch.dataset.viewer.run_logs import read_log


def writer(root, n):
    logs=RunLogs(root,'parallel')
    for i in range(8):logs.write('detail.log','work',value={'worker':n,'index':i})


class RunLogChecks(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);case=self.root/'reports/run/fresh/test-0001';case.mkdir(parents=True)
        self.journal=Journal(case,'test-0001');self.folder=self.root/'log/run/fresh'

    def rows(self,path):
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_actual_arguments_and_inputs_outputs_share_function(self):
        j=self.journal
        @traced('llm')
        def inner():
            record_cli(['codex','exec','-m','test-model','-c','model_reasoning_effort=none'],self.root)
            j.artifact('01-input.json',{'input':'first\nsecond'})
            j.artifact('response.json',{'output':'third\nfourth'})
        with j.activate(),j.span('02-generation.02-generate-text.realization',kind='llm',axis='EA'):
            inner()
        pipeline=self.rows(self.folder/'test-0001/08-records/pipeline.log')
        self.assertEqual(len(pipeline),1)
        self.assertEqual(pipeline[0]['function'],'02-generation.02-generate-text.realization')
        self.assertNotIn('02-generation.02-generate-text.realization',pipeline[0])
        llm=self.rows(self.folder/'test-0001/08-records/llm-ea.log')
        values=[r['02-generation.02-generate-text.realization'].get('value') for r in llm]
        self.assertIn({'input':'first\nsecond'},values)
        self.assertIn({'output':'third\nfourth'},values)
        cli=self.rows(self.root/'log/cli.log')
        self.assertEqual(cli[0]['02-generation.02-generate-text.realization']['argv'][-1],'model_reasoning_effort=none')
        default=self.rows(self.folder/'default.log')
        self.assertEqual([r['sequence'] for r in default],list(range(1,len(default)+1)))
        for file in self.folder.rglob('*.log'):
            if file.name!='default.log':
                for row in self.rows(file):self.assertIn(row,default)
        self.assertIn(cli[0],default)

    def test_type_routing_and_reader_pages(self):
        j=self.journal
        for axis,suffix in [('IC_VALUE','ic-value'),('IC_SOURCE','ic-source'),('IC_RELATION','ic-relation'),('EA','ea'),(None,None)]:
            for role in ['02-generation.02-generate-text.realization','shared.01-02.02-03.review-and-validation']:
                with j.activate(),j.span(role,kind='llm',axis=axis):
                    j.artifact('response.json',{'axis':axis})
            path=self.folder/'test-0001/08-records'/('llm-'+suffix+'.log' if suffix else 'llm.log')
            self.assertEqual({r['function'] for r in self.rows(path)},{'02-generation.02-generate-text.realization','shared.01-02.02-03.review-and-validation'})
        first=read_log(self.root/'log','fresh','default.log',limit=2)
        second=read_log(self.root/'log','fresh','default.log',offset=first['offset'],limit=2)
        self.assertLess(first['records'][-1]['sequence'],second['records'][0]['sequence'])
        with self.assertRaises(ValueError):read_log(self.root/'log','../fresh','default.log')
        with self.assertRaises(ValueError):read_log(self.root/'log','fresh','../../config.json')

    def test_stage_log_matches_artifact_directory(self):
        with self.journal.activate(), self.journal.span('02-generation.02-generate-text.realization',kind='llm',stage='05-text/EA_01/01-generate-text/attempt-01',step='T01'):
            self.journal.artifact('05-text/EA_01/01-generate-text/attempt-01/02-raw-response.json',{'text':'saved raw response'})
        filename='test-0001/05-text/EA_01/01-generate-text/attempt-01/detail.log'
        rows=read_log(self.root/'log','fresh',filename)['records']
        self.assertEqual(rows[-1]['artifact_directory'],'test-0001/05-text/EA_01/01-generate-text/attempt-01')
        self.assertIn(rows[-1],self.rows(self.folder/'default.log'))

    def test_parallel_process_order(self):
        context=multiprocessing.get_context('spawn')
        processes=[context.Process(target=writer,args=(self.root/'log',i)) for i in range(3)]
        for process in processes:process.start()
        for process in processes:
            process.join(10);self.assertEqual(process.exitcode,0)
        rows=self.rows(self.root/'log/run/parallel/default.log')
        self.assertEqual([r['sequence'] for r in rows],list(range(1,25)))
        self.assertEqual([r['timestamp'] for r in rows],sorted(r['timestamp'] for r in rows))


if __name__=='__main__':unittest.main()
