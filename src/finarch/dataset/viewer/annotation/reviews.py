"""Independent manager notes, input-bound review history and recipient exports."""
from copy import deepcopy
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import uuid
import zipfile
from zoneinfo import ZoneInfo

from .agreement import build_view
from .normalize import parse_export
from .store import documents, safe_directory, write_json, LOCK

FORMAT = 'finarch-annotation-manager-reviews-v1'
KINDS = ('CHECKED', 'RECHECK', 'WHY', 'REPAIR')
MAX_NOTE = 10000


def timestamp():
    return datetime.now(ZoneInfo('Asia/Seoul')).isoformat()


def empty():
    return {'format': FORMAT, 'revision': 0, 'groups': {}}


def metadata(root, date, create=False):
    parent = safe_directory(root, date) / '_manager'
    if parent.is_symlink():
        raise ValueError('Manager directory cannot be a symlink.')
    if create:
        parent.mkdir(exist_ok=True)
    for name in ('reviews.json', 'review-history.jsonl'):
        if (parent / name).is_symlink():
            raise ValueError('Manager review file cannot be a symlink.')
    return parent


def read(root, date):
    path = metadata(root, date) / 'reviews.json'
    if not path.exists():
        return empty()
    value = json.loads(path.read_text())
    if (not isinstance(value, dict) or value.get('format') != FORMAT or
            type(value.get('revision')) is not int or value['revision'] < 0 or
            not isinstance(value.get('groups'), dict)):
        raise ValueError('관리자 기록 형식을 확인해 주세요. 원본 기록은 보존됩니다.')
    return value


def group_view(group, state):
    saved = state['groups'].get(group['id'], {})
    active_files = set(group['file_ids'])
    result = {}
    for name, review in saved.get('cases', {}).items():
        entries = [{**entry, 'stale': not set(entry['file_ids']).issubset(active_files)}
                   for entry in review.get('entries', [])]
        checked = bool(review.get('checked'))
        changed = set(review.get('file_ids', [])) != active_files
        result[name] = {**review, 'checked': checked and not changed,
                        'stale_checked': checked and changed,
                        'stale_note': bool(review.get('note')) and changed, 'entries': entries}
    return {'revision': state['revision'], 'group': group['id'], 'cases': result,
            'recipients': saved.get('recipients', [])}


def attach(groups, state):
    for group in groups:
        data = group_view(group, state)
        group['manager_reviews'] = data['cases']
        group['manager_recipients'] = data['recipients']
    return groups


def select(root, date, group_id, included=None):
    docs = documents(root, date)
    full = build_view(docs)
    if included is not None:
        if (not isinstance(included, list) or not included or
                any(not isinstance(value, str) for value in included) or
                not set(included).issubset({doc['id'] for doc in docs})):
            raise ValueError('입력 파일이 변경되었습니다. 새로고침 후 다시 확인해 주세요.')
        selected = build_view([doc for doc in docs if doc['id'] in included])
    else:
        selected = full
    group = next((value for value in selected if value['id'] == group_id), None)
    complete = next((value for value in full if value['id'] == group_id), None)
    if not group or not complete:
        raise ValueError('Unknown annotation comparison group.')
    return docs, group, complete


def note(value, required=False):
    if not isinstance(value, str) or len(value) > MAX_NOTE:
        raise ValueError('관리자 주석은 10,000자 이하로 입력해 주세요.')
    if required and not value.strip():
        raise ValueError('수정할 내용을 관리자 주석에 입력해 주세요.')
    return value


def source_snapshot(root, date, docs, row, reviewer):
    cells = {name: cell for name, cell in row['cells'].items() if reviewer is None or name == reviewer}
    ids = {ident for cell in cells.values() for ident in cell.get('file_ids', [])}
    # Missing ratings still identify the intended reviewer's submission.
    if not ids:
        ids = {doc['id'] for doc in docs if doc.get('reviewer') == reviewer}
    sources = []
    for doc in docs:
        if doc['id'] not in ids:
            continue
        raw_bytes = (safe_directory(root, date) / doc['filename']).read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != doc['sha256']:
            raise ValueError('입력 파일이 변경되었습니다. 새로고침 후 다시 확인해 주세요.')
        raw, _ = parse_export(raw_bytes)
        # Inspect the actual contract rather than guessing its record field.
        field = 'labels' if isinstance(raw.get('labels'), list) else 'evaluations'
        records = [deepcopy(raw[field][entry['source_index']]) for entry in doc['evaluations']
                   if entry['case'] == row['case'] and entry['variant'] == row['variant']]
        sources.append({'id': doc['id'], 'filename': doc['filename'], 'sha256': doc['sha256'],
                        'reviewer': doc.get('reviewer'), 'records': records})
    return sources, {name: deepcopy(cell) for name, cell in cells.items()}


def save(root, payload):
    if not isinstance(payload, dict):
        raise ValueError('Invalid manager review request.')
    date = payload['date']
    with LOCK:
        docs, group, complete = select(root, date, payload['group'], payload.get('files'))
        item = next((value for value in group['cases'] if value['case'] == payload['case']), None)
        if item is None:
            raise ValueError('Unknown annotation case.')
        state = read(root, date)
        if type(payload.get('revision')) is not int or payload['revision'] != state['revision']:
            raise ValueError('다른 화면에서 관리자 기록이 변경되었습니다. 새로고침 후 다시 저장해 주세요.')
        saved = state['groups'].setdefault(group['id'], {'recipients': [], 'cases': {}})
        for reviewer in complete['reviewers']:
            if not any(value['reviewer'] == reviewer for value in saved['recipients']):
                saved['recipients'].append({'reviewer': reviewer, 'filename': 'annotator' + str(len(saved['recipients']) + 1) + '.json'})
        review = saved['cases'].setdefault(item['case'], {'checked': False, 'note': '', 'entries': []})
        before = deepcopy(review)
        operation = payload.get('operation')
        now = timestamp()
        if operation == 'case':
            if type(payload.get('checked')) is not bool:
                raise ValueError('Invalid manager confirmation flag.')
            review.update(checked=payload['checked'], note=note(payload.get('note', '')),
                          file_ids=sorted(group['file_ids']), updated_at=now)
        elif operation == 'entry':
            variant = payload.get('variant')
            row = next((value for value in item['rows'] if value['variant'] == variant), None)
            kind = payload.get('kind')
            reviewer = payload.get('reviewer')
            if not row or kind not in KINDS:
                raise ValueError('Invalid manager review type or request kind.')
            if kind in ('CHECKED', 'REPAIR'):
                if reviewer is not None:
                    raise ValueError('확인 완료와 문항 수정은 평가자를 지정하지 않습니다.')
            elif reviewer not in group['reviewers']:
                raise ValueError('문의할 평가자를 선택해 주세요.')
            text = note(payload.get('note', ''), required=kind == 'REPAIR')
            ident = payload.get('id')
            previous = next((entry for entry in review['entries'] if entry['id'] == ident), None)
            if ident is not None and previous is None:
                raise ValueError('Unknown manager note.')
            snapshots, cells = source_snapshot(root, date, [doc for doc in docs if doc['id'] in group['file_ids']], {**row, 'case': item['case']}, reviewer)
            if not snapshots:
                raise ValueError('요청과 연결할 평가 입력 파일이 없습니다.')
            entry = {'id': ident or uuid.uuid4().hex, 'variant': variant, 'label': row['label'],
                     'title': row['title'], 'kind': kind, 'reviewer': reviewer, 'note': text,
                     'file_ids': [value['id'] for value in snapshots], 'sources': snapshots, 'ratings': cells,
                     'created_at': previous['created_at'] if previous else now, 'updated_at': now}
            review['entries'] = [entry if old['id'] == ident else old for old in review['entries']] if previous else review['entries'] + [entry]
            review['updated_at'] = now
        elif operation == 'remove':
            ident = payload.get('id')
            if not any(entry['id'] == ident for entry in review['entries']):
                raise ValueError('Unknown manager note.')
            review['entries'] = [entry for entry in review['entries'] if entry['id'] != ident]
            review['updated_at'] = now
        else:
            raise ValueError('Invalid manager review operation.')
        state['revision'] += 1
        parent = metadata(root, date, create=True)
        event = {'revision': state['revision'], 'time': now, 'group': group['id'],
                 'case': item['case'], 'operation': operation, 'before': before, 'after': deepcopy(review)}
        # Keep every previous note recoverable even when its active entry is removed.
        with (parent / 'review-history.jsonl').open('a') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        write_json(parent / 'reviews.json', state)
        return group_view(group, state)


def export_files(root, date, group_id, included=None, revision=None):
    with LOCK:
        _, group, _ = select(root, date, group_id, included)
        state = read(root, date)
        if revision is not None and str(state['revision']) != str(revision):
            raise ValueError('관리자 기록이 변경되었습니다. 내보내기 목록을 다시 열어 주세요.')
        data = group_view(group, state)
        current_cases = {item['case'] for item in group['cases']}
        requests = []
        stale = 0
        for case, review in data['cases'].items():
            for entry in review['entries']:
                if entry['stale'] or case not in current_cases:
                    stale += 1
                    continue
                if entry['kind'] != 'CHECKED':
                    requests.append({'case': case, **entry, 'manager_case_note': '' if review.get('stale_note') else review.get('note', '')})
        scope = {key: group.get(key) for key in ('run', 'round', 'package_id')}
        common = {'date': date, 'group': group_id, 'scope': scope,
                  'review_revision': state['revision'], 'exported_at': timestamp()}
        files = []
        from .review_export import render
        evidence = {}
        from .store import g02_links
        for case in dict.fromkeys(entry['case'] for entry in requests):
            evidence[case] = g02_links(root, date, group_id, case, group['file_ids'])['links']
        for entry in requests:
            link = evidence[entry['case']][entry['variant']]
            entry['evidence'] = {'status': link['status'], 'reason': link.get('reason')}
            if link['status'] == 'AVAILABLE':
                target = Path(root).parent / link['path']
                if target.is_symlink():
                    raise ValueError('Export context cannot be a symlink.')
                observation = json.loads(target.read_text())
                digest = hashlib.sha256(json.dumps({key: observation.get(key) for key in ('context', 'question')}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                if digest != link['context_sha256']:
                    raise ValueError('생성 본문이 변경되었습니다. 내보내기를 다시 열어 주세요.')
                input_path = target.parent / '01-input.json'
                source = json.loads(input_path.read_text()) if input_path.is_file() and not input_path.is_symlink() else {}
                entry['evidence'].update(question=observation.get('question') or source.get('question'),
                                         context=observation['context'], input_context=source.get('context'),
                                         run=link['run'], round=link['origin_round'],
                                         context_sha256=link['context_sha256'])
        for recipient in data['recipients']:
            entries = [entry for entry in requests if entry['reviewer'] == recipient['reviewer'] and entry['kind'] in ('RECHECK', 'WHY')]
            if entries:
                stem = Path(recipient['filename']).stem
                name = re.sub(r'[/\\<>:"|?*\x00-\x1f]', '_', recipient['reviewer']).strip('. ')[:70] or 'reviewer'
                filename = stem + '_' + name + '.html'
                document = {'format': 'finarch-annotation-review-requests-v1', **common,
                            'annotator': recipient['reviewer'], 'requests': entries}
                files.append({'filename': filename, 'reviewer': recipient['reviewer'],
                              'kind': 'REVIEWER', 'count': len(entries), 'data': document, 'html': render(document)})
        repairs = [entry for entry in requests if entry['kind'] == 'REPAIR']
        if repairs:
            document = {'format': 'finarch-annotation-repair-requests-v1', **common, 'requests': repairs}
            files.append({'filename': 'repair_' + date + '.html', 'reviewer': None, 'kind': 'REPAIR',
                          'count': len(repairs), 'data': document, 'html': render(document)})
        return {'date': date, 'group': group_id, 'revision': state['revision'],
                'files': files, 'stale_entries': stale, 'recipients': data['recipients']}


def zip_export(result):
    if not result['files']:
        raise ValueError('내보낼 평가자 문의나 문항 수정 주석이 없습니다.')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for item in result['files']:
            archive.writestr(item['filename'], item['html'])
    return stream.getvalue()
