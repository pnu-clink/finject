"""Saved real API outcomes and hash-bound artifacts; no API calls on GET."""
import hashlib
import json
from pathlib import Path

def view(bundle):
    bundle=Path(bundle);report=json.loads((bundle/'quality-api-check.json').read_text())
    if report.get('schema_version')!='quality-api-check-v1':raise ValueError('INVALID_API_CHECK_REPORT')
    payload={'format':'fin-arch-viewer-v1','runs':[],'batch':{'name':bundle.name,'layout':'quality-api-check-v1','rounds':[],'round':None,
        'quality_api_check':report,'summary':report['summary'],'readme':(bundle/'README.md').read_text()}}
    payload['revision']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();return payload
