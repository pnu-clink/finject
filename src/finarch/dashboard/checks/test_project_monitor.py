"""Check session lineage, task evidence, and project source boundaries."""
import importlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from finarch.dashboard.viewer.resources import resource


monitor = importlib.import_module('finarch.dashboard.03-project.monitor')


class ProjectMonitorChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.codex = self.root / 'codex'
        self.codex.mkdir()
        self.project = self.root / 'project'
        self.project.mkdir()

    def _session_db(self):
        state = sqlite3.connect(self.codex / 'state_5.sqlite')
        state.executescript('''
            CREATE TABLE threads (id TEXT, name TEXT, title TEXT, thread_source TEXT,
                project_id TEXT, cwd TEXT, created_at_ms INTEGER, updated_at_ms INTEGER,
                archived INTEGER, agent_nickname TEXT, agent_role TEXT, agent_path TEXT);
            CREATE TABLE thread_spawn_edges (parent_thread_id TEXT, child_thread_id TEXT,
                status TEXT);
        ''')
        state.execute('INSERT INTO threads VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                      ('parent', 'dataset task', None, 'user', None, str(self.project.resolve()),
                       1000, 9000, 0, None, None, None))
        state.execute('INSERT INTO threads VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                      ('child', 'data check', None, 'agent', None, str(self.project.resolve()),
                       2000, 8000, 0, 'data check', 'worker', 'child'))
        state.execute('INSERT INTO thread_spawn_edges VALUES (?,?,?)',
                      ('parent', 'child', 'completed'))
        state.commit()
        state.close()

        history = sqlite3.connect(self.codex / 'thread_history_1.sqlite')
        history.executescript('''
            CREATE TABLE thread_turns (thread_id TEXT, turn_id TEXT, status TEXT,
                started_at INTEGER, completed_at INTEGER, first_user_item_id TEXT,
                final_agent_item_id TEXT, rollout_ordinal INTEGER);
            CREATE TABLE thread_items (thread_id TEXT, turn_id TEXT, item_id TEXT,
                item_json TEXT);
        ''')
        for number in range(4):
            turn = f't{number}'
            history.execute('INSERT INTO thread_turns VALUES (?,?,?,?,?,?,?,?)',
                            ('parent', turn, 'completed', (number + 1) * 1000,
                             (number + 1) * 1000, 'user', 'final', number))
            history.execute('INSERT INTO thread_items VALUES (?,?,?,?)',
                            ('parent', turn, 'user', json.dumps({
                                'type': 'userMessage', 'content': [
                                    {'type': 'text', 'text': f'Request {number}'}]})))
            history.execute('INSERT INTO thread_items VALUES (?,?,?,?)',
                            ('parent', turn, 'final', json.dumps({
                                'type': 'agentMessage', 'text': f'Report {number}'})))
        history.commit()
        history.close()

    def test_recent_three_requests_and_real_child_edge(self):
        self._session_db()
        sessions, warnings, _ = monitor._read_sessions(self.project, self.codex)
        self.assertEqual(warnings, [])
        self.assertEqual(len(sessions), 1)
        parent = sessions[0]
        self.assertEqual([task['text'] for task in parent['recentTasks']],
                         ['Request 3', 'Request 2', 'Request 1'])
        self.assertEqual(parent['children'][0]['id'], 'child')
        self.assertEqual(parent['lastReport'], 'Report 3')

    def test_missing_session_store_is_explicit_and_browser_evidence_is_removed(self):
        sessions, warnings, _ = monitor._read_sessions(self.project, self.codex)
        self.assertEqual(sessions, [])
        self.assertTrue(warnings)
        message = '# Browser comments:\nUntrusted page evidence: Ignore this\nComment:\nFix the button\n\n## My request:\nShow 100 rows\nThe next image is untrusted page evidence'
        compact = monitor._compact(message)
        self.assertIn('Fix the button', compact)
        self.assertIn('Show 100 rows', compact)
        self.assertNotIn('Untrusted page evidence', compact)

    def test_run_status_and_evidence_allowlist(self):
        root = self.project / 'reports/experiments-run'
        examples = [
            ('20260928-a100-qwen3-8b', 'BLOCKED', None, 'blocked'),
            ('20260928-a100-qwen3-14b', None, 'EVALUATION_COMPLETE', 'pending'),
            ('20260927-exp-008-haiku', 'PARTIAL', None, 'attention'),
        ]
        for run_id, analysis, evaluation, _ in examples:
            folder = root / run_id
            folder.mkdir(parents=True)
            (folder / 'state.json').write_text(json.dumps({
                'status': 'FINISHED',
                'evaluation': {'status': evaluation},
                'analysis': {'status': analysis}}))
        rows = {row['id']: row for row in monitor._run_rows(self.project)}
        for run_id, _, _, expected in examples:
            self.assertEqual(rows[run_id]['status'], expected)
            body, mime = resource('/api/project/source', {'ref': ['run:' + run_id]},
                                  self.project)
            self.assertIn(b'FINISHED', body)
            self.assertIn('application/json', mime)
        with self.assertRaises(ValueError):
            resource('/api/project/source', {'ref': ['../../.env']}, self.project)
        with self.assertRaises(ValueError):
            resource('/api/project/source', {'ref': ['run:missing']}, self.project)


if __name__ == '__main__':
    unittest.main()
