"""Read saved offline coefficient examples without executing programs."""
import hashlib
import json
from pathlib import Path


def view(bundle):
    bundle=Path(bundle);report=json.loads((bundle/'coefficient-policy.json').read_text())
    if report.get('schema_version')!='coefficient-policy-report-v1' or report.get('model_calls')!=0:raise ValueError('INVALID_COEFFICIENT_REPORT')
    payload={'format':'fin-arch-viewer-v1','runs':[],'batch':{'name':bundle.name,'layout':'coefficient-policy-report-v1','rounds':[],'round':None,
        'coefficient_policy':report,'summary':report['summary'],'readme':(bundle/'README.md').read_text()}}
    payload['revision']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();return payload
