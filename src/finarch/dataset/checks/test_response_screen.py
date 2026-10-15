"""Bounded offline screening regressions; synthetic fixtures are not semantic judges."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
execution = __import__('finarch.dataset.03-release.response_screen', fromlist=['execution']).execution
numbers = __import__('finarch.dataset.03-release.response_screen', fromlist=['numbers']).numbers
compare = __import__('finarch.dataset.03-release.response_screen', fromlist=['compare']).compare
screen = __import__('finarch.dataset.03-release.response_screen', fromlist=['screen']).screen
InputSnapshot = __import__('finarch.dataset.03-release.response_screen', fromlist=['InputSnapshot']).InputSnapshot
build = __import__('finarch.dataset.03-release.response_screen', fromlist=['build']).build
from finarch.dataset.schemas.response_screen import ScreenReport

PROJECT = (Path(__file__).resolve().parent / '../../../..').resolve()

def raw(answer='10', finish='stop'):
    return {'choices': [{'finish_reason': finish, 'message': {'content': json.dumps({'answer': answer}), 'reasoning_content': 'Do not use this.'}}]}

def fixture(answer):
    item = {'id': 'case/variant', 'question': 'Q', 'context': 'C'}
    result = {'id': item['id'], 'repeat': 1, 'status': 'COMPLETED', 'answer': answer}
    generation = {'observation': {'question': 'Q', 'context': 'C'}, 'plan': {'original_graph': {'output': 'o', 'nodes': [{'id': 'o', 'computed': '10'}]}, 'execution': {'exact_value': '20'}}}
    return item, raw(answer), result, generation, {'axis': 'EA'}, {}

class ResponseScreenChecks(unittest.TestCase):
    def test_length_precedes_null_partial_and_error(self):
        for content in (None, '{"answer":', '{"answer":"cannot answer"}'):
            r=raw(finish='length');r['choices'][0]['message']['content']=content
            state=execution(r, {'status':'ERROR'})
            self.assertEqual(state[0], 'TRUNCATED');self.assertIsNone(state[4])

    def test_transport_schema_and_missing_are_distinct(self):
        self.assertEqual(execution(None, {'status':'ERROR','error':'Connection timeout'})[0], 'TRANSPORT_ERROR')
        self.assertEqual(execution(None, {'status':'ERROR','error':'unknown error'})[0], 'MISSING')
        self.assertEqual(execution(None, None)[0], 'MISSING')
        self.assertEqual(execution('INVALID_JSON', {})[0], 'SCHEMA_ERROR')
        self.assertEqual(execution({'choices':[]}, {})[0], 'SCHEMA_ERROR')
        self.assertEqual(execution(raw(), None)[0], 'MISSING')
        r=raw();r['choices'][0]['message']['content']=None
        self.assertEqual(execution(r, {})[0], 'SCHEMA_ERROR')

    def test_raw_result_disagreement_and_schema(self):
        self.assertEqual(execution(raw(), {'status':'COMPLETED','answer':'20'})[0], 'SCHEMA_ERROR')
        for content in ('[]','{"answer":10}', '{"answer":"10","extra":1}'):
            r=raw();r['choices'][0]['message']['content']=content
            self.assertEqual(execution(r, {})[0], 'SCHEMA_ERROR')

    def test_cues_coexist_with_two_conditional_answers(self):
        answer='Conflicting amounts; cannot choose. If A, $10; if B, $20.'
        r=screen(*fixture(answer))
        self.assertEqual(len(r.behavior_candidates),3)
        self.assertTrue(all(r.cues.values()))
        for cues in r.cues.values():
            for c in cues:self.assertEqual(answer[c.start:c.end],c.quote)
        self.assertEqual(r.comparison.match,'UNRESOLVED');self.assertEqual(r.numeric_candidates,[])

    def test_false_positive_cues_never_become_semantic_labels(self):
        r=screen(*fixture('There is no conflict. However, all information is sufficient.'))
        self.assertTrue(r.cues['conflict']);self.assertTrue(r.cues['condition'])
        self.assertEqual(r.semantic_status,'NOT_REVIEWED')
        self.assertEqual(r.validity.original,'NOT_REVIEWED')

    def test_explanation_numbers_and_unsupported_formats_not_extracted(self):
        for answer in ('Inputs 10 and 20 sum to 30.', 'Final answer: 30', '10 million', '$10%', '1,23', 'NaN', '1e3'):
            self.assertEqual(numbers(answer),[])

    def test_bare_number_units_precision_and_match(self):
        n=numbers('$1,000.00');self.assertEqual(n[0]['value'],'1000.00')
        self.assertEqual(n[0]['decimal_places'],2)
        for a,b,expected in [('1000','2000','A'),('2000','1000','B'),('1000','1000','BOTH'),('2000','3000','NEITHER')]:
            self.assertEqual(compare(n,a,b,'USD',2)['match'],expected)
        for unit,digits in [('EUR',2),('USD',0),(None,2),('USD',None)]:
            self.assertEqual(compare(n,'1000','2000',unit,digits)['match'],'UNRESOLVED')
        self.assertEqual(compare(numbers('10'),'10','20','USD',0)['match'],'UNRESOLVED')
        self.assertEqual(numbers('10%')[0]['unit'],'percent')

    def test_truncated_all_semantic_axes_unevaluated(self):
        args=list(fixture('conflict cannot if 10'));args[1]=raw('conflict cannot if 10', 'length')
        r=screen(*args)
        for field in ('answer','cues','behavior_candidates','numeric_candidates'):self.assertIsNone(getattr(r,field))
        self.assertEqual(r.semantic_status,'NOT_EVALUATED');self.assertEqual(r.comparison.match,'UNRESOLVED')

    def test_validity_only_linked_recovery_not_approval(self):
        args=list(fixture('10'));r=screen(*args);self.assertEqual(r.validity.perturbation,'UNKNOWN')
        args[4]={'axis':'EA','bounded_recovery_status':'RECOVERABLE'}
        self.assertEqual(screen(*args).validity.perturbation,'INVALID')
        args[3]['observation']['context']='other'
        r=screen(*args);self.assertEqual(r.validity.perturbation,'UNKNOWN');self.assertIsNone(r.comparison.A)

    def test_identity_mismatch_not_complete(self):
        args=list(fixture('10'));args[2]['id']='wrong'
        self.assertEqual(screen(*args).execution,'SCHEMA_ERROR')

    def test_import_has_no_file_or_provider_side_effects(self):
        legacy = __import__('finarch.dataset.03-release.review_first_repeat', fromlist=['*'])
        with patch.object(Path,'write_text',side_effect=AssertionError('write')), patch.object(Path,'read_text',side_effect=AssertionError('read')):
            importlib.reload(legacy)

    def test_snapshot_change_and_missing_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'raw.json';p.write_text('{}');s=InputSnapshot(tmp);s.capture(p);p.write_text('[]')
            with self.assertRaisesRegex(ValueError,'SNAPSHOT_CHANGED'):s.verify()
            s=InputSnapshot(tmp);missing=Path(tmp)/'missing';s.capture(missing);missing.write_text('x')
            with self.assertRaisesRegex(ValueError,'SNAPSHOT_CHANGED'):s.verify()

    def test_output_cannot_overwrite_old_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';quality=root/'quality';source.mkdir();quality.mkdir()
            for output in (source, source/'new', quality, quality/'new'):
                with self.assertRaises(ValueError):build(source,output,quality,project=root)
            output=root/'existing';output.mkdir()
            with self.assertRaises(FileExistsError):build(source,output,quality,project=root)

    def test_actual_624_raw_execution_regression(self):
        root=PROJECT/'reports/run/20260916-001/03-experiment/qwen-8b'
        frozen=json.loads((root/'dataset.json').read_text());self.assertEqual(len(frozen),624)
        states=[];nulls=0
        for n,item in enumerate(frozen,1):
            folder=root/'01-repeat'/f'{n:04d}'
            state=execution(json.loads((folder/'response.json').read_text()),json.loads((folder/'result.json').read_text()))
            states.append(state[0]);nulls+=state[0]=='TRUNCATED' and state[3]
        self.assertEqual(states.count('COMPLETE'),529);self.assertEqual(states.count('TRUNCATED'),95);self.assertEqual(nulls,93)

if __name__=='__main__':unittest.main()

class SavedResponseScreenChecks(unittest.TestCase):
    def test_saved_report_schema_denominators_cues_and_hashes(self):
        from finarch.shared.source_archive import read_source_reference
        import hashlib
        root=PROJECT/'reports/run/20260916-review-v2'
        report=ScreenReport.model_validate_json((root/'response_screen.json').read_text())
        self.assertEqual(report.summary['records'],624)
        self.assertEqual(len({r.id for r in report.records}),624)
        self.assertEqual(report.summary['COMPLETE'],529);self.assertEqual(report.summary['TRUNCATED'],95)
        self.assertEqual(report.summary['known_invalid_perturbations'],3)
        self.assertEqual(report.summary['manual_samples'],5);self.assertEqual(report.summary['semantic_adjudicated'],0)
        self.assertEqual(json.loads((root/'sidecar-schema.json').read_text()),ScreenReport.model_json_schema())
        for r in report.records:
            if r.cues:
                for cue_list in r.cues.values():
                    for c in cue_list:self.assertEqual(r.answer[c.start:c.end],c.quote)
        manifest=json.loads((root/'manifest.json').read_text())
        for ref in manifest['inputs']:
            self.assertEqual(hashlib.sha256(read_source_reference(ref['path'], ref['sha256'], project=PROJECT)).hexdigest(),ref['sha256'],ref['path'])
        for p in manifest['missing']:self.assertFalse((PROJECT/p).exists())
        self.assertTrue(any(r['path'].endswith('first-review.csv') for r in manifest['inputs']))
        self.assertTrue(any('20260916-quality-v1/' in r['path'] for r in manifest['inputs']))

    def test_saved_viewer_and_hash_bound_source_read_only(self):
        from finarch.dataset.viewer.server import batch_data, list_batches
        from finarch.dataset.viewer.reports.quality_report import source
        from finarch.dataset.viewer.assets import render
        root=PROJECT/'reports/run';bundle=root/'20260916-review-v2'
        with patch.object(Path,'write_text',side_effect=AssertionError('write')),patch.object(__import__('finarch.dataset.03-release.response_screen', fromlist=['*']), 'build',side_effect=AssertionError('analysis')):
            payload=batch_data(root,bundle.name)
            self.assertEqual(payload['batch']['response_screen']['summary']['TRUNCATED'],95)
            ref=payload['batch']['response_screen']['records'][0]['references']['raw']
            self.assertIn(b'3150',source(bundle,ref['path']))
        with self.assertRaises(ValueError):source(bundle,'../not-authorized')
        self.assertIn('renderResponseScreen',render())
        self.assertIn(bundle.name,json.dumps(list_batches(root)))
