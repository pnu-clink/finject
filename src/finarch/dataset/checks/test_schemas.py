"""Schema boundary checks; raw inputs are real, transports are local test doubles."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from finarch.dataset.schemas.registry import CONTRACTS, LLM_ROLES, describe, export
from finarch.dataset.schemas.validation import validate, check_json
PreparedInputs = __import__('finarch.dataset.90-operations.staging', fromlist=['PreparedInputs']).PreparedInputs
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
StepStopped = __import__('finarch.dataset.90-operations.staging', fromlist=['StepStopped']).StepStopped
from finarch.shared.providers.structured import complete

ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()

class SchemaChecks(unittest.TestCase):
    def test_all_prepared_inputs_without_rewriting(self):
        for name in ("first-10", "next-30", "first-100"):
            path = ROOT / "data/prepared" / name / "input.json"
            before = path.read_bytes()
            PreparedInputs(path)
            self.assertEqual(before, path.read_bytes())

    def test_reference_types_and_source_locations(self):
        data = json.loads((ROOT / "data/prepared/first-10/input.json").read_text())
        changes = [("reference_precision", "0"), ("reference_precision", True),
                   ("reference_answer", "not a number"), ("extra", 1)]
        for key, value in changes:
            changed = copy.deepcopy(data)
            changed[0][key] = value
            with self.assertRaises(ValidationError):
                validate("prepared.input", changed)
        changed = copy.deepcopy(data)
        changed[0]["answer_metadata"]["negative"] = True
        with self.assertRaises(ValidationError):
            validate("prepared.input", changed)
        changed = copy.deepcopy(data)
        changed[0]["context_mapping"]["segments"][0]["context_span"][1] -= 1
        with self.assertRaises(ValidationError):
            validate("prepared.input", changed)

    def test_report_identifies_invalid_field_without_repair(self):
        original = '{"text": 42}'
        result = check_json("dtt.answer.response", original)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["errors"][0]["loc"], ("text",))
        self.assertEqual(result["errors"][0]["type"], "string_type")
        self.assertEqual(check_json("dtt.answer.response", '{"text":"ok"}')["status"], "PASS")
        duplicate = check_json("dtt.answer.response", '{"text":"a","text":"b"}')
        self.assertEqual(duplicate["reason"], "JSON_INVALID")

    def test_generated_files_match_canonical_definitions(self):
        with tempfile.TemporaryDirectory() as d:
            index = export(d)
            self.assertEqual(len(index), len(CONTRACTS))
            for item in index:
                generated = json.loads((Path(d) / item["file"]).read_text())
                self.assertEqual(generated, describe(item["schema_id"])["schema"])

    def call(self, raw, payload=None, role="dtt.answer", schema_mode="prompt"):
        calls, files = [], {}
        def transport(**request):
            calls.append(request)
            return raw
        result = complete(role, payload if payload is not None else {"context": "C", "question": "Q"},
                          transport=transport, save=lambda key, value: files.__setitem__(key, value),
                          schema_mode=schema_mode)
        return result, calls, files

    def test_send_schema_then_validate_no_retry(self):
        result, calls, files = self.call('{"text":"local boundary test"}')
        self.assertEqual(result.status, "PASS")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["response_schema"], describe("dtt.answer.response")["schema"])
        self.assertEqual(files["03-result/schema-check.json"]["status"], "PASS")

    def test_invalid_outputs_preserved_and_rejected(self):
        for raw in ('{}', '{"text":4}', '{"text":"ok","extra":1}',
                    '{"text":"a","text":"b"}', 'not json'):
            result, calls, files = self.call(raw)
            self.assertEqual(result.status, "FAIL")
            self.assertEqual(len(calls), 1)
            self.assertEqual(files["02-raw-response.json"]["text"], raw)

    def test_blind_input_rejects_private_fields_before_call(self):
        result, calls, _ = self.call('{"text":"unused"}', {"context":"C","question":"Q","reference_answer":"42"})
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(calls, [])

    def test_draft_role_stops_before_model_call(self):
        result, calls, _ = self.call('{}', role="dag.source")
        self.assertEqual(result.status, "NOT_IMPLEMENTED")
        self.assertEqual(calls, [])

    def test_program_schema_does_not_limit_python_operators(self):
        value = {"code": "import math\nanswer = math.log(10) ** 2", "facts": [
            {"id":"a", "value": "10", "text": "10", "span": [0,2], "unit": None}], "grounding": "Schema shape only"}
        self.assertIs(validate("pot.author.response", value), value)

    def test_invoke_cannot_pass_invalid_llm_output(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = RunContext(Path(d)/"run", {"01-preparation.03-calculation.pot": lambda p, *, response_schema: StepResult("PASS", "invalid", {"code":"answer=1"})})
            with self.assertRaises(StepStopped) as error:
                ctx.invoke("02-calculation", "P01-author", "01-preparation.03-calculation.pot", {})
            self.assertEqual(error.exception.result.status, "FAIL")
            raw = json.loads((ctx.root/"02-calculation/01-generate-code/05-validate-response/02-handler-response.json").read_text())
            self.assertEqual(raw["data"], {"code":"answer=1"})
            self.assertTrue((ctx.root/"02-calculation/01-generate-code/05-validate-response/03-handler-check.json").exists())

    def test_missing_response_schema_blocks_every_role_before_transport(self):
        for role in LLM_ROLES:
            with self.subTest(role=role):
                remaining = {k: v for k, v in CONTRACTS.items() if k != role + ".response"}
                with patch.dict(CONTRACTS, remaining, clear=True):
                    result, calls, files = self.call('{}', role=role)
                self.assertEqual((result.status, result.reason), ("FAIL", "MISSING_LLM_SCHEMA"))
                self.assertEqual(calls, [])
                self.assertFalse(files["03-result/schema-check.json"]["transport_invoked"])
                self.assertNotIn("01-input/model-request.json", files)

    def test_missing_internal_input_definition_blocks_transport(self):
        for role in ("01-preparation.03-calculation.pot", "dtt.answer"):
            with self.subTest(role=role):
                remaining = {k: v for k, v in CONTRACTS.items() if k != role + ".request"}
                with patch.dict(CONTRACTS, remaining, clear=True):
                    result, calls, files = self.call('{}', role=role)
                self.assertEqual(result.reason, "MISSING_LLM_SCHEMA")
                self.assertEqual(calls, [])
                self.assertEqual(files["03-result/schema-check.json"]["schema_id"], role + ".request")

    def test_unknown_role_and_unspecified_mode_are_recorded_without_transport(self):
        for options, reason in (({"role": "pot.new_author"}, "UNKNOWN_LLM_ROLE"),
                                ({"role": None}, "UNKNOWN_LLM_ROLE"),
                                ({"schema_mode": None}, "EXPLICIT_SCHEMA_MODE_REQUIRED")):
            with self.subTest(options=options):
                result, calls, files = self.call('{}', **options)
                self.assertEqual((result.status, result.reason), ("FAIL", reason))
                self.assertEqual(calls, [])
                self.assertEqual(files["03-result/schema-check.json"]["phase"], "before_call")

    def test_empty_response_definition_is_not_a_schema(self):
        definition = {**describe("dtt.answer.response"), "schema": {}}
        with patch("finarch.dataset.schemas.registry.describe", return_value=definition):
            result, calls, files = self.call('{}')
        self.assertEqual(result.reason, "INVALID_LLM_SCHEMA")
        self.assertEqual(calls, [])
        self.assertFalse(files["03-result/schema-check.json"]["transport_invoked"])

    def test_missing_response_schema_blocks_all_stage_handlers_and_local_overrides(self):
        for role in LLM_ROLES:
            for use_local in (False, True):
                with self.subTest(role=role, local=use_local), tempfile.TemporaryDirectory() as d:
                    calls = []
                    def handler(payload, *, response_schema):
                        calls.append(payload)
                        return StepResult("PASS", "must not run", {})
                    ctx = RunContext(Path(d)/"run", {role: handler})
                    remaining = {k: v for k, v in CONTRACTS.items() if k != role + ".response"}
                    with patch.dict(CONTRACTS, remaining, clear=True), self.assertRaises(StepStopped) as error:
                        ctx.invoke("test", "step", role, {}, local=handler if use_local else None)
                    self.assertEqual(error.exception.result.reason, "MISSING_LLM_SCHEMA")
                    self.assertEqual(calls, [])
                    report = json.loads((ctx.root/"test/step/03-result/schema-check.json").read_text())
                    self.assertFalse(report["handler_invoked"])
                    events = [json.loads(line) for line in (ctx.root/"events.jsonl").read_text().splitlines()]
                    event = [e for e in events if e["phase"] == "END" and e.get("role") == role][-1]
                    self.assertEqual((event["status"], event["reason"]), ("FAIL", "MISSING_LLM_SCHEMA"))

    def test_unregistered_hook_cannot_bypass_llm_check(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            handler = lambda payload: calls.append(payload)
            ctx = RunContext(Path(d)/"run", {"pot.new_author": handler})
            with self.assertRaises(StepStopped) as error:
                ctx.invoke("test", "step", "pot.new_author", {}, local=handler)
            self.assertEqual(error.exception.result.reason, "UNREGISTERED_STAGE_HOOK")
            self.assertEqual(calls, [])

    def test_every_llm_stage_receives_schema_before_call_and_rejects_invalid_response(self):
        for role in LLM_ROLES:
            with self.subTest(role=role), tempfile.TemporaryDirectory() as d:
                calls = []
                def handler(payload, *, response_schema):
                    calls.append(response_schema)
                    saved = json.loads((ctx.root/"test/step/01-input/response-schema.json").read_text())
                    self.assertEqual(saved["schema"], response_schema)
                    return StepResult("PASS", "test invalid output", {"unrecognized": 1})
                ctx = RunContext(Path(d)/"run", {role: handler})
                with self.assertRaises(StepStopped) as error:
                    ctx.invoke("test", "step", role, {})
                self.assertEqual(error.exception.result.reason, "RESPONSE_SCHEMA_INVALID")
                self.assertEqual(calls, [describe(role + ".response")["schema"]])
                raw = json.loads((ctx.root/"test/step/02-raw-response.json").read_text())
                self.assertEqual(raw["data"], {"unrecognized": 1})
                self.assertEqual(json.loads((ctx.root/"test/step/03-result/schema-check.json").read_text())["status"], "FAIL")

    def test_old_schema_free_handler_is_not_retried_without_schema(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            def handler(payload):
                calls.append(payload)
                return StepResult("PASS", "must not run", {"text": "unused"})
            ctx = RunContext(Path(d)/"run", {"dtt.answer": handler})
            with self.assertRaises(StepStopped) as error:
                ctx.invoke("test", "step", "dtt.answer", {})
            self.assertEqual(error.exception.result.status, "FAIL")
            self.assertEqual(calls, [])

if __name__ == "__main__":
    unittest.main()
