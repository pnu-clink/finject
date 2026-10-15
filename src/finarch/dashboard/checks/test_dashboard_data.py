"""Regression checks for the read-only experiment dashboard payload."""
import hashlib
import json
import tempfile
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

dashboard_data = __import__('finarch.dashboard.01-data.data', fromlist=['*'])
ROOT = __import__('finarch.dashboard.01-data.data', fromlist=['ROOT']).ROOT
SOURCE_PATHS = __import__('finarch.dashboard.01-data.data', fromlist=['SOURCE_PATHS']).SOURCE_PATHS
load_data = __import__('finarch.dashboard.01-data.data', fromlist=['load_data']).load_data
response_detail = __import__('finarch.dashboard.01-data.data', fromlist=['response_detail']).response_detail


class Fixture:
    def __init__(self, project):
        self.project = project
        self.rows = []
        self.add("zero", answer=0, metric_zero=True)
        self.add("null", answer=None)
        self.add("missing", missing=True)
        self.write_sources()

    def save(self, path, value):
        target = self.project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value) + "\n")

    def add(self, trial, answer=None, metric_zero=False, missing=False):
        call_path = f"reports/experiments-run/fixture/model/calls/{trial}/call.json"
        result_path = f"reports/experiments-run/fixture/model/calls/{trial}/result.json"
        raw_path = f"reports/experiments-run/fixture/model/calls/{trial}/raw-response.json"
        response = None if missing else {"answer": answer, "answer_meta": {"negative": None if answer is None else False, "scale": None}, "explanation": "Saved explanation.", "evidence": []}
        row = {"run_id": "fixture", "model": "model", "trial_id": trial,
               "case": "case-" + trial, "variant": "ORIGINAL", "prompt_condition": "P0", "reasoning": "off",
               "response": response, "saved_status": "NOT_COLLECTED" if missing else "VALID",
               "response_object_observed": not missing, "answer_field_observed": not missing,
               "answer_is_null": None if missing else answer is None,
               "signed_numeric_field": "0" if answer == 0 else None,
               "call_path": call_path, "result_path": result_path, "raw_path": raw_path,
               "original_outcome": "NOT_NUMERICALLY_EVALUATED", "tags": []}
        self.rows.append(row)
        if missing:
            return
        result = {"response": response}
        if metric_zero:
            result.update(elapsed_seconds=0, token_cost_estimate_usd=0,
                          usage={"input_tokens": 0, "output_tokens": 0,
                                 "output_tokens_details": {"reasoning_tokens": 0}})
        self.save(call_path, {"request": {"trial_id": trial, "input": {"question": "q" * 180, "context": "Actual context for " + trial}}, "result": result})
        self.save(result_path, result)

    def write_sources(self):
        path = self.project / SOURCE_PATHS["rows"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row) + "\n" for row in self.rows))
        self.save(SOURCE_PATHS["summary"], {"run_id": "fixture", "model": "model", "source_run": "reports/experiments-run/fixture", "overall": {"planned": len(self.rows)}})
        self.save(SOURCE_PATHS["contrasts"], {"kind": "SAVED_CONTRASTS"})
        self.save(SOURCE_PATHS["review_evidence"], {"responses": [], "review_notes": [], "semantic_gold_assigned": False})
        self.save(SOURCE_PATHS["a100"], {"status": "RUNNING", "updated_at": "saved-time", "gpu_cost_usd": None})
        self.save(SOURCE_PATHS["execution"], {"experiment_request_attempts": 1, "successful_responses": 0})

    def update_result(self, trial, **values):
        row = next(row for row in self.rows if row["trial_id"] == trial)
        path = self.project / row["call_path"]
        call = json.loads(path.read_text())
        call["result"].update(values)
        self.save(row["call_path"], call)


class DashboardDataChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.fixture = Fixture(self.project)

    def test_null_missing_and_real_zero_are_distinct(self):
        payload = load_data(self.project)
        rows = {row["trial_id"]: row for row in payload["rows"]}
        self.assertEqual(rows["zero"]["signed_numeric_field"], "0")
        self.assertIs(rows["zero"]["answer_is_null"], False)
        self.assertIs(rows["null"]["answer_is_null"], True)
        self.assertIsNone(rows["missing"]["answer_is_null"])
        self.assertIs(rows["missing"]["response_object_observed"], False)
        self.assertEqual(rows["zero"]["metrics"], {"elapsed_seconds": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "cost_estimate_usd": 0})
        self.assertTrue(all(value is None for value in rows["null"]["metrics"].values()))
        self.assertTrue(all(value is None for value in rows["missing"]["metrics"].values()))
        self.assertEqual(len(rows["zero"]["question_preview"]), 160)
        self.assertIsNone(rows["missing"]["question_preview"])
        self.assertEqual(rows["missing"]["data_warnings"], ["CALL_ARTIFACT_MISSING"])

    def test_detail_uses_registered_call_request(self):
        detail = response_detail("zero", self.project)
        self.assertEqual(detail["context"], "Actual context for zero")
        self.assertEqual(detail["question"], "q" * 180)
        self.assertEqual(detail["response"]["answer"], 0)
        missing = response_detail("missing", self.project)
        self.assertIsNone(missing["question"])
        self.assertIsNone(missing["response"])

    def test_timing_preserves_saved_offset_and_real_epoch_zero(self):
        self.fixture.update_result("zero", started_at="1970-01-01T09:00:00+09:00", ended_at="1970-01-01T00:00:00.125Z")
        row = load_data(self.project)["rows"][0]
        self.assertEqual(row["timing"], {
            "started_at": "1970-01-01T09:00:00+09:00", "ended_at": "1970-01-01T00:00:00.125Z",
            "started_epoch_ms": 0, "ended_epoch_ms": 125,
        })
        self.assertEqual(row["metrics"]["elapsed_seconds"], 0)
        self.assertEqual(row["data_warnings"], [])

    def test_timing_null_and_missing_are_not_synthetic_dates(self):
        self.fixture.update_result("zero", started_at=None, ended_at=None)
        payload = load_data(self.project)
        for row in payload["rows"]:
            self.assertTrue(all(value is None for value in row["timing"].values()))
        self.assertEqual(payload["rows"][0]["data_warnings"], [])
        self.fixture.update_result("zero", ended_at="1970-01-01T00:00:00Z")
        timing = load_data(self.project, refresh=True)["rows"][0]["timing"]
        self.assertIsNone(timing["started_epoch_ms"])
        self.assertEqual(timing["ended_epoch_ms"], 0)

    def test_invalid_or_naive_timestamps_are_null_with_warnings(self):
        invalid = (0, False, "", "2026-02-30T12:00:00Z", "2026-01-01T25:00:00Z",
                   "2026-01-01T12:00:00+00:99", "2026-01-01X12:00:00Z", "not-a-date")
        for value in invalid:
            with self.subTest(value=value):
                self.fixture.update_result("zero", started_at=value, ended_at="2026-01-01T12:00:00")
                row = load_data(self.project, refresh=True)["rows"][0]
                self.assertTrue(all(value is None for value in row["timing"].values()))
                self.assertEqual(row["data_warnings"], ["TIMING_STARTED_AT_INVALID", "TIMING_ENDED_AT_TIMEZONE_MISSING"])
                self.assertEqual(row["metrics"]["elapsed_seconds"], 0)

    def test_reversed_timestamps_remain_observable_without_changing_elapsed(self):
        self.fixture.update_result("zero", started_at="1970-01-01T00:00:01Z", ended_at="1970-01-01T00:00:00Z")
        row = load_data(self.project)["rows"][0]
        self.assertEqual(row["timing"]["started_epoch_ms"], 1000)
        self.assertEqual(row["timing"]["ended_epoch_ms"], 0)
        self.assertEqual(row["data_warnings"], ["TIMING_END_BEFORE_START"])
        self.assertEqual(row["metrics"]["elapsed_seconds"], 0)
        self.fixture.update_result("zero", started_at="1970-01-01T00:00:00.000900Z", ended_at="1970-01-01T00:00:00.000100Z")
        row = load_data(self.project, refresh=True)["rows"][0]
        self.assertEqual(row["timing"]["started_epoch_ms"], row["timing"]["ended_epoch_ms"])
        self.assertEqual(row["data_warnings"], ["TIMING_END_BEFORE_START"])

    def test_timing_compares_instants_across_offsets_and_preserves_pre_epoch(self):
        self.fixture.update_result("zero", started_at="1969-12-31T23:59:59.999999Z", ended_at="1970-01-01T09:00+09")
        row = load_data(self.project)["rows"][0]
        self.assertEqual(row["timing"]["started_epoch_ms"], -1)
        self.assertEqual(row["timing"]["ended_epoch_ms"], 0)
        self.assertEqual(row["data_warnings"], [])
        self.fixture.update_result("zero", started_at="2026-09-23T09:00:00+09:00", ended_at="2026-09-23T00:00:00Z")
        row = load_data(self.project, refresh=True)["rows"][0]
        self.assertEqual(row["timing"]["started_epoch_ms"], row["timing"]["ended_epoch_ms"])
        self.assertEqual(row["data_warnings"], [])

    def test_unsafe_and_unknown_ids_are_rejected(self):
        for value in ("../status", "/tmp/file", "%2e%2e%2f", "x/y", "", None, "a\x00b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                response_detail(value, self.project)
        with self.assertRaises(KeyError):
            response_detail("unregistered", self.project)

    def test_registered_path_cannot_escape_experiment_directory(self):
        self.fixture.rows[0]["call_path"] = "reports/run/secret.json"
        self.fixture.write_sources()
        with self.assertRaisesRegex(ValueError, "UNSAFE_REGISTERED_ARTIFACT_PATH"):
            load_data(self.project)

    def test_registered_symlink_cannot_escape(self):
        call = self.project / self.fixture.rows[0]["call_path"]
        call.unlink()
        outside = self.project / "outside.json"
        outside.write_text('{}')
        call.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "UNSAFE_REGISTERED_ARTIFACT_PATH"):
            load_data(self.project)

    def test_cache_reuse_refresh_and_source_change(self):
        first = load_data(self.project)
        self.assertIs(first, load_data(self.project))
        refreshed = load_data(self.project, refresh=True)
        self.assertIsNot(first, refreshed)
        self.fixture.save(SOURCE_PATHS["execution"], {"experiment_request_attempts": 2, "successful_responses": 0})
        changed = load_data(self.project)
        self.assertIsNot(refreshed, changed)
        self.assertEqual(changed["execution"]["experiment_request_attempts"], 2)
        self.fixture.save(SOURCE_PATHS["a100"], {"status": "FINISHED", "updated_at": "new-saved-time"})
        latest = load_data(self.project)
        self.assertEqual(latest["a100"]["snapshot_at"], "new-saved-time")
        self.assertIs(latest["a100"]["live_state_verified"], False)

    def test_rows_and_summary_changes_invalidate_cache(self):
        first = load_data(self.project)
        self.fixture.rows[0]['tags'].append('SAVED_NEW_OBSERVATION')
        self.fixture.write_sources()
        changed = load_data(self.project)
        self.assertIsNot(first, changed)
        self.assertEqual(changed['rows'][0]['tags'], ['SAVED_NEW_OBSERVATION'])
        self.assertNotEqual(first['source_sha256'][str(SOURCE_PATHS['rows'])], changed['source_sha256'][str(SOURCE_PATHS['rows'])])
        summary = dict(changed['summary'], saved_annotation='Updated summary')
        self.fixture.save(SOURCE_PATHS['summary'], summary)
        latest = load_data(self.project)
        self.assertIsNot(changed, latest)
        self.assertEqual(latest['summary']['saved_annotation'], 'Updated summary')

    def test_concurrent_cold_requests_build_one_snapshot(self):
        with patch.object(dashboard_data, '_build', wraps=dashboard_data._build) as build:
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(lambda _: load_data(self.project), range(4)))
            self.assertEqual(build.call_count, 1)
            self.assertTrue(all(result is results[0] for result in results))

    def test_no_writes_and_saved_sources_have_hashes(self):
        before = {str(path): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
                  for path in self.project.rglob('*') if path.is_file()}
        payload = load_data(self.project)
        response_detail("zero", self.project)
        after = {str(path): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in self.project.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(set(payload["source_files"]), set(payload["source_sha256"]))
        self.assertEqual(payload["new_model_calls"], 0)
        self.assertEqual(payload["semantic_assessment"], "NOT_SCORED")

    def test_recorded_call_must_match_trial(self):
        path = self.project / self.fixture.rows[0]["call_path"]
        call = json.loads(path.read_text())
        call['request']['trial_id'] = 'different'
        path.write_text(json.dumps(call))
        with self.assertRaisesRegex(ValueError, 'REGISTERED_CALL_TRIAL_MISMATCH'):
            load_data(self.project)


class SavedBaselineChecks(unittest.TestCase):
    def test_all_3000_rows_and_existing_counts_are_preserved(self):
        payload = load_data(ROOT, refresh=True)
        original = [json.loads(line) for line in (ROOT / SOURCE_PATHS['rows']).read_text().splitlines() if line]
        self.assertEqual(len(payload['rows']), 3000)
        self.assertEqual(payload['run_id'], '20260920-exp-006')
        self.assertEqual(payload['summary'], json.loads((ROOT / SOURCE_PATHS['summary']).read_text()))
        self.assertEqual(Counter(row['saved_status'] for row in payload['rows']), {'VALID': 2768, 'INVALID_RESPONSE': 232})
        tags = Counter(tag for row in payload['rows'] for tag in row['tags'])
        self.assertEqual(tags['DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER'], 211)
        self.assertEqual(tags['SAVED_DECIMAL_PLACES_FAILURE'], 21)
        self.assertEqual(tags['EVIDENCE_NOT_EXACT_SUBSTRING'], 412)
        for source, row in zip(original, payload['rows']):
            self.assertEqual(source, {key: row[key] for key in source})
        self.assertTrue(all(row['metrics']['elapsed_seconds'] is not None for row in payload['rows']))
        self.assertTrue(all(row['metrics']['cost_estimate_usd'] is not None for row in payload['rows']))
        self.assertTrue(all(len(row['question_preview']) <= 160 for row in payload['rows']))
        self.assertEqual(payload['a100']['snapshot_at'], payload['a100']['updated_at'])

    def test_all_3000_timings_come_from_saved_call_results(self):
        payload = load_data(ROOT)
        for row in payload["rows"]:
            call = json.loads((ROOT / row["call_path"]).read_text())
            for field in ("started_at", "ended_at"):
                self.assertEqual(row["timing"][field], call["result"][field])
                parsed = datetime.fromisoformat(call["result"][field]).astimezone(timezone.utc)
                self.assertEqual(row["timing"][field.replace("_at", "_epoch_ms")], int(parsed.timestamp()) * 1000)
            self.assertLessEqual(row["timing"]["started_epoch_ms"], row["timing"]["ended_epoch_ms"])
            self.assertFalse(any(warning.startswith("TIMING_") for warning in row["data_warnings"]))


if __name__ == '__main__':
    unittest.main()
