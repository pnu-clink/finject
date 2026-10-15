"""Full input enumeration and static AST inventory; no source execution or model calls."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
PreparedInputs = __import__('finarch.dataset.90-operations.staging', fromlist=['PreparedInputs']).PreparedInputs

full=importlib.import_module('finarch.dataset.00-input.full_finance')

class FullFinanceTests(unittest.TestCase):
    def test_empty_serialized_context_does_not_remove_valid_numeric_content(self):
        for text in ('', '  ', '[]', ' [ ] ', '{}', 'null', '""'):
            with self.subTest(text=text):
                self.assertTrue(full.empty_context(text))
        for text in ('[0]', '{"revenue": 0}', '0', 'false', 'No debt.', '[table]'):
            with self.subTest(text=text):
                self.assertFalse(full.empty_context(text))

    def test_only_exact_qc_duplicates_and_explicit_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);catalog={'sources':[]}
            def row(number,q,c,a,source='FinanceReasoning-test-1'):
                return {'question_id':str(number),'question':q,'context':c,'ground_truth':a,
                        'source':source,'level':'easy','python_solution':'answer = 2'}
            groups=[
                [row(1,'Q1','same C',2),row(2,'Q2','same C',3),row(3,'Q1','same C',2)],
                [row(4,'Q3','',4),row(5,'Q4','C4',True),row(7,'Q7','[]',7)],
                [row(6,'Q5','C5',5,'FinanceMath-test-1')],
            ]
            for level,rows in zip(('easy','medium','hard'),groups):
                path=root/f'{level}.json';path.write_text(json.dumps(rows))
                catalog['sources'].append({'name':'finance-'+level,'path':str(path),
                    'sha256':full.sha256(path.read_bytes()),'url':'https://example.test/raw','commit':'pinned'})
            source=root/'catalog.json';source.write_text(json.dumps(catalog))
            result=full.prepare(source,root/'prepared')
            self.assertEqual(result['totals'],{'total':7,'empty_context':2,'boolean_answer':1,'duplicate_qc':1,'selected':3})
            inputs=PreparedInputs(root/'prepared/input.json')
            self.assertEqual(len(inputs.samples),3)
            manifest=json.loads((root/'prepared/selection-manifest.json').read_text())
            duplicate=next(r for r in manifest['exclusions'] if r['reason']=='duplicate_qc')
            self.assertEqual(duplicate['kept_raw_id'],'finance-1')
            self.assertTrue(duplicate['same_answer'])
            self.assertEqual([s['question'] for s in inputs.samples.values()],['Q1','Q2','Q5'])

    def test_syntax_counts_distinguish_inline_condition_and_wrapper(self):
        self.assertEqual(full.inspect_code('def solve():\n return 1 if True else 0')['patterns'],[])
        result=full.inspect_code('def solve():\n if True:\n  return sum(x for x in range(3))')
        self.assertEqual(result['patterns'],['block_if','comprehension','unsupported_numeric_call'])
        self.assertEqual(result['unsupported_numeric_calls'],['range','sum'])

if __name__=='__main__':unittest.main()
