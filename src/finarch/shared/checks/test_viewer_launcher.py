"""Launcher identity, browser timing and headless override contracts."""
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from finarch.paths import PROJECT
from finarch.shared.viewer import serve


class LauncherChecks(unittest.TestCase):
    def test_browser_opens_after_bind_and_server_closes_on_interrupt(self):
        server = MagicMock(server_port=8893)
        server.serve_forever.side_effect = KeyboardInterrupt
        events = []
        def bind(*args):
            events.append('bound')
            return server
        with patch('finarch.shared.viewer.ThreadingHTTPServer', side_effect=bind), \
             patch('finarch.shared.viewer.webbrowser.open', side_effect=lambda url: events.append(url)):
            serve(object, name='dataset', port=8893, argv=['--open'])
        self.assertEqual(events, ['bound', 'http://127.0.0.1:8893/'])
        server.server_close.assert_called_once()

    def test_no_open_overrides_launcher_default(self):
        server = MagicMock(server_port=8895)
        server.serve_forever.side_effect = KeyboardInterrupt
        with patch('finarch.shared.viewer.ThreadingHTTPServer', return_value=server), \
             patch('finarch.shared.viewer.webbrowser.open') as opener:
            serve(object, name='dashboard', port=8895, argv=['--open', '--no-open'])
        opener.assert_not_called()

    def test_reuses_only_the_same_domain_and_project(self):
        for name, project, allowed in [('dashboard', str(PROJECT), True),
                                       ('dataset', str(PROJECT), False),
                                       ('dashboard', '/another/project', False)]:
            reply = io.BytesIO(json.dumps({'viewer': name, 'project': project}).encode())
            with self.subTest(name=name, project=project), \
                 patch('finarch.shared.viewer.ThreadingHTTPServer', side_effect=OSError('occupied')), \
                 patch('finarch.shared.viewer.urlopen', return_value=reply), \
                 patch('finarch.shared.viewer.webbrowser.open') as opener:
                if allowed:
                    serve(object, name='dashboard', port=8895, argv=['--no-open'])
                else:
                    with self.assertRaises(SystemExit):
                        serve(object, name='dashboard', port=8895, argv=['--open'])
                opener.assert_not_called()
