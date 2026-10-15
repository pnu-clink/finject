"""Regression tests for cohort boundaries, NASU exclusions and denominator accounting."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("rq_export", Path(__file__).with_name("export.py"))
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


class ClassificationTests(unittest.TestCase):
    def test_exhaustive_supported_unsupported_and_unresolved(self):
        s, u, d = "SUPPORTED", "UNSUPPORTED", "UNDETERMINED"
        cases = [
            ("N", "NOT_APPLICABLE", s, False, "NS", "NS"),
            ("N", "NOT_APPLICABLE", u, True, "NU", "NU_MATCH"),
            ("N", "NOT_APPLICABLE", u, False, "NU", "NU_MISMATCH"),
            ("N", "NOT_APPLICABLE", u, None, "NU", "NU_UNKNOWN"),
            ("N", "NOT_APPLICABLE", d, True, "ND", "ND"),
            ("A", s, s, False, "AS", "AS"),
            ("A", u, u, False, "AU", "AU_U_U"),
            ("A", s, u, False, "AU", "AU_S_U"),
            ("A", u, s, False, "AU", "AU_U_S"),
            ("A", d, u, False, "AU", "AU_D_U"),
            ("A", u, d, False, "AU", "AU_U_D"),
            ("A", s, d, False, "AD", "AD"),
            ("A", d, s, False, "AD", "AD"),
            ("A", d, d, False, "AD", "AD"),
        ]
        for action, arv, dg, match, coarse, detail in cases:
            with self.subTest(action=action, arv=arv, dg=dg, match=match):
                self.assertEqual(export.classify(action, "COMPLETED", arv, dg, match), (coarse, detail))

    def test_missing_is_neither_numeric_nor_abstention_failure(self):
        self.assertEqual(export.classify("UNKNOWN", "NOT_REVIEWABLE", None, None, None)[0], "F")
        self.assertEqual(export.classify("A", "REVIEW_FAILED", "SUPPORTED", "SUPPORTED", False)[0], "F")
        self.assertEqual(export.classify("N", "COMPLETED", "NOT_APPLICABLE", None, True)[0], "F")

    def test_original_invalid_is_unknown_but_valid_null_is_incorrect(self):
        compare = lambda response, ref: {"matches": response["answer"] == ref["reference_answer"]}
        self.assertIsNone(export.numeric_match({"answer": None}, "INVALID_RESPONSE", {}, compare))
        self.assertFalse(export.numeric_match({"answer": None}, "VALID", {}, compare))
        self.assertTrue(export.numeric_match({"answer": 5}, "VALID", {"reference_answer": 5}, compare))

    def test_latest_failed_attempt_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for number, status in [(1, "VALID"), (2, "INVALID_RESPONSE"), (10, "PROVIDER_ERROR")]:
                path = root / "calls/trial" / f"attempt-{number:03d}" / "result.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"status": status}))
            self.assertEqual(export.latest_result(root, "trial").parent.name, "attempt-010")

    def test_duplicate_rows_fail_instead_of_double_counting(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            export.unique([{"id": "x"}, {"id": "x"}], "id", "TEST")

    def test_snapshot_detects_a_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            path.write_text('{"n":1}')
            snapshot = export.Snapshot()
            snapshot.read(path)
            path.write_text('{"n":200}')
            with self.assertRaisesRegex(ValueError, "SOURCE_CHANGED"):
                snapshot.assert_unchanged()

    def test_all_statuses_reconcile_without_dropping_mixed_au(self):
        rows, originals = [], []
        cases = [("NS", "NS"), ("NU", "NU_MATCH"), ("NU", "NU_MISMATCH"),
                 ("AS", "AS"), ("AU", "AU_U_U"), ("AU", "AU_S_U"),
                 ("AU", "AU_U_S"), ("AU", "AU_D_U"), ("AU", "AU_U_D"),
                 ("ND", "ND"), ("AD", "AD"), ("F", "NOT_REVIEWED")]
        fields = dict(run="run", label="Model", dataset="TAT-QA", model="model", prompt_condition="guided",
                      reasoning="on", cohort="CORRECT", variant="IC_VALUE_01_BEFORE")
        for nasu, detail in cases:
            rows.append({**fields, "nasu": nasu, "detail": detail})
            originals.append(fields.copy())
        result = export.aggregate(rows, originals)[0]
        self.assertEqual(result["planned"], 12)
        self.assertEqual(result["AU"], 5)
        self.assertEqual(result["NU"], 2)
        self.assertEqual(result["NS"] + result["NU_MISMATCH"], 2)
        self.assertEqual(result["AS"] + result["AU_U_U"], 2)
        self.assertEqual(sum(result[k] for k in export.COUNTS[:7]), 12)


if __name__ == "__main__":
    unittest.main()
