"""Archive completed production Q/C and seven variants without dropping failures."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from importlib import import_module
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from functools import lru_cache

from finarch.dataset.viewer.summary_reader import read_generation_summary

export = import_module('finarch.dataset.03-release.export_run_results')
policy = import_module('finarch.dataset.03-release.export_policy')
schema = import_module('finarch.dataset.03-release.publication.schema')
inverse = import_module('finarch.dataset.02-generation.03-validation.ea_inverse_review')
SELECTION_POLICY = 'ALL_SEVEN_AUTOMATIC_PASS_NO_HUMAN_REJECTION'
ARCHIVE_POLICY = 'ALL_SELECTED_CASES_INCLUDING_FAILURES_AND_REJECTIONS'
PROJECT = Path(__file__).resolve().parents[5]
TEMPLATE = PROJECT / 'src/finarch/documentation/templates/generated-dataset.md'
TERMINAL = {'PASS', 'LIMIT_REACHED', 'REQUIRES_PLAN_REVIEW', 'COMPLETED_SOURCE_OVERLAY'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class Sources:
    """Capture every consumed input and reject changes before publishing."""
    def __init__(self, run):
        self.run = run
        self.hashes = {}

    def key(self, path):
        path = Path(path).resolve()
        return str(path.relative_to(self.run)) if path.is_relative_to(self.run) else str(path)

    def track(self, path, expected=None):
        key = self.key(path)
        digest = export.sha(path)
        if (expected and digest != expected) or (key in self.hashes and self.hashes[key] != digest):
            raise ValueError('SOURCE_CHANGED:' + key)
        self.hashes[key] = digest
        return digest

    def read(self, path):
        raw = Path(path).read_bytes()
        key = self.key(path)
        digest = hashlib.sha256(raw).hexdigest()
        if key in self.hashes and self.hashes[key] != digest:
            raise ValueError('SOURCE_CHANGED:' + key)
        self.hashes[key] = digest
        return json.loads(raw)

    def verify(self):
        for name, expected in self.hashes.items():
            self.track(self.run / name, expected)


def child(run, relative):
    path = (run / relative).resolve()
    if not path.is_relative_to(run) or not path.is_file():
        raise ValueError('INVALID_SOURCE_PATH:' + str(relative))
    return path


def latest_records(run, sources):
    """Project only final identity/state, not the very large stored graphs."""
    path = run / '02-generation/summary.json'
    sources.track(path)
    try:
        import simdjson
    except ImportError:
        document = sources.read(path)
    else:
        document = simdjson.Parser().load(str(path))
    result = {}
    for case, records in document.get('latest', {}).items():
        for item in records.values():
            label = item.get('label')
            key = (case, label)
            if label not in schema.TYPES or key in result:
                raise ValueError('INVALID_LATEST_TYPE:' + str(key))
            result[key] = {name: item.get(name) for name in ('label', 'status', 'path', 'reason')}
    report_path = run / '02-generation/result-report.json'
    if report_path.is_file():
        rows = sources.read(report_path)['rows']
        projected = {(row['case'], row['type']): (row['status'], row.get('origin')) for row in rows}
        if len(projected) != len(rows) or projected != {k: (v['status'], v['path']) for k, v in result.items()}:
            raise ValueError('FINAL_REPORT_LATEST_MISMATCH')
    sources.track(path)
    return result


def check_completed(run, sources):
    path = run / '02-generation/summary.json'
    sources.track(path)
    summary = read_generation_summary(path) or {}
    if summary.get('status') not in TERMINAL:
        raise ValueError('GENERATION_NOT_COMPLETED')
    timing_path = run / '02-generation/timing.json'
    completion_path = run / 'completion-report.json'
    if summary['status'] == 'COMPLETED_SOURCE_OVERLAY':
        if sources.read(completion_path).get('status') != 'COMPLETED':
            raise ValueError('OVERLAY_NOT_COMPLETED')
    elif not timing_path.is_file() or sources.read(timing_path).get('status') != 'COMPLETED':
        raise ValueError('GENERATION_TIMING_NOT_COMPLETED')
    return {k: summary.get(k) for k in ('status', 'source_runs')}


def review(sources, folder, phase, state):
    recorded, path = policy.review(folder, phase)
    if path:
        recorded = sources.read(path)
    return {'decision': policy.current_decision(state, recorded), 'record': recorded,
            'source': sources.key(path) if path else None}


def item(run, case, label, qc, status, recorded, source, metadata=None):
    complete = all(isinstance(qc.get(k), str) for k in ('question', 'context'))
    return {'item_id': f'{run.name}:{case}:{label}', 'type': label,
            'question': qc.get('question'), 'context': qc.get('context'),
            'content_sha256': hashlib.sha256(canonical({k: qc[k] for k in ('question', 'context')})).hexdigest() if complete else None,
            'automatic_validation': status, 'production_review': recorded,
            'annotation': {'status': 'UNREVIEWED', 'ratings': []},
            'source': source, 'metadata': metadata or {}}


def collect_cases(run, sources):
    run = Path(run).resolve()
    completion = check_completed(run, sources)
    selection = sources.read(run / 'input-selection.json')
    input_path = Path(selection['input_path'])
    if not input_path.is_absolute():
        input_path = run / input_path
    originals_list = sources.read(input_path)
    originals = {row['id']: row for row in originals_list}
    ids = selection['cases']
    if len(ids) != len(set(ids)) or len(originals) != len(originals_list) or any(i not in originals for i in ids):
        raise ValueError('INVALID_INPUT_SELECTION')
    latest = latest_records(run, sources)
    if any(case not in ids for case, _ in latest):
        raise ValueError('RESULT_OUTSIDE_INPUT_SELECTION')
    cases = []
    for case in ids:
        root = run / '01-preparation' / case
        state = sources.read(root / 'run.json')
        active = state.get('active_round')
        folder = root / active if active else root
        data_path = folder / 'data.json'
        sample = sources.read(data_path) if data_path.is_file() else originals[case]
        if sample.get('id') != case:
            raise ValueError('PREPARATION_ID_MISMATCH:' + case)
        repairs = None
        if state['status'] == 'PASS':
            accepted = folder / '02-review/accepted-input.json'
            if accepted.is_file():
                sources.track(accepted)
            sample, repairs = export.complete_reference(sample, accepted)
        origin = item(run, case, 'ORIGINAL', sample,
            {'status': state['status'], 'reason': state.get('reason', ''), 'round': active},
            review(sources, folder, 'preparation', state),
            {'file': sources.key(data_path if data_path.is_file() else input_path),
             'sha256': sources.hashes[sources.key(data_path if data_path.is_file() else input_path)]},
            {k: sample.get(k) for k in ('raw_id', 'reference_answer', 'reference_answer_type',
                                      'reference_precision', 'answer_metadata', 'provenance')})
        knowledge, evidence = export.external_knowledge.classify(run,
            {'id': case, 'status': state['status'], 'round': active, 'input': sample})
        for relative, digest in evidence['sources'].items():
            sources.track(child(run, relative), digest)
        origin['metadata'].update(external_knowledge=knowledge, reference_metadata_repair=repairs)
        variants = []
        for label, name in export.TYPES:
            final = latest.get((case, label))
            if final:
                marker = child(run, final['path'] + '/run.json')
                variant_root = marker.parent
                if variant_root.name != name or variant_root.parent.name != case or variant_root.parent.parent.parent != run / '02-generation':
                    raise ValueError('VARIANT_ID_ORIGIN_MISMATCH:' + case + ':' + label)
                saved = sources.read(marker)
                if saved.get('status') != final['status'] or saved.get('label') != label:
                    raise ValueError('VARIANT_STATE_MISMATCH:' + case + ':' + label)
                observation = variant_root / '02-generate-text/04-observation.json'
                qc = sources.read(observation) if observation.is_file() else {}
                status = {'status': final['status'], 'reason': final.get('reason') or saved.get('reason', ''),
                          'round': variant_root.parent.parent.name}
                record = review(sources, variant_root, 'generation', saved)
                source = {'file': sources.key(observation) if observation.is_file() else None,
                          'sha256': sources.hashes.get(sources.key(observation)),
                          'result': final['path']}
                comparison = variant_root / '03-validation/04-comparison.json'
                comparison_data = sources.read(comparison) if comparison.is_file() else None
                metadata = {'edit_provenance': export.provenance.build(case, label, sample, qc, comparison_data)}
                ref = saved.get('inverse_review_ref')
                if ref:
                    if not qc:
                        raise ValueError('INVERSE_WITHOUT_OBSERVATION')
                    metadata['inverse_review'] = inverse.verify_reference(variant_root, ref, qc)
                    sources.track(child(variant_root, ref['path']), ref['sha256'])
            else:
                if state['status'] == 'PASS':
                    raise ValueError('COMPLETED_GENERATION_MISSING_TYPE:' + case + ':' + label)
                qc, source, metadata = {}, {}, {}
                status = {'status': 'NOT_RUN', 'reason': 'PREPARATION_NOT_PASSED', 'round': None}
                record = {'decision': None, 'record': {}, 'source': None}
            variants.append(item(run, case, label, qc, status, record, source, metadata))
        reasons = []
        for entry in [origin, *variants]:
            if entry['automatic_validation']['status'] != 'PASS':
                reasons.append(entry['type'] + ':' + entry['automatic_validation']['status'])
            if entry['production_review']['decision'] in policy.REJECTED:
                reasons.append(entry['type'] + ':EXPLICIT_REJECTION')
        row = {'format': schema.FORMAT, 'run': run.name, 'id': case, 'source_input': originals[case],
               'original': origin, 'variants': variants,
               'production_selection': {'policy': SELECTION_POLICY, 'eligible': not reasons, 'exclusion_reasons': reasons}}
        cases.append(schema.DatasetCase.model_validate(row).model_dump())
    return cases, completion


def attach_annotations(cases, document):
    """Attach content-bound ratings only; do not infer a consensus or change production."""
    if document.get('format') != 'finarch-generated-annotations-v1' or not isinstance(document.get('ratings'), list):
        raise ValueError('CONTENT_BOUND_ANNOTATIONS_REQUIRED')
    cases = deepcopy(cases)
    items = {i['item_id']: i for case in cases for i in [case['original'], *case['variants']]}
    seen = set()
    for raw in document['ratings']:
        rating = schema.Rating.model_validate(raw).model_dump()
        target = items.get(rating['item_id'])
        if not target or not target['content_sha256'] or rating['content_sha256'] != target['content_sha256']:
            raise ValueError('ANNOTATION_CONTENT_MISMATCH:' + rating['item_id'])
        key = (rating['item_id'], rating['reviewer'])
        if key in seen:
            raise ValueError('DUPLICATE_ANNOTATOR_RATING')
        seen.add(key)
        target['annotation']['ratings'].append(rating)
        target['annotation']['status'] = 'ANNOTATED'
    return [schema.DatasetCase.model_validate(case).model_dump() for case in cases]


def verify_output(folder):
    manifest = export.read(folder / 'manifest.json')
    for name, value in manifest['files'].items():
        if name != Path(name).name or export.sha(folder / name) != value['sha256']:
            raise ValueError('GENERATED_FILE_HASH_MISMATCH:' + name)
    count = 0
    with (folder / 'dataset.jsonl').open() as stream:
        for line in stream:
            schema.DatasetCase.model_validate_json(line)
            count += 1
    if count != manifest['counts']['cases']:
        raise ValueError('GENERATED_COUNT_MISMATCH')
    return manifest


@lru_cache(maxsize=4)
def _archive_index(path, stamp, expected):
    """Keep only line offsets in memory; verify the actual complete data bytes."""
    if export.sha(path) != expected:
        raise ValueError('GENERATED_DATA_HASH_MISMATCH')
    offsets, digest = {}, hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            offset = stream.tell()
            line = stream.readline()
            if not line:
                break
            digest.update(line)
            row = json.loads(line)
            if row['id'] in offsets:
                raise ValueError('DUPLICATE_ARCHIVE_CASE')
            offsets[row['id']] = offset
    if digest.hexdigest() != expected:
        raise ValueError('GENERATED_DATA_HASH_MISMATCH')
    return offsets


def view(folder, case=None):
    """Read the standalone archive through the common viewer, without source runs."""
    folder = Path(folder)
    manifest = export.read(folder / 'manifest.json')
    path = folder / 'dataset.jsonl'
    stat = path.stat()
    index = _archive_index(str(path.resolve()), (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns),
                           manifest['files']['dataset.jsonl']['sha256'])
    if len(index) != manifest['counts']['cases']:
        raise ValueError('GENERATED_COUNT_MISMATCH')
    chosen = case or next(iter(index), None)
    record = None
    if chosen:
        if chosen not in index:
            raise ValueError('UNKNOWN_ARCHIVE_CASE')
        with path.open('rb') as stream:
            stream.seek(index[chosen])
            record = schema.DatasetCase.model_validate_json(stream.readline()).model_dump()
    return {'source_run': manifest['source_run'], 'counts': manifest['counts'],
            'archive_policy': manifest['archive_policy'], 'annotation_state': manifest['annotation_state'],
            'cases': list(index), 'case': record}


def publish(run, output=None, *, annotations=None):
    run = Path(run).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run.name):
        raise ValueError('INVALID_RUN_NAME')
    output = Path(output).resolve() if output else PROJECT / 'data/generated' / run.name
    if output.is_relative_to(run) or run.is_relative_to(output):
        raise ValueError('OUTPUT_MUST_BE_SEPARATE_FROM_RUN')
    sources = Sources(run)
    rows, completion = collect_cases(run, sources)
    if annotations:
        rows = attach_annotations(rows, sources.read(annotations))
    data = b''.join(canonical(row) + b'\n' for row in rows)
    source_signature = hashlib.sha256(canonical(sources.hashes)).hexdigest()
    if output.exists():
        manifest = verify_output(output)
        if manifest['source_signature'] != source_signature or manifest['files']['dataset.jsonl']['sha256'] != hashlib.sha256(data).hexdigest():
            raise ValueError('GENERATED_SNAPSHOT_EXISTS_USE_NEW_OUTPUT')
        sources.verify()
        return {**manifest, 'output': str(output), 'changed': False}
    entries = [i for row in rows for i in [row['original'], *row['variants']]]
    counts = {'cases': len(rows), 'variant_slots': len(rows) * 7,
              'saved_variants': sum(i['content_sha256'] is not None for row in rows for i in row['variants']),
              'production_eligible_cases': sum(row['production_selection']['eligible'] for row in rows),
              'production_rejected_cases': sum(any(i['production_review']['decision'] in policy.REJECTED for i in [row['original'], *row['variants']]) for row in rows),
              'automatic_original': dict(Counter(row['original']['automatic_validation']['status'] for row in rows)),
              'automatic_variants': dict(Counter(i['automatic_validation']['status'] for row in rows for i in row['variants'])),
              'annotated_items': sum(i['annotation']['status'] == 'ANNOTATED' for i in entries),
              'unreviewed_items': sum(i['annotation']['status'] == 'UNREVIEWED' for i in entries)}
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=output.parent, prefix='.' + run.name + '-'))
    try:
        export.save_bytes(staging / 'dataset.jsonl', data)
        export.save(staging / 'dataset.schema.json', schema.DatasetCase.model_json_schema())
        export.save(staging / 'annotation.schema.json', {'format': 'finarch-generated-annotations-v1',
            'rating_schema': schema.Rating.model_json_schema(), 'join': ['item_id', 'content_sha256']})
        timestamp = datetime.now(timezone.utc).isoformat()
        export.save_bytes(staging / 'events.jsonl', canonical({'event': 'DATASET_CONSOLIDATED', 'time': timestamp,
            'run': run.name, 'counts': counts, 'model_calls': 0}) + b'\n')
        export.save_bytes(staging / 'README.md', TEMPLATE.read_text().format(run=run.name, **counts).encode())
        files = {p.name: {'sha256': export.sha(p), 'bytes': p.stat().st_size} for p in staging.iterdir()}
        manifest = {'format': schema.FORMAT, 'source_run': run.name, 'created_at': timestamp,
                    'archive_policy': ARCHIVE_POLICY, 'production_selection_policy': SELECTION_POLICY,
                    'source_completion': completion, 'source_signature': source_signature,
                    'sources': sources.hashes, 'files': files, 'counts': counts,
                    'annotation_state': 'APPLIED' if counts['annotated_items'] else 'NOT_APPLIED',
                    'annotation_source': sources.key(annotations) if annotations else None,
                    'model_calls': 0}
        export.save(staging / 'manifest.json', manifest)
        verify_output(staging)
        sources.verify()
        os.rename(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {**manifest, 'output': str(output), 'changed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--output', help='New archive directory; existing snapshots are never replaced.')
    parser.add_argument('--annotations', help='Content-bound ratings; use a new output for an annotated revision.')
    args = parser.parse_args()
    result = publish(args.run, args.output, annotations=args.annotations)
    print(json.dumps({k: result[k] for k in ('output', 'changed', 'counts', 'annotation_state', 'model_calls')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
