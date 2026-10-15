"""Read pipeline documentation through the existing run viewer."""
import hashlib
import json
import re
from pathlib import Path

PROJECT = (Path(__file__).resolve().parent / '../../../../..').resolve()
ALIASES_PATH = PROJECT / 'src/finarch/documentation/experiment-document-aliases.json'


def document_aliases():
    return json.loads(ALIASES_PATH.read_text()) if ALIASES_PATH.is_file() else {}


def load_index(bundle):
    value = json.loads((bundle / 'documentation.json').read_text())
    if value.get('kind') != 'PIPELINE_DOCUMENTATION':
        raise ValueError('INVALID_DOCUMENTATION_INDEX')
    aliases, documents, seen = document_aliases(), [], set()
    for original in value['documents']:
        row = dict(original)
        target = aliases.get(row['path'])
        if target:
            row['path'] = target
            content = (PROJECT / target).read_text()
            row['title'] = re.search(r'^# (.+)', content, re.M).group(1)
            row['group'] = '/'.join(target.split('/')[1:3])
        if row['path'] not in seen:
            documents.append(row)
            seen.add(row['path'])
    value['documents'] = documents
    value['aliases'] = aliases
    value['navigation'] = [[label, aliases.get(path, path)] for label, path in value.get('navigation', [])] or None
    return value


def catalog(bundle):
    index = load_index(bundle)
    migration = json.loads((bundle / 'migration.json').read_text())
    if isinstance(migration, dict):
        migration = [{**row, 'original': row['old'], 'destination': row['new']}
                     for row in migration['files']]
    rows = [dict(row, original=row['path'], archived=False) for row in index['documents']]
    rows += [{'path': row['archive'], 'original': row['original'],
              'title': Path(row['original']).name, 'archived': True,
              'destination': row['destination']} for row in migration]
    known = {row['path'] for row in rows}
    for relative in index.get('reference_files', []):
        if relative not in known:
            rows.append({'path': relative, 'original': relative, 'title': Path(relative).name,
                         'archived': relative.startswith('archive/'), 'group': 'references'})
            known.add(relative)
    for name in ['README.md', 'migration.json', 'source-inventory.json', 'requirements-map.json', 'run-layout-reference.json', 'validation.json', 'ui-review.json']:
        path = bundle / name
        if path.is_file():
            rows.append({'path': str(path.relative_to(PROJECT)), 'original': str(path.relative_to(PROJECT)),
                         'title': name, 'archived': False, 'group': 'migration'})
    for name in ['README.md', 'MIGRATION.md']:
        path = PROJECT / 'archive/20260923-documentation-reorganization' / name
        rows.append({'path': str(path.relative_to(PROJECT)), 'original': str(path.relative_to(PROJECT)),
                     'title': name, 'archived': False, 'group': 'migration'})
    return index, rows


def read_document(bundle, relative):
    index, rows = catalog(bundle)
    relative = document_aliases().get(relative, relative)
    selected = next((row for row in rows if row['path'] == relative), None)
    if selected is None:
        raise ValueError('DOCUMENT_NOT_IN_INDEX')
    path = PROJECT / relative
    allowed = [PROJECT / name for name in ('docs', 'archive/20260923-documentation-reorganization',
        'archive/20260927-experiment-pipeline-reorganization', 'archive/20260927-experiment-source-layout',
        'config/experiments', 'config/MODELS-README.md', 'src/finarch', 'experiment/archtecture', 'reports', 'viewer')]
    if path.is_symlink() or not any(path.resolve().is_relative_to(root.resolve()) for root in allowed):
        raise ValueError('INVALID_DOCUMENT_PATH')
    raw = path.read_bytes()
    return {**selected, 'content': raw.decode(), 'sha256': hashlib.sha256(raw).hexdigest(),
            'format': path.suffix.lstrip('.')}


def view(bundle):
    index, rows = catalog(bundle)
    documents = [read_document(bundle, row['path']) for row in index['documents']]
    validation_file = next((path for path in
                            (bundle / 'current-documentation-validation.json', bundle / 'validation.json')
                            if path.is_file()), None)
    data = {'title': index['title'], 'documents': documents, 'catalog': rows,
            'aliases': index.get('aliases', {}),
            'entry_document': index.get('entry_document'), 'navigation': index.get('navigation'),
            'validation': json.loads(validation_file.read_text()) if validation_file else None,
            'model_calls': index.get('model_calls', 0)}
    payload = {'format': 'fin-arch-viewer-v1', 'runs': [], 'batch': {
        'name': bundle.name, 'layout': 'pipeline-documentation-v1', 'rounds': [], 'round': None,
        'documentation': data, 'summary': {'documents': len(documents)},
        'readme': (bundle / 'README.md').read_text()}}
    payload['revision'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload
