"""Source-backed preparation checks. All derived outputs are temporary.

No invented financial records, source edits, provider solution execution or LLM calls.
"""

import importlib
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

load_case = __import__('finarch.dataset.90-operations.staging', fromlist=['load_case']).load_case
PreparedInputs = __import__('finarch.dataset.90-operations.staging', fromlist=['PreparedInputs']).PreparedInputs

build = importlib.import_module("finarch.dataset.00-input.build")
ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()


class PreparationChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="finarch-preparation-check-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = json.loads((ROOT / "config/source-catalog.json").read_text())
        for spec in self.catalog["sources"]:
            spec["path"] = str((ROOT / "config" / spec["path"]).resolve())
        self.catalog_path = self.root / "catalog.json"
        self.save_catalog()

    def save_catalog(self):
        self.catalog_path.write_text(json.dumps(self.catalog))

    def prepare(self, name="output", **kwargs):
        output = self.root / name
        build.prepare(self.catalog_path, output, seed="raw-ratio-check", **kwargs)
        return output

    def test_owner_ratio_and_no_silent_rounding(self):
        for total, expected in [(10, (3, 2, 1, 4)), (30, (9, 6, 3, 12)), (100, (30, 20, 10, 40))]:
            self.assertEqual(tuple(build.source_counts(total).values()), expected)
        for total in (0, -10, 9, 11, 30.0, True):
            with self.assertRaisesRegex(ValueError, "MULTIPLE_OF_TEN"):
                build.source_counts(total)

    def test_real_inputs_reproducible_and_grounded(self):
        first = self.prepare("first", total=10)
        second = self.prepare("second", total=10)
        self.assertEqual((first / "input.json").read_bytes(), (second / "input.json").read_bytes())
        samples = json.loads((first / "input.json").read_text())
        self.assertEqual(Counter(s["provenance"]["name"] for s in samples), build.source_counts(10))
        self.assertEqual([s["id"] for s in samples], [f"test-{i:04d}" for i in range(1, 11)])
        manifest = json.loads((first / "selection-manifest.json").read_text())
        self.assertEqual(manifest["families"], 10)
        self.assertEqual(manifest["model_calls"], 0)
        providers = json.loads((first / "provider-records.json").read_text())
        self.assertEqual(set(providers), {s["raw_id"] for s in samples})
        for sample in samples:
            loaded = load_case(first / "input.json", sample["id"])
            self.assertEqual(loaded["sample"], sample)
            self.assertEqual(loaded["provider_record"], providers[sample["raw_id"]])
            record = loaded["provider_record"]["record"]
            source = json.loads(Path(loaded["comparison"]["source"]["path"]).read_text())
            self.assertEqual(record, source[loaded["comparison"]["record_index"]])
            question_id = loaded["provider_record"]["question_id"]
            original_question = (record["question"] if question_id is None else
                                 next(q["question"] for q in record["questions"] if q["uid"] == question_id))
            self.assertEqual(sample["question"], original_question)
            for segment in sample["context_mapping"]["segments"]:
                value = record
                for key in segment["source_pointer"].split("/")[1:]:
                    value = value[int(key)] if isinstance(value, list) else value[key]
                self.assertEqual(segment["text"], str(value))
                a, b = segment["context_span"]
                self.assertEqual(sample["context"][a:b], str(value))

    def test_hash_failure_retains_previous_source_counts(self):
        self.catalog["sources"][1]["sha256"] = "0" * 64
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
            self.prepare(total=10)
        result = json.loads((self.root / "output/preparation-result.json").read_text())
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["source"], self.catalog["sources"][1]["name"])
        self.assertEqual(result["stage"], "source_integrity")
        self.assertGreater(result["counts"]["finance-easy:examined"], 0)
        self.assertTrue(result["exclusions"])

    def test_candidate_shortage_retains_exclusions(self):
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_ELIGIBLE_INPUTS"):
            self.prepare(per_source=100000)
        result = json.loads((self.root / "output/preparation-result.json").read_text())
        self.assertEqual(result["stage"], "select")
        self.assertEqual(result["counts"]["finance-easy:requested"], 100000)
        self.assertTrue(result["exclusions"])

    def test_partial_written_case_cannot_be_loaded(self):
        original_write = build.write_json

        def fail_second_case(path, value):
            if path.name == "selection-manifest.json":
                raise OSError("injected output write failure")
            original_write(path, value)

        with patch.object(build, "write_json", side_effect=fail_second_case):
            with self.assertRaisesRegex(OSError, "injected"):
                self.prepare(total=10)
        case = self.root / "output/input.json"
        self.assertTrue(case.exists())
        with self.assertRaisesRegex(ValueError, "PREPARATION_NOT_COMPLETE"):
            load_case(case, "test-0001")
        result = json.loads((self.root / "output/preparation-result.json").read_text())
        self.assertEqual(result["stage"], "write_bundle")
        self.assertIsNone(result["record_index"])

    def test_incomplete_or_changed_bundle_is_rejected(self):
        output = self.prepare(total=10)
        case = output / "input.json"
        result = output / "preparation-result.json"
        saved = result.read_bytes()
        result.unlink()
        with self.assertRaisesRegex(ValueError, "PREPARATION_NOT_COMPLETE"):
            load_case(case, "test-0001")
        result.write_bytes(saved)
        with (output / "selection-manifest.json").open("a") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "MANIFEST_HASH_MISMATCH"):
            load_case(case, "test-0001")

    def test_collection_selection_and_tampering(self):
        output = self.prepare(total=10)
        self.assertFalse((output / "cases").exists())
        inputs = PreparedInputs(output / "input.json")
        case = inputs.case("test-0001")
        case["sample"]["question"] = "changed"
        self.assertNotEqual(inputs.case("test-0001")["sample"]["question"], "changed")
        with self.assertRaisesRegex(ValueError, "UNKNOWN_INPUT_ID"):
            inputs.case("missing")
        with self.assertRaisesRegex(ValueError, "INPUT_ID_REQUIRED"):
            load_case(output / "input.json")
        for name, message in [("input.json", "INPUT_HASH"), ("provider-records.json", "RECORD_HASH")]:
            path = output / name
            saved = path.read_bytes()
            path.write_bytes(saved + b" ")
            with self.assertRaisesRegex(ValueError, message):
                PreparedInputs(output / "input.json")
            path.write_bytes(saved)

    def test_existing_output_is_not_changed(self):
        output = self.root / "output"
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_text("existing output")
        with self.assertRaises(FileExistsError):
            self.prepare(total=10)
        self.assertEqual(list(output.iterdir()), [marker])
        self.assertEqual(marker.read_text(), "existing output")


if __name__ == "__main__":
    unittest.main()
