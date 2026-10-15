"""Offline checks for full archives, final-round selection and bound ratings."""
from copy import deepcopy
from importlib import import_module
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

c = import_module('finarch.dataset.03-release.publication.consolidate')


class GeneratedDatasetChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.run = self.base / 'fixture-run'
        self.output = self.base / 'data/generated/fixture-run'
        ids = ['test-0001', 'test-0002', 'test-0003']
        inputs = [{'id': case, 'question': 'What is the total?', 'context': 'A: 10. B: 2.',
                   'reference_answer': '12', 'reference_answer_type': 'integer', 'reference_precision': 0,
                   'answer_metadata': {'scale': 'USD', 'negative': False}} for case in ids]
        c.export.save(self.run / 'input.json', inputs)
        c.export.save(self.run / 'input-selection.json', {'cases': ids, 'input_path': str(self.run / 'input.json')})
        latest = {}
        for sample in inputs:
            case = sample['id']
            root = self.run / '01-preparation' / case
            state = {'status': 'FAIL' if case == ids[2] else 'PASS', 'active_round': '01-round', 'human_decision': 'PENDING'}
            c.export.save(root / 'run.json', state)
            c.export.save(root / '01-round/data.json', sample)
            if case == ids[1]:
                c.export.save(root / '01-round/07-human-review/03-record-decision/decision.json',
                              {'decision': 'REJECTED', 'reason': 'Duplicate source question.'})
            if state['status'] != 'PASS':
                continue
            latest[case] = {}
            for index, (label, folder) in enumerate(c.export.TYPES):
                path = f'02-generation/01-round/{case}/{folder}'
                value = {'label': label, 'status': 'PASS', 'path': path}
                c.export.save(self.run / path / 'run.json', value)
                c.export.save(self.run / path / '02-generate-text/04-observation.json',
                              {'question': sample['question'], 'context': 'A: 10. B: 2. A: 11.'})
                latest[case][str(index)] = value
        # A later failure replaces an earlier PASS; it must remain in the archive.
        folder = c.export.TYPES[4][1]
        self.final = self.run / f'02-generation/03-round/test-0001/{folder}'
        value = {'label': c.schema.TYPES[4], 'status': 'FAIL', 'reason': 'Invalid relation.',
                 'path': str(self.final.relative_to(self.run))}
        c.export.save(self.final / 'run.json', value)
        c.export.save(self.final / '02-generate-text/04-observation.json',
                      {'question': inputs[0]['question'], 'context': 'Final relation text.'})
        latest[ids[0]]['4'] = value
        c.export.save(self.run / '02-generation/summary.json', {'status': 'LIMIT_REACHED', 'latest': latest})
        c.export.save(self.run / '02-generation/timing.json', {'status': 'COMPLETED'})
        self.knowledge = patch.object(c.export.external_knowledge, 'classify',
            return_value=({'used': False, 'used_types': []}, {'sources': {}}))
        self.knowledge.start()
        self.addCleanup(self.knowledge.stop)

    def test_complete_archive_keeps_reject_failure_and_missing_variants(self):
        result = c.publish(self.run, self.output)
        self.assertEqual(result['counts']['cases'], 3)
        self.assertEqual(result['counts']['production_eligible_cases'], 0)
        self.assertEqual(result['counts']['production_rejected_cases'], 1)
        self.assertEqual(result['counts']['automatic_variants']['NOT_RUN'], 7)
        view = c.view(self.output, 'test-0001')
        relation = view['case']['variants'][4]
        self.assertEqual(relation['context'], 'Final relation text.')
        self.assertEqual(relation['automatic_validation']['round'], '03-round')
        self.assertEqual(relation['automatic_validation']['status'], 'FAIL')
        self.assertEqual(relation['annotation']['status'], 'UNREVIEWED')
        # Reading needs no source run after publication.
        self.run.rename(self.base / 'hidden-source-run')
        self.assertEqual(c.view(self.output, 'test-0002')['case']['original']['production_review']['decision'], 'REJECTED')

    def test_schema_hash_and_immutable_snapshot(self):
        c.publish(self.run, self.output)
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.assertFalse(c.publish(self.run, self.output)['changed'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})
        c.export.save(self.final / '02-generate-text/04-observation.json',
                      {'question': 'What is the total?', 'context': 'Changed after export.'})
        with self.assertRaisesRegex(ValueError, 'SNAPSHOT_EXISTS'):
            c.publish(self.run, self.output)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})
        (self.output / 'dataset.jsonl').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'HASH_MISMATCH'):
            c.view(self.output)

    def test_annotation_requires_current_content_and_preserves_disagreement(self):
        rows, _ = c.collect_cases(self.run, c.Sources(self.run))
        target = rows[0]['variants'][4]
        rating = {'item_id': target['item_id'], 'content_sha256': target['content_sha256'],
                  'reviewer': 'Reviewer A', 'decision': 'APPROVED', 'confirmed': True}
        doc = {'format': 'finarch-generated-annotations-v1',
               'ratings': [rating, {**rating, 'reviewer': 'Reviewer B', 'decision': 'REJECTED'}]}
        attached = c.attach_annotations(rows, doc)
        self.assertEqual(len(attached[0]['variants'][4]['annotation']['ratings']), 2)
        self.assertEqual(attached[0]['production_selection'], rows[0]['production_selection'])
        self.assertEqual(rows[0]['variants'][4]['annotation']['status'], 'UNREVIEWED')
        stale = deepcopy(doc); stale['ratings'][0]['content_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'CONTENT_MISMATCH'):
            c.attach_annotations(rows, stale)

    def test_running_or_partial_run_does_not_publish(self):
        path = self.run / '02-generation/summary.json'
        value = c.export.read(path);value['status'] = 'RETRY';c.export.save(path, value)
        with self.assertRaisesRegex(ValueError, 'NOT_COMPLETED'):
            c.publish(self.run, self.output)
        self.assertFalse(self.output.exists())

    def test_changed_source_is_not_committed(self):
        sources = c.Sources(self.run)
        sources.read(self.run / 'input.json')
        c.export.save(self.run / 'input.json', [])
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            sources.verify()

    def test_common_viewer_reads_and_downloads_the_actual_archive(self):
        import hashlib
        from http.server import ThreadingHTTPServer
        import threading
        from urllib.request import urlopen
        from urllib.error import HTTPError
        server_module = import_module('finarch.dataset.viewer.server')
        result = c.publish(self.run, self.output)
        with patch.object(server_module, 'PROJECT', self.base):
            server = ThreadingHTTPServer(('127.0.0.1', 0), server_module.handler_for(self.base))
            worker = threading.Thread(target=server.serve_forever, daemon=True);worker.start()
            self.addCleanup(server.server_close)
            try:
                url = f'http://127.0.0.1:{server.server_port}'
                with urlopen(url+'/api/generated?name=fixture-run&case=test-0002') as response:
                    view = json.load(response)
                    self.assertEqual(view['case']['original']['production_review']['decision'], 'REJECTED')
                    self.assertEqual(len(view['case']['variants']), 7)
                with urlopen(url+'/api/generated-file?name=fixture-run') as response:
                    self.assertEqual(hashlib.sha256(response.read()).hexdigest(), result['files']['dataset.jsonl']['sha256'])
                    self.assertIn('attachment', response.headers['Content-Disposition'])
                with self.assertRaises(HTTPError) as error:
                    urlopen(url+'/api/generated?name=../fixture-run')
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
            finally:
                server.shutdown();worker.join()


if __name__ == '__main__':
    unittest.main()
