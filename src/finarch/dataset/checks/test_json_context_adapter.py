"""Source-preservation and actual-corpus checks for JSON context normalization."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest

converter = importlib.import_module("finarch.dataset.00-input.json_context")
content = importlib.import_module("finarch.dataset.00-input.content")
adapters = importlib.import_module("finarch.dataset.00-input.adapters")
full_finance = importlib.import_module("finarch.dataset.00-input.full_finance")
plans = importlib.import_module("finarch.dataset.02-generation.01-perturbation.generation_plan")
from finarch.dataset.schemas.validation import validate
from finarch.shared.reference import load_raw

ROOT = Path(__file__).resolve().parents[4]


class JsonContextAdapterChecks(unittest.TestCase):
    def convert(self, text):
        result = content.assemble({"context": text}, "finance")
        converter.validate_conversion(text, result)
        return result

    def test_all_actual_nonempty_json_contexts_through_finance_adapter(self):
        sources = json.loads((ROOT / "config/source-catalog.json").read_text())["sources"]
        total, targets, samples = 0, 0, []
        for source in sources:
            if source["adapter"] != "finance":
                continue
            path = (ROOT / "config" / source["path"]).resolve()
            before = path.read_bytes()
            self.assertEqual(hashlib.sha256(before).hexdigest(), source["sha256"])
            provenance = {key: source[key] for key in ("name", "url", "commit", "sha256")}
            records = load_raw(before)
            total += len(records)
            for record in records:
                try:
                    raw = json.loads(record["context"])
                except ValueError:
                    continue
                if not isinstance(raw, (dict, list)) or not raw:
                    continue
                with self.subTest(raw_id=record["question_id"]):
                    targets += 1
                    sample = {"id": "finance-" + record["question_id"],
                              **adapters.finance(record, provenance, distributed=True)}
                    validate("prepared.input", [sample])
                    converter.validate_conversion(record["context"], sample)
                    self.assertEqual(sample["question"], record["question"])
                    self.assertEqual(sample, {"id": sample["id"],
                        **adapters.finance(record, provenance, distributed=True)})
                    samples.append(sample)
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual((total, targets), (2238, 289))
        validate("prepared.input", samples)

    def test_numeric_lexemes_and_string_types_are_preserved(self):
        source = '{"Metric":{"decimal":1.2300,"exponent":1e+3,"negative_zero":-0.00,"string":"001","integer":123456789012345678901234567890}}'
        result = self.convert(source)
        types = {s["json_source"]["pointer"]: s["json_source"]["value_type"]
                 for s in result["context_mapping"]["segments"]}
        self.assertEqual(types["/Metric/string"], "string")
        self.assertEqual(types["/Metric/integer"], "integer")
        for literal in ("1.2300", "1e+3", "-0.00", "001", "123456789012345678901234567890"):
            self.assertIn(literal, result["context"])

    def test_full_input_builder_routes_by_context_shape_and_retains_raw_records(self):
        catalog_path = ROOT / "config/source-catalog.json"
        sources = [source for source in json.loads(catalog_path.read_text())["sources"]
                   if source["adapter"] == "finance"]
        sources.sort(key=lambda source: ("finance-easy", "finance-medium", "finance-hard").index(source["name"]))
        for source in sources:
            source["path"] = str((catalog_path.parent / source["path"]).resolve())
        with tempfile.TemporaryDirectory() as task_temp:
            temporary = Path(task_temp)
            catalog = temporary / "catalog.json"
            catalog.write_text(json.dumps({"sources": sources}))
            output = temporary / "prepared"
            result = full_finance.prepare(catalog, output)
            samples = json.loads((output / "input.json").read_text())
            providers = load_raw((output / "provider-records.json").read_bytes())
            manifest = json.loads((output / "selection-manifest.json").read_text())
            normalized, plain, mixed_source_formats = 0, 0, set()
            for sample in samples:
                record = providers[sample["raw_id"]]["record"]
                try:
                    original = json.loads(record["context"])
                except ValueError:
                    original = None
                is_json = isinstance(original, (dict, list)) and bool(original)
                if is_json:
                    converter.validate_conversion(record["context"], sample)
                    self.assertTrue(sample["source_content"]["tables"])
                    normalized += 1
                else:
                    self.assertEqual(sample["context"], record["context"])
                    plain += 1
                reference = adapters.extract_reference(record["ground_truth"]).fields()
                for key, value in reference.items():
                    self.assertEqual(sample[key], value)
                self.assertEqual(sample["question"], record["question"])
                if record["source"].startswith("FinanceMath-validation-"):
                    mixed_source_formats.add("json" if is_json else "plain_text")
            self.assertEqual(result["totals"]["total"], 2238)
            self.assertEqual(result["totals"]["selected"], len(samples))
            self.assertGreater(normalized, 0)
            self.assertEqual(normalized + plain, len(samples))
            self.assertEqual(mixed_source_formats, {"json", "plain_text"})
            self.assertEqual(manifest["selection_policy"]["duplicate_key"], ["question", "context"])
            self.assertEqual(manifest["input_file_sha256"], hashlib.sha256((output / "input.json").read_bytes()).hexdigest())
            for source in sources:
                self.assertEqual(hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest(), source["sha256"])

    def test_grouping_retains_duplicate_item_names_and_source_order(self):
        source = '{"Assets: -- Net":{"2019":202085},"Liabilities: -- Net":{"2019":83009},"Assets: -- Other":{"2019":7}}'
        result = self.convert(source)
        self.assertEqual(len(result["source_content"]["tables"]), 3)
        cells = [c for t in result["source_content"]["tables"] for c in t["cells"] if c.get("json_source")]
        paths = [c["json_source"]["pointer"] for c in cells if c["column"] == 0]
        self.assertEqual(paths, ["/Assets: -- Net", "/Liabilities: -- Net", "/Assets: -- Other"])
        for t in result["source_content"]["tables"]:
            self.assertEqual(len(t["cells"]), len({c["id"] for c in t["cells"]}))

    def test_empty_missing_null_boolean_and_dashes_are_distinct(self):
        source = '{"A":{"empty":"","dash":"—","nothing":null,"flag":false},"B":{"flag":true}}'
        result = self.convert(source)
        self.assertIn("[missing]", result["context"])
        self.assertIn("null", result["context"])
        self.assertIn("false", result["context"])
        cells = {s["json_source"]["pointer"]: s for s in result["context_mapping"]["segments"]}
        self.assertEqual(cells["/A/empty"]["text"], "")
        self.assertEqual(cells["/A/nothing"]["json_source"]["value_type"], "null")

    def test_unicode_pointer_escaping_and_markdown_characters(self):
        source = json.dumps({"😀 A/B~C": {"2019": "12|34\n56\r78 & <br> \\"}}, ensure_ascii=False)
        result = self.convert(source)
        cell = next(s for s in result["context_mapping"]["segments"]
                    if s["json_source"]["value_type"] == "string")
        self.assertEqual(cell["json_source"]["pointer"], "/😀 A~1B~0C/2019")
        self.assertEqual(converter.unescape_cell(cell["text"]), "12|34\n56\r78 & <br> \\")
        self.assertEqual([n["text"] for n in cell["numbers"]], ["12", "34", "56", "78"])

    def test_existing_table_string_array_is_unwrapped_and_cells_bound(self):
        table = "| Debt | $10 million |\n|---|---|\n| Cash | $2.5 million |"
        result = self.convert(json.dumps([table]))
        self.assertEqual(result["context"], table)
        self.assertEqual(result["source_content"]["tables"][0]["rows"],
                         [["Debt", "$10 million"], ["Cash", "$2.5 million"]])
        self.assertTrue(all(c["json_source"]["pointer"] == "/0"
                            for c in result["source_content"]["tables"][0]["cells"]))

    def test_valid_unsupported_json_and_duplicate_keys_are_rejected(self):
        for source in ('{"A":{"x":{"amount":1}}}', '[{"amount":1}]',
                       '{"A":{"x":1,"x":2}}', '{"A":{"x":NaN}}'):
            with self.subTest(source=source), self.assertRaises(converter.JsonContextError):
                content.assemble({"context": source}, "finance")

    def test_ordinary_bracketed_prose_and_empty_contexts_are_not_normalized(self):
        for text in ("[Report](https://example.org) debt: 10.", "Revenue is 10.", "[]", "{}"):
            result = content.assemble({"context": text}, "finance")
            self.assertEqual(result["context"], text)
            self.assertFalse(result["source_content"]["tables"])

    def test_changed_rendered_value_and_type_are_detected(self):
        source = '{"Sales":{"2019":100.0}}'
        original = self.convert(source)
        changed = copy.deepcopy(original)
        location = next(s for s in changed["context_mapping"]["segments"] if s["text"] == "100.0")
        a, b = location["context_span"]
        changed["context"] = changed["context"][:a] + "900.0" + changed["context"][b:]
        with self.assertRaises(converter.JsonContextError):
            converter.validate_conversion(source, changed)
        changed = copy.deepcopy(original)
        for location in changed["context_mapping"]["segments"]:
            if location["text"] == "100.0":
                location["json_source"]["value_type"] = "string"
        with self.assertRaises(converter.JsonContextError):
            converter.validate_conversion(source, changed)

    def test_value_claim_boundaries_keep_entire_converted_table_intact(self):
        result = self.convert('{"Revenue":{"2019":100.0,"2018":80.0},"Cost":{"2019":60.0,"2018":50.0}}')
        context = result["context"]
        start = context.index("100.0")
        self.assertEqual(plans.value_boundaries(context, [start, start + 5]), (0, len(context)))


if __name__ == "__main__":
    unittest.main()
