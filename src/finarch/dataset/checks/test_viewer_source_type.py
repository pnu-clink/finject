"""Compare list/detail source identity against recorded dataset provenance."""
import json
from pathlib import Path
import subprocess
import unittest

from finarch.dataset.viewer.annotation.sources import source_kind
from finarch.dataset.viewer.server import compact_preparation_case

ROOT = Path(__file__).resolve().parents[4]


class SourceTypeTests(unittest.TestCase):
    def test_real_provenance_matches_the_existing_source_catalog(self):
        records = json.loads((ROOT / 'reports/run/20260917-002/results/00-input.json').read_text())
        provenance = [row['input'].get('provenance', {}) for row in records]
        code = (ROOT / 'viewer/dataset/source-type.js').read_text()
        script = code + '\nconsole.log(JSON.stringify(JSON.parse(process.argv[1]).map(originalSourceType)));'
        actual = json.loads(subprocess.check_output(['node', '-e', script, json.dumps(provenance)], text=True))
        expected = ['\ucd9c\ucc98 \ubbf8\ud655\uc778' if source_kind(p) == 'UNKNOWN' else source_kind(p) for p in provenance]
        self.assertEqual(actual, expected)
        self.assertEqual(set(actual), {'FinQA', 'TAT-QA', 'FinanceMath', 'FinanceReasoning'})

    def test_summary_keeps_original_source_id_before_loading_detail(self):
        case = ROOT / 'reports/run/20260917-002/01-preparation/test-0001'
        detail = json.loads((case / '01-round/01-source/01-receive-input/01-input.json').read_text())
        summary = compact_preparation_case(case, '01-round')
        provenance = summary['artifacts']['00-data-preparation/01-select-input/01-input.json']['provenance']
        self.assertEqual(provenance['source_id'], detail['provenance']['source_id'])
        self.assertEqual(source_kind(provenance), source_kind(detail['provenance']))
        self.assertNotIn('sha256', provenance)


if __name__ == '__main__':
    unittest.main()
