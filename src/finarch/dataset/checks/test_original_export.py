"""Original export conserves final Python/graphs and excludes final failures."""
import base64
import copy
import gzip
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from finarch.dataset.viewer.original_export import build, keep_final_artifact, final_generation_files
from finarch.dataset.viewer.evaluation_export import REQUIRED_VARIANTS
from finarch.dataset.viewer.server import generation_view


def unpack(html):
    text = html.decode()
    data = json.loads(re.search(r'<script id="data"[^>]*>(.*?)</script>',text,re.S)[1])
    details = {}
    for entry in data['original']['cases']:
        encoded = re.search(r'id="'+entry['blob']+r'">(.*?)</script>',text,re.S)[1]
        details[entry['case']] = json.loads(gzip.decompress(base64.b64decode(encoded)))
    return data, details


class OriginalExportTests(unittest.TestCase):
    def test_final_selection_preserves_code_graph_and_saved_decisions(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);bundle=root/'run';(bundle/'01-preparation').mkdir(parents=True)
            graph={'nodes':[{'id':'n1','value':2},{'id':'n2','inputs':['n1'],'value':4}]}
            code='answer = 2 * 2\n# literal </script> & stays intact\n'
            rows=[]
            for number,status in [(1,'PASS'),(2,'FAIL'),(3,'PASS')]:
                case=f'test-{number:04d}'
                rows.append({'path':str(bundle/'01-preparation'/case/'01-round'),
                    'case_path':str(bundle/'01-preparation'/case),'layout':'preparation-generation-v1',
                    'artifacts':{'run.json':{'status':status},'03-calculation/02-prepare-code/02-code.py':code,
                                 '04-graph/05-save-graph/01-graph.json':graph,
                                 '07-human-review/02-record-decision/decision.json':{'decision':'APPROVED'}},
                    'generation':{v+'/run.json':{'status':'FAIL' if number==3 and v==REQUIRED_VARIANTS[0] else 'PASS'} for v in REQUIRED_VARIANTS},
                    'generation_origins':{v:'03-round' for v in REQUIRED_VARIANTS},
                    'generation_snapshots':{v:'recorded' for v in REQUIRED_VARIANTS}})
            data={'batch':{'name':'run','round':'03-round','rounds':['01-round','03-round'],
                          'generation_overview':[{'case':f'test-{n:04d}','path':v+'/run.json','record':{'status':'PASS'}} for n in range(1,4) for v in REQUIRED_VARIANTS]},'runs':rows}
            with patch('finarch.dataset.viewer.server.batch_data',side_effect=lambda *a,**k:copy.deepcopy(data)):
                html,info=build(root,'run',{'case':'test-0001','lang':'ko'})
            payload,details=unpack(html)
            self.assertEqual(info['cases'],2);self.assertEqual(info['variants'],13)
            self.assertNotIn('test-0002',details)
            self.assertEqual(details['test-0001']['artifacts']['03-calculation/02-prepare-code/02-code.py'],code)
            self.assertEqual(details['test-0001']['artifacts']['04-graph/05-save-graph/01-graph.json'],graph)
            self.assertEqual(details['test-0001']['artifacts']['07-human-review/02-record-decision/decision.json']['decision'],'APPROVED')
            self.assertNotIn(REQUIRED_VARIANTS[0],details['test-0003']['generation_origins'])
            self.assertEqual(payload['batch']['rounds'],['03-round'])
            self.assertEqual(len(payload['batch']['generation_overview']),13)
            self.assertFalse(payload['live']);self.assertNotIn('evaluation',payload)
            self.assertIn('window.FINARCH_ORIGINAL=true',html.decode())
            self.assertIn('function renderPreparationGraph',html.decode())
            self.assertIn('function originalLoadCase',html.decode())
            self.assertIn('global.FinarchI18n =',html.decode())
            with self.assertRaises(ValueError):build(root,'../escape')

    def test_latest_failure_does_not_export_an_older_success(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for number,status in [('01-round','PASS'),('02-round','FAIL')]:
                folder=root/number/'test-0001'/REQUIRED_VARIANTS[0];folder.mkdir(parents=True)
                (folder/'run.json').write_text(json.dumps({'status':status}))
            other=root/'01-round'/'test-0001'/REQUIRED_VARIANTS[1];other.mkdir(parents=True)
            (other/'run.json').write_text('{"status":"PASS"}')
            (other/'02-generate-text').mkdir();(other/'02-generate-text/04-observation.json').write_text('{"context":"final"}')
            result=generation_view(root,['01-round','02-round'],'02-round','test-0001',final_only=True,artifact_filter=keep_final_artifact)
            self.assertNotIn(REQUIRED_VARIANTS[0],result['generation_origins'])
            self.assertEqual(result['generation_origins'][REQUIRED_VARIANTS[1]],'01-round')
            self.assertEqual(result['generation'][REQUIRED_VARIANTS[1]+'/02-generate-text/04-observation.json']['context'],'final')

    def test_final_file_projection_keeps_python_graphs_without_retry_history(self):
        for path in ('03-calculation/02-prepare-code/02-code.py','04-graph/05-save-graph/01-graph.json',
                     '01-perturbation/02-graph.json','01-perturbation/03-result.json',
                     '05-human-review/02-record-decision/decision.json'):
            self.assertTrue(keep_final_artifact(path),path)
        for path in ('03-calculation/stage-history/old.json','logs/calls.jsonl','02-generate-text/02-raw-response.json'):
            self.assertFalse(keep_final_artifact(path),path)

    def test_only_current_inverse_annotation_and_its_evidence_are_kept(self):
        variant=REQUIRED_VARIANTS[-1];base=variant+'/03-validation/07-ea-inverse-review/'
        report='03-validation/07-ea-inverse-review/attempt-002/03-result/inverse-review.json'
        qc='03-validation/07-ea-inverse-review/attempt-002/01-input/qc.json'
        display='03-validation/07-ea-inverse-review/attempt-002/03-result/evidence-display-check.json'
        files={variant+'/run.json':{'inverse_review_ref':{'path':report}},
               base+'latest.ref.json':{'path':report},variant+'/'+report:{'request_ref':qc,'evidence_display_check_ref':display},
               variant+'/'+qc:{'question':'Q','context':'C'},variant+'/'+display:{'status':'PASS'},
               base+'attempt-001/03-result/inverse-review.json':{'status':'CALL_FAILED'},
               base+'attempt-001/01-input/qc.json':{'question':'old'}}
        result=final_generation_files(files,[variant])
        self.assertEqual(len(result),5)
        self.assertNotIn(base+'attempt-001/03-result/inverse-review.json',result)
        self.assertTrue(keep_final_artifact(qc))
        self.assertTrue(keep_final_artifact(report))


if __name__=='__main__':unittest.main()
