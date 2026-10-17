"""Join registered human judgments to verified ER evidence for rejection review."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from .ea_inverse_export import build_package
from .evaluation_export import inline_json


def verified_json(path, expected_sha256, *, lines=False):
    if path.is_symlink():
        raise ValueError('ER_COMPARISON_SYMLINK')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('ER_COMPARISON_FILE_HASH_MISMATCH')
    if lines:
        return [json.loads(line) for line in raw.decode('utf-8').splitlines() if line]
    return json.loads(raw)


def build_comparison(project, comparison_id=None):
    registry = json.loads((project/'viewer/dataset/ea-inverse-comparisons.json').read_text())
    selected = comparison_id or registry['default']
    entry = next((item for item in registry['comparisons'] if item['id'] == selected), None)
    if entry is None:
        raise ValueError('ER_COMPARISON_NOT_REGISTERED')
    report_root = (project/'reports/dataset-review').resolve()
    folder = report_root/entry['report_directory']
    if folder.is_symlink() or folder.resolve().parent != report_root:
        raise ValueError('ER_COMPARISON_REPORT_PATH')
    summary = verified_json(folder/'summary.json', entry['summary_sha256'])
    rows = verified_json(folder/'comparison.jsonl', entry['comparison_sha256'], lines=True)
    if summary['run'] != entry['run'] or summary['format'] != 'finarch-er-inverse-agreement-v1':
        raise ValueError('ER_COMPARISON_SCOPE')
    if [item['annotator'] for item in summary['inputs']] != entry['annotators'] or \
            [item['sha256'] for item in summary['inputs']] != entry['source_sha256']:
        raise ValueError('ER_COMPARISON_SOURCE_MISMATCH')
    package = build_package(project, entry['run'], summary['snapshot_file'])
    if package['package_id'] != summary['package_id'] or \
            package['snapshot_sha256'] != summary['snapshot_sha256']:
        raise ValueError('ER_COMPARISON_SNAPSHOT_MISMATCH')
    actual = {(case['id'], item['type']): (case, item)
              for case in package['cases'] for item in case['items']}
    keys = [(row['id'], row['type']) for row in rows]
    if len(keys) != len(set(keys)) or set(keys) != set(actual):
        raise ValueError('ER_COMPARISON_ID_COVERAGE')
    counts = {side: Counter() for side in ('first', 'second')}
    mapped = 0
    items = []
    for row in sorted(rows, key=lambda item: (item['id'], item['type'])):
        case, item = actual[(row['id'], row['type'])]
        if row['content_sha256'] != item['content_sha256']:
            raise ValueError('ER_COMPARISON_CONTENT_MISMATCH')
        for index, side in enumerate(('first', 'second')):
            annotation = row[side]
            original = annotation['decision_original']
            effective = 'accept' if side == 'second' and original == 'pending' else original
            if original not in ('accept', 'reject', 'pending') or \
                    annotation['decision_effective'] != effective or \
                    annotation['annotator'] != entry['annotators'][index] or \
                    not isinstance(annotation['comment'], str):
                raise ValueError('ER_COMPARISON_INVALID_ANNOTATION')
            counts[side][original] += 1
        was_mapped = row['second']['decision_original'] == 'pending'
        agrees = row['first']['decision_effective'] == row['second']['decision_effective']
        if row['second_pending_mapped_to_accept'] != was_mapped or \
                row['agreement_effective'] != agrees:
            raise ValueError('ER_COMPARISON_MAPPING_MISMATCH')
        mapped += was_mapped
        if any(row[side]['decision_effective'] == 'reject' for side in counts):
            items.append({**item, 'id': case['id'], 'source_dataset': case['source_dataset'],
                          'original_context': case['original_context'],
                          'first': row['first'], 'second': row['second'],
                          'agreement_effective': agrees})
    for index, side in enumerate(counts):
        if any(counts[side][label] != summary['inputs'][index]['counts_original'][label]
               for label in ('accept', 'reject', 'pending')):
            raise ValueError('ER_COMPARISON_COUNT_MISMATCH')
    if mapped != summary['decision_mapping']['count']:
        raise ValueError('ER_COMPARISON_PENDING_COUNT_MISMATCH')
    totals = {}
    for kind in ('all', 'EA_01', 'EA_02'):
        subset = items if kind == 'all' else [item for item in items if item['type'] == kind]
        totals[kind] = {'items': len(subset), 'cases': len({item['id'] for item in subset}),
                        'disagreements': sum(not item['agreement_effective'] for item in subset),
                        'both_reject': sum(item['agreement_effective'] for item in subset)}
    return {'format': 'finarch-er-inverse-rejection-view-v1', 'comparison_id': selected,
            'run': package['run'], 'taxonomy': package['taxonomy'],
            'snapshot_file': package['snapshot_file'], 'snapshot_sha256': package['snapshot_sha256'],
            'source_items': len(rows), 'pending_mapped_to_accept': mapped,
            'sources': [{'annotator': item['annotator'], 'filename': Path(item['path']).name,
                         'sha256': item['sha256'], 'exported_at': item['exported_at']}
                        for item in summary['inputs']],
            'totals': totals, 'items': items}


def render(project, comparison_id=None):
    package = build_comparison(project, comparison_id)
    folder = project/'viewer/dataset'
    html = (folder/'ea-inverse-comparison.html').read_text()
    for marker, filename in (('__STYLE__', 'ea-inverse-comparison.css'),
                             ('__UI__', 'ea-inverse-comparison.js')):
        html = html.replace(marker, (folder/filename).read_text())
    html = html.replace('__FINARCH_LOCALE_CSS__', (project/'viewer/shared/i18n.css').read_text())
    locale = (project/'viewer/shared/i18n.js').read_text().replace('</script', '<\\/script')
    html = html.replace('__FINARCH_LOCALE_JS__', locale)
    return html.replace('__PACKAGE__', inline_json(package)).encode('utf-8')
