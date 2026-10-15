"""Generic comparisons must not assume a financial case or code response."""
import unittest
from finarch.dataset.viewer.reports.request_change_report import changes, capture

class RequestChangeTests(unittest.TestCase):
    def test_required_and_nested_type(self):
        rows=changes({'required':['a'],'properties':{'a':{'type':'string'}}},{'required':['a','b'],'properties':{'a':{'type':'number'}}})
        self.assertEqual({r['path'] for r in rows},{'$/required','$/properties/a/type'})
    def test_non_code_response(self):
        self.assertEqual(changes({'passed':False},{'passed':True})[0]['path'],'$/passed')
    def test_missing_is_not_null(self):
        self.assertEqual(changes({}, {'a':None})[0]['kind'],'added')
    def test_bool_not_integer(self):
        self.assertEqual(len(changes(True,1)),1)
    def test_same(self):
        self.assertEqual(changes({'items':[1,2]},{'items':[1,2]}),[])

if __name__=='__main__':unittest.main()
