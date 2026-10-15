"""Check asset allowlists and the read-only dashboard API boundary."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from finarch.dashboard.viewer.resources import resource


class DashboardRouteChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        page = self.project / 'viewer/dashboard/01-overview/index.html'
        page.parent.mkdir(parents=True)
        page.write_text('<main>Saved results only</main>')

    def test_registered_page_served_and_arbitrary_paths_rejected(self):
        body, mime = resource('/dashboard/01-overview/', project=self.project)
        self.assertIn(b'Saved results only', body)
        self.assertEqual(mime, 'text/html; charset=utf-8')
        for path in ['/dashboard/../../.env', '/dashboard/README.md',
                     '/dashboard/01-overview/unknown.js', '/api/dashboard/file']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                resource(path, project=self.project)

    def test_symlink_cannot_replace_registered_asset(self):
        target = self.project / 'viewer/dashboard/01-overview/index.html'
        target.unlink()
        outside = self.project / 'secret.txt'
        outside.write_text('Not an asset')
        target.symlink_to(outside)
        with self.assertRaises(ValueError):
            resource('/dashboard/01-overview/', project=self.project)

    @patch.object(__import__('finarch.dashboard.01-data.data', fromlist=['*']), 'load_data')
    def test_data_refresh_is_explicit_and_missing_values_remain_null(self, loader):
        loader.return_value = {'rows': [{'metrics': {'output_tokens': None}, 'answer': 0}]}
        body, mime = resource('/api/dashboard/data', {'refresh': ['1']}, self.project)
        loader.assert_called_once_with(project=self.project, refresh=True)
        self.assertEqual(json.loads(body)['rows'][0]['answer'], 0)
        self.assertIsNone(json.loads(body)['rows'][0]['metrics']['output_tokens'])
        self.assertEqual(mime, 'application/json; charset=utf-8')

    @patch.object(__import__('finarch.dashboard.01-data.data', fromlist=['*']), 'response_detail')
    def test_detail_requires_identifier_and_never_accepts_file_parameter(self, detail):
        with self.assertRaises(ValueError):
            resource('/api/dashboard/response', {'path': ['.env']}, self.project)
        detail.assert_not_called()
        detail.return_value = {'row': {'trial_id': 'registered'}}
        body, _ = resource('/api/dashboard/response', {'trial_id': ['registered']}, self.project)
        detail.assert_called_once_with('registered', project=self.project)
        self.assertEqual(json.loads(body)['row']['trial_id'], 'registered')


if __name__ == '__main__':
    unittest.main()
