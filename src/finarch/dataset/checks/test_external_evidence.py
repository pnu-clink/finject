"""External rates require a reviewed source and real selector dependencies."""
import copy
import unittest
from finarch.dataset.shared.calculation.python_graph import compile_graph
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.dataset.shared.calculation.external_evidence import resolve

def example():
    return {'context':'150000 5','facts':{
        'cost':{'text':'150000','value':'150000','span':[0,6],'unit':'USD'},
        'life':{'text':'5','value':'5','span':[7,8],'unit':'years'}},
        'external_evidence':[{'id':'irs-p946-2025-a1-5year','application_note':'Half-year convention is assumed, not source stated.'}],
        'code':'cost=fact("cost")\nlife=fact("life")\nyear=3\npercent=evidence("irs-p946-2025-a1-5year",life,year)\nrate=percent/100\nanswer=cost*rate'}

class EvidenceTests(unittest.TestCase):
    def test_native_schema_requires_all_fields(self):
        from finarch.dataset.schemas.registry import describe
        schema=describe('pot.author.response')['schema']
        self.assertEqual(set(schema['required']),set(schema['properties']))
        external=schema['$defs']['ExternalEvidence']
        self.assertEqual(set(external['required']),set(external['properties']))
    def test_runtime_graph_and_selector(self):
        for year,answer in [(2,'48000.0'),(3,'28800.0')]:
            p=example();p['code']=p['code'].replace('year=3',f'year={year}')
            result=execute(p);graph,value,_=compile_graph(p)
            self.assertEqual(result.status,'PASS');self.assertEqual(str(value),answer)
            self.assertEqual(str(value),result.data['exact_value'])
            lookup=next(n for n in graph['nodes'] if n.get('operator')=='evidence')
            self.assertEqual(len(lookup['inputs']),2)
            self.assertEqual(graph['external_evidence']['irs-p946-2025-a1-5year']['application_status'],'REQUIRES_REVIEW')
    def test_unknown_source_blocked(self):
        p=example();p['external_evidence'][0]['id']='invented'
        with self.assertRaisesRegex(ValueError,'UNVERIFIED_EXTERNAL'):resolve(p)
    def test_unsupported_selector_blocked(self):
        p=example();p['code']=p['code'].replace('year=3','year=9')
        self.assertEqual(execute(p).status,'FAIL')
        with self.assertRaisesRegex(ValueError,'SELECTION_NOT_SUPPORTED'):compile_graph(p)
    def test_missing_declaration_blocked(self):
        p=example();p['external_evidence']=[]
        with self.assertRaisesRegex(ValueError,'DECLARATION_CALL_MISMATCH'):resolve(p)

if __name__=='__main__':unittest.main()
