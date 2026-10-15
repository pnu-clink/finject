"""Read-only saved quality report and hash-bound evidence access; no analysis."""
import hashlib
import json
from pathlib import Path
from finarch.dataset.schemas.quality_scope import QualityReport
from finarch.shared.source_archive import read_source_reference

PROJECT = (Path(__file__).resolve().parent / '../../../../..').resolve()


def view(bundle):
    bundle = Path(bundle)
    report = QualityReport.model_validate_json((bundle / 'quality_scope.json').read_text()).model_dump()
    payload = {'format': 'fin-arch-viewer-v1', 'runs': [], 'batch': {
        'name': bundle.name, 'layout': 'quality-scope-v1', 'rounds': [], 'round': None,
        'quality_scope': report, 'summary': report['summary'], 'readme': (bundle / 'README.md').read_text()}}
    payload['revision'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def source(bundle, relative, *, project=PROJECT):
    project = Path(project).resolve()
    manifest = json.loads((Path(bundle) / 'manifest.json').read_text())
    refs = {item['path']: item['sha256'] for item in manifest['inputs']}
    if relative not in refs:
        raise ValueError('SOURCE_NOT_IN_QUALITY_MANIFEST')
    path = project / relative
    if path.is_symlink() or not path.resolve().is_relative_to(project) or path.resolve().relative_to(project).as_posix() != relative:
        raise ValueError('INVALID_QUALITY_SOURCE_PATH')
    return read_source_reference(relative, refs[relative], project=project)
