"""Fail before execution when the deployed code or frozen public inputs drift."""
import json
from pathlib import Path
from .sync_protocol import code_manifest, differences, digest, safe, sha


def verify(root, project=None):
    project = Path(project) if project else Path(__file__).resolve().parents[4]
    release_path = project / 'sync-release.json'
    inputs_path = Path(root) / 'sync-input.json'
    if not release_path.is_file() or not inputs_path.is_file():
        raise ValueError('MANAGED_RELEASE_AND_SYNC_INPUT_REQUIRED')
    release, inputs = (json.loads(p.read_text()) for p in (release_path, inputs_path))
    if digest(release['files']) != release['release']:
        raise ValueError('INVALID_CODE_RELEASE_MANIFEST')
    diff = differences(release['files'], code_manifest(project))
    if any(diff.values()):
        raise ValueError('EXECUTION_CODE_DRIFT:' + json.dumps(diff))
    if inputs['code_release'] != release['release']:
        raise ValueError('INPUTS_NOT_ACKNOWLEDGED_FOR_CURRENT_RELEASE')
    for relative, expected in inputs['files'].items():
        if sha(safe(root, relative)) != expected:
            raise ValueError('EXECUTION_INPUT_DRIFT:' + relative)
    return {'status': 'VERIFIED', 'run_id': inputs['run_id'], 'code_release': release['release'],
            'input_digest': digest(inputs['files']), 'files': len(inputs['files']),
            'new_model_calls': 0, 'scope': 'CODE_AND_PUBLIC_FROZEN_INPUTS_ONLY'}
