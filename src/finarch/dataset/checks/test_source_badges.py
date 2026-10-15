import json
import tempfile
import unittest
from pathlib import Path
from finarch.dataset.viewer.server import preparation_list_metadata

class SourceBadgeTests(unittest.TestCase):
    def test_failed_case_keeps_external_sources_without_pass_round(self):
        with tempfile.TemporaryDirectory() as directory:
            case=Path(directory)
            (case/'run.json').write_text(json.dumps({'status':'FAIL','active_round':'01-round'}))
            program=case/'01-round/03-calculation/05-record-calculation-artifacts/03-program.json'
            program.parent.mkdir(parents=True)
            program.write_text(json.dumps({'calculation_input_sources':['EXTERNAL_RULE'],'source_usage':[{'kind':'EXTERNAL_DATA'}]}))
            result=preparation_list_metadata(case)
            self.assertEqual(result['sources'],['EXTERNAL_RULE','EXTERNAL_DATA'])
            self.assertIsNone(result['pass_round'])
