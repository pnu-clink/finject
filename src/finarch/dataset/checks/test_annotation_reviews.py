"""Manager persistence and recipient-safe portable exports in temporary projects."""
from copy import deepcopy
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

from finarch.dataset.viewer.annotation.normalize import TYPES
from finarch.dataset.viewer.annotation.reviews import save, read, export_files, zip_export
from finarch.dataset.viewer.annotation.store import view, refresh
from finarch.dataset.viewer.server import handler_for

PROJECT = Path(__file__).resolve().parents[4]


def make_fixture(project):
    date = project / 'annotation/20261001'
    date.mkdir(parents=True)
    run = project / 'reports/run/fixture-run'
    for case in ('test-0001', 'test-0002'):
        preparation = run / '01-preparation' / case
        preparation.mkdir(parents=True)
        original = {'question': 'What is the total?', 'context': 'The original amount is 10.',
                    'provenance': {'source_id': 'finqa_' + case}}
        (preparation / 'data.json').write_text(json.dumps(original))
        for variant, _, _ in TYPES:
            stage = run / '02-generation/01-round' / case / variant / '02-generate-text'
            stage.mkdir(parents=True)
            (stage / '01-input.json').write_text(json.dumps(original))
            (stage / '04-observation.json').write_text(json.dumps({
                'question': original['question'], 'context': original['context'] + ' Added condition for ' + variant + '.'}))
    for filename, name in (('a.json', 'Reviewer A'), ('b.json', 'Reviewer B')):
        evaluations = [{'case': case, 'variant': variant, 'decision': 'APPROVED', 'confirmed': True,
                        'comment': 'Private note by ' + name, 'checklist': {}}
                       for case in ('test-0001', 'test-0002') for variant, _, _ in TYPES]
        if name == 'Reviewer B':
            evaluations[0]['decision'] = 'REJECTED'
        value = {'format': 'finarch-evaluation-results-v1', 'run': 'fixture-run', 'round': '01-round',
                 'package_id': 'fixture-package', 'kind': 'final', 'reviewer': name,
                 'cases': ['test-0001', 'test-0002'], 'evaluations': evaluations}
        (date / filename).write_text(json.dumps(value))
    assets = project / 'viewer/dataset/annotation'
    assets.mkdir(parents=True)
    for name in ('index.html', 'manager.js', 'reviews.js', 'style.css'):
        shutil.copyfile(PROJECT / 'viewer/dataset/annotation' / name, assets / name)
    return project / 'annotation'


def html_data(html):
    return json.loads(re.search(r'<script type="application/json" id="review-data">(.*?)</script>', html, re.S).group(1))


class ManagerReviewChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.root = make_fixture(self.project)
        initial = view(self.root, '20261001')
        self.group = initial['groups'][0]
        self.metrics = deepcopy(self.group['metrics'])
        self.originals = {path.name: path.read_bytes() for path in (self.root / '20261001').glob('*.json')}

    def save(self, **fields):
        return save(self.root, {'date': '20261001', 'group': self.group['id'], 'case': 'test-0001',
                    'files': self.group['file_ids'], 'revision': read(self.root, '20261001')['revision'], **fields})

    def entry(self, kind='RECHECK', reviewer='Reviewer A', **fields):
        return self.save(operation='entry', variant=TYPES[0][0], kind=kind, reviewer=reviewer,
                         note='Please review this rating.', **fields)

    def test_reload_and_refresh_preserve_manager_notes_originals_and_metrics(self):
        self.save(operation='case', checked=True, note='Checked against the whole context.')
        self.entry()
        result = refresh(self.root, '20261001')
        manager = result['groups'][0]['manager_reviews']['test-0001']
        self.assertTrue(manager['checked'])
        self.assertEqual(manager['note'], 'Checked against the whole context.')
        self.assertEqual(manager['entries'][0]['kind'], 'RECHECK')
        self.assertEqual(result['groups'][0]['metrics'], self.metrics)
        for name, raw in self.originals.items():
            self.assertEqual((self.root / '20261001' / name).read_bytes(), raw)

    def test_two_recipients_and_single_repair_html_have_only_their_requests(self):
        self.entry()
        self.entry(kind='WHY', reviewer='Reviewer B')
        self.entry(kind='REPAIR', reviewer=None)
        files = export_files(self.root, '20261001', self.group['id'])['files']
        self.assertEqual([item['filename'] for item in files], ['annotator1_Reviewer A.html', 'annotator2_Reviewer B.html', 'repair_20261001.html'])
        first, second, repair = [html_data(item['html']) for item in files]
        self.assertEqual([entry['kind'] for entry in first['requests']], ['RECHECK'])
        self.assertEqual([entry['kind'] for entry in second['requests']], ['WHY'])
        self.assertEqual([entry['kind'] for entry in repair['requests']], ['REPAIR'])
        self.assertNotIn('Private note by Reviewer B', files[0]['html'])
        self.assertNotIn('Private note by Reviewer A', files[1]['html'])
        self.assertEqual(len(repair['requests']), 1)

    def test_type_confirmation_is_persisted_without_reviewer_or_export(self):
        self.save(operation='entry', variant=TYPES[1][0], kind='CHECKED', reviewer=None, note='')
        result = refresh(self.root, '20261001')
        review = result['groups'][0]['manager_reviews']['test-0001']
        self.assertFalse(review['checked'])
        self.assertEqual(len(review['entries']), 1)
        self.assertEqual(review['entries'][0]['variant'], TYPES[1][0])
        self.assertEqual(review['entries'][0]['kind'], 'CHECKED')
        self.assertIsNone(review['entries'][0]['reviewer'])
        self.assertEqual(review['entries'][0]['note'], '')
        self.assertEqual(export_files(self.root, '20261001', self.group['id'])['files'], [])
        self.assertEqual(result['groups'][0]['metrics'], self.metrics)
        for name, raw in self.originals.items():
            self.assertEqual((self.root / '20261001' / name).read_bytes(), raw)

    def test_type_confirmation_cannot_be_routed_as_reviewer_request(self):
        with self.assertRaises(ValueError):
            self.save(operation='entry', variant=TYPES[0][0], kind='CHECKED', reviewer='Reviewer A', note='Checked.')
        self.assertEqual(read(self.root, '20261001')['revision'], 0)

    def test_empty_reviewer_requests_persist_and_export_without_changing_ratings(self):
        for kind, reviewer in (('RECHECK', 'Reviewer A'), ('WHY', 'Reviewer B')):
            self.save(operation='entry', variant=TYPES[0][0], kind=kind, reviewer=reviewer, note='')
        result = refresh(self.root, '20261001')
        entries = result['groups'][0]['manager_reviews']['test-0001']['entries']
        self.assertEqual([(entry['kind'], entry['note']) for entry in entries], [('RECHECK', ''), ('WHY', '')])
        files = export_files(self.root, '20261001', self.group['id'])['files']
        self.assertEqual([item['filename'] for item in files], ['annotator1_Reviewer A.html', 'annotator2_Reviewer B.html'])
        for item in files:
            self.assertEqual(html_data(item['html'])['requests'][0]['note'], '')
            self.assertIn('주석 없음', item['html'])
        self.assertEqual(result['groups'][0]['metrics'], self.metrics)
        for name, raw in self.originals.items():
            self.assertEqual((self.root / '20261001' / name).read_bytes(), raw)

    def test_repair_requires_nonblank_note_and_cannot_append_history(self):
        for text in ('', '  \n\t'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.save(operation='entry', variant=TYPES[0][0], kind='REPAIR', reviewer=None, note=text)
        self.assertEqual(read(self.root, '20261001')['revision'], 0)
        self.assertFalse((self.root / '20261001/_manager/review-history.jsonl').exists())

    def test_portable_html_contains_verified_whole_body_and_no_runtime_dependencies(self):
        self.entry()
        item = export_files(self.root, '20261001', self.group['id'])['files'][0]
        data = html_data(item['html'])
        evidence = data['requests'][0]['evidence']
        self.assertEqual(evidence['context'], 'The original amount is 10. Added condition for ' + TYPES[0][0] + '.')
        self.assertEqual(evidence['question'], 'What is the total?')
        self.assertEqual(evidence['input_context'], 'The original amount is 10.')
        self.assertNotRegex(item['html'], r'<(?:script|link|img)\b[^>]*(?:src|href)=')
        self.assertNotIn('fetch(', item['html'])
        self.assertNotIn(str(self.project), item['html'])

    def test_html_data_cannot_break_out_of_the_script_element(self):
        text = '</script><script>throw new Error("injected")</script>'
        self.save(operation='entry', variant=TYPES[0][0], kind='WHY', reviewer='Reviewer A', note=text)
        html = export_files(self.root, '20261001', self.group['id'])['files'][0]['html']
        self.assertNotIn(text, html)
        self.assertEqual(html_data(html)['requests'][0]['note'], text)

    def test_conflicting_revision_does_not_overwrite_notes_or_append_history(self):
        self.entry()
        path = self.root / '20261001/_manager/reviews.json'
        history = path.parent / 'review-history.jsonl'
        before, log = path.read_bytes(), history.read_bytes()
        with self.assertRaises(ValueError):
            save(self.root, {'date': '20261001', 'group': self.group['id'], 'case': 'test-0001',
                             'revision': 0, 'operation': 'case', 'checked': True, 'note': 'Stale overwrite'})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(history.read_bytes(), log)

    def test_edit_and_remove_keep_before_and_after_in_recoverable_history(self):
        result = self.entry()
        ident = result['cases']['test-0001']['entries'][0]['id']
        self.save(operation='entry', id=ident, variant=TYPES[1][0], kind='WHY', reviewer='Reviewer B', note='Updated question.')
        self.save(operation='remove', id=ident)
        self.assertEqual(read(self.root, '20261001')['groups'][self.group['id']]['cases']['test-0001']['entries'], [])
        history = [json.loads(line) for line in (self.root / '20261001/_manager/review-history.jsonl').read_text().splitlines()]
        self.assertEqual(len(history), 3)
        self.assertEqual(history[1]['before']['entries'][0]['note'], 'Please review this rating.')
        self.assertEqual(history[2]['before']['entries'][0]['note'], 'Updated question.')

    def test_changed_submission_is_unconfirmed_and_old_request_is_not_exported(self):
        self.save(operation='case', checked=True, note='Saved case note.')
        self.entry()
        source = self.root / '20261001/a.json'
        payload = json.loads(source.read_text())
        payload['evaluations'][0]['comment'] = 'Changed after manager review.'
        source.write_text(json.dumps(payload))
        manager = view(self.root, '20261001')['groups'][0]['manager_reviews']['test-0001']
        self.assertFalse(manager['checked'])
        self.assertTrue(manager['stale_checked'])
        self.assertTrue(manager['entries'][0]['stale'])
        result = export_files(self.root, '20261001', self.group['id'])
        self.assertEqual(result['files'], [])
        self.assertEqual(result['stale_entries'], 1)

    def test_selected_files_keep_recipient_number_and_reject_changed_file_ids(self):
        self.entry()
        self.entry(kind='WHY', reviewer='Reviewer B')
        selected = [file['id'] for file in view(self.root, '20261001')['files'] if file['reviewer'] == 'Reviewer B']
        result = export_files(self.root, '20261001', self.group['id'], selected)
        self.assertEqual([file['filename'] for file in result['files']], ['annotator2_Reviewer B.html'])
        with self.assertRaises(ValueError):
            export_files(self.root, '20261001', self.group['id'], ['unknown-file-id'])

    def test_invalid_request_fields_and_paths_cannot_write(self):
        for override in ({'reviewer': 'Unknown'}, {'variant': 'ANSWER'}, {'kind': 'OTHER'},
                         {'note': None}, {'note': 'x' * 10001}, {'case': 'test-9999'}, {'date': '../20261001'}):
            payload = {'date': '20261001', 'group': self.group['id'], 'case': 'test-0001', 'revision': 0,
                       'operation': 'entry', 'variant': TYPES[0][0], 'kind': 'RECHECK', 'reviewer': 'Reviewer A', 'note': 'Keep evidence.'}
            with self.subTest(override=override), self.assertRaises(ValueError):
                save(self.root, {**payload, **override})
        self.assertEqual(read(self.root, '20261001')['revision'], 0)

    def test_symlinked_manager_log_is_rejected(self):
        metadata = self.root / '20261001/_manager'
        metadata.mkdir()
        victim = self.project / 'untouched.txt'
        victim.write_text('Preserved')
        (metadata / 'review-history.jsonl').symlink_to(victim)
        with self.assertRaises(ValueError):
            self.entry()
        self.assertEqual(victim.read_text(), 'Preserved')

    def test_zip_contains_the_exact_named_html_and_rejects_changed_revision(self):
        self.entry()
        result = export_files(self.root, '20261001', self.group['id'])
        with zipfile.ZipFile(io.BytesIO(zip_export(result))) as archive:
            self.assertEqual(archive.namelist(), ['annotator1_Reviewer A.html'])
            self.assertEqual(archive.read(archive.namelist()[0]).decode(), result['files'][0]['html'])
        self.entry(kind='WHY', reviewer='Reviewer B')
        with self.assertRaises(ValueError):
            export_files(self.root, '20261001', self.group['id'], revision=result['revision'])

    def test_http_save_requires_origin_and_downloads_a_real_html_zip(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.project / 'reports/run'))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f'http://127.0.0.1:{server.server_port}'
        payload = {'date': '20261001', 'group': self.group['id'], 'case': 'test-0001', 'revision': 0,
                   'operation': 'entry', 'variant': TYPES[0][0], 'kind': 'WHY', 'reviewer': 'Reviewer A', 'note': ''}
        with patch('finarch.dataset.viewer.server.PROJECT', self.project):
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url + '/api/annotation/manager-review', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}))
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
            result = json.load(urlopen(Request(url + '/api/annotation/manager-review', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'Origin': url})))
            self.assertEqual(result['revision'], 1)
            query = '?date=20261001&group=' + self.group['id']
            response = urlopen(url + '/api/annotation/review-export' + query)
            self.assertEqual(response.headers.get_content_type(), 'application/zip')
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                self.assertEqual(archive.namelist(), ['annotator1_Reviewer A.html'])
            response.close()


def serve_fixture():
    from urllib.parse import unquote, urlsplit
    with tempfile.TemporaryDirectory(prefix='finarch-manager-ui-') as temporary:
        project = Path(temporary)
        root = make_fixture(project)
        handler = handler_for(project / 'reports/run')
        class FixtureHandler(handler):
            def do_GET(self):
                route = urlsplit(self.path)
                if route.path.startswith('/delivered/'):
                    group = view(root, '20261001')['groups'][0]
                    result = export_files(root, '20261001', group['id'])
                    name = unquote(route.path.removeprefix('/delivered/'))
                    file = next((item for item in result['files'] if item['filename'] == name), None)
                    if file is None:
                        self.send_error(404)
                        return
                    body = file['html'].encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                return super().do_GET()
        with patch('finarch.dataset.viewer.server.PROJECT', project):
            server = ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler)
            print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}/annotation/?date=20261001', 'project': str(project)}), flush=True)
            try:
                server.serve_forever()
            finally:
                server.server_close()


if __name__ == '__main__':
    serve_fixture() if '--serve' in sys.argv else unittest.main()
