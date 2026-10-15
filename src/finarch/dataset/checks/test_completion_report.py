"""Verify round denominators, carry-forward, and non-executed rounds."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
from finarch.dataset.viewer.reports.completion_report import snapshot, build, view
TYPES = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['TYPES']).TYPES


class CompletionReportTests(unittest.TestCase):
    def test_in_progress_run_does_not_probe_unstarted_rounds(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle=Path(folder)
            write(bundle/'input-selection.json',{'cases':['test-0001']})
            write(bundle/'01-preparation/test-0001/01-round/run.json',{'status':'PASS'})
            write(bundle/'02-generation/01-round/test-0001'/TYPES[0][0]/'run.json',{'status':'FAIL'})
            from finarch.dataset.viewer.summary_reader import read_status_record
            with patch('finarch.dataset.viewer.reports.completion_report.read_status_record',wraps=read_status_record) as read_status:
                report=snapshot(bundle,gate={'approved':['test-0001'],'rejected':[]})
            self.assertTrue(read_status.called)
            for call in read_status.call_args_list:
                self.assertNotIn('02-round',call.args[0].parts)
                self.assertNotIn('03-round',call.args[0].parts)
            self.assertEqual(report['status'],'IN_PROGRESS')
            self.assertEqual(report['generation']['rounds'][0]['counts'],{'FAIL':1,'NOT_EVALUATED':6})
            self.assertEqual(report['generation']['rounds'][1]['counts'],{'NOT_RUN':7})
            self.assertEqual(report['preparation']['rounds'][1]['counts'],{'NOT_RUN':1})

    def test_completed_view_reuses_only_unchanged_existing_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle=Path(folder);source=bundle/'01-preparation/test-0001/01-round/run.json'
            write(source,{'status':'PASS'})
            saved={'status':'COMPLETED','approved_cases':[],'excluded_cases':[],
                   'preparation':{'rows':[{'rounds':[{'status':'PASS','source':str(source.relative_to(bundle))}]}]},
                   'generation':{'rows':[]}}
            write(bundle/'completion-report.json',saved)
            with patch('finarch.dataset.viewer.reports.completion_report.snapshot',return_value={'rebuilt':True}) as rebuild:
                self.assertEqual(view(bundle)['status'],'COMPLETED')
                rebuild.assert_not_called()
                write(source,{'status':'FAIL'})
                self.assertEqual(view(bundle),{'rebuilt':True})
                write(bundle/'completion-report.json',saved)
                source.unlink()
                self.assertEqual(view(bundle),{'rebuilt':True})

    def test_separate_rounds_and_retained_results(self):
        with tempfile.TemporaryDirectory() as folder:
            b=Path(folder);prep=b/'01-preparation';gen=b/'02-generation'
            write(b/'input-selection.json',{'cases':['one','two']})
            write(prep/'repair-history/01-original/batch/01-preparation/summary.json',{'results':[{'input_id':'one','status':'PASS'},{'input_id':'two','status':'FAIL','reason':'source'}]})
            write(prep/'repair-history/results.json',{'planned':1,'processed':1,'results':[{'input_id':'two','status':'PASS'}]})
            for name in ('one','two'):
                write(prep/name/'run.json',{'status':'PASS'})
                for path,axis,label in TYPES:write(gen/'01-round'/name/path/'run.json',{'status':'PASS' if name=='one' else 'FAIL','reason':'source'})
            write(gen/'01-round/final-validator.json',{'decision':'RETRY'})
            write(gen/'02-round/two'/TYPES[0][0]/'run.json',{'status':'PASS'})
            gate={'approved':['one','two'],'rejected':[]}
            with patch('finarch.dataset.viewer.reports.completion_report.evaluate',return_value=gate):
                r=snapshot(b)
                self.assertEqual(r['preparation']['rounds'][0]['counts'],{'PASS':1,'FAIL':1})
                self.assertEqual(r['preparation']['rounds'][1]['counts'],{'PASS':2})
                self.assertEqual(r['preparation']['rounds'][1]['attempted'],1)
                self.assertEqual(r['generation']['rounds'][1]['counts'],{'PASS':8,'FAIL':6})
                self.assertEqual(r['generation']['rounds'][1]['attempted'],1)
                self.assertEqual(r['generation']['rounds'][2]['state'],'NOT_RUN')
                self.assertEqual(r['generation']['rounds'][2]['counts'],{'NOT_RUN':14})
                self.assertTrue(r['generation']['rows'][0]['rounds'][1]['carried'])
                with self.assertRaisesRegex(ValueError,'NOT_FINISHED'):build(b)
                self.assertFalse((b/'completion-report.json').exists())
                write(gen/'timing.json',{'status':'COMPLETED'})
                write(gen/'summary.json',{'status':'PASS'})
                with patch('finarch.dataset.viewer.reports.generation_report.build',return_value={'status':'PASS'}):
                    completed=build(b)
                    with (b/'README.md').open('a') as stream:stream.write('\nUser review note.\n')
                    build(b)
                    self.assertIn('User review note.',(b/'README.md').read_text())
                    self.assertEqual((b/'README.md').read_text().count('<!-- completion-report:start -->'),1)
                self.assertEqual(completed['status'],'COMPLETED')
                self.assertTrue((b/'completion-report.json').exists())
                self.assertIn('미실행|—|—|—|—',(b/'RESULTS.md').read_text())

    def test_explicit_three_preparation_rounds(self):
        with tempfile.TemporaryDirectory() as folder:
            b=Path(folder);prep=b/'01-preparation'
            write(b/'input-selection.json',{'cases':['one','two']})
            for number,rows in [(1,[{'input_id':'one','status':'PASS'},{'input_id':'two','status':'FAIL'}]),(2,[{'input_id':'two','status':'FAIL'}]),(3,[{'input_id':'two','status':'PASS'}])]:
                write(prep/'rounds'/f'{number:02d}-round.json',{'round':number,'results':rows})
            with patch('finarch.dataset.viewer.reports.completion_report.evaluate',return_value={'approved':[],'rejected':[]}):
                r=snapshot(b)['preparation']
            self.assertEqual([c['attempted'] for c in r['rounds']],[2,1,1])
            self.assertEqual([c['state'] for c in r['rounds']],['COMPLETED']*3)
            self.assertEqual(r['rounds'][2]['counts'],{'PASS':2})
            self.assertTrue(r['rows'][0]['rounds'][2]['carried'])
            self.assertFalse(r['rows'][1]['rounds'][2]['carried'])
