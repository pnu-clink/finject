"""Current case-local round paths and historical read-only compatibility."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from finarch.dataset.viewer.build import collect
from finarch.dataset.viewer.preparation_paths import select_round, feedback_sources
from finarch.dataset.viewer.server import batch_data
from finarch.dataset.viewer.reports.completion_report import snapshot


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class CaseRounds(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.runs=Path(self.tmp.name);self.bundle=self.runs/'new'
        self.prep=self.bundle/'01-preparation';self.case=self.prep/'test-0001'
        put(self.bundle/'input-selection.json',{'cases':['test-0001','test-0002']})
        for case in ('test-0001','test-0002'):
            put(self.prep/case/'run.json',{'status':'PASS','active_round':'02-round'})
            put(self.prep/case/'01-round/run.json',{'input_id':case,'status':'FAIL' if case=='test-0001' else 'PASS','reason':'original error'})
            put(self.prep/case/'01-round/01-source/01-receive-input/01-input.json',{'id':case,'context':'Value 2','question':'Value?','reference_answer':'2','reference_answer_type':'integer','reference_precision':0})
        put(self.case/'02-round/run.json',{'input_id':'test-0001','status':'PASS'})
        put(self.case/'02-round/01-source/01-receive-input/01-input.json',{'id':'test-0001','context':'Value 2','question':'Value?','reference_answer':'2','reference_answer_type':'integer','reference_precision':0})
        put(self.case/'02-round/03-calculation/03-preserve-response-and-code/03-program.json',{'code':'answer=2','facts':{}})
        put(self.case/'02-round/06-exception-handler/feedback/03-round/feedback.json',{'guidance':'Check span'})
        code=self.case/'02-round/03-calculation/03-preserve-response-and-code/02-program.py';code.write_text('answer=2\n')
        self.gate={'approved':[],'rejected':[],'pending':['test-0001','test-0002'],'allow_generation':False}

    def test_collect_code_alias_points_to_real_file(self):
        r=collect(self.case/'02-round')
        current='03-calculation/03-preserve-response-and-code/03-program.json'
        alias='03-calculation/02-prepare-code/03-program.json'
        self.assertEqual(r['artifact_aliases'][alias],current)
        self.assertEqual(r['artifacts'][alias]['code'],'answer=2')
        self.assertIn('03-calculation/03-preserve-response-and-code/02-program.py',r['artifacts'])
        self.assertIn('06-exception-handler/feedback/03-round/feedback.json',r['artifacts'])

    def test_round_selection_isolation_and_no_disk_mutation(self):
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.bundle.rglob('*') if p.is_file()}
        with patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'evaluate',return_value=self.gate),patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'snapshot',return_value={}),patch('finarch.dataset.viewer.reports.completion_report.evaluate',return_value=self.gate):
            old=batch_data(self.runs,'new','01-round','test-0001')
            new=batch_data(self.runs,'new','02-round','test-0001')
        self.assertEqual(new['batch']['rounds'],['01-round','02-round'])
        self.assertEqual(old['runs'][0]['artifacts']['run.json']['status'],'FAIL')
        self.assertEqual(new['runs'][0]['artifacts']['run.json']['status'],'PASS')
        self.assertEqual(new['runs'][0]['round'],'02-round')
        self.assertEqual(new['runs'][1]['round'],'01-round')
        self.assertNotIn('03-calculation/03-preserve-response-and-code/03-program.json',old['runs'][0]['artifacts'])
        after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.bundle.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_completion_counts_actual_attempts_and_preserves_error(self):
        with patch('finarch.dataset.viewer.reports.completion_report.evaluate',return_value=self.gate):
            r=snapshot(self.bundle)['preparation']
        self.assertEqual([x['attempted'] for x in r['rounds']],[2,1,0])
        self.assertEqual(r['rounds'][0]['counts'],{'FAIL':1,'PASS':1})
        self.assertEqual(r['rounds'][1]['counts'],{'PASS':2})
        self.assertTrue(r['rows'][1]['rounds'][1]['carried'])
        self.assertEqual(r['rows'][0]['rounds'][0]['reason'],'original error')
        self.assertEqual(r['rounds'][2]['state'],'NOT_RUN')

    def test_historical_flat_case_still_readable(self):
        path=self.runs/'legacy';put(path/'run.json',{'status':'FAIL'})
        put(path/'02-review-and-correct/accepted-input.json',{'question':'Q'})
        self.assertEqual(select_round(path)[0],path)
        r=collect(path)
        self.assertEqual(r['artifacts']['02-review/accepted-input.json'],{'question':'Q'})
        self.assertEqual(r['artifact_aliases']['02-review/accepted-input.json'],'02-review-and-correct/accepted-input.json')

    def test_detail_request_never_loads_other_cases_or_batch_reports(self):
        server = __import__('finarch.dataset.viewer.server', fromlist=['*'])
        original=server.read_optional
        def selected_only(path):
            self.assertNotIn('test-0002',str(path))
            return original(path)
        with patch.object(server,'read_optional',side_effect=selected_only), \
             patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'evaluate',side_effect=AssertionError('batch gate')), \
             patch('finarch.dataset.viewer.reports.completion_report.view',side_effect=AssertionError('batch report')), \
             patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'snapshot',return_value={}):
            value=batch_data(self.runs,'new','03-round','test-0001',detail_only=True)
        self.assertTrue(value['detail_only'])
        self.assertEqual(len(value['runs']),1)
        self.assertEqual(value['runs'][0]['round'],'02-round')
        self.assertTrue(value['runs'][0]['list_entry']['summary_only'])
        self.assertNotIn('completion_report',value['batch'])
        with self.assertRaises(ValueError):
            batch_data(self.runs,'new','02-round','../outside',detail_only=True)

    def test_list_keeps_search_text_without_duplicate_source_payloads(self):
        from finarch.dataset.viewer.server import compact_preparation_case
        source=self.case/'02-round/01-source/01-receive-input/01-input.json'
        data=json.loads(source.read_text())
        data.update(context_mapping={'large':'not needed in navigation'},source_content={'raw':'original'},
                    provenance={'name':'finance-easy','raw_record':{'large':'raw'}})
        put(source,data);put(self.case/'02-round/data.json',data)
        result=compact_preparation_case(self.case,'02-round')
        artifacts=result['artifacts'];sample=artifacts['00-data-preparation/01-select-input/01-input.json']
        self.assertEqual(sample['context'],'Value 2')
        self.assertEqual(sample['provenance'],{'name':'finance-easy'})
        self.assertNotIn('context_mapping',sample)
        self.assertEqual(artifacts['data.json'],{'reference_answer':'2'})

    def test_feedback_ref_resolves_same_case_and_checks_hash(self):
        target=self.case/'01-round/06-exception-handler/feedback/02-round/feedback.json'
        put(target,{'guidance':'Fix only the source span.'})
        good={'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
        foreign=self.prep/'test-0002/feedback.json';put(foreign,{'guidance':'Do not expose another case'})
        path='03-calculation/02-LLM-generate-code/01-input/feedback-ref.json'
        values=feedback_sources(self.case,{path:{'references':[good,{'path':str(foreign)}]}})[path]
        self.assertTrue(values[0]['hash_matches'])
        self.assertEqual(values[0]['content']['guidance'],'Fix only the source span.')
        self.assertEqual(values[1]['error'],'FEEDBACK_OUTSIDE_CASE')
        self.assertNotIn('content',values[1])

    def test_in_progress_retry_is_not_carried_as_completed_failure(self):
        (self.case/'02-round/run.json').unlink()
        with patch('finarch.dataset.viewer.reports.completion_report.evaluate',return_value=self.gate):
            r=snapshot(self.bundle)['preparation']
        self.assertEqual(r['rounds'][1]['state'],'RUNNING')
        self.assertEqual(r['rows'][0]['rounds'][1]['status'],'NOT_EVALUATED')
        self.assertEqual(r['rounds'][1]['attempted'],0)
