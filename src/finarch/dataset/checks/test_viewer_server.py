"""Central viewer reads current records without writing per-run views."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from urllib.error import HTTPError
from finarch.dataset.viewer.server import list_batches, batch_data, handler_for, generation_overview


class CentralViewerChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'run';self.root.mkdir()
        self.batch=self.root/'first';self.case=self.batch/'case';self.case.mkdir(parents=True)
        (self.case/'events.jsonl').write_text('{"phase":"START"}\n')
        (self.batch/'README.md').write_text('실행 안내')

    def test_generation_overview_reads_saved_annotation(self):
        generation=self.batch/'02-generation';folder=generation/'01-round/test-1/01-ic-value-before'
        review=folder/'04-human-review/02-record-decision';review.mkdir(parents=True)
        (review/'decision.json').write_text('{"decision":"APPROVED"}')
        (generation/'01-round/progress.json').write_text(json.dumps({'cases':{'test-1':{'IC_VALUE':{'status':'PASS','path':str(folder.relative_to(self.batch))}}}}))
        rows=generation_overview(generation,['01-round'],'01-round')
        self.assertEqual(rows[0]['review']['decision'],'APPROVED')
        self.assertEqual(rows[0]['record']['status'],'PASS')

    def test_new_batches_and_changed_artifacts_are_read_without_html(self):
        self.assertEqual([r['name'] for r in list_batches(self.root)],['first'])
        before=batch_data(self.root,'first')
        self.assertEqual(before['runs'][0]['artifacts']['run.json']['status'],'INCOMPLETE')
        (self.case/'run.json').write_text('{"status":"FAIL","reason":"provider rejected"}')
        (self.root/'second/case').mkdir(parents=True)
        (self.root/'second/case/events.jsonl').write_text('{"phase":"START"}\n')
        after=batch_data(self.root,'first')
        self.assertNotEqual(before['revision'],after['revision'])
        self.assertEqual(after['runs'][0]['artifacts']['run.json']['status'],'FAIL')
        self.assertEqual(len(list_batches(self.root)),2)
        self.assertEqual(list(self.root.rglob('*.html')),[])

    def test_dataset_selector_excludes_reports_and_sorts_run_names(self):
        report=self.root/'20261004-report';report.mkdir()
        (report/'documentation.json').write_text('{}')
        (report/'run.json').write_text('{}')
        for name in ('20261002-001','20261003-concat-001'):
            dataset=self.root/name/'results';dataset.mkdir(parents=True)
            (dataset/'00-input.json').write_text('[]')
        self.assertEqual([r['name'] for r in list_batches(self.root)],
                         ['first','20261003-concat-001','20261002-001'])

    def test_evaluator_export_uses_preparation_data_not_run_name(self):
        names=('20260917-002','20261003-concat-001','20261003-001-CodeTAT-QA-0917-002')
        for name in names:
            (self.root/name/'01-preparation').mkdir(parents=True)
        results=self.root/'20261003-results-only/results';results.mkdir(parents=True)
        (results/'00-input.json').write_text('[]')
        batches={row['name']:row for row in list_batches(self.root)}
        for name in names:
            self.assertTrue(batches[name]['evaluation_exportable'],name)
        self.assertFalse(batches['first']['evaluation_exportable'])
        self.assertFalse(batches['20261003-results-only']['evaluation_exportable'])

    def test_invalid_paths_and_symlinks_do_not_expose_outside_data(self):
        outside=Path(self.temp.name)/'outside';outside.mkdir()
        (outside/'run.json').write_text('{"secret":"outside"}')
        (self.root/'link').symlink_to(outside,target_is_directory=True)
        (self.case/'leak.json').symlink_to(outside/'run.json')
        for name in ['..','../outside','link','missing']:
            with self.assertRaises(ValueError):batch_data(self.root,name)
        self.assertNotIn('leak.json',batch_data(self.root,'first')['runs'][0]['artifacts'])

    def test_removed_directories_disappear_from_live_api(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.root))
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}/api/runs'
            def names():
                with urlopen(url) as reply:
                    self.assertEqual(reply.headers['Cache-Control'],'no-store')
                    return [r['name'] for r in json.load(reply)]
            self.assertEqual(names(),['first'])
            moved=Path(self.temp.name)/'removed'
            self.batch.rename(moved)
            self.assertEqual(names(),[])
            moved.rename(self.root/'renamed')
            self.assertEqual(names(),['renamed'])
        finally:server.shutdown();server.server_close();worker.join()

    def test_partially_written_summary_is_reported_without_hiding_cases(self):
        (self.batch/'summary.json').write_text('{')
        payload=batch_data(self.root,'first')
        self.assertIn('read_error',payload['batch']['summary'])
        self.assertEqual(len(payload['runs']),1)

    def test_http_serves_one_viewer_and_readonly_batch_routes(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.root))
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            with urlopen(url) as reply:
                self.assertIn('"live":true',reply.read().decode())
            with urlopen(url+'/api/run?name=first') as reply:
                self.assertEqual(json.load(reply)['batch']['readme'],'실행 안내')
            with urlopen(url+'/contract') as reply:
                self.assertIn('응답 schema ↔ prompt 대조',reply.read().decode())
            with urlopen(url+'/api/experiment-contract') as reply:
                contract=json.load(reply)
                self.assertEqual(contract['title'],'FinancialAnswerV7')
                self.assertIn('"answer_meta"',contract['files']['schema']['text'])
                self.assertIn('answer_format.decimal_places',contract['files']['common']['text'])
                self.assertIn('`classification`',contract['files']['guided']['text'])
                self.assertIn('"classification"',contract['files']['schema']['text'])
                for name in ('common','unguided','guided'):
                    prompt=contract['files'][name]
                    translation=prompt['translation']
                    self.assertEqual(translation['status'],'AVAILABLE')
                    self.assertEqual(translation['source_sha256'],prompt['sha256'])
                    self.assertEqual(len(translation['text'].splitlines()),len(prompt['text'].splitlines()))
            with self.assertRaises(HTTPError) as error:urlopen(url+'/api/experiment-contract?source=../../private')
            self.assertEqual(error.exception.code,404)
            error.exception.close()
            for axis in ('IC_VALUE','IC_SOURCE','IC_RELATION','EA'):
                with urlopen(url+'/api/realization-prompt?axis='+axis) as reply:
                    prompt=json.load(reply)
                    self.assertEqual(prompt['axis'],axis)
                    self.assertEqual(len(prompt['parts']),2)
                    self.assertIn('not a saved model call',prompt['scope'])
            for axis in ('ANSWER','IC_VALUE','IC_SOURCE','IC_RELATION','EA'):
                with urlopen(url+'/api/audit-prompt?axis='+axis) as reply:
                    prompt=json.load(reply)
                    self.assertEqual(prompt['axis'],axis)
                    self.assertEqual(prompt['id'],'dtt.audit.'+axis.lower())
                    self.assertIn('not a saved model call',prompt['scope'])
            for route in ['/api/run?name=..','/AGENTS.md','/reports/run/first/README.md']:
                with self.assertRaises(HTTPError) as error:urlopen(url+route)
                self.assertEqual(error.exception.code,404)
                error.exception.close()
            with self.assertRaises(HTTPError) as error:urlopen(url+'/api/realization-prompt?axis=../ea')
            self.assertEqual(error.exception.code,404)
            error.exception.close()
            with self.assertRaises(HTTPError) as error:urlopen(url+'/api/audit-prompt?axis=../ea')
            self.assertEqual(error.exception.code,404)
            error.exception.close()
        finally:server.shutdown();server.server_close();worker.join()

    def test_korean_review_translations_cover_saved_v6_prompt_versions(self):
        from finarch.experiments.viewer.contract_view import read_contract
        from finarch.dataset.viewer.server import PROJECT
        for source in ('current','20260923-exp-001','20260923-exp-006','20260926-exp-001'):
            with self.subTest(source=source):
                files=read_contract(PROJECT,source)['files']
                for name in ('common','unguided','guided'):
                    english=files[name]
                    korean=english['translation']
                    self.assertEqual(korean['status'],'AVAILABLE')
                    self.assertEqual(korean['source_sha256'],english['sha256'])
                    self.assertEqual(len(korean['text'].splitlines()),len(english['text'].splitlines()))
