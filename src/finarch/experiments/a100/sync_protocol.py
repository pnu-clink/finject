"""Content manifests shared by the PC controller and the Python 3.8 SSH agent."""
import hashlib
import json
from pathlib import Path
import re

CODE_ROOTS = ('src/finarch', 'config/experiments', 'viewer/experiments',
              'viewer/shared', 'docs/02-experiments')
RUN_ID = re.compile(r'\d{8}-[a-z0-9][a-z0-9.-]*\Z')
SKIP = {'__pycache__', '.git', 'node_modules', '.pytest_cache'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def safe(root, relative, checked_dirs=None):
    part = Path(relative)
    if not relative or part.is_absolute() or '..' in part.parts or '\\' in relative:
        raise ValueError('UNSAFE_SYNC_PATH:' + relative)
    original_root = Path(root)
    root = original_root if checked_dirs is not None and original_root in checked_dirs else original_root.resolve()
    if checked_dirs is not None:
        checked_dirs.add(root)
    target = root / part
    inspected = []
    for parent in (target, *target.parents):
        if parent == root:
            break
        if parent != target and checked_dirs is not None and parent in checked_dirs:
            break
        if parent.is_symlink():
            raise ValueError('SYMLINK_SYNC_PATH:' + relative)
        if parent != target:
            inspected.append(parent)
    if checked_dirs is not None:
        checked_dirs.update(inspected)
    return target


def inventory(root, names):
    root = Path(root).resolve()
    files = {}
    for name in names:
        base = safe(root, name)
        if not base.exists():
            continue
        paths = base.rglob('*') if base.is_dir() else [base]
        for path in paths:
            rel = path.relative_to(root).as_posix()
            if any(p in SKIP for p in path.parts) or path.name.endswith(('.pyc', '.tmp', '.lock')):
                continue
            safe(root, rel)
            if path.is_file():
                files[rel] = sha(path)
    return dict(sorted(files.items()))


def code_manifest(root):
    return inventory(Path(root), (*CODE_ROOTS, 'pyproject.toml'))


def differences(expected, actual):
    return {'missing': sorted(expected.keys() - actual.keys()),
            'changed': sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k]),
            'extra': sorted(actual.keys() - expected.keys())}


def public_input_manifest(root):
    """Select public frozen files; private/gold stay on the PC."""
    root = Path(root)
    frozen = json.loads((root / 'manifest.json').read_text())
    names = [name for name in frozen if name == 'config.json' or name == '00_input/public.jsonl'
             or name.startswith('01_evaluation/02_request/')
             or name == '01_evaluation/01_preparation/a100-runtime.json']
    for name in names:
        if sha(safe(root, name)) != frozen[name]:
            raise ValueError('FROZEN_INPUT_CHANGED:' + name)
    required = {'config.json', '00_input/public.jsonl'}
    if not required.issubset(names) or not any(name.endswith('/manifest.jsonl') for name in names):
        raise ValueError('CANONICAL_PUBLIC_RUN_INPUTS_REQUIRED')
    return {name: frozen[name] for name in sorted(names)}
