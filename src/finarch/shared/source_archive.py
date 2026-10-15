"""Read hash-bound source evidence after a source-only directory migration."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from finarch.paths import PROJECT

ARCHIVE = Path('archive/20260924-source-layout')


def read_source_reference(relative, expected_sha256, *, project=PROJECT):
    project = Path(project).resolve()
    relative = str(relative)
    parts = PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts or str(parts) != relative:
        raise ValueError('INVALID_SOURCE_REFERENCE')
    current = project / relative
    if current.is_symlink() or not current.resolve().is_relative_to(project):
        raise ValueError('INVALID_SOURCE_REFERENCE')
    if current.is_file():
        raw = current.read_bytes()
        if hashlib.sha256(raw).hexdigest() == expected_sha256:
            return raw
    index_path = project / ARCHIVE / 'manifest.json'
    if index_path.exists() and parts.parts[0] in ('src', 'viewer', 'dashboard'):
        index = json.loads(index_path.read_text())
        if index['files'].get(relative) == expected_sha256:
            with tarfile.open(project / ARCHIVE / 'source-before.tar.gz', 'r:gz') as archive:
                member = archive.getmember(relative)
                if not member.isfile():
                    raise ValueError('INVALID_ARCHIVED_SOURCE')
                raw = archive.extractfile(member).read()
            if hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise ValueError('ARCHIVED_SOURCE_HASH_CHANGED')
            return raw
    raise ValueError('SOURCE_HASH_CHANGED_OR_MISSING:' + relative)
