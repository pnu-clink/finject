"""Regression checks for read-only viewer transport and summary caching."""
import json
import tempfile
import unittest
from pathlib import Path
from finarch.dataset.viewer.summary_reader import read_generation_summary, read_status_record
from finarch.dataset.viewer.response_encoding import encode


class ViewerSpeedTests(unittest.TestCase):
    def test_saved_gate_reuse_revalidates_changed_evidence(self):
        from unittest.mock import patch
        from finarch.dataset.viewer.server import viewer_review_gate
        with tempfile.TemporaryDirectory() as directory:
            bundle=Path(directory);case=bundle/'01-preparation/test-0001';case.mkdir(parents=True)
            (bundle/'input-selection.json').write_text('{"cases":["test-0001"]}')
            (case/'run.json').write_text('{"status":"PASS"}')
            evidence=case/'data.json';evidence.write_text('{"value":1}')
            value={'allow_generation':True,'approved':['test-0001'],'approved_inputs':{'test-0001':{'files':{'input':{'path':'data.json'}}}}}
            gate=bundle/'01-preparation/review-gate.json';gate.write_text(json.dumps(value))
            with patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'evaluate',return_value={'revalidated':True}) as check:
                self.assertEqual(viewer_review_gate(bundle),value);check.assert_not_called()
                evidence.write_text('{"value":2}')
                self.assertEqual(viewer_review_gate(bundle),{'revalidated':True})
                gate.write_text(json.dumps(value));evidence.unlink()
                self.assertEqual(viewer_review_gate(bundle),{'revalidated':True})

    def test_status_projection_excludes_payload_and_tracks_replacements(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'run.json'
            path.write_text(json.dumps({'status':'FAIL','reason':'old','plan':{'payload':'x'*100000}}))
            value=read_status_record(path)
            self.assertEqual(value,{'status':'FAIL','reason':'old'})
            value['status']='edited'
            self.assertEqual(read_status_record(path)['status'],'FAIL')
            new=path.with_suffix('.tmp');new.write_text('{"status":"PASS","reason":"new"}');new.replace(path)
            self.assertEqual(read_status_record(path),{'status':'PASS','reason':'new'})
            path.unlink();self.assertIsNone(read_status_record(path))

    def test_metadata_cache_invalidation_and_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'summary.json'
            path.write_text(json.dumps({'latest': {'large': [1, 2]}, 'rounds': [1], 'status': 'PASS'}))
            value = read_generation_summary(path)
            self.assertEqual(value, {'rounds': [1], 'status': 'PASS'})
            value['rounds'].append(9)
            self.assertEqual(read_generation_summary(path)['rounds'], [1])
            replacement = path.with_suffix('.tmp')
            replacement.write_text(json.dumps({'status': 'FAIL', 'latest': {}}))
            replacement.replace(path)
            self.assertEqual(read_generation_summary(path), {'status': 'FAIL'})
            path.write_text('{')
            self.assertIn('read_error', read_generation_summary(path))
            path.write_text('{}')
            self.assertIsNone(read_generation_summary(path))
            path.unlink()
            self.assertIsNone(read_generation_summary(path))
            path.symlink_to(Path(directory)/'missing')
            self.assertIsNone(read_generation_summary(path))

    def test_phi_two_lazy_reader_and_path_checks(self):
        from finarch.dataset.viewer.phi_two import load
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root/'example'
            case = run/'cases/finance-easy/easy-0001'
            case.mkdir(parents=True)
            (run/'config.json').write_text('{"workflow":"phi_two"}')
            (run/'selection.json').write_text('[{"id":"finance-easy/easy-0001"}]')
            (case/'input.json').write_text('{"question":"Q","context":"C"}')
            self.assertNotIn('input', load(root))
            detail = load(root, 'example', 'finance-easy/easy-0001')
            self.assertEqual(detail['input']['question'], 'Q')
            self.assertIsNone(detail['result'])
            self.assertEqual(detail['graph_execution'], 'NOT_EXECUTED')
            with self.assertRaises(ValueError):load(root, 'example', '../outside')

    def test_http_etag_rechecks_live_changes(self):
        import threading
        from http.server import ThreadingHTTPServer
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from finarch.dataset.viewer.server import handler_for
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = root/'example/case'
            case.mkdir(parents=True)
            (case/'run.json').write_text('{"status":"PASS"}')
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(root))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}/api/run?name=example'
                with urlopen(url) as response:
                    tag = response.headers['ETag']
                    self.assertEqual(json.load(response)['runs'][0]['artifacts']['run.json']['status'], 'PASS')
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(url, headers={'If-None-Match': tag}))
                self.assertEqual(error.exception.code, 304)
                error.exception.close()
                (case/'run.json').write_text('{"status":"FAIL"}')
                with urlopen(Request(url, headers={'If-None-Match': tag})) as response:
                    self.assertNotEqual(response.headers['ETag'], tag)
                    self.assertEqual(json.load(response)['runs'][0]['artifacts']['run.json']['status'], 'FAIL')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_encoder_preserves_decoded_values(self):
        for value in [{'text': '\ud55c\uae00 😀'}, {'integer': 2**100}, {'number': float('inf')}, {'x': -0.0}, {'1': 'str', 1: 'number'}]:
            self.assertEqual(json.loads(encode(value)), json.loads(json.dumps(value)))


if __name__ == '__main__':
    unittest.main()
