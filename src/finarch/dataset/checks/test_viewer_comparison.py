import unittest
from finarch.dataset.viewer.comparison import aligned_diff, code_links, enrich


class ComparisonChecks(unittest.TestCase):
    def test_aligned_diff_preserves_text_and_line_numbers(self):
        rows=aligned_diff('same\nold\nlast','same\nnew\ninsert\nlast')
        self.assertEqual('\n'.join(r['left'] for r in rows if r['left'] is not None),'same\nold\nlast')
        self.assertEqual('\n'.join(r['right'] for r in rows if r['right'] is not None),'same\nnew\ninsert\nlast')
        self.assertEqual(rows[0]['kind'],'equal')
        self.assertTrue(any(r['left'] is None for r in rows))

    def test_code_lines_link_literal_facts_and_variable_calculation(self):
        links=code_links('a=fact("sales")\nb=fact("cost")\nanswer=(a-b)/a',{'sales':{},'cost':{}})
        self.assertEqual(links[1],['sales']);self.assertEqual(links[2],['cost'])
        self.assertEqual(set(links[3]),{'sales','cost'})

    def test_missing_source_is_not_replaced_by_prepared_text(self):
        result=enrich({'00-data-preparation/01-select-input/01-input.json':{'context':'prepared'}})
        self.assertIn('error',result['source_diff'])

    def test_full_raw_record_fields_and_prepared_input_both_retained(self):
        result=enrich({'00-data-preparation/raw-record.json':{'record':{'context':'\uc6d0\ubb38 100','other':'raw only'}},
                       '00-data-preparation/01-select-input/01-input.json':{'context':'\uc6d0\ubb38 101'}})
        self.assertEqual(result['source_diff']['raw']['other'],'raw only')
        self.assertEqual(result['source_diff']['context_rows'][0]['kind'],'replace')

    def test_response_normalization_rejects_duplicate_fact_ids(self):
        from finarch.dataset.schemas.llm import executable_program
        fact={'id':'a','value':'1','text':'1','span':[0,1],'unit':None}
        with self.assertRaises(ValueError):executable_program({'code':'answer=fact("a")','facts':[fact,fact],'grounding':'test'})
        result=executable_program({'code':'answer=fact("a")','facts':[fact],'grounding':'test'})
        self.assertEqual(result['facts']['a']['text'],'1')

    def test_final_precision_applied_separately_without_hiding_graph_mismatch(self):
        sample={'reference_answer':'15.3','reference_answer_type':'float','reference_precision':1}
        artifacts={'00-data-preparation/01-select-input/01-input.json':sample,
                   '03-graph/03-compare-calculation/04-comparison.json':{'python':'15.300000000000002','graph':'15.46'}}
        result=enrich(artifacts)['final_answers']
        self.assertEqual(result['python']['computed'],'15.3')
        self.assertTrue(result['python']['matches'])
        self.assertEqual(result['graph']['computed'],'15.5')
        self.assertFalse(result['graph']['matches'])
        self.assertEqual(artifacts['03-graph/03-compare-calculation/04-comparison.json']['python'],'15.300000000000002')

    def test_final_precision_keeps_trailing_zeros_and_negative_half_up(self):
        sample={'reference_answer':'-2.10','reference_answer_type':'float','reference_precision':2}
        result=enrich({'00-data-preparation/01-select-input/01-input.json':sample,
                       '03-graph/03-compare-calculation/04-comparison.json':{'python':'-2.095','graph':'-2.095'}})['final_answers']
        self.assertEqual(result['graph']['computed'],'-2.10')
        self.assertTrue(result['graph']['matches'])

    def test_missing_precision_never_invents_a_final_answer(self):
        result=enrich({'03-graph/03-compare-calculation/04-comparison.json':{'python':'15.3','graph':'15.3'}})
        self.assertIn('error',result['final_answers'])
