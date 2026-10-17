"""Validate and materialize the actual one-file annotator deliverable."""
import hashlib
import json
import re
from pathlib import Path
from finarch.dataset.viewer.ea_inverse_export import build_package, render

project=Path(__file__).resolve().parents[4]
run='finject-20261007'
name='EA_INVERSE_REVIEW.OFFLINE-20261008-003047-v2.jsonl'
folder=project/'reports/dataset-review/finject-20261007-ea-inverse-annotator-20261008-v2'
folder.mkdir(exist_ok=True)
protected=[project/'data/final'/run/f for f in ('dataset.jsonl','EA_INVERSE_REVIEW.jsonl','EA_INVERSE_REVIEW.backup-20261008-003047.jsonl',name)]
before={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
package=build_package(project,run,name)
html=render(project,run,name)
assert len(package['cases'])==1354
assert sum(len(c['items']) for c in package['cases'])==2708
for c in package['cases']:
 for v in c['items']:
  for s in v['display_ko'].values():assert re.search('[\uac00-\ud7a3]',s)
  assert v['removals']
  for removed in v['removals']:assert c['original_context'][removed['start']:removed['end']]==removed['text']
  source=project/v['removal_source']['path']
  assert hashlib.sha256(source.read_bytes()).hexdigest()==v['removal_source']['sha256']
assert package['taxonomy']['EA_01']['label']=='ER-1'
assert package['taxonomy']['EA_02']['label']=='ER-2'
text=html.decode()
assert '__PACKAGE__' not in text and '__STATE__' not in text and '__STYLE__' not in text and '__UI__' not in text
assert not re.search(r'<(?:script|link|iframe|img)\b[^>]*(?:src|href)\s*=',text,re.I)
assert not re.search(r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(',text)
embedded=re.search(r'<script id="package-data" type="application/json">(.*?)</script>',text,re.S)[1]
assert json.loads(embedded)==package
html_path=folder/(run+'-er-inverse-annotator-v2.html');html_path.write_bytes(html)
(project/'tmp/ea-inverse-annotation-package.json').write_text(json.dumps(package,ensure_ascii=False))
after={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
assert before==after
report={'status':'PASS','display_revision':2,'cases':1354,'items':2708,'bilingual_items':2708,'verified_removal_items':2708,'html_bytes':len(html),'html_sha256':hashlib.sha256(html).hexdigest(),'model_calls':0,'source_hashes':after,'checks':['registered snapshot hash','exact ID and ER coverage','exact evidence spans','original removal spans and plan hashes','Korean display coverage','embedded JSON round trip','zero external dependencies and requests','original records unchanged'],'browser_verification':'PENDING','human_annotations':'NOT_PERFORMED'}
(folder/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
