"""Offline provenance and saved-report boundaries; never call a provider."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError
from finarch.dataset.shared.review.quality_scope import adapt, Snapshot, SOURCES, build
from finarch.dataset.schemas.quality_scope import QualityReport, QualityRecord
from finarch.dataset.viewer.reports.quality_report import view, source
from finarch.shared.providers.profiles import read_profile
from finarch.shared.providers.cli import read_settings

PROJECT = (Path(__file__).resolve().parent / '../../../..').resolve()


def fixture():
    frozen = {'id': 'test-0001/06-ea-earlier-input', 'context': 'Remaining evidence.', 'question': 'What amount?'}
    observation = {k: frozen[k] for k in ('context', 'question')}
    findings = [{'criterion': key, 'judgment': 'PASS', 'reason': ''}
                for key in ('planned_change', 'unintended_change', 'readability')]
    audit = {'audit_version': 3, 'status': 'PASS', 'scope': 'FINAL_TEXT_ONLY', 'model': 'gpt-5.6-luna',
             'effort': 'max', 'findings': findings, 'full_EA_verdict': 'NOT_EVALUATED',
             'stage18': 'NOT_RUN', 'recovery_review': 'DEFERRED_BY_USER'}
    decision = {'decision': 'APPROVED', 'reviewer': 'user-directed-bulk-accept',
                'reason': 'Accepted on explicit user instruction.', 'recorded_at': '2026-09-16T00:00:00Z'}
    values = {'generation': {'observation': observation, 'status': 'PASS', 'audit': audit, 'axis': 'EA'},
              'audit': audit, 'audit_raw': {'text': json.dumps({'findings': findings})},
              'audit_request': {'input': observation}, 'audit_call': {'model': 'gpt-5.6-luna'},
              'audit_profile': {'id': 'luna-max-api', 'model': 'gpt-5.6-luna', 'effort': 'max'},
              'decision': decision, 'decision_history': [decision]}
    refs = {key: {'path': 'fixture/' + key + '.json', 'sha256': 'a' * 64} for key in SOURCES}
    return frozen, values, refs


class QualityScopeChecks(unittest.TestCase):
    def test_bulk_is_not_independent_review(self):
        frozen, values, refs = fixture();record = adapt(frozen, values, refs)
        self.assertEqual(record.approval.method, 'BULK_AT_USER_DIRECTION')
        self.assertEqual(record.independent_review.status, 'NOT_REVIEWED')
        self.assertEqual(record.status, 'RECORDED')

    def test_legacy_user_or_missing_reviewer_is_unknown(self):
        for reviewer in ('user', None):
            frozen, values, refs = fixture();values['decision']['reviewer'] = reviewer
            record = adapt(frozen, values, refs)
            self.assertEqual(record.approval.method, 'UNKNOWN')
            self.assertEqual(record.independent_review.status, 'NOT_REVIEWED')

    def test_three_pass_findings_do_not_upgrade_full_ea(self):
        record = adapt(*fixture())
        self.assertEqual(len(record.audit.findings), 3)
        self.assertEqual(record.audit.status, 'PASS')
        self.assertEqual(record.audit.full_EA_verdict, 'NOT_EVALUATED')

    def test_raw_audit_mismatch_is_not_evaluated(self):
        frozen, values, refs = fixture();values['audit_raw']['text'] = '{"findings": []}'
        record = adapt(frozen, values, refs)
        self.assertEqual(record.status, 'NOT_EVALUATED')
        self.assertIn('AUDIT_RAW_FINDINGS_MISMATCH', record.skip_reasons)

    def test_qc_mismatch_is_not_evaluated(self):
        frozen, values, refs = fixture();values['generation']['observation'] = {'context': 'changed'}
        self.assertIn('FROZEN_QC_MISMATCH', adapt(frozen, values, refs).skip_reasons)

    def test_missing_evidence_is_explicit(self):
        frozen, values, refs = fixture();values.pop('decision');refs.pop('decision')
        record = adapt(frozen, values, refs)
        self.assertEqual(record.approval.method, 'UNKNOWN')
        self.assertIn('MISSING_DECISION', record.skip_reasons)

    def test_schema_rejects_bad_hash_and_fake_independent_review(self):
        record = adapt(*fixture()).model_dump()
        for key in ('hash', 'independent'):
            changed = deepcopy(record)
            if key == 'hash':changed['references']['decision']['sha256'] = 'wrong'
            else:changed['independent_review']['status'] = 'HUMAN_REVIEWED'
            with self.assertRaises(ValidationError):QualityRecord.model_validate(changed)

    def test_snapshot_detects_modified_and_new_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);p = root/'decision.json';p.write_text('{}')
            snapshot = Snapshot(root);snapshot.read(p);snapshot.verify()
            p.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'SNAPSHOT_CHANGED'):snapshot.verify()
            snapshot = Snapshot(root);snapshot.read(root/'missing.json');(root/'missing.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'SNAPSHOT_CHANGED'):snapshot.verify()

    def test_build_preserves_sources_and_viewer_reads_latest_saved_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);src = root/'reports/run/original';out = root/'reports/run/quality'
            frozen, values, refs = fixture();variant = src/'02-generation/01-round'/frozen['id']
            for key, rel in SOURCES.items():
                path = variant/rel;path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('\n'.join(json.dumps(x) for x in values[key]) if path.suffix == '.jsonl' else json.dumps(values[key]))
            data = src/'03-experiment/qwen-8b/dataset.json';data.parent.mkdir(parents=True);data.write_text(json.dumps([frozen]))
            before = {str(p): p.read_bytes() for p in src.rglob('*') if p.is_file()}
            report = build(src, out, project=root, expected=1)
            self.assertEqual(report.status, 'COMPLETE')
            self.assertEqual(before, {str(p): p.read_bytes() for p in src.rglob('*') if p.is_file()})
            payload = view(out);self.assertEqual(payload['batch']['quality_scope']['records'][0]['independent_review']['status'], 'NOT_REVIEWED')
            raw = source(out, data.relative_to(root).as_posix(), project=root);self.assertEqual(raw, data.read_bytes())
            saved = report.model_dump();saved['records'][0]['approval']['method'] = 'UNKNOWN'
            (out/'quality_scope.json').write_text(json.dumps(saved))
            self.assertNotEqual(view(out)['revision'], payload['revision'])
            with self.assertRaises(FileExistsError):build(src, out, project=root, expected=1)
            with self.assertRaisesRegex(ValueError, 'SOURCE_NOT_IN'):source(out, '../secret', project=root)
            data.write_text('[]')
            with self.assertRaisesRegex(ValueError, 'SOURCE_HASH_CHANGED'):source(out, data.relative_to(root).as_posix(), project=root)

    def test_actual_624_report_and_all_input_hashes(self):
        report_path = PROJECT/'reports/run/20260916-quality-v1'
        report = QualityReport.model_validate_json((report_path/'quality_scope.json').read_text())
        self.assertEqual(report.status, 'COMPLETE')
        self.assertEqual(len(report.records), 624)
        for key in ('recorded', 'generation_pass', 'qc_matches_frozen', 'three_audit_axes_pass',
                    'bulk_at_user_direction', 'independent_not_reviewed'):
            self.assertEqual(report.summary[key], 624)
        self.assertEqual(report.summary['ea_full_not_evaluated'], 177)
        self.assertEqual(report.summary['qi01_counterexamples_linked'], 3)
        self.assertEqual(json.loads((report_path/'sidecar-schema.json').read_text()), QualityReport.model_json_schema())
        manifest = json.loads((report_path/'manifest.json').read_text())
        for ref in manifest['inputs']:
            self.assertEqual(hashlib.sha256((PROJECT/ref['path']).read_bytes()).hexdigest(), ref['sha256'], ref['path'])


class LunaLowConfigChecks(unittest.TestCase):
    def test_profile_matches_max_except_effort(self):
        low = read_profile(PROJECT/'config/codex-profiles.toml', 'luna-low-api')
        high = read_profile(PROJECT/'config/codex-profiles.toml', 'luna-max-api')
        for field in ('provider', 'model', 'transport', 'max_output_tokens', 'total_token_budget'):
            self.assertEqual(low[field], high[field])
        self.assertEqual(low['effort'], 'low')

    def test_test_config_only_selects_low_and_keeps_execution_disabled(self):
        path = PROJECT/'config/llm-test-luna-low-api.json';config = json.loads(path.read_text())
        self.assertFalse(config['use_model_selection'])
        for role in config['roles']:
            settings = read_settings(path, role)
            self.assertEqual(settings['profile']['id'], 'luna-low-api')
            self.assertEqual(settings['effort'], 'low')
            self.assertFalse(settings['execution_enabled'])
        import tomllib
        selections = tomllib.loads((PROJECT/'config/codex-profiles.toml').read_text())['selection']
        self.assertNotIn('luna-low-api', selections.values())


if __name__ == '__main__':
    unittest.main()
