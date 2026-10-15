"""Read saved SOURCE/VALUE pairs only; never recompute on GET."""
import hashlib
import json
from pathlib import Path
from finarch.dataset.schemas.source_pair_review import PairReport


def view(bundle):
    bundle=Path(bundle);report=PairReport.model_validate_json((bundle/'pair_manifest.json').read_text()).model_dump()
    payload={'format':'fin-arch-viewer-v1','runs':[],'batch':{'name':bundle.name,'layout':'source-pair-review-v1','rounds':[],'round':None,
        'source_pair_review':report,'summary':report['summary'],'readme':(bundle/'README.md').read_text()}}
    payload['revision']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    return payload
