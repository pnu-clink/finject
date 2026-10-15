"""Read frozen generation/audit/decision evidence; never mutate or approve it."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from finarch.dataset.schemas.quality_scope import QualityRecord, QualityReport, SourceRef

PROJECT = (Path(__file__).resolve().parent / '../../../../..').resolve()
SOURCES = {
    'generation': 'run.json', 'audit': '03-validation/03-result.json',
    'audit_raw': '03-validation/audit/02-raw-response.json',
    'audit_request': '03-validation/audit/01-input/model-request.json',
    'audit_call': '03-validation/audit/01-input.json',
    'audit_profile': '03-validation/audit/01-input/cli-profile.json',
    'decision': '05-human-review/02-record-decision/decision.json',
    'decision_history': '05-human-review/02-record-decision/history.jsonl',
}


class Snapshot:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self.references = {}
        self.missing = set()

    def read(self, path):
        path = Path(path).resolve()
        relative = path.relative_to(self.project).as_posix()
        if not path.is_file():
            self.missing.add(relative)
            return None
        raw = path.read_bytes()
        ref = {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}
        if relative in self.references and self.references[relative] != ref:
            raise ValueError('SNAPSHOT_CHANGED:' + relative)
        self.references[relative] = ref
        return [json.loads(line) for line in raw.decode().splitlines() if line.strip()] if path.suffix == '.jsonl' else json.loads(raw)

    def ref(self, path):
        return self.references.get(Path(path).resolve().relative_to(self.project).as_posix())

    def verify(self):
        for relative, ref in self.references.items():
            path = self.project / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
                raise ValueError('SNAPSHOT_CHANGED:' + relative)
        if any((self.project / path).exists() for path in self.missing):
            raise ValueError('SNAPSHOT_CHANGED:MISSING_INPUT_APPEARED')


def adapt(frozen, values, references):
    """Approval provenance, audit scope, and independent review remain separate."""
    generation = values.get('generation') or {}
    audit = values.get('audit') or {}
    decision = values.get('decision') or {}
    profile = values.get('audit_profile') or {}
    skip = ['MISSING_' + key.upper() for key in SOURCES if values.get(key) is None]
    observation = {k: frozen[k] for k in ('context', 'question')}
    matched = generation.get('observation') == observation if generation else None
    if matched is False:
        skip.append('FROZEN_QC_MISMATCH')
    if generation and generation.get('audit') != audit:
        skip.append('GENERATION_AUDIT_MISMATCH')
    raw_match = None
    if values.get('audit_raw'):
        try:
            raw_match = json.loads(values['audit_raw']['text']).get('findings') == audit.get('findings')
        except (ValueError, TypeError, KeyError):
            raw_match = False
        if not raw_match:
            skip.append('AUDIT_RAW_FINDINGS_MISMATCH')
    findings = audit.get('findings', [])
    if len(findings) != 3 or {f['criterion'] for f in findings} != {'planned_change', 'unintended_change', 'readability'}:
        skip.append('AUDIT_AXES_UNKNOWN')
    if profile and (profile.get('model') != audit.get('model') or profile.get('effort') != audit.get('effort')):
        skip.append('SAVED_PROFILE_AUDIT_MISMATCH')
    request = (values.get('audit_request') or {}).get('input', {})
    if values.get('audit_request') and any(request.get(k) != observation[k] for k in observation):
        skip.append('AUDIT_REQUEST_QC_MISMATCH')
    history = values.get('decision_history')
    history_match = decision in history if isinstance(history, list) and decision else None
    if history_match is False:
        skip.append('CURRENT_DECISION_NOT_IN_HISTORY')
    method = ('BULK_AT_USER_DIRECTION' if decision.get('reviewer') == 'user-directed-bulk-accept'
              and decision.get('decision') == 'APPROVED' and 'decision' in references else 'UNKNOWN')
    case, variant = frozen['id'].split('/')
    return QualityRecord.model_validate({
        'id': frozen['id'], 'case': case, 'variant': variant, 'repeat': None,
        'axis': generation.get('axis'), 'generation_status': generation.get('status'),
        'status': 'NOT_EVALUATED' if skip else 'RECORDED', 'qc_matches_frozen': matched,
        'audit': {'version': audit.get('audit_version'), 'status': audit.get('status'), 'scope': audit.get('scope'),
                  'model': audit.get('model'), 'effort': audit.get('effort'), 'profile_id': profile.get('id'),
                  'findings': findings, 'findings_match_raw': raw_match,
                  'recovery_review': audit.get('recovery_review'), 'full_EA_verdict': audit.get('full_EA_verdict'),
                  'independent_answer_stage': audit.get('stage18'), 'limitation': audit.get('limitation')},
        'approval': {'method': method, 'decision': decision.get('decision'), 'reviewer': decision.get('reviewer'),
                     'recorded_at': decision.get('recorded_at'), 'reason': decision.get('reason'),
                     'history_contains_current': history_match},
        'independent_review': {'status': 'NOT_REVIEWED', 'kind': 'NONE_DOCUMENTED_IN_SELECTED_EVIDENCE',
            'scope': 'Independent item-level semantic review; not administrative approval or single-model audit.',
            'reason': 'No independent review evidence is imported by this adapter; approval history is not such evidence.'},
        'references': references, 'bounded_recovery_status': None, 'skip_reasons': skip,
    })


def build(source, output, *, project=PROJECT, expected=624, qi01=None):
    source, output, project = Path(source).resolve(), Path(output).resolve(), Path(project).resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('OUTPUT_MUST_BE_SEPARATE_FROM_SOURCE')
    output.relative_to(project)
    output.mkdir(parents=True, exist_ok=False)
    snapshot = Snapshot(project)

    def save(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    def event(phase, **extra):
        with (output / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps({'timestamp': datetime.now(timezone.utc).isoformat(), 'phase': phase,
                                     'step': 'QI05', 'model_calls': 0, **extra}) + '\n')

    event('START', status='RUNNING')
    try:
        dataset_path = source / '03-experiment/qwen-8b/dataset.json'
        frozen = snapshot.read(dataset_path)
        if not isinstance(frozen, list) or len(frozen) != expected or len({v['id'] for v in frozen}) != expected:
            raise ValueError('FROZEN_COUNT_OR_ID_MISMATCH')
        generation = source / '02-generation'
        inventory = sorted(generation.glob('*-round/test-*/*/run.json'))
        latest = {p.parent.parent.name + '/' + p.parent.name: p.parent for p in inventory}
        records = []
        related = {}
        qi01 = Path(qi01).resolve() if qi01 else None
        if qi01:
            snapshot.read(qi01 / 'summary.json')
            related['QI01'] = snapshot.ref(qi01 / 'summary.json')
        for frozen_item in frozen:
            directory = latest.get(frozen_item['id'])
            values, refs = {}, {'frozen_dataset': snapshot.ref(dataset_path)}
            if directory:
                for key, relative in SOURCES.items():
                    path = directory / relative
                    values[key] = snapshot.read(path)
                    if snapshot.ref(path):
                        refs[key] = snapshot.ref(path)
            record = adapt(frozen_item, values, refs)
            if qi01:
                case, variant = frozen_item['id'].split('/')
                prefix = qi01 / (case + '-' + variant[:2])
                if prefix.is_dir():
                    observation = snapshot.read(prefix / 'observation.json')
                    sidecar = snapshot.read(prefix / '03-validation/05-recovery-screen.json')
                    if observation == {k: frozen_item[k] for k in ('context', 'question')}:
                        record.bounded_recovery_status = sidecar['status']
                        record.references['bounded_recovery'] = SourceRef.model_validate(snapshot.ref(prefix / '03-validation/05-recovery-screen.json'))
                        record.references['bounded_observation'] = SourceRef.model_validate(snapshot.ref(prefix / 'observation.json'))
            records.append(record)
        snapshot.verify()
        if sorted(generation.glob('*-round/test-*/*/run.json')) != inventory:
            raise ValueError('SNAPSHOT_CHANGED:GENERATION_INVENTORY')
        counts = {'records': len(records), 'qc_matches_frozen': sum(r.qc_matches_frozen is True for r in records),
                  'unique_qc': len({(v['question'], v['context']) for v in frozen}),
                  'original_cases': len({r.case for r in records}),
                  'recorded': sum(r.status == 'RECORDED' for r in records),
                  'generation_pass': sum(r.generation_status == 'PASS' for r in records),
                  'three_audit_axes_pass': sum(len(r.audit.findings) == 3 and all(f.judgment == 'PASS' for f in r.audit.findings) for r in records),
                  'bulk_at_user_direction': sum(r.approval.method == 'BULK_AT_USER_DIRECTION' for r in records),
                  'independent_not_reviewed': sum(r.independent_review.status == 'NOT_REVIEWED' for r in records),
                  'ea_full_not_evaluated': sum(r.axis == 'EA' and r.audit.full_EA_verdict == 'NOT_EVALUATED' for r in records),
                  'qi01_counterexamples_linked': sum(r.bounded_recovery_status == 'RECOVERABLE' for r in records)}
        report = QualityReport(schema_version='quality-scope-v1', rubric_version='audit-scope-and-approval-provenance-v1',
            run_id=output.name, source_run=source.name, created_at=datetime.now(timezone.utc).isoformat(),
            processor='offline-python-adapter', model_calls=0,
            status='COMPLETE' if counts['recorded'] == len(records) else 'PARTIAL',
            records=records, summary=counts, related_reports=related)
        save('quality_scope.json', report.model_dump())
        save('sidecar-schema.json', QualityReport.model_json_schema())
        save('manifest.json', {'schema_version': 'quality-scope-manifest-v1', 'snapshot_status': 'UNCHANGED',
             'inputs': list(snapshot.references.values()), 'missing': sorted(snapshot.missing)})
        save('summary.json', {'workflow': 'quality_scope', 'status': report.status, **counts, 'model_calls': 0})
        template = Path(__file__).with_name('quality-scope-readme-template.md').read_text()
        (output / 'README.md').write_text(template.format(run_id=output.name, source_run=source.name, **counts))
        event('END', status=report.status, records=len(records))
        return report
    except Exception as error:
        changed = str(error).startswith('SNAPSHOT_CHANGED')
        save('failure.json', {'status': 'SNAPSHOT_CHANGED' if changed else 'FAIL', 'reason': str(error), 'model_calls': 0})
        event('FAIL', status='SNAPSHOT_CHANGED' if changed else 'FAIL', reason=str(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--qi01')
    args = parser.parse_args()
    result = build(args.source, args.output, qi01=args.qi01)
    print(json.dumps({'status': result.status, **result.summary, 'model_calls': 0}))
