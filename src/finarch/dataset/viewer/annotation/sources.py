"""Attach verified source families without inventing an annotation run scope."""
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

KINDS = ('FinQA', 'TAT-QA', 'FinanceMath', 'FinanceReasoning')
UNKNOWN = 'UNKNOWN'


def source_kind(provenance):
    if not isinstance(provenance, dict):
        return UNKNOWN
    source_id = provenance.get('source_id', '')
    if isinstance(source_id, str):
        for prefix, kind in (('CodeFinQA-', 'FinQA'), ('CodeTAT-QA-', 'TAT-QA'),
                             ('FinanceMath-', 'FinanceMath'), ('FinanceReasoning-', 'FinanceReasoning')):
            if source_id.startswith(prefix):
                return kind
    return 'TAT-QA' if provenance.get('dataset') == 'TAT-QA' else UNKNOWN


def file_stamp(path):
    if path.is_symlink() or not path.is_file():
        return None
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


@lru_cache(maxsize=16)
def read_catalog(path, stamp, manifest_stamp):
    source = Path(path)
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    manifest = json.loads((source.parent / 'manifest.json').read_text())
    if manifest.get('files', {}).get('00-input.json', {}).get('sha256') != digest:
        return {}
    rows = json.loads(raw)
    if not isinstance(rows, list):
        return {}
    result = {}
    for row in rows:
        sample = row.get('input', {}) if isinstance(row, dict) else {}
        if not isinstance(sample, dict):
            continue
        provenance = sample.get('provenance', {})
        case = row.get('id')
        if isinstance(case, str) and source_kind(provenance) != UNKNOWN:
            result[case] = {'type': source_kind(provenance), 'source_id': provenance.get('source_id'),
                            'dataset': provenance.get('dataset'), 'sha256': digest}
    return result


@lru_cache(maxsize=8192)
def read_small_json(path, stamp):
    return json.loads(Path(path).read_text())


def read_optional(path):
    stamp = file_stamp(path)
    if stamp is None:
        return None
    try:
        return read_small_json(str(path), stamp)
    except (OSError, ValueError):
        return None


def catalogs(root):
    result = []
    if not root.is_dir() or root.is_symlink():
        return result
    for bundle in sorted(root.iterdir()):
        if not bundle.is_dir() or bundle.is_symlink() or (bundle / 'results').is_symlink():
            continue
        path = bundle / 'results/00-input.json'
        stamp = file_stamp(path)
        manifest_stamp = file_stamp(path.parent / 'manifest.json')
        if stamp is None or manifest_stamp is None:
            continue
        try:
            index = read_catalog(str(path), stamp, manifest_stamp)
        except (OSError, ValueError, TypeError):
            continue
        generation = bundle / '02-generation'
        rounds = sorted((p for p in generation.iterdir() if p.is_dir() and not p.is_symlink()
                         and re.fullmatch(r'\d+-round', p.name)), reverse=True) if generation.is_dir() and not generation.is_symlink() else []
        result.append({'run': bundle.name, 'index': index, 'rounds': rounds, 'path': path})
    return result


def match_edit(item, catalog):
    # An ID alone is not an identity: separate runs reuse test-0001 etc.
    if not re.fullmatch(r'test-\d+', item['case']):
        return None
    for row in item['rows']:
        if not re.fullmatch(r'0[1-7]-[a-z0-9-]+', row['variant']):
            continue
        edits = {(entry['inserted'], entry['removed']) for entry in row['content']
                 if entry['inserted'] or entry['removed']}
        if not edits:
            continue
        for round_path in catalog['rounds']:
            path = round_path / item['case'] / row['variant'] / '02-generate-text/05-patches.json'
            if not path.resolve().is_relative_to(round_path.resolve()):
                continue
            patches = read_optional(path)
            if not isinstance(patches, list) or not patches:
                continue
            if any(not isinstance(patch, dict) or not isinstance(patch.get('text'), str)
                   or not isinstance(patch.get('before'), str) for patch in patches):
                continue
            saved = (''.join(patch['text'] for patch in patches), ''.join(patch['before'] for patch in patches))
            if saved in edits:
                return path
    return None


def scoped_source(root, group, item, available):
    run = group.get('run')
    if not isinstance(run, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', run):
        return None
    catalog = next((value for value in available if value['run'] == run), None)
    if catalog and item['case'] in catalog['index']:
        return {**catalog['index'][item['case']], 'run': run,
                'path': str(catalog['path'].relative_to(root.parent.parent)), 'method': 'EXPLICIT_RUN'}
    round_name = group.get('round')
    if not isinstance(round_name, str) or not re.fullmatch(r'\d+-round', round_name) or not re.fullmatch(r'test-\d+', item['case']):
        return None
    bundle = root / run
    if bundle.is_symlink():
        return None
    for name in ('data.json', '01-source/01-receive-input/01-input.json'):
        path = bundle / '01-preparation' / item['case'] / round_name / name
        if not path.resolve().is_relative_to(bundle.resolve()):
            continue
        sample = read_optional(path)
        provenance = sample.get('provenance', {}) if isinstance(sample, dict) else {}
        kind = source_kind(provenance)
        if kind != UNKNOWN:
            return {'type': kind, 'source_id': provenance.get('source_id'), 'dataset': provenance.get('dataset'),
                    'run': run, 'path': str(path.relative_to(root.parent.parent)),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'method': 'EXPLICIT_RUN_ROUND'}
    return None


def attach_sources(groups, runs_root):
    root = Path(runs_root)
    available = catalogs(root)
    for group in groups:
        for item in group['cases']:
            reference = scoped_source(root, group, item, available) if group.get('run') else None
            if not group.get('run'):
                candidates = []
                for catalog in available:
                    metadata = catalog['index'].get(item['case'])
                    if metadata is None:
                        continue
                    matched = match_edit(item, catalog)
                    if matched is not None:
                        candidates.append({**metadata, 'run': catalog['run'],
                                           'path': str(catalog['path'].relative_to(root.parent.parent)),
                                           'match_path': str(matched.relative_to(root.parent.parent)), 'method': 'EXACT_SAVED_EDIT'})
                identities = {(value['type'], value['source_id'], value['dataset']) for value in candidates}
                if len(identities) == 1:
                    reference = candidates[0]
            item['source_type'] = reference['type'] if reference else UNKNOWN
            item['source_reference'] = reference
        counts = Counter(item['source_type'] for item in group['cases'])
        group['source_types'] = [{'value': kind, 'label': '출처 미확인' if kind == UNKNOWN else kind, 'count': counts[kind]}
                                 for kind in (*KINDS, UNKNOWN) if counts[kind]]
    return groups
