"""Annotation repairs, agreement, scope and persistence without model calls."""
from copy import deepcopy
from fractions import Fraction
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from finarch.dataset.viewer.annotation.normalize import normalize, parse_export, TYPES
from finarch.dataset.viewer.annotation.agreement import build_view, kappa, align_scopes
from finarch.dataset.viewer.annotation.store import refresh, view, upload, file_data, g02_links
from finarch.dataset.viewer.annotation.sources import attach_sources, source_kind
from finarch.dataset.viewer.annotation.links import case_links
from finarch.dataset.viewer.server import handler_for


def legacy(name='Reviewer A', decision='accept', **overrides):
    row={'id':'test-0001','type':TYPES[0][0],'label':TYPES[0][1],
         'annotator':'','decision':decision,'note':'Original note','timestamp':'2026-10-01T00:00:00Z',
         'inserted':'A saved claim, [unchanged].','removed':''}
    row.update(overrides)
    return {'annotator':name,'exported_at':'2026-10-01T00:00:00Z','n':1,'labels':[row]}


def document(payload, ident='a'):
    return {'id':ident,'filename':ident+'.json',**normalize(json.dumps(payload))}


class NormalizationChecks(unittest.TestCase):
    def test_legacy_repairs_reviewer_but_preserves_decision_note_and_evidence(self):
        payload=legacy(); before=deepcopy(payload); result=normalize(json.dumps(payload))
        self.assertEqual(payload,before)
        self.assertEqual(result['repaired']['labels'][0],{**payload['labels'][0],'annotator':'Reviewer A'})
        self.assertEqual(result['evaluations'][0]['decision'],'APPROVED')
        self.assertEqual(result['evaluations'][0]['comment'],'Original note')
        self.assertEqual(result['changes'][0]['rule'],'FILL_HEADER_ANNOTATOR')
        self.assertIsNone(result['run']);self.assertIsNone(result['package_id'])

    def test_json_repairs_do_not_change_punctuation_inside_strings(self):
        payload=legacy(note='Note \\" and comma, ] and comma, }')
        raw=json.dumps(payload); raw=raw[:-1]+',}'
        value,changes=parse_export('\ufeff```json\n'+raw+'\n```')
        self.assertEqual(value,payload)
        self.assertEqual([change['rule'] for change in changes],['REMOVE_UTF8_BOM','REMOVE_JSON_FENCE','REMOVE_TRAILING_COMMAS'])

    def test_duplicate_json_keys_and_nonfinite_values_are_not_silently_selected(self):
        for raw in ('{"annotator":"A","annotator":"B"}','{"n":NaN}'):
            with self.assertRaises(ValueError):parse_export(raw)

    def test_unknown_and_duplicate_judgments_remain_visible_and_excluded(self):
        payload=legacy(decision='unknown');payload['labels']*=2
        result=document(payload)
        self.assertIn('UNKNOWN_DECISION',result['evaluations'][0]['issues'])
        self.assertIn('DUPLICATE_RECORD',result['evaluations'][0]['issues'])
        self.assertEqual(result['repaired']['labels'][0]['decision'],'unknown')
        group=build_view([result,document(legacy(name='B'),'b')])[0]
        self.assertIn('FORMAT',group['cases'][0]['rows'][0]['flags'])
        self.assertEqual(group['metrics'][0]['included'],0)

    def test_current_html_export_and_draft_save_flags(self):
        payload={'format':'finarch-evaluation-results-v1','reviewer':'A','run':'run-1','round':'03-round',
                 'package_id':'hash','kind':'draft','cases':['test-0001'],
                 'evaluations':[{'case':'test-0001','variant':TYPES[0][0],'decision':'REJECTED',
                                 'comment':'Exact note','confirmed':False,'checklist':{}}]}
        result=normalize(json.dumps(payload))
        self.assertFalse(result['evaluations'][0]['confirmed']);self.assertEqual(result['changes'],[])
        payload['evaluations'][0]['confirmed']='false'
        self.assertFalse(normalize(json.dumps(payload))['evaluations'][0]['confirmed'])
        del payload['evaluations'][0]['confirmed']
        self.assertFalse(normalize(json.dumps(payload))['evaluations'][0]['confirmed'])
        payload['kind']='final'
        result=normalize(json.dumps(payload))
        self.assertFalse(result['evaluations'][0]['confirmed'])
        self.assertIn('MISSING_CONFIRMED',result['evaluations'][0]['issues'])

    def test_malformed_row_identifiers_are_reported_without_losing_other_rows(self):
        payload=legacy();payload['labels'].append({'id':{},'type':[],'decision':'accept','note':'preserve'})
        result=normalize(json.dumps(payload))
        self.assertEqual(len(result['evaluations']),2)
        self.assertIn('INVALID_CASE',result['evaluations'][1]['issues'])
        self.assertIn('UNKNOWN_VARIANT',result['evaluations'][1]['issues'])

    def test_known_old_ea_labels_follow_the_type_path_without_changing_content(self):
        for variant,old_label,new_label in [('06-ea-earlier-input','EA_02','EA_01'),('07-ea-later-input','EA_03','EA_02')]:
            payload=legacy(type=variant,label=old_label)
            result=normalize(json.dumps(payload))
            self.assertEqual(result['repaired']['labels'][0]['label'],new_label)
            self.assertEqual(result['repaired']['labels'][0]['inserted'],payload['labels'][0]['inserted'])
            self.assertEqual(result['issues'],[])
        result=normalize(json.dumps(legacy(type='06-ea-earlier-input',label='EA_03')))
        self.assertIn('TYPE_LABEL_MISMATCH',result['evaluations'][0]['issues'])


class AgreementChecks(unittest.TestCase):
    def test_explicit_legacy_run_pairs_with_one_native_package(self):
        labels=legacy();labels.update(run='r1',dataset='tatqa-dev')
        native={'format':'finarch-evaluation-results-v1','reviewer':'B','run':'r1','round':'03-round',
                'package_id':'p1','cases':['test-0001'],
                'evaluations':[{'case':'test-0001','variant':TYPES[0][0],'decision':'REJECTED','confirmed':True,'comment':''}]}
        a,b=document(labels),document(native,'b'); bound=align_scopes([a,b]); groups=build_view(bound)
        self.assertEqual(len(groups),1);self.assertEqual(groups[0]['reviewers'],['Reviewer A','B'])
        self.assertEqual(groups[0]['metrics'][0]['included'],1)
        self.assertIn('DISAGREE',groups[0]['cases'][0]['flags'])
        self.assertEqual(groups[0]['id'],build_view([b])[0]['id'])
        self.assertEqual(build_view([bound[0]])[0]['id'],groups[0]['id'])
        self.assertEqual(a['repaired'],normalize(json.dumps(labels))['repaired'])

    def test_legacy_run_does_not_bind_an_ambiguous_package_or_another_run(self):
        native={'format':'finarch-evaluation-results-v1','reviewer':'B','run':'r1','round':'03-round',
                'package_id':'p1','cases':['test-0001'],
                'evaluations':[{'case':'test-0001','variant':TYPES[0][0],'decision':'APPROVED','confirmed':True,'comment':''}]}
        labels=legacy();labels.update(run='r1',dataset='tatqa-dev')
        a=document(labels); b=document(native,'b')
        other=deepcopy(native);other['package_id']='p2';c=document(other,'c')
        self.assertEqual(len(build_view([a,b,c])),3)
        different=legacy();different['run']='different'
        self.assertEqual(len(build_view([document(different),b])),2)
        self.assertEqual(len(build_view([document(legacy()),b])),2)

    def test_cohen_uses_separate_rater_marginals_and_can_be_negative(self):
        a,b= 'APPROVED','REJECTED'
        metric=kappa([[a,a],[a,b],[a,b],[b,b]],4)
        self.assertAlmostEqual(metric['kappa'],float(Fraction(1,5)))
        self.assertEqual(metric['method'],'Cohen');self.assertEqual(metric['agreement'],.5)
        self.assertEqual(kappa([[a,b],[b,a]],2)['kappa'],-1)

    def test_fleiss_three_raters_matches_count_table(self):
        a,b='APPROVED','REJECTED'
        # Two unanimous rows and two 2:1 splits: Po=2/3, Pe=1/2, kappa=1/3.
        metric=kappa([[a,a,a],[b,b,b],[a,a,b],[b,b,a]],4)
        self.assertEqual(metric['method'],'Fleiss');self.assertAlmostEqual(metric['kappa'],1/3)
        self.assertAlmostEqual(metric['agreement'],2/3);self.assertEqual(metric['unanimous'],.5)

    def test_missing_and_unconfirmed_are_not_pending_or_pass(self):
        left=document(legacy());right=document(legacy(name='B'),'b')
        right['evaluations'][0]['confirmed']=False
        group=build_view([left,right])[0]
        self.assertEqual(group['metrics'][0]['included'],0);self.assertEqual(group['metrics'][0]['excluded'],1)
        self.assertIn('MISSING',group['cases'][0]['rows'][0]['flags'])
        self.assertIsNone(group['metrics'][0]['kappa'])
        right['evaluations'][0]['confirmed']=True;right['evaluations'][0]['decision']='PENDING'
        group=build_view([left,right])[0]
        self.assertEqual(group['metrics'][0]['included'],1)
        self.assertIn('PENDING',group['cases'][0]['rows'][0]['flags'])

    def test_single_category_has_perfect_observed_agreement_and_undefined_kappa(self):
        metric=kappa([['APPROVED','APPROVED']],1)
        self.assertEqual(metric['agreement'],1);self.assertIsNone(metric['kappa']);self.assertIsNotNone(metric['reason'])

    def test_content_changes_and_reviewer_file_conflicts_exclude_the_item(self):
        left=document(legacy());right=document(legacy(name='B',inserted='A different claim.'),'b')
        group=build_view([left,right])[0]
        self.assertIn('CONTENT',group['cases'][0]['rows'][0]['flags']);self.assertEqual(group['metrics'][0]['included'],0)
        right=document(legacy(name='B'),'b');duplicate=document(legacy(decision='reject'),'c')
        group=build_view([left,right,duplicate])[0]
        self.assertEqual(len(group['reviewers']),2)
        self.assertIn('CONFLICTING_REVIEWER_FILES',group['cases'][0]['rows'][0]['cells']['Reviewer A']['issues'])
        self.assertEqual(group['metrics'][0]['included'],0)
        duplicate=document(legacy(),'c');self.assertEqual(build_view([left,right,duplicate])[0]['metrics'][0]['included'],1)

    def test_scopes_do_not_mix_packages_rounds_runs_or_legacy_exports(self):
        payload={'format':'finarch-evaluation-results-v1','reviewer':'A','run':'r1','round':'01-round','package_id':'p1','cases':['test-0001'],
                 'evaluations':[{'case':'test-0001','variant':TYPES[0][0],'decision':'APPROVED','confirmed':True,'comment':''}]}
        docs=[document(payload)]
        for index,key in enumerate(('run','round','package_id')):
            variant=deepcopy(payload);variant[key]='different';variant['reviewer']='B';docs.append(document(variant,str(index)))
        docs.append(document(legacy(),'legacy'))
        self.assertEqual(len(build_view(docs)),5)


class SourceChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.runs=Path(self.temp.name)/'reports/run';self.runs.mkdir(parents=True)

    def catalog(self, run, source_id, edit='A saved claim, [unchanged].'):
        bundle=self.runs/run;results=bundle/'results';results.mkdir(parents=True,exist_ok=True)
        raw=json.dumps([{'id':'test-0001','input':{'provenance':{'source_id':source_id}}}]).encode()
        (results/'00-input.json').write_bytes(raw)
        (results/'manifest.json').write_text(json.dumps({'files':{'00-input.json':{'sha256':hashlib.sha256(raw).hexdigest()}}}))
        path=bundle/'02-generation/01-round/test-0001'/TYPES[0][0]/'02-generate-text/05-patches.json'
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps([{'text':edit,'before':''}]))
        return bundle

    def test_source_families_use_the_saved_origin_including_direct_tatqa(self):
        for prefix,kind in [('CodeFinQA-','FinQA'),('CodeTAT-QA-','TAT-QA'),('FinanceMath-','FinanceMath'),('FinanceReasoning-','FinanceReasoning')]:
            self.assertEqual(source_kind({'source_id':prefix+'test-1'}),kind)
        self.assertEqual(source_kind({'dataset':'TAT-QA','document_id':'saved-document'}),'TAT-QA')
        self.assertEqual(source_kind({'source_id':'unknown-test-1'}),'UNKNOWN')

    def test_reused_case_id_is_bound_by_exact_edits_without_inventing_annotation_scope(self):
        self.catalog('run-a','CodeFinQA-test-1')
        self.catalog('run-b','CodeTAT-QA-test-1','A different saved claim.')
        groups=attach_sources(build_view([document(legacy())]),self.runs)
        item=groups[0]['cases'][0]
        self.assertEqual(item['source_type'],'FinQA');self.assertIsNone(groups[0]['run'])
        self.assertEqual(item['source_reference']['method'],'EXACT_SAVED_EDIT')
        self.assertEqual(item['source_reference']['run'],'run-a')
        unmatched=attach_sources(build_view([document(legacy(inserted='No saved matching edit.'))]),self.runs)
        self.assertEqual(unmatched[0]['cases'][0]['source_type'],'UNKNOWN')

    def test_ambiguous_matches_and_failed_catalog_hash_do_not_assign_an_origin(self):
        self.catalog('run-a','CodeFinQA-test-1')
        second=self.catalog('run-b','CodeTAT-QA-test-1')
        groups=attach_sources(build_view([document(legacy())]),self.runs)
        self.assertEqual(groups[0]['cases'][0]['source_type'],'UNKNOWN')
        (second/'results/manifest.json').write_text(json.dumps({'files':{'00-input.json':{'sha256':'wrong'}}}))
        groups=attach_sources(build_view([document(legacy())]),self.runs)
        self.assertEqual(groups[0]['cases'][0]['source_type'],'FinQA')
        self.assertEqual(groups[0]['source_types'],[{'value':'FinQA','label':'FinQA','count':1}])

    def test_explicit_run_and_round_use_their_own_saved_source(self):
        self.catalog('different-run','CodeFinQA-test-1')
        path=self.runs/'requested-run/01-preparation/test-0001/01-round/data.json'
        path.parent.mkdir(parents=True);path.write_text(json.dumps({'provenance':{'source_id':'FinanceMath-validation-1'}}))
        groups=build_view([document(legacy())]);groups[0].update(run='requested-run',round='01-round')
        groups=attach_sources(groups,self.runs)
        self.assertEqual(groups[0]['cases'][0]['source_type'],'FinanceMath')
        self.assertEqual(groups[0]['cases'][0]['source_reference']['method'],'EXPLICIT_RUN_ROUND')


class G02Checks(unittest.TestCase):
    setUp = SourceChecks.setUp
    catalog = SourceChecks.catalog

    def generation(self, bundle, round_name, variant, patches, context, input_context=None):
        (bundle/'01-preparation/test-0001/01-round').mkdir(parents=True,exist_ok=True)
        stage=bundle/'02-generation'/round_name/'test-0001'/variant/'02-generate-text'
        stage.mkdir(parents=True,exist_ok=True)
        (stage/'05-patches.json').write_text(json.dumps(patches))
        (stage/'04-observation.json').write_text(json.dumps({'context':context,'question':'Saved question?'}))
        if input_context is not None:
            (stage/'01-input.json').write_text(json.dumps({'context':input_context}))
        return stage

    def links(self, payload, **scope):
        groups=build_view([document(payload)]);groups[0].update(scope)
        attach_sources(groups,self.runs)
        return case_links(groups,self.runs,groups[0]['id'],'test-0001')['links']

    def test_each_variant_uses_its_matching_round_and_full_context(self):
        bundle=self.catalog('run-a','CodeFinQA-test-1')
        value_patch=[{'text':'A saved claim, [unchanged].','before':''}]
        self.generation(bundle,'01-round',TYPES[0][0],value_patch,'Original. A saved claim, [unchanged].')
        self.generation(bundle,'03-round',TYPES[0][0],[{'text':'Later claim.','before':''}],'Original. Later claim.')
        ea_variant=TYPES[5][0];self.generation(bundle,'02-round',ea_variant,[{'text':'Replacement.','before':'Old text.'}],'Replacement.')
        payload=legacy();payload['labels'].append(legacy(type=ea_variant,label=TYPES[5][1],inserted='Replacement.',removed='Old text.')['labels'][0])
        links=self.links(payload)
        self.assertEqual(links[TYPES[0][0]]['origin_round'],'01-round')
        self.assertEqual(links[ea_variant]['origin_round'],'02-round')
        self.assertIn('stage=02-generate-text',links[ea_variant]['href'])
        self.assertTrue(links[ea_variant]['href'].endswith('#g02-full-context'))
        self.assertIn('variant='+ea_variant,links[ea_variant]['href'])
        self.assertEqual(links[TYPES[6][0]]['status'],'UNAVAILABLE')

    def test_source_links_compose_value_and_attribution_and_verify_saved_context(self):
        bundle=self.catalog('run-a','CodeFinQA-test-1','Conflict. ')
        original='Original statement.';front='Conflict. ';back=' Conflict.'
        self.generation(bundle,'01-round',TYPES[0][0],[{'start':0,'end':0,'text':front,'before':''}],front+original)
        self.generation(bundle,'01-round',TYPES[1][0],[{'start':len(original),'end':len(original),'text':back,'before':''}],original+back)
        source=' (source A)';position=len(front+original)
        self.generation(bundle,'02-round',TYPES[2][0],[{'start':position,'end':position,'text':source,'before':''}],front+original+source,front+original)
        position=len(original+back)-1;source_b=' (source B)';combined=back[:-1]+source_b+'.'
        stage=self.generation(bundle,'02-round',TYPES[3][0],[{'start':position,'end':position,'text':source_b,'before':''}],original+combined,original+back)
        payload=legacy(inserted=front)
        for index,text in [(2,front+' || '+source),(3,combined)]:
            payload['labels'].append(legacy(type=TYPES[index][0],label=TYPES[index][1],inserted=text)['labels'][0])
        links=self.links(payload)
        for variant in (TYPES[2][0],TYPES[3][0]):
            self.assertEqual(links[variant]['method'],'EXACT_COMBINED_INSERTIONS')
            self.assertEqual(links[variant]['origin_round'],'02-round')
        (stage/'04-observation.json').write_text(json.dumps({'context':'Unexpected changed context.'}))
        self.assertEqual(self.links(payload)[TYPES[3][0]]['status'],'UNAVAILABLE')

    def test_explicit_round_carries_prior_output_but_does_not_use_future_or_unknown_round(self):
        bundle=self.catalog('run-a','CodeFinQA-test-1')
        self.generation(bundle,'01-round',TYPES[0][0],[{'text':'Saved.','before':''}],'Round one context.')
        self.generation(bundle,'02-round',TYPES[1][0],[{'text':'Other.','before':''}],'Other context.')
        self.generation(bundle,'03-round',TYPES[0][0],[{'text':'Future.','before':''}],'Future context.')
        links=self.links(legacy(),run='run-a',round='02-round')
        self.assertEqual(links[TYPES[0][0]]['round'],'02-round')
        self.assertEqual(links[TYPES[0][0]]['origin_round'],'01-round')
        self.assertEqual(self.links(legacy(),run='run-a',round='99-round')[TYPES[0][0]]['status'],'UNAVAILABLE')

    def test_identical_edits_in_different_full_contexts_do_not_pick_a_run(self):
        for run,context in [('run-a','First full context.'),('run-b','Different full context.')]:
            bundle=self.catalog(run,'CodeFinQA-test-1')
            self.generation(bundle,'01-round',TYPES[0][0],[{'text':'A saved claim, [unchanged].','before':''}],context)
        self.assertEqual(self.links(legacy())[TYPES[0][0]]['status'],'UNAVAILABLE')
        self.assertEqual(self.links(legacy(inserted='Unmatched.'))[TYPES[0][0]]['status'],'UNAVAILABLE')

    def test_latest_explicit_variant_without_a_full_context_does_not_fall_back(self):
        bundle=self.catalog('run-a','CodeFinQA-test-1')
        self.generation(bundle,'01-round',TYPES[0][0],[{'text':'Saved.','before':''}],'Full context.')
        (bundle/'02-generation/02-round/test-0001'/TYPES[0][0]).mkdir(parents=True)
        self.assertEqual(self.links(legacy(),run='run-a',round='02-round')[TYPES[0][0]]['status'],'UNAVAILABLE')


class StoreChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'annotation';self.folder=self.root/'20261001';self.folder.mkdir(parents=True)
        self.source=self.folder/'original.json';self.source.write_text(json.dumps(legacy()))

    def test_refresh_preserves_original_and_writes_repaired_export_log_readme_and_summary(self):
        raw=self.source.read_bytes();result=refresh(self.root,'20261001');ident=result['files'][0]['id']
        self.assertEqual(self.source.read_bytes(),raw)
        self.assertEqual(ident,hashlib.sha256(raw).hexdigest())
        self.assertTrue((self.folder/'README.md').exists());self.assertTrue((self.folder/'_manager/summary.json').exists())
        comparison=json.loads((self.folder/'_manager/comparison.json').read_text())
        self.assertEqual(comparison['groups'][0]['cases'][0]['rows'][0]['cells']['Reviewer A']['comment'],'Original note')
        repaired=json.loads(next((self.folder/'normalized').glob('*.json')).read_text())
        self.assertEqual(repaired['labels'][0]['annotator'],'Reviewer A')
        log=self.folder/'_manager/normalization-log.jsonl';size=log.stat().st_size;refresh(self.root,'20261001');self.assertEqual(size,log.stat().st_size)
        self.assertEqual(file_data(self.root,'20261001',ident,'original')[0],raw)

    def test_same_filename_new_content_is_preserved_as_a_separate_input(self):
        raw=self.source.read_bytes();upload(self.root,'20261001',[{'name':'original.json','text':json.dumps(legacy(name='B'))}])
        self.assertEqual(self.source.read_bytes(),raw);self.assertEqual(len(list(self.folder.glob('*.json'))),2)
        self.assertEqual(len(view(self.root,'20261001')['groups'][0]['reviewers']),2)

    def test_current_files_and_explicit_selection_change_the_actual_denominator(self):
        result=upload(self.root,'20261001',[{'name':'b.json','text':json.dumps(legacy(name='B'))}])
        self.assertEqual(result['groups'][0]['metrics'][0]['included'],1)
        selected=view(self.root,'20261001',[result['files'][0]['id']])
        self.assertEqual(len(selected['groups'][0]['reviewers']),1)
        self.assertEqual(selected['groups'][0]['metrics'][0]['included'],0)
        self.source.write_text(json.dumps(legacy(decision='reject')))
        self.assertEqual(view(self.root,'20261001')['groups'][0]['totals']['DISAGREE'],1)

    def test_bad_file_is_retained_and_other_inputs_still_display(self):
        bad=self.folder/'bad.json';bad.write_text('{"bad":')
        result=refresh(self.root,'20261001');self.assertEqual(len(result['groups']),1)
        self.assertTrue(next(file for file in result['files'] if file['filename']=='bad.json')['error'])
        self.assertEqual(bad.read_text(),'{"bad":')

    def test_g02_lookup_matches_only_the_selected_case_and_respects_file_selection(self):
        payload=legacy();payload['labels'].append(legacy(id='test-0002')['labels'][0])
        self.source.write_text(json.dumps(payload))
        (self.folder/'other.json').write_text(json.dumps(legacy(name='B',inserted='Different evidence.')))
        result=view(self.root,'20261001');group_id=result['groups'][0]['id']
        selected=next(file['id'] for file in result['files'] if file['filename']=='original.json')
        with patch('finarch.dataset.viewer.annotation.store.attach_sources',wraps=attach_sources) as matched:
            links=g02_links(self.root,'20261001',group_id,'test-0001',[selected])
        groups=matched.call_args.args[0]
        self.assertEqual(groups[0]['reviewers'],['Reviewer A'])
        self.assertEqual([item['case'] for item in groups[0]['cases']],['test-0001'])
        self.assertEqual(len(links['links']),7)
        with self.assertRaises(ValueError):g02_links(self.root,'20261001',group_id,'test-0001',[])

    def test_registration_checks_origin_and_path_and_serves_the_shared_api(self):
        project=Path(self.temp.name);runs=project/'reports/run';runs.mkdir(parents=True)
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(runs));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url=f'http://127.0.0.1:{server.server_port}'
        with patch('finarch.dataset.viewer.server.PROJECT',project):
            body=json.dumps({'date':'20261001'}).encode()
            with self.assertRaises(HTTPError) as error:urlopen(Request(url+'/api/annotation/refresh',data=body,headers={'Content-Type':'application/json'}))
            self.assertEqual(error.exception.code,403)
            error.exception.close()
            result=json.load(urlopen(Request(url+'/api/annotation/refresh',data=body,headers={'Content-Type':'application/json','Origin':url})))
            self.assertEqual(len(result['groups']),1)
            self.assertEqual(json.load(urlopen(url+'/api/annotation?date=20261001'))['date'],'20261001')
            links=json.load(urlopen(url+'/api/annotation/g02?date=20261001&case=test-0001&group='+result['groups'][0]['id']))
            self.assertEqual(links['case'],'test-0001');self.assertEqual(len(links['links']),7)
            self.assertTrue(all(link['status']=='UNAVAILABLE' for link in links['links'].values()))
            bad=json.dumps({'date':'../20261001'}).encode()
            with self.assertRaises(HTTPError) as error:urlopen(Request(url+'/api/annotation/refresh',data=bad,headers={'Content-Type':'application/json','Origin':url}))
            self.assertEqual(error.exception.code,400)
            error.exception.close()


if __name__ == '__main__':unittest.main()
