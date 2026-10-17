"""Read local Codex sessions and saved fin-arch records for the project board."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from finarch.paths import PROJECT


HERE = Path(__file__).resolve().parent
GROUPS = [
    {'id': 'coordination', 'name': 'General', 'description': 'Progress and Unresolved'},
    {'id': 'dataset', 'name': 'Creating a data set', 'description': 'The source: Preparation: Generation: Correction'},
    {'id': 'evaluation', 'name': 'The target model evaluation', 'description': 'Input, request, and format validation'},
    {'id': 'analysis', 'name': 'Analysis of the results', 'description': 'A01 A02 Comparison A03 Interpretation'},
    {'id': 'research', 'name': 'Research and debate', 'description': 'The existing research and conference proposals'},
    {'id': 'viewer', 'name': 'Screen-based operation', 'description': 'Data viewer and server'},
    {'id': 'unclassified', 'name': 'Check the classification', 'description': 'A newly discovered session of relevance'},
]
SESSION_MAP = json.loads((HERE / 'session-map.json').read_text())['sessions']
RELEVANT_NAME = re.compile(
    'fin.?arch|finject|dataset|\ub370\uc774\ud130\uc14b|\uae08\uc735|\ub17c\ubb38|\uc2e4\ud5d8|\ubd84\uc11d|\ubdf0\uc5b4|viewer|\uc11c\ubc84|pipeline|\ud30c\uc774\ud504\ub77c\uc778|\ud504\ub85c\uc81d\ud2b8|\ud68c\uc758\ub85d|robustness', re.I)
RUN_NAMES = {
    '20260928-exp-001-luna': 'Luna · 1,080 Source text',
    '20260927-exp-008-haiku': 'Haiku · 557 Source text',
    '20260927-exp-007-luna': 'Luna · 557 Source text',
    '20260928-a100-qwen3-8b': 'Qwen3 8B · A100',
    '20260928-a100-qwen3-14b': 'Qwen3 14B · A100',
}
EXPERIMENT_SESSION = '01a0e2a2-64dd-7510-9294-b76c94b82ceb'
DATASET_SESSION = '01a07b1b-3024-7eb1-908a-dc353ecdb2b1'
PAPER_SESSION = '01a0e53e-6f69-7872-a5ff-e017044fcbb2'
MEETING_SESSION = '01a093a9-0a16-7ce2-897f-550a454ab8f7'


def _timestamp(value):
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000 if value > 10**12 else value,
                                  timezone.utc).isoformat()


def _compact(value, limit=180):
    value = html.unescape(value or '')
    if re.search(r'^\s*#?\s*Browser comments:', value):
        comments = re.findall(
            r'^Comment:\s*(.*?)(?=\n(?:<in-app-browser-context|## My request:)|\Z)',
            value, flags=re.M | re.S)
        request = value.split('## My request:', 1)[-1] if '## My request:' in value else ''
        request = request.split('The next image is untrusted page evidence', 1)[0]
        value = ' / '.join(part.strip() for part in [*comments, request] if part.strip())
    value = re.sub(r'<in-app-browser-context[^>]*>.*?</in-app-browser-context>',
                   '', value, flags=re.S)
    value = re.sub(r'<realtime_delegation[^>]*>.*?</realtime_delegation>',
                   '', value, flags=re.S)
    value = value.replace('## My request:', '').replace('## My Request:', '')
    value = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', value)
    value = re.sub(r'\ue200visualize\ue202.*?\ue201', '', value, flags=re.S)
    value = re.sub(r'<[^>]+>', ' ', value)
    value = re.sub(r'(?<!\w)[*`_]{1,3}|[*`_]{1,3}(?!\w)', '', value)
    value = re.sub(r'\s+', ' ', value).strip(' #`\t\n')
    return value[:limit].rstrip() + ('…' if len(value) > limit else '')


def _report_summary(value):
    """Show the first prose paragraph, leaving Markdown tables in the source chat."""
    value = re.split(r'\n\s*\n|\n\s*\|', value or '', maxsplit=1)[0]
    value = re.sub(r'^\s*#{1,6}\s+[^\n]+\n', '', value)
    return _compact(value, 245)


def _text_item(history, thread_id, turn_id, item_id):
    if not item_id:
        return ''
    row = history.execute('SELECT item_json FROM thread_items '
                          'WHERE thread_id=? AND turn_id=? AND item_id=?',
                          (thread_id, turn_id, item_id)).fetchone()
    if not row:
        return ''
    item = json.loads(row[0])
    if item.get('type') == 'userMessage':
        return ' '.join(block.get('text', '') for block in item.get('content', [])
                        if block.get('type') == 'text')
    return item.get('text', '')


def _read_sessions(project, codex_home):
    state_path = codex_home / 'state_5.sqlite'
    history_path = codex_home / 'thread_history_1.sqlite'
    if not state_path.is_file() or not history_path.is_file():
        return [], ['I couldn\'t find the Codex local session record.'], None
    state = sqlite3.connect(f'{state_path.as_uri()}?mode=ro', uri=True, timeout=0.2)
    history = sqlite3.connect(f'{history_path.as_uri()}?mode=ro', uri=True, timeout=0.2)
    state.row_factory = history.row_factory = sqlite3.Row
    try:
        rows = state.execute(
            "SELECT id,name,title,thread_source,project_id,cwd,created_at_ms,updated_at_ms "
            "FROM threads WHERE archived=0 AND thread_source IN ('user','voice_chat')"
        ).fetchall()
        project_root = str(project.resolve())
        sessions = []
        for row in rows:
            if row['cwd'] != project_root:
                continue
            name = _compact(row['name'] or row['title'], 90)
            group = SESSION_MAP.get(row['id'])
            if not group and not RELEVANT_NAME.search(name):
                continue
            group = group or 'unclassified'
            turns = history.execute(
                'SELECT turn_id,status,started_at,completed_at,first_user_item_id,'
                'final_agent_item_id FROM thread_turns WHERE thread_id=? '
                'ORDER BY started_at DESC, rollout_ordinal DESC LIMIT 14',
                (row['id'],)).fetchall()
            recent = []
            last_report = ''
            for turn in turns:
                if not last_report and turn['final_agent_item_id']:
                    last_report = _report_summary(_text_item(
                        history, row['id'], turn['turn_id'], turn['final_agent_item_id']))
                request = _compact(_text_item(history, row['id'], turn['turn_id'],
                                              turn['first_user_item_id']), 175)
                if request and len(recent) < 3:
                    recent.append({
                        'text': request,
                        'turnStatus': turn['status'],
                        'at': _timestamp(turn['started_at']),
                    })
            latest = turns[0]['status'] if turns else 'unknown'
            sessions.append({
                'id': row['id'], 'name': name, 'group': group,
                'status': 'active' if latest == 'inProgress' else
                          'attention' if latest in ('needsInput', 'failed') else 'idle',
                'latestTurnStatus': latest, 'updatedAt': _timestamp(row['updated_at_ms']),
                'createdAt': _timestamp(row['created_at_ms']),
                'recentTasks': recent, 'lastReport': last_report,
                'children': [], 'parentId': None,
                'source': 'Codex Local session recording',
            })
        by_id = {session['id']: session for session in sessions}
        for edge in state.execute('SELECT parent_thread_id,child_thread_id,status '
                                  'FROM thread_spawn_edges'):
            parent = by_id.get(edge['parent_thread_id'])
            if not parent:
                continue
            child = state.execute(
                'SELECT id,name,title,agent_nickname,agent_role,agent_path,updated_at_ms '
                'FROM threads WHERE id=?', (edge['child_thread_id'],)).fetchone()
            if not child:
                continue
            parent['children'].append({
                'id': child['id'],
                'name': _compact(child['name'] or child['agent_nickname'] or
                                 child['agent_path'] or child['title'], 65) or 'An unnamed adjunct session.',
                'role': child['agent_role'], 'edgeStatus': edge['status'],
                'updatedAt': _timestamp(child['updated_at_ms']),
            })
            if child['id'] in by_id:
                by_id[child['id']]['parentId'] = parent['id']
        sessions.sort(key=lambda s: s['updatedAt'] or '', reverse=True)
        return sessions, [], _timestamp(state_path.stat().st_mtime_ns // 10**6)
    except (sqlite3.Error, ValueError, json.JSONDecodeError) as error:
        return [], [f'The Codex session failed to visit: {type(error).__name__}'], None
    finally:
        history.close()
        state.close()


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _run_rows(project):
    root = project / 'reports/experiments-run'
    candidates = [root / run_id for run_id in RUN_NAMES]
    baseline = max((path.joinpath('state.json').stat().st_mtime for path in candidates
                    if path.joinpath('state.json').is_file()), default=0)
    recent = sorted((path for path in root.glob('*/state.json')
                     if path.parent.name not in RUN_NAMES and path.stat().st_mtime > baseline),
                    key=lambda p: p.stat().st_mtime, reverse=True)[:5] if root.is_dir() else []
    candidates.extend(path.parent for path in recent)
    runs = []
    for folder in dict.fromkeys(candidates):
        state_path = folder / 'state.json'
        state = _read_json(state_path)
        if not isinstance(state, dict):
            continue
        models = state.get('models') or {}
        counts = [m.get('request_counts') or {} for m in models.values()
                  if isinstance(m, dict)]
        evaluation = state.get('evaluation') or {}
        analysis = state.get('analysis') or {}
        full = state.get('full_pipeline') or {}
        planned = max((c.get('total') or c.get('succeeded') or 0 for c in counts),
                      default=0) or evaluation.get('responses')
        completed = max((c.get('completed') or c.get('succeeded') or 0 for c in counts),
                        default=0) or evaluation.get('responses')
        analysis_status = analysis.get('status')
        if analysis_status == 'COMPLETE' and full.get('status') in (None, 'COMPLETE'):
            state_label = 'complete'
        elif analysis_status == 'BLOCKED':
            state_label = 'blocked'
        elif full.get('status') == 'NEEDS_REVIEW' or analysis_status == 'PARTIAL':
            state_label = 'attention'
        elif analysis_status is None and (evaluation.get('status') == 'EVALUATION_COMPLETE'
                                           or state.get('status') == 'FINISHED'):
            state_label = 'pending'
        elif state.get('status') == 'FINISHED':
            state_label = 'attention'
        else:
            state_label = 'running'
        runs.append({
            'id': folder.name, 'name': RUN_NAMES.get(folder.name, folder.name),
            'status': state_label, 'runStatus': state.get('status'),
            'evaluationStatus': evaluation.get('status') or
                                ('FINISHED' if counts and completed else None),
            'analysisStatus': analysis_status,
            'fullPipelineStatus': full.get('status'),
            'pauseReason': full.get('analysis_execution'),
            'reason': analysis.get('reason'),
            'planned': planned, 'completed': completed,
            'analysisRequests': analysis.get('requests'),
            'analysisValid': analysis.get('valid'),
            'analysisIssueCounts': analysis.get('statuses') or {},
            'updatedAt': _timestamp(state_path.stat().st_mtime_ns // 10**6),
            'sourceRef': 'run:' + folder.name,
            'sourcePath': str(state_path.relative_to(project)),
        })
    runs.sort(key=lambda r: r['updatedAt'] or '', reverse=True)
    return runs


def _table_cells(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def _task_rows(project, runs):
    tasks = []
    issues = project / 'docs/01-dataset/99-open-issues.md'
    if issues.is_file():
        for line in issues.read_text().splitlines():
            if not line.startswith('|OPEN-'):
                continue
            cells = _table_cells(line)
            if len(cells) < 4:
                continue
            issue_id = cells[0].split(' · ')[0]
            tasks.append({
                'id': issue_id, 'title': _compact(cells[1], 110),
                'detail': _compact(cells[3], 210), 'status': 'open',
                'group': 'dataset', 'relatedSessionId': DATASET_SESSION,
                'sourceRef': 'dataset-open-issues',
                'sourcePath': 'docs/01-dataset/99-open-issues.md',
            })
    for run in runs:
        if run['status'] == 'complete':
            continue
        if run['status'] == 'blocked':
            title = run['name'] + ' · Block the analysis'
            detail = 'The reason: ' + (run['reason'] or 'I need to check the status file.')
        elif run['pauseReason'] == 'PAUSED_BY_USER':
            title = run['name'] + ' · Analysis user stop'
            detail = 'Some of the results are saved and restarted, following user instructions.'
        elif run['status'] == 'pending':
            title = run['name'] + ' · Analysis completed No record'
            detail = 'We need to distinguish between the state of the grass collection and the start of the analysis.'
        else:
            title = run['name'] + ' · Follow-up status check'
            detail = 'You need to check the saved run.'
        tasks.append({
            'id': 'run-' + run['id'], 'title': title, 'detail': detail,
            'status': run['status'], 'group': 'analysis',
            'relatedSessionId': EXPERIMENT_SESSION,
            'sourceRef': run['sourceRef'], 'sourcePath': run['sourcePath'],
        })
    meetings = sorted((project / 'reports/run').glob('meeting-*/MINUTES.md'))
    if meetings:
        meeting = meetings[-1]
        content = meeting.read_text()
        section = content.split('## \ub2e4\uc74c\uc5d0 \ud560 \uc77c', 1)
        if len(section) == 2:
            section = section[1].split('\n## ', 1)[0]
            for number, line in enumerate(section.splitlines()):
                if not line.startswith('|') or '\uc0c1\ud0dc: \ud560 \uc77c' not in line:
                    continue
                cells = _table_cells(line)
                if len(cells) < 2:
                    continue
                description = re.split('\uc0b0\ucd9c\ubb3c:|\uae30\ud55c:|\\*\\*\uc0c1\ud0dc:', cells[1])[0]
                tasks.append({
                    'id': f'{meeting.parent.name}-task-{number}',
                    'title': _compact(description, 125),
                    'detail': _compact(cells[1], 215),
                    'status': 'decision' if '\ud655\uc815' in cells[1] else 'open',
                    'group': 'research', 'relatedSessionId': MEETING_SESSION,
                    'sourceRef': 'latest-meeting',
                    'sourcePath': str(meeting.relative_to(project)),
                })
    paper = project / 'paper/README.md'
    if paper.is_file() and '\ubd84\uc11d \uacb0\uacfc\uc640 \uacb0\ub860\uc740 \uacf5\ub780' in paper.read_text():
        tasks.append({
            'id': 'paper-results-conclusion',
            'title': 'The results of the paper analysis; the proof of the conclusion',
            'detail': 'The two paragraphs in the current petition are absurd, and you have to write them down after you have confirmed the interpretation and the argument.',
            'status': 'pending', 'group': 'research',
            'relatedSessionId': PAPER_SESSION,
            'sourceRef': 'paper-index', 'sourcePath': 'paper/README.md',
        })
    priority = {'blocked': 0, 'attention': 1, 'decision': 2,
                'running': 3, 'pending': 4, 'open': 5}
    tasks.sort(key=lambda task: (priority.get(task['status'], 8), task['id']))
    return tasks


def _dataset_snapshot(project):
    candidates = sorted((project / 'reports/run').glob('*/full-pipeline-status.json'),
                        key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        report = path.parent / 'RESULTS.md'
        if not report.is_file():
            continue
        text = report.read_text()
        original = re.search('\uc6d0\ubb38\\s+([\\d,]+)\ubb38\ud56d', text)
        approved = re.search('Preparation \uc2b9\uc778\\s+([\\d,]+)\ubb38\ud56d', text)
        generation_section = text.split('## Generation', 1)
        generation = ([_table_cells(line) for line in generation_section[1].splitlines()
                       if line.startswith('|3\ucc28|')] if len(generation_section) == 2 else [])
        gen_pass = gen_fail = None
        if generation:
            cells = generation[-1]
            if len(cells) >= 6:
                gen_pass, gen_fail = [int(x.replace(',', '')) for x in cells[3:5]]
        return {
            'run': path.parent.name,
            'status': (_read_json(path) or {}).get('status'),
            'originals': int(original.group(1).replace(',', '')) if original else None,
            'preparationPass': int(approved.group(1).replace(',', '')) if approved else None,
            'generationPass': gen_pass, 'generationFail': gen_fail,
            'sourcePath': str(report.relative_to(project)),
            'updatedAt': _timestamp(report.stat().st_mtime_ns // 10**6),
        }
    return None


def _probe_service(item):
    from urllib.request import Request
    url = f"http://127.0.0.1:{item['port']}{item['probe']}"
    try:
        with urlopen(Request(url, headers={'Accept': 'application/json'}), timeout=0.65) as response:
            viewer = response.headers.get('X-Finarch-Viewer')
            if item['id'] != 'experiments':
                payload = json.loads(response.read(2048))
                viewer = payload.get('viewer')
            status = 'online' if response.status == 200 and viewer == item['id'] else 'unknown'
    except (TimeoutError, HTTPError, URLError, OSError, ValueError):
        status = 'unavailable'
    return {**item, 'status': status}


def _services():
    items = [
        {'id': 'dataset', 'name': 'The data set', 'port': 8893, 'probe': '/api/health'},
        {'id': 'experiments', 'name': 'Experiment', 'port': 8894, 'probe': '/'},
        {'id': 'dashboard', 'name': 'The dashboard.', 'port': 8895, 'probe': '/api/health'},
        {'id': 'research', 'name': 'Research data', 'port': 8896, 'probe': '/api/health'},
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        checked = list(pool.map(_probe_service, (item for item in items if item['id'] != 'dashboard')))
    checked.insert(2, {**items[2], 'status': 'online'})
    return checked


def load_project_data(project=PROJECT, codex_home=None):
    """Build one current, read-only snapshot for the project site."""
    project = Path(project).resolve()
    codex_home = Path(codex_home or os.environ.get('CODEX_HOME') or Path.home() / '.codex')
    sessions, warnings, session_updated = _read_sessions(project, codex_home)
    runs = _run_rows(project)
    tasks = _task_rows(project, runs)
    return {
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'sessionStoreUpdatedAt': session_updated,
        'scope': 'Local Codex session + saved run record of this project',
        'groups': GROUPS, 'sessions': sessions, 'runs': runs,
        'tasks': tasks, 'dataset': _dataset_snapshot(project),
        'services': _services(), 'warnings': warnings,
        'notes': [
            'The task group is the parent-child classification, and the parent-spawn sequence actually only shows the Codex spawn record.',
            'Completion of the session response does not imply implementation, verification, or user approval of the request.',
            'The session of the other host may not be in the local session list. The save run state is displayed separately.',
        ],
    }


def source_bytes(ref, project=PROJECT):
    """Return only a named evidence file, never an arbitrary caller supplied path."""
    project = Path(project).resolve()
    fixed = {
        'dataset-open-issues': 'docs/01-dataset/99-open-issues.md',
        'paper-index': 'paper/README.md',
    }
    if ref in fixed:
        path = project / fixed[ref]
    elif ref == 'latest-meeting':
        meetings = sorted((project / 'reports/run').glob('meeting-*/MINUTES.md'))
        if not meetings:
            raise ValueError('NO_MEETING')
        path = meetings[-1]
    elif re.fullmatch(r'run:[a-zA-Z0-9-]{8,80}', ref or ''):
        path = project / 'reports/experiments-run' / ref[4:] / 'state.json'
    else:
        raise ValueError('UNKNOWN_PROJECT_SOURCE')
    if path.is_symlink() or not path.resolve().is_relative_to(project) or not path.is_file():
        raise ValueError('INVALID_PROJECT_SOURCE')
    if path.stat().st_size > 2_000_000:
        raise ValueError('PROJECT_SOURCE_TOO_LARGE')
    return path.read_bytes(), ('application/json; charset=utf-8' if path.suffix == '.json'
                               else 'text/plain; charset=utf-8')
