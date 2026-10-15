import json
import tempfile
import unittest
from pathlib import Path
from finarch.dataset.viewer.reports.token_charts import build

class TokenChartsTests(unittest.TestCase):
    def test_retries_duplicates_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for n, identity, tokens in [(1,'a',10),(2,'b',20),(3,'a',10),(4,'c',None)]:
                path = root / f'01-preparation/test-0001/{n:02d}-round/02-review/call/03-result/usage.json'
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({'response_id':identity,'model':'model','tokens':{'total_tokens':tokens},'reported_usage':None}))
            report = build(root)
            self.assertEqual(report['series'][0]['points'], [(1,30)])
            self.assertEqual(report['missing_usage'], 1)
            self.assertEqual(report['call_records'], 3)
