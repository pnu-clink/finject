import importlib
import unittest

assemble = importlib.import_module("finarch.dataset.00-input.content").assemble


class ContentChecks(unittest.TestCase):
    def check_locations(self, record, result):
        for segment in result["context_mapping"]["segments"]:
            value = record
            for key in segment["source_pointer"].split("/")[1:]:
                value = value[int(key)] if isinstance(value, list) else value[key]
            self.assertEqual(str(value), segment["text"])
            start, end = segment["context_span"]
            self.assertEqual(result["context"][start:end], str(value))
            for number in segment["numbers"]:
                a, b = number["context_span"]
                c, d = number["source_text_span"]
                self.assertEqual(result["context"][a:b], number["text"])
                self.assertEqual(str(value)[c:d], number["text"])

    def test_finance_unicode_repeated_numbers(self):
        record = {"context": "😀 \ub9e4\ucd9c 1,200.5, \ube44\uc6a9 1,200.5. \ube44\uc728 20%."}
        result = assemble(record, "finance")
        self.assertEqual(result["context"], record["context"])
        self.assertEqual(result["source_content"]["tables"], [])
        self.assertEqual(len(result["context_mapping"]["segments"][0]["numbers"]), 3)
        self.check_locations(record, result)

    def test_table_duplicate_values_and_paragraph_original_index(self):
        record = {"table": {"table": [["", "2019", "2018"], ["😀 \ube44\uc6a9", "80", "80"]]},
                  "paragraphs": [{"order": 2, "text": "\ub450\ubc88\uc9f8 80"}, {"order": 1, "text": "\uccab\ubc88\uc9f8 80"}]}
        result = assemble(record, "tatqa")
        self.assertEqual(result["context"], " | 2019 | 2018\n😀 \ube44\uc6a9 | 80 | 80\n\n\uccab\ubc88\uc9f8 80\n\ub450\ubc88\uc9f8 80")
        self.assertEqual(result["source_content"]["paragraphs"][0]["source_pointer"], "/paragraphs/1/text")
        self.check_locations(record, result)


if __name__ == "__main__":
    unittest.main()
