"""Offline baseline identity, request isolation, and saved-report tests."""
from copy import deepcopy
from finarch.shared.source_archive import read_source_reference
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pydantic import ValidationError
group_frozen = __import__('finarch.dataset.03-release.original_baseline', fromlist=['group_frozen']).group_frozen
approved_directory = __import__('finarch.dataset.03-release.original_baseline', fromlist=['approved_directory']).approved_directory
public_original = __import__('finarch.dataset.03-release.original_baseline', fromlist=['public_original']).public_original
make_request = __import__('finarch.dataset.03-release.original_baseline', fromlist=['make_request']).make_request
settings = __import__('finarch.dataset.03-release.original_baseline', fromlist=['settings']).settings
build = __import__('finarch.dataset.03-release.original_baseline', fromlist=['build']).build
InputSnapshot = __import__('finarch.dataset.03-release.response_screen', fromlist=['InputSnapshot']).InputSnapshot
from finarch.dataset.schemas.original_baseline import PublicOriginal, BaselineReport

PROJECT=(Path(__file__).resolve().parent / '../../../..').resolve()
ROOT=PROJECT/'reports/run/20260916-original-baseline-v1'
TEMPLATE=PROJECT/'reports/run/20260916-001/03-experiment/qwen-8b/01-repeat/0001/request.json'

class OriginalBaselineChecks(unittest.TestCase):
    def test_duplicate_variants_rejected(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE_VARIANT'):group_frozen([{'id':'test-0001/01-value'}]*2)

    def test_invalid_parent_ids_rejected(self):
        for identifier in ('../test-0001/01-value','test-0001','other/01-value'):
            with self.assertRaisesRegex(ValueError,'INVALID_VARIANT_PARENT'):group_frozen([{'id':identifier}])

    def test_wrong_parent_round_and_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for approval in ({'case_path':'01-preparation/test-0002'}, {'case_path':'../test-0001'},
                {'case_path':'01-preparation/test-0001','files':{'working_input':{'path':'../02-round/data.json'}}}):
                with self.assertRaises(ValueError):approved_directory(root,'test-0001',approval)
            with self.assertRaisesRegex(ValueError,'ORIGINAL_PARENT_MISMATCH'):public_original({'id':'test-0002'},'test-0001')

    def test_public_allowlist_rejects_private_keys(self):
        public={'id':'test-0001','question':'Q','context':'C'}
        for key in ('gold','reference_answer','provenance','A','B','python_code','variants'):
            with self.assertRaises(ValidationError):PublicOriginal.model_validate(public|{key:'SECRET'})

    def test_private_mutation_cannot_change_public_or_request(self):
        template=json.loads(TEMPLATE.read_text());data={'id':'test-0001','question':'Q','context':'C','reference_answer':'SECRET','provenance':{'private':'A'},'python_code':'hidden'}
        public=public_original(data,'test-0001');request=make_request(public,template)
        data.update(reference_answer='CHANGED',provenance={'private':'B'},python_code='different')
        self.assertEqual(public_original(data,'test-0001'),public)
        self.assertEqual(make_request(public_original(data,'test-0001'),template),request)
        self.assertNotIn('SECRET',json.dumps(request));self.assertNotIn('CHANGED',json.dumps(request))
        self.assertEqual(request['messages'][1]['content'],'Question:\nQ\n\nContext:\nC')

    def test_changed_conditions_or_extra_messages_rejected(self):
        original=json.loads(TEMPLATE.read_text())
        for key,value in [('temperature',1),('max_tokens',100),('response_format',{}),('private','SECRET')]:
            r=deepcopy(original);r[key]=value
            with self.assertRaises(ValueError):settings(r)
        r=deepcopy(original);r['messages'][0]['content']+=' Secret gold.'
        with self.assertRaisesRegex(ValueError,'SYSTEM_PROMPT_CHANGED'):settings(r)
        r=deepcopy(original);r['messages'].append({'role':'assistant','content':'gold'})
        with self.assertRaises(ValueError):settings(r)

    def test_hash_and_missing_input_changes_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.json';p.write_text('{}');s=InputSnapshot(tmp);s.capture(p);p.write_text('[]')
            with self.assertRaisesRegex(ValueError,'SNAPSHOT_CHANGED'):s.verify()
            s=InputSnapshot(tmp);missing=Path(tmp)/'missing';s.capture(missing);missing.write_text('{}')
            with self.assertRaisesRegex(ValueError,'SNAPSHOT_CHANGED'):s.verify()

    def test_output_overwrite_and_denominator_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';quality=root/'quality';source.mkdir();quality.mkdir()
            with self.assertRaises(ValueError):build(source,source/'new',quality,project=root)
            existing=root/'existing';existing.mkdir()
            with self.assertRaises(FileExistsError):build(source,existing,quality,project=root)
            path=source/'03-experiment/qwen-8b/dataset.json';path.parent.mkdir(parents=True);path.write_text('[]')
            with self.assertRaisesRegex(ValueError,'DENOMINATOR_MISMATCH'):build(source,root/'out',quality,project=root)

    def test_real_92_624_links_rounds_schema_and_request_isolation(self):
        report=BaselineReport.model_validate_json((ROOT/'private/originals.json').read_text())
        public=json.loads((ROOT/'public/dataset.json').read_text());self.assertEqual(len(public),92)
        self.assertEqual(len({p['id'] for p in public}),92)
        self.assertEqual(len({(p['question'],p['context']) for p in public}),92)
        variants=[v for r in report.records for v in r.variants];self.assertEqual(len(variants),624);self.assertEqual(len(set(variants)),624)
        self.assertEqual(report.summary['FinanceReasoning'],55);self.assertEqual(report.summary['TAT_QA'],37)
        self.assertEqual(report.summary['prepared'],92);self.assertEqual(report.summary['baseline_calls'],0)
        self.assertEqual(next(r for r in report.records if r.id=='test-0017').approved_round,'03-round')
        self.assertTrue(all(r.semantic_review=='NOT_REVIEWED' for r in report.records))
        self.assertEqual(json.loads((ROOT/'sidecar-schema.json').read_text()),BaselineReport.model_json_schema())
        template=json.loads(TEMPLATE.read_text())
        for row in public:
            PublicOriginal.model_validate(row)
            self.assertEqual(json.loads((ROOT/'public/requests'/f"{row['id']}.json").read_text()),make_request(row,template))

    def test_all_saved_input_output_hashes_unchanged(self):
        manifest=json.loads((ROOT/'manifest.json').read_text())
        for ref in manifest['inputs']:self.assertEqual(hashlib.sha256(read_source_reference(ref['path'], ref['sha256'], project=PROJECT)).hexdigest(),ref['sha256'],ref['path'])
        for ref in manifest['outputs']:self.assertEqual(hashlib.sha256((ROOT/ref['path']).read_bytes()).hexdigest(),ref['sha256'],ref['path'])

    def test_common_viewer_reads_only_saved_private_report(self):
        from finarch.dataset.viewer.server import batch_data, list_batches
        from finarch.dataset.viewer.reports.quality_report import source
        with patch.object(Path,'write_text',side_effect=AssertionError('write')),patch.object(__import__('finarch.dataset.03-release.original_baseline', fromlist=['*']), 'build',side_effect=AssertionError('build')):
            payload=batch_data(PROJECT/'reports/run',ROOT.name)
            self.assertEqual(payload['batch']['original_baseline']['summary']['originals'],92)
            ref=payload['batch']['original_baseline']['records'][0]['references']['working_input']
            self.assertTrue(source(ROOT,ref['path']))
        self.assertIn(ROOT.name,json.dumps(list_batches(PROJECT/'reports/run')))

if __name__=='__main__':unittest.main()
