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
    {'id': 'coordination', 'name': '총괄', 'description': '진행과 미해결 사항'},
    {'id': 'dataset', 'name': '데이터셋 제작', 'description': '원천·Preparation·Generation·선정'},
    {'id': 'evaluation', 'name': '대상 모델 평가', 'description': '입력·요청·풀이·형식 검사'},
    {'id': 'analysis', 'name': '결과 분석', 'description': 'A01 취합·A02 비교·A03 해석'},
    {'id': 'research', 'name': '연구·논문', 'description': '기존 연구·회의·원고'},
    {'id': 'viewer', 'name': '화면·운영', 'description': '자료 뷰어와 서버'},
    {'id': 'unclassified', 'name': '분류 확인', 'description': '새로 발견한 관련 세션'},
]
SESSION_MAP = json.loads((HERE / 'session-map.json').read_text())['sessions']
RELEVANT_NAME = re.compile(
    r'fin.?arch|finject|dataset|데이터셋|금융|논문|실험|분석|뷰어|viewer|'
    r'서버|pipeline|파이프라인|프로젝트|회의록|robustness', re.I)
RUN_NAMES = {
    '20260928-exp-001-luna': 'Luna · 1,080 원문',
    '20260927-exp-008-haiku': 'Haiku · 557 원문',
    '20260927-exp-007-luna': 'Luna · 557 원문',
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
        return [], ['Codex 로컬 세션 기록을 찾지 못했습니다.'], None
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
                'source': 'Codex 로컬 세션 기록',
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
                                 child['agent_path'] or child['title'], 65) or '이름 없는 보조 세션',
                'role': child['agent_role'], 'edgeStatus': edge['status'],
                'updatedAt': _timestamp(child['updated_at_ms']),
            })
            if child['id'] in by_id:
                by_id[child['id']]['parentId'] = parent['id']
        sessions.sort(key=lambda s: s['updatedAt'] or '', reverse=True)
        return sessions, [], _timestamp(state_path.stat().st_mtime_ns // 10**6)
    except (sqlite3.Error, ValueError, json.JSONDecodeError) as error:
        return [], [f'Codex 세션 조회 실패: {type(error).__name__}'], None
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
            title = run['name'] + ' · Analysis 차단'
            detail = '사유: ' + (run['reason'] or '상태 기록 확인 필요')
        elif run['pauseReason'] == 'PAUSED_BY_USER':
            title = run['name'] + ' · Analysis 사용자 중지'
            detail = '일부 결과가 저장됐으며 재개 여부는 사용자 지시를 따릅니다.'
        elif run['status'] == 'pending':
            title = run['name'] + ' · Analysis 완료 기록 없음'
            detail = '풀이 수집 상태와 분석 시작 여부를 구분해 확인해야 합니다.'
        else:
            title = run['name'] + ' · 후속 상태 확인'
            detail = '저장된 실행 상태를 확인해야 합니다.'
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
        section = content.split('## 다음에 할 일', 1)
        if len(section) == 2:
            section = section[1].split('\n## ', 1)[0]
            for number, line in enumerate(section.splitlines()):
                if not line.startswith('|') or '상태: 할 일' not in line:
                    continue
                cells = _table_cells(line)
                if len(cells) < 2:
                    continue
                description = re.split(r'산출물:|기한:|\*\*상태:', cells[1])[0]
                tasks.append({
                    'id': f'{meeting.parent.name}-task-{number}',
                    'title': _compact(description, 125),
                    'detail': _compact(cells[1], 215),
                    'status': 'decision' if '확정' in cells[1] else 'open',
                    'group': 'research', 'relatedSessionId': MEETING_SESSION,
                    'sourceRef': 'latest-meeting',
                    'sourcePath': str(meeting.relative_to(project)),
                })
    paper = project / 'paper/README.md'
    if paper.is_file() and '분석 결과와 결론은 공란' in paper.read_text():
        tasks.append({
            'id': 'paper-results-conclusion',
            'title': '논문 분석 결과·결론 근거 확정',
            'detail': '현행 원고에서 두 절은 공란입니다. 해석과 주장을 확정한 뒤 작성해야 합니다.',
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
        original = re.search(r'원문\s+([\d,]+)문항', text)
        approved = re.search(r'Preparation 승인\s+([\d,]+)문항', text)
        generation_section = text.split('## Generation', 1)
        generation = ([_table_cells(line) for line in generation_section[1].splitlines()
                       if line.startswith('|3차|')] if len(generation_section) == 2 else [])
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
        {'id': 'dataset', 'name': '데이터셋', 'port': 8893, 'probe': '/api/health'},
        {'id': 'experiments', 'name': '실험', 'port': 8894, 'probe': '/'},
        {'id': 'dashboard', 'name': '대시보드', 'port': 8895, 'probe': '/api/health'},
        {'id': 'research', 'name': '연구 자료', 'port': 8896, 'probe': '/api/health'},
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
        'scope': '로컬 Codex 세션 + 이 프로젝트의 저장된 실행 기록',
        'groups': GROUPS, 'sessions': sessions, 'runs': runs,
        'tasks': tasks, 'dataset': _dataset_snapshot(project),
        'services': _services(), 'warnings': warnings,
        'notes': [
            '업무 묶음은 대시보드 분류입니다. 실제 부모·자식은 Codex spawn 기록만 표시합니다.',
            '세션의 응답 완료는 요청의 구현·검증·사용자 승인을 뜻하지 않습니다.',
            '다른 호스트의 세션은 로컬 세션 목록에 없을 수 있습니다. 저장 run 상태는 별도로 표시합니다.',
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
