"""Serve the saved editorial review in the shared run viewer."""
import hashlib
import json


def view(bundle):
    report = json.loads((bundle / 'failure-review.json').read_text())
    for row in report['rows']:
        row.pop('evidence', None)
    payload = {'format': 'fin-arch-viewer-v1', 'runs': [], 'batch': {
        'name': bundle.name, 'layout': 'failure-cause-review-v1', 'rounds': [], 'round': None,
        'failure_review': report, 'summary': report['summary'],
        'readme': (bundle / 'README.md').read_text(), 'review_document': (bundle / 'REPORT.md').read_text()}}
    payload['revision'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload
