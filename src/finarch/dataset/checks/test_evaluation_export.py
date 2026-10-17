"""Portable snapshot checks, with no model calls or production writes."""
import base64
import gzip
import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from finarch.dataset.viewer.evaluation_export import build, keep_artifact, inline_json, eligible_record, eligible_case, REQUIRED_VARIANTS, SELECTION_POLICY

class EvaluationExportTests(unittest.TestCase):
    def test_automatic_pass_does_not_require_accept_but_excludes_reject(self):
        with TemporaryDirectory() as directory:
            folder=Path(directory)
            for decision in (None,'PENDING','APPROVED','REJECT','REJECTED','EXCLUDE','EXCLUDED'):
                state={'status':'PASS','human_decision':decision}
                self.assertEqual(eligible_record(folder,'generation',state),decision not in {'REJECT','REJECTED','EXCLUDE','EXCLUDED'})
            for status in ('FAIL','NOT_EVALUATED','NOT_RUN','INCOMPLETE'):
                self.assertFalse(eligible_record(folder,'generation',{'status':status,'human_decision':'APPROVED'}))
            review=folder/'05-human-review/02-record-decision/decision.json'
            review.parent.mkdir(parents=True);review.write_text('{"decision":"REJECTED"}')
            self.assertFalse(eligible_record(folder,'generation',{'status':'PASS'}))

    def test_export_requires_complete_seven_type_group(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);bundle=root/'named-merge';(bundle/'01-preparation').mkdir(parents=True)
            rows=[];overview=[]
            for number in range(1,8):
                case=f'test-{number:04d}';folder=bundle/'01-preparation'/case/'01-round';folder.mkdir(parents=True)
                generation={key+'/run.json':{'status':'PASS','human_decision':'PENDING'} for key in REQUIRED_VARIANTS}
                origins={key:'01-round' for key in REQUIRED_VARIANTS}
                if number==2:generation[REQUIRED_VARIANTS[0]+'/run.json']['status']='FAIL'
                if number==3:generation[REQUIRED_VARIANTS[0]+'/run.json']['status']='NOT_EVALUATED'
                if number==4:origins.pop(REQUIRED_VARIANTS[0])
                if number==5:generation[REQUIRED_VARIANTS[0]+'/run.json']['human_decision']='REJECTED'
                if number in (6,7):
                    review=(folder/'07-human-review/02-record-decision/decision.json' if number==6 else bundle/'02-generation/01-round'/case/REQUIRED_VARIANTS[-1]/'05-human-review/02-record-decision/decision.json')
                    review.parent.mkdir(parents=True);review.write_text('{"decision":"REJECTED"}')
                rows.append({'path':str(folder),'case_path':str(folder.parent),'artifacts':{'run.json':{'status':'PASS'}},'generation':generation,'generation_origins':origins,'generation_snapshots':{key:'hash' for key in origins}})
                overview.extend({'case':case,'path':key,'record':state} for key,state in generation.items())
                self.assertEqual(eligible_case(bundle,case,rows[-1]),number==1)
            data={'batch':{'name':'named-merge','round':'01-round','generation_overview':overview},'runs':rows}
            with patch('finarch.dataset.viewer.server.batch_data',return_value=data):html,info=build(root,[{'name':'named-merge'}])
            text=html.decode();payload=json.loads(re.search(r'<script id="data"[^>]*>(.*?)</script>',text,re.S)[1])
            batch=payload['evaluation']['batches'][0]
            self.assertEqual(info['cases'],1)
            self.assertEqual(batch['cases'][0]['case'],'test-0001')
            self.assertEqual(batch['cases'][0]['variants'],list(REQUIRED_VARIANTS))
            self.assertEqual(payload['evaluation']['selection_policy'],SELECTION_POLICY)
            blob=re.search(r'type="application/octet-stream"[^>]*>(.*?)</script>',text,re.S)[1]
            exported=json.loads(gzip.decompress(base64.b64decode(blob)))
            self.assertEqual(set(exported['generation_origins']),set(REQUIRED_VARIANTS))
            self.assertEqual(len(exported['generation']),7)
            self.assertEqual(len(batch['batch']['generation_overview']),7)
            data['runs']=rows[1:]
            with patch('finarch.dataset.viewer.server.batch_data',return_value=data),self.assertRaisesRegex(ValueError,'7\uc720\ud615'):
                build(root,[{'name':'named-merge'}])

    def test_projected_evidence_and_no_call_history(self):
        for path in ['03-calculation/02-prepare-code/03-program.json','02-generate-text/01-input.json','04-graph/05-save-graph/01-graph.json','data-comparison.json']:
            self.assertTrue(keep_artifact(path),path)
        for path in ['02-review/stage-history/03-result.json','03-calculation/01-request/03-result.json','07-human-review/02-record-decision/decision.json','02-generate-text/02-raw-response.json']:
            self.assertFalse(keep_artifact(path),path)

    def test_inline_json_cannot_close_script(self):
        value={'comment':'</script><script>alert(1)</script>&\u2028'}
        serialized=inline_json(value)
        self.assertNotIn('<',serialized)
        self.assertEqual(json.loads(serialized),value)

    def test_snapshot_round_cases_and_decision_isolation(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'20260917-002'/'01-preparation').mkdir(parents=True)
            summary={'path':'test-0001','case_path':'test-0001','summary_only':True,'artifacts':{},'decisions':{'ANSWER':'old'}}
            detail={'path':'test-0001','case_path':'test-0001','artifacts':{'run.json':{'status':'PASS'}},'generation_origins':{key:'03-round' for key in REQUIRED_VARIANTS},'generation':{key+'/run.json':{'status':'PASS'} for key in REQUIRED_VARIANTS},'list_entry':summary}
            data={'batch':{'name':'20260917-002','round':'03-round','generation_overview':[]},'runs':[detail]}
            with patch('finarch.dataset.viewer.server.batch_data',return_value=data):
                html,info=build(root,[{'name':'20260917-002','cases':['test-0001']}],initial_view={'lang':'en'})
            text=html.decode();payload=json.loads(re.search(r'<script id="data"[^>]*>(.*?)</script>',text,re.S)[1])
            compressed=re.search(r'type="application/octet-stream"[^>]*>(.*?)</script>',text,re.S)[1]
            case=json.loads(gzip.decompress(base64.b64decode(compressed)))
            self.assertEqual(case['decisions'],{})
            self.assertEqual(payload['runs'][0]['decisions'],{})
            self.assertEqual(payload['batch']['rounds'],['03-round'])
            self.assertFalse(payload['live']);self.assertIn('window.FINARCH_EVALUATION=true',text)
            self.assertEqual(payload['evaluation']['initial_view']['lang'],'en')
            self.assertIn('global.FinarchI18n =',text)
            self.assertIn('viewer-language button',text)
            self.assertNotIn('src="/i18n.js"',text)
            self.assertEqual(info['cases'],1)
            with self.assertRaises(ValueError):build(root,[{'name':'../escape'}])

if __name__=='__main__':unittest.main()
