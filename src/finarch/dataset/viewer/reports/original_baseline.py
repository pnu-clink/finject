"""Researcher-only saved baseline preparation report; never sends model requests."""
import hashlib
import json
from pathlib import Path
from finarch.dataset.schemas.original_baseline import BaselineReport


def view(bundle):
    bundle=Path(bundle)
    report=BaselineReport.model_validate_json((bundle/'private/originals.json').read_text()).model_dump()
    payload={'format':'fin-arch-viewer-v1','runs':[],'batch':{'name':bundle.name,'layout':'original-baseline-v1',
        'rounds':[],'round':None,'original_baseline':report,'summary':report['summary'],'readme':(bundle/'README.md').read_text()}}
    payload['revision']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    return payload
