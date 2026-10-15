"""Offline path tests; no provider requests or production samples."""
import tempfile
import unittest
from pathlib import Path
CALL_FILES = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['CALL_FILES']).CALL_FILES
TEXT_FILES = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['TEXT_FILES']).TEXT_FILES
HANDLER_FILES = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['HANDLER_FILES']).HANDLER_FILES
ordered_path = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['ordered_path']).ordered_path
resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read
viewer_aliases = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['viewer_aliases']).viewer_aliases
from finarch.dataset.viewer.stage_flow import build_flow

class OrderedLayoutTests(unittest.TestCase):
 def test_call_lifecycle_writes_reads_and_viewer(self):
  for task,role in [('01-generate-text','realize'),('02-audit-meaning','audit')]:
   base='05-text/'+task+'/06-ea-earlier-input/attempt-001/'
   pairs={base+role+'/'+k:base+v for k,v in CALL_FILES.items()}
   pairs.update({base+k:base+v for k,v in TEXT_FILES.items()})
   pairs.update({base+'T01-realize/'+k:base+v for k,v in HANDLER_FILES.items()})
   self.assertEqual(len(set(pairs.values())),len(pairs))
   with tempfile.TemporaryDirectory() as t:
    artifacts={}
    for old,new in pairs.items():
     self.assertEqual(ordered_path(old),new)
     p=Path(t)/new;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('raw unchanged')
     self.assertEqual(resolve_read(Path(t)/old).read_text(),'raw unchanged')
     artifacts[new]={'status':'PASS'}
    aliases=viewer_aliases(artifacts)
    for old,new in pairs.items():self.assertEqual(aliases.get(old,old),new)
 def test_error_tree_uses_physical_paths(self):
  path='05-text/02-audit-meaning/06-ea-earlier-input/attempt-001/06-apply-result/04-result.json'
  tree=build_flow({path:{'status':'FAIL','reason':'quotation field mismatch'}})
  self.assertIn(path,tree[5]['failures'])
  self.assertEqual(tree[4]['failures'],[])
 def test_paths_are_idempotent(self):
  for suffix in CALL_FILES.values():
   path='05-text/01-generate-text/01-ic-value-before/attempt-001/'+suffix
   self.assertEqual(ordered_path(path),path)
