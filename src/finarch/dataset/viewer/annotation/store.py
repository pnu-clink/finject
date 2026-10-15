"""Date-folder ingestion, immutable originals, repair logs and cached views."""
from datetime import datetime
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import threading
from zoneinfo import ZoneInfo

from .agreement import build_view, align_scopes, dataset_label
from .normalize import normalize, TYPES
from .sources import attach_sources

PROJECT = Path(__file__).resolve().parents[5]
TEMPLATES = PROJECT / 'src/finarch/documentation/templates'
MAX_BYTES = 16 * 1024 * 1024
LOCK = threading.RLock()


def today():
    return datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d')


def safe_directory(root, date, create=False):
    if not isinstance(date, str) or not re.fullmatch(r'\d{8}', date): raise ValueError('날짜는 YYYYMMDD 형식이어야 합니다.')
    datetime.strptime(date, '%Y%m%d')
    root = Path(root)
    if root.is_symlink(): raise ValueError('Annotation root cannot be a symlink.')
    directory = root / date
    if directory.is_symlink(): raise ValueError('Annotation date cannot be a symlink.')
    if create: directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir(): raise ValueError('Annotation date folder does not exist.')
    return directory


def list_dates(root):
    if not Path(root).is_dir(): return []
    return sorted([path.name for path in Path(root).iterdir() if path.is_dir() and not path.is_symlink()
                   and re.fullmatch(r'\d{8}', path.name)], reverse=True)


@lru_cache(maxsize=48)
def read_document(path, stamp, size):
    source = Path(path)
    if source.is_symlink() or size > MAX_BYTES: raise ValueError('Invalid annotation source or file size.')
    raw = source.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
    result = {'id': digest, 'sha256': digest, 'filename': source.name, 'bytes': len(raw)}
    try: result.update(normalize(raw))
    except (ValueError, TypeError, UnicodeError) as error:
        result.update(reviewer=None, changes=[], issues=[{'code': 'UNREADABLE_EXPORT',
            'message': str(error), 'source_index': None, 'case': None, 'variant': None}], evaluations=None)
    return result


def documents(root, date):
    directory = safe_directory(root, date)
    return align_scopes([read_document(str(path), path.stat().st_mtime_ns, path.stat().st_size)
                         for path in sorted(directory.glob('*.json')) if path.is_file() and not path.is_symlink()])


def comparison_catalog(root):
    """List independent comparisons across dates without loading generation evidence."""
    choices = []; seen = set()
    for date in list_dates(root):
        for group in build_view(documents(root, date)):
            identity = (group['id'], tuple(sorted(group['file_ids'])))
            if identity in seen:
                continue
            seen.add(identity)
            choices.append({'date': date, 'group': group['id'], 'dataset_label': dataset_label(group),
                            'run': group['run'], 'round': group['round'], 'cases': len(group['cases']),
                            'reviewers': group['reviewers']})
    return {'comparisons': choices}


def view(root, date=None, included=None):
    dates = list_dates(root); date = date or (dates[0] if dates else today())
    docs = documents(root, date) if date in dates else []
    selected = docs if included is None else [doc for doc in docs if doc['id'] in included]
    files = [{key: doc.get(key) for key in ('id', 'filename', 'sha256', 'bytes', 'reviewer', 'source_format', 'run', 'round', 'package_id')}
             | {'records': len(doc.get('evaluations') or []), 'repairs': len(doc['changes']), 'issues': doc['issues'],
                'error': doc.get('evaluations') is None, 'included': included is None or doc['id'] in included} for doc in docs]
    from .reviews import read, empty, attach
    reviews = read(root, date) if docs else empty()
    groups = attach(attach_sources(build_view(selected), Path(root).parent / 'reports/run'), reviews)
    for group in groups:
        group['dataset_label'] = dataset_label(group)
    return {'format': 'finarch-annotation-view-v1', 'date': date, 'dates': dates, 'path': str(Path(root) / date),
            'files': files, 'groups': groups,
            'manager_revision': reviews['revision'],
            'types': [{'variant': v, 'label': l, 'title': t} for v, l, t in TYPES],
            'generated_at': datetime.now(ZoneInfo('Asia/Seoul')).isoformat()}


def g02_links(root, date, group_id, case_name, included=None):
    from .links import case_links
    dates = list_dates(root); date = date or (dates[0] if dates else today())
    docs = documents(root, date) if date in dates else []
    selected = docs if included is None else [doc for doc in docs if doc['id'] in included]
    group = next((group for group in build_view(selected) if group['id'] == group_id), None)
    item = next((item for item in group['cases'] if item['case'] == case_name), None) if group else None
    if item is None:
        raise ValueError('Unknown annotation group or case.')
    # Source matching is needed only for the selected case, not all imported cases.
    groups = [{**group, 'cases': [item]}]
    runs_root = Path(root).parent / 'reports/run'
    attach_sources(groups, runs_root)
    return case_links(groups, runs_root, group_id, case_name)


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    if path.is_symlink() or temporary.is_symlink(): raise ValueError('Output cannot be a symlink.')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def refresh(root, date):
    with LOCK:
        directory = safe_directory(root, date, create=True)
        for subdir in ('normalized', '_manager'):
            if (directory / subdir).is_symlink(): raise ValueError('Output directory cannot be a symlink.')
            (directory / subdir).mkdir(exist_ok=True)
        docs = documents(root, date); metadata = directory / '_manager'
        logfile = metadata / 'normalization-log.jsonl'
        if logfile.is_symlink(): raise ValueError('Log cannot be a symlink.')
        for doc in docs:
            target = metadata / (doc['id'] + '.json')
            previous = json.loads(target.read_text()) if target.exists() else None
            if previous is None or (previous.get('normalization_version'), previous.get('normalization_sha256')) != (doc.get('normalization_version'), doc.get('normalization_sha256')):
                if previous is not None:
                    history = metadata / (doc['id'] + '-previous-' + hashlib.sha256(target.read_bytes()).hexdigest()[:12] + '.json')
                    if not history.exists(): write_json(history, previous)
                write_json(target, doc)
                if doc.get('repaired') is not None:
                    write_json(directory / 'normalized' / (doc['id'][:12] + '-' + doc['filename']), doc['repaired'])
                with logfile.open('a') as stream:
                    for change in doc['changes']:
                        stream.write(json.dumps({'source_sha256': doc['sha256'], 'filename': doc['filename'],
                            'normalization_version': doc.get('normalization_version'), **change}, ensure_ascii=False) + '\n')
                    stream.write(json.dumps({'event': 'NORMALIZED' if doc.get('evaluations') is not None else 'INPUT_ERROR',
                        'source_sha256': doc['sha256'], 'filename': doc['filename'], 'repairs': len(doc['changes']),
                        'issues': len(doc['issues']), 'time': datetime.now(ZoneInfo('Asia/Seoul')).isoformat()}, ensure_ascii=False) + '\n')
        result = view(root, date)
        summary = {key: result[key] for key in ('format', 'date', 'path', 'generated_at', 'files')}
        summary['groups'] = [{key: group[key] for key in ('id', 'run', 'round', 'package_id', 'reviewers', 'metrics', 'totals', 'flagged_entries', 'disagreement_cases', 'source_types')}
                             | {'cases': len(group['cases'])} for group in result['groups']]
        write_json(metadata / 'summary.json', summary)
        write_json(metadata / 'comparison.json', result)
        template = (TEMPLATES / 'annotation-date-readme.md').read_text()
        for before, after in (('__DATE__', date), ('__FILES__', str(len(docs))),
                              ('__REPAIRS__', str(sum(len(doc['changes']) for doc in docs))),
                              ('__ISSUES__', str(sum(len(doc['issues']) for doc in docs)))):
            template = template.replace(before, after)
        (directory / 'README.md').write_text(template)
        for folder, template_name in (('normalized', 'annotation-normalized-readme.md'), ('_manager', 'annotation-cache-readme.md')):
            (directory / folder / 'README.md').write_text((TEMPLATES / template_name).read_text())
        return result


def upload(root, date, files):
    if not isinstance(files, list) or not 1 <= len(files) <= 20: raise ValueError('Select between 1 and 20 JSON files.')
    with LOCK:
        directory = safe_directory(root, date, create=True)
        for file in files:
            name = file.get('name'); text = file.get('text')
            if not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name or not name.endswith('.json'):
                raise ValueError('Invalid JSON filename.')
            if not isinstance(text, str) or not 0 < len(text.encode()) <= MAX_BYTES: raise ValueError('Invalid JSON content or size.')
        for file in files:
            raw = file['text'].encode(); target = directory / file['name']
            if target.exists() and (target.is_symlink() or target.read_bytes() != raw):
                target = directory / (Path(file['name']).stem + '-' + hashlib.sha256(raw).hexdigest()[:12] + '.json')
            if target.is_symlink(): raise ValueError('Input cannot be a symlink.')
            if not target.exists():
                with target.open('xb') as stream: stream.write(raw)
        return refresh(root, date)


def file_data(root, date, ident, kind):
    doc = next((doc for doc in documents(root, date) if doc['id'] == ident), None)
    if not doc: raise ValueError('Unknown annotation file.')
    if kind == 'original': return (safe_directory(root, date) / doc['filename']).read_bytes(), doc['filename']
    if kind == 'repaired':
        if doc.get('repaired') is None: raise ValueError('This export could not be repaired safely.')
        return json.dumps(doc['repaired'], ensure_ascii=False, indent=2).encode(), 'normalized-' + doc['filename']
    if kind == 'log':
        return json.dumps({key: doc[key] for key in ('filename', 'sha256', 'changes', 'issues')}, ensure_ascii=False, indent=2).encode(), 'repair-log.json'
    raise ValueError('Unknown annotation file kind.')
