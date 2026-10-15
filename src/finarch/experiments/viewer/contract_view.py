run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
"""Read only the four fixed experiment contract files for side-by-side review."""

import hashlib
import json
import re
from pathlib import Path
from finarch.experiments import assets


FILES = {
    'schema': 'response.schema.json',
    'common': 'common.md',
    'unguided': 'prompt-unguided.md',
    'guided': 'prompt-guided.md',
}
SOURCE_RUN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*\Z')


def _read_file(directory, filename, project):
    path = directory / filename
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(project):
        raise ValueError('CONTRACT_FILE_UNAVAILABLE')
    raw = path.read_bytes()
    return {
        'path': path.relative_to(project).as_posix(),
        'text': raw.decode('utf-8'),
        'sha256': hashlib.sha256(raw).hexdigest(),
    }


def _definition(project, source):
    if source == 'current':
        return project / 'src/finarch/experiments'
    if not SOURCE_RUN.fullmatch(source):
        raise ValueError('UNKNOWN_CONTRACT_SOURCE')
    run_root = project / 'reports/experiments-run'
    run = run_root / source
    if run.is_symlink() or not run.is_dir() or run.resolve().parent != run_root.resolve():
        raise ValueError('UNKNOWN_CONTRACT_SOURCE')
    definition = run_layout.definition(run)
    if definition.is_symlink() or not definition.is_dir():
        raise ValueError('UNKNOWN_CONTRACT_SOURCE')
    return definition


def _files(project, source):
    definition = _definition(project, source)
    if source == 'current':
        schema = _read_file(definition / 'schemas/json', assets.SCHEMAS['solver_response'], project)
        prompts = definition / 'prompts'
        return {'schema': schema,
                'common': _read_file(prompts, assets.PROMPTS['solver_common'], project),
                'unguided': _read_file(prompts, assets.PROMPTS['solver_unguided'], project),
                'guided': _read_file(prompts, assets.PROMPTS['solver_guided'], project)}
    else:
        schema = _read_file(definition, FILES['schema'], project)
        prompts = definition
    return {'schema': schema, 'common': _read_file(prompts, FILES['common'], project),
            **{key: _read_file(prompts, run_layout.prompt_file(prompts, condition).name, project)
               for key, condition in (('unguided', 'unguided'), ('guided', 'guided'))}}


def _translation(project, original):
    """Review-only Korean text is bound to exact English bytes by SHA-256."""
    path = project / 'viewer/dataset/translations' / (original['sha256'] + '.ko.md')
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(project):
        return {'status': 'UNAVAILABLE', 'source_sha256': original['sha256']}
    raw = path.read_bytes()
    translated = raw.decode('utf-8')
    if len(translated.splitlines()) != len(original['text'].splitlines()):
        return {'status': 'LINE_COUNT_MISMATCH', 'source_sha256': original['sha256']}
    return {
        'status': 'AVAILABLE',
        'source_sha256': original['sha256'],
        'path': path.relative_to(project).as_posix(),
        'text': translated,
        'sha256': hashlib.sha256(raw).hexdigest(),
    }


def read_contract(project, source='current'):
    """Never accept a path; a source is the working definition or a frozen run name."""
    project = Path(project).resolve()
    files = _files(project, source)
    for key in ('common', 'unguided', 'guided'):
        files[key]['translation'] = _translation(project, files[key])
    schema = json.loads(files['schema']['text'])
    return {
        'source': source,
        'title': schema.get('title'),
        'files': files,
        'scope': 'Working definition' if source == 'current' else 'Saved run definition; historical files are read only',
    }


def list_contract_sources(project):
    project = Path(project).resolve()
    root = project / 'reports/experiments-run'
    if not root.is_dir():
        return []
    result = []
    for run in sorted(root.iterdir(), reverse=True):
        if not run.is_dir() or run.is_symlink() or not SOURCE_RUN.fullmatch(run.name):
            continue
        definition = run_layout.definition(run)
        try:
            names = [FILES['schema'], FILES['common'],
                     *(run_layout.prompt_file(definition, condition).name for condition in ('unguided', 'guided'))]
        except FileNotFoundError:
            continue
        if definition.is_symlink() or not all(
            (definition / name).is_file() and not (definition / name).is_symlink() for name in names):
            continue
        schema = definition / FILES['schema']
        if schema.is_symlink() or not schema.is_file():
            continue
        try:
            title = json.loads(schema.read_text())['title']
        except (OSError, ValueError, KeyError):
            continue
        if title in ('FinancialAnswerV6', 'FinancialAnswerV7'):
            result.append(run.name)
    return result
