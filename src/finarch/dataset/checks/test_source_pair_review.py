"""Five bounded fixtures plus real immutable pair and viewer checks."""
from copy import deepcopy
from finarch.shared.source_archive import read_source_reference
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
verify_pair = __import__('finarch.dataset.03-release.source_pair_review', fromlist=['verify_pair']).verify_pair
response_pair = __import__('finarch.dataset.03-release.source_pair_review', fromlist=['response_pair']).response_pair
observation_hash = __import__('finarch.dataset.03-release.source_pair_review', fromlist=['observation_hash']).observation_hash
from finarch.dataset.schemas.source_pair_review import PairReport

PROJECT=(Path(__file__).resolve().parent / '../../../..').resolve()
ROOT=PROJECT/'reports/run/20260916-source-pairs-v1'

def fixture():
    base={'id':'test-0001/01-ic-value-before','context':'B 20. A 10.','question':'Q'}
    text=' (verified)';position=10
    src={'id':'test-0001/03-ic-source-type-1','context':base['context'][:position]+text+base['context'][position:],'question':'Q'}
    intent={'value_pair':['10','20'],'target':'fact','source_condition':'A_ONLY','base_variant':'IC_VALUE_01_BEFORE'}
    slot={'start':position,'end':position,'before':'','element_ids':['n1'],'kind':'SOURCE_A'}
    br={'path':'02-generation/01-round/test-0001/01-ic-value-before','observation':{k:base[k] for k in ('question','context')},'plan':{'intent':deepcopy(intent)}}
    sr={'observation':{k:src[k] for k in ('question','context')},'plan':{'intent':intent},'generation_request':{**br['observation'],'edit_slots':[slot],'instructions':['Attribute the later original claim only.']},'patches':[{**slot,'text':text}]}
    dep={'source':br['path'],'observation_sha256':observation_hash(br['observation'])}
    return src,base,sr,br,dep

class SourcePairChecks(unittest.TestCase):
    def test_fixture_1_exact_base_inverse_and_no_approximate_removal(self):
        args=list(fixture());reasons,inverse,_,_=verify_pair(*args)
        self.assertEqual(reasons,[]);self.assertTrue(inverse)
        args[0]['context']+=' unrelated edit';args[2]['observation']['context']=args[0]['context']
        reasons,inverse,_,_=verify_pair(*args)
        self.assertIn('INVERSE_QC_MISMATCH',reasons);self.assertIn('FORWARD_PATCH_MISMATCH',reasons);self.assertFalse(inverse)

    def test_fixture_2_ab_identity_and_table_position(self):
        args=list(fixture());args[1]['context']='| A | 10 |';args[3]['observation']['context']=args[1]['context']
        args[2]['generation_request']['context']=args[1]['context']
        for obj in (args[2]['patches'][0],args[2]['generation_request']['edit_slots'][0]):obj.update(start=8,end=8)
        args[0]['context']='| A | 10 (verified) |';args[2]['observation']['context']=args[0]['context'];args[4]['observation_sha256']=observation_hash(args[3]['observation'])
        reasons,inverse,identity,location=verify_pair(*args)
        self.assertEqual(reasons,[]);self.assertTrue(inverse);self.assertEqual(identity['A'],'10')
        self.assertEqual(location['layout'],'TABLE_CELL');self.assertEqual(location['position_interpretation'],'CELL_LOCAL_NOT_PROSE_ORDER')
        args[2]['plan']['intent']['value_pair']=['20','10']
        self.assertIn('VALUE_IDENTITY_OR_TARGET_MISMATCH',verify_pair(*args)[0])

    def test_fixture_3_dependency_hash_path_and_parent_mismatch(self):
        args=list(fixture());args[4]['observation_sha256']='0'*64
        self.assertIn('DEPENDENCY_OBSERVATION_HASH_MISMATCH',verify_pair(*args)[0])
        args=list(fixture());args[4]['source']='wrong'
        self.assertIn('DEPENDENCY_PATH_MISMATCH',verify_pair(*args)[0])
        args=list(fixture());args[1]['id']='test-0002/01-ic-value-before'
        self.assertIn('WRONG_BASE_PARENT_OR_VARIANT',verify_pair(*args)[0])

    def test_fixture_4_missing_pair_preserved(self):
        args=list(fixture());args[1]=None
        self.assertEqual(verify_pair(*args)[0],['MISSING_BASE'])
        args=list(fixture());args[4]=None
        self.assertEqual(verify_pair(*args)[0],['MISSING_SOURCE_OR_DEPENDENCY'])

    def test_fixture_5_one_truncated_keeps_states_but_excludes_cue_delta(self):
        complete={'execution':'COMPLETE','cues':{'conflict':[{}],'reject':[],'condition':[{}]},'semantic_status':'NOT_REVIEWED','comparison':{'match':'UNRESOLVED'}}
        truncated={'execution':'TRUNCATED','cues':None,'semantic_status':'NOT_EVALUATED','comparison':{'match':'UNRESOLVED'}}
        states,comparison=response_pair(complete,truncated,True)
        self.assertEqual(states['base']['execution'],'TRUNCATED');self.assertIsNone(comparison)
        self.assertIsNone(response_pair(complete,complete,False)[1])
        self.assertTrue(response_pair(complete,complete,True)[1]['conflict']['source'])

    def test_actual_176_exact_pairs_input_hashes_and_denominators(self):
        report=PairReport.model_validate_json((ROOT/'pair_manifest.json').read_text())
        self.assertEqual(len(report.records),176);self.assertEqual(len({r.source_id for r in report.records}),176)
        self.assertEqual(report.summary['SOURCE1']['total'],86);self.assertEqual(report.summary['SOURCE2']['total'],90)
        self.assertEqual(report.summary['overall']['matched'],176)
        self.assertEqual(report.summary['overall']['cue_comparable'],132);self.assertEqual(report.summary['overall']['either_truncated'],44)
        self.assertTrue(all(r.inverse_matches_base and r.semantic_effect=='NOT_EVALUATED' and r.ab_effect=='UNRESOLVED' for r in report.records))
        self.assertEqual(json.loads((ROOT/'sidecar-schema.json').read_text()),PairReport.model_json_schema())
        manifest=json.loads((ROOT/'manifest.json').read_text())
        for ref in manifest['inputs']:self.assertEqual(hashlib.sha256(read_source_reference(ref['path'], ref['sha256'], project=PROJECT)).hexdigest(),ref['sha256'],ref['path'])
        self.assertTrue(any(r.claim_location['layout']=='TABLE_CELL' for r in report.records))
        for kind in ('SOURCE1','SOURCE2'):
            c=report.summary[kind]
            for axis in ('conflict','reject','condition'):self.assertEqual(sum(c['cue_transitions'][axis].values()),c['cue_comparable'])

    def test_viewer_saved_read_and_hash_link(self):
        from finarch.dataset.viewer.server import batch_data, list_batches
        from finarch.dataset.viewer.reports.quality_report import source
        with patch.object(Path,'write_text',side_effect=AssertionError('write')),patch.object(__import__('finarch.dataset.03-release.source_pair_review', fromlist=['*']), 'build',side_effect=AssertionError('analysis')):
            payload=batch_data(PROJECT/'reports/run',ROOT.name)
            report=payload['batch']['source_pair_review'];self.assertEqual(report['summary']['records'],176)
            ref=report['records'][0]['references']['dependency'];self.assertTrue(source(ROOT,ref['path']))
        self.assertIn(ROOT.name,json.dumps(list_batches(PROJECT/'reports/run')))

if __name__=='__main__':unittest.main()
