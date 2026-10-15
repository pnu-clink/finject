"""Read a saved v2 report without analysis, writes or provider calls."""
import hashlib
import json
from pathlib import Path
from finarch.dataset.schemas.response_screen import ScreenReport


def view(bundle):
    bundle = Path(bundle)
    report = ScreenReport.model_validate_json((bundle / 'response_screen.json').read_text()).model_dump()
    payload = {'format': 'fin-arch-viewer-v1', 'runs': [], 'batch': {
        'name': bundle.name, 'layout': 'response-screen-v2', 'rounds': [], 'round': None,
        'response_screen': report, 'summary': report['summary'], 'readme': (bundle / 'README.md').read_text()}}
    payload['revision'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload
