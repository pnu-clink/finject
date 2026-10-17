"""Collect run inputs and all seven generation types for human review."""
import argparse
import gzip
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

provenance = __import__('finarch.dataset.03-release.edit_provenance', fromlist=['*'])
external_knowledge = __import__('finarch.dataset.03-release.external_knowledge', fromlist=['classify'])
export_policy = __import__('finarch.dataset.03-release.export_policy', fromlist=['*'])

TYPES = (
    ('IC_VALUE_01_BEFORE', '01-ic-value-before'),
    ('IC_VALUE_01_AFTER', '02-ic-value-after'),
    ('IC_SOURCE_A_ONLY', '03-ic-source-type-1'),
    ('IC_SOURCE_B_ONLY', '04-ic-source-type-2'),
    ('IC_RELATION_01', '05-ic-relation'),
    ('EA_01', '06-ea-earlier-input'),
    ('EA_02', '07-ea-later-input'),
)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(handle, 'w') as output:
            json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_bytes(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(handle, 'wb') as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def external_records(run, rows):
    records, sources = [], {}
    for row in rows:
        label, evidence = external_knowledge.classify(run, row)
        records.append({**row, 'external_knowledge': label})
        sources[row['id']] = evidence
    return records, sources


def results_readme(run_name, count, selection_policy):
    template = Path(__file__).with_name('results-readme-template.md').read_text()
    note = ('The current variable is the explicit `REJECT`/`REJECTED`/`EXCLUDE`/`EXCLUDED` Except for the judgment of the people. '
            'Except for the preparation original, the original and the 7Except for all types, one type of Generation is the '
            'If you\'re excluded, you\'re only excluding the type line. Accept, pending, pending and automatic FAIL are not excluded by this rule alone. '
            'Excluding reason: judgment file: `manifest.json`and `export-log.json` `exclusions`It\'s preserved.'
            if selection_policy == export_policy.POLICY else
            'This copy maintains the previous export policy, which is that we\'re only reinforcing metadata, not excluding existing lines or rejects. '
            'The actual ranking is `manifest.json.selection_policy`Check out the current rule excluding Reject only applies to new full Export.')
    return template.format(run_name=run_name, count=count, export_policy_note=note)


def enrich_external_existing(run):
    """Backfill only the confirmed-use label; retain the prior result bytes."""
    run = Path(run).resolve()
    root = run / 'results'
    manifest = read(root / 'manifest.json')
    if manifest.get('source_run') != run.name:
        raise ValueError('RESULTS_RUN_MISMATCH')
    names = ['00-input.json', *(folder + '.json' for _, folder in TYPES)]
    for name in names:
        if sha(root / name) != manifest['files'][name]['sha256']:
            raise ValueError('RESULTS_FILE_HASH_MISMATCH:' + name)
    if (manifest.get('source_report_sha256') and
            sha(run / '02-generation/result-report.json') != manifest['source_report_sha256']):
        raise ValueError('RESULTS_SOURCE_REPORT_CHANGED')
    before = {name: (root / name).read_bytes() for name in
              ('00-input.json', 'manifest.json', 'export-log.json', 'README.md')}
    original_rows = json.loads(before['00-input.json'])
    rows, sources = external_records(run, original_rows)
    if len({row['id'] for row in rows}) != len(rows) or len(rows) != manifest['selected_count']:
        raise ValueError('RESULTS_INPUT_COUNT_OR_ID_MISMATCH')
    counts = dict(Counter('true' if row['external_knowledge']['used'] else 'false' for row in rows))
    if rows == original_rows:
        return {'changed': False, 'external_knowledge_counts': counts, 'model_calls': 0}
    for name, raw in before.items():
        if (root / name).read_bytes() != raw:
            raise ValueError('RESULTS_CONCURRENT_EDIT:' + name)
    for name in names[1:]:
        if sha(root / name) != manifest['files'][name]['sha256']:
            raise ValueError('RESULTS_CONCURRENT_EDIT:' + name)
    for case, evidence in sources.items():
        for relative, digest in evidence['sources'].items():
            if sha(run / relative) != digest:
                raise ValueError('EXTERNAL_KNOWLEDGE_SOURCE_CHANGED:' + case + ':' + relative)
    if [{k: v for k, v in row.items() if k != 'external_knowledge'} for row in rows] != [
            {k: v for k, v in row.items() if k != 'external_knowledge'} for row in original_rows]:
        raise ValueError('EXTERNAL_KNOWLEDGE_REFRESH_CHANGED_DATA')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = root / 'revisions' / ('external-knowledge-' + stamp)
    save_bytes(backup / '00-input.json.gz', gzip.compress(before['00-input.json'], mtime=0))
    for name in ('manifest.json', 'export-log.json', 'README.md'):
        save_bytes(backup / name, before[name])
    save_bytes(backup / 'README-before-change.txt',
        b'Original consolidated result bytes before the external-knowledge backfill. No model calls.\n')
    written = {}
    try:
        save(root / '00-input.json', rows)
        written['00-input.json'] = (root / '00-input.json').read_bytes()
        manifest['files']['00-input.json'].update(sha256=sha(root / '00-input.json'),
                                                   external_knowledge_counts=counts)
        manifest['external_knowledge_schema_version'] = 1
        save(root / 'manifest.json', manifest)
        written['manifest.json'] = (root / 'manifest.json').read_bytes()
        save_bytes(root / 'README.md', results_readme(run.name, len(rows), manifest.get('selection_policy')).encode())
        written['README.md'] = (root / 'README.md').read_bytes()
        log = json.loads(before['export-log.json'])
        log.setdefault('external_knowledge_revisions', []).append({
            'time': datetime.now(timezone.utc).isoformat(),
            'operation': 'EXTERNAL_KNOWLEDGE_BACKFILL', 'model_calls': 0,
            'original_files_unchanged_except_external_knowledge': True,
            'backup': str(backup.relative_to(run)),
            'counts': counts, 'sources': sources,
            'files': {name: {'before_sha256': hashlib.sha256(before[name]).hexdigest(),
                             'after_sha256': sha(root / name)}
                      for name in ('00-input.json', 'manifest.json', 'README.md')},
            'previous_export_log_sha256': hashlib.sha256(before['export-log.json']).hexdigest(),
        })
        save(root / 'export-log.json', log)
        written['export-log.json'] = (root / 'export-log.json').read_bytes()
    except Exception:
        for name, raw in written.items():
            if (root / name).read_bytes() == raw:
                save_bytes(root / name, before[name])
        raise
    return {'changed': True, 'external_knowledge_counts': counts, 'model_calls': 0,
            'backup': str(backup.relative_to(run))}


def edit_record(run, baseline, row, variant):
    final = row['input'] if variant == 'ORIGINAL' else row
    origin = row.get('result')
    comparison = run / origin / '03-validation/04-comparison.json' if origin else None
    return provenance.from_file(run, row['id'], variant, baseline, final, comparison)


def enrich_existing(run):
    """Add review metadata to an existing snapshot without regenerating its data."""
    run = Path(run).resolve()
    root = run / 'results'
    manifest = read(root / 'manifest.json')
    names = ['00-input.json', *(folder + '.json' for _, folder in TYPES)]
    for name in names:
        if sha(root / name) != manifest['files'][name]['sha256']:
            raise ValueError('RESULTS_FILE_HASH_MISMATCH:' + name)
    before = {name: (root / name).read_bytes() for name in
              [*names, 'manifest.json', 'export-log.json', 'README.md'] if (root / name).exists()}
    arrays = {name: json.loads(before[name]) for name in names}
    originals = {row['id']: row['input'] for row in arrays['00-input.json']}
    if len(originals) != len(arrays['00-input.json']):
        raise ValueError('DUPLICATE_INPUT_ID')
    counts, changed = {}, False
    for (variant, name) in zip(('ORIGINAL', *(label for label, _ in TYPES)), names):
        if not export_policy.aligned_ids(arrays[name], list(originals),
                sparse=name != '00-input.json' and manifest.get('selection_policy') == export_policy.POLICY):
            raise ValueError('RESULTS_ID_ORDER_MISMATCH:' + name)
        for row in arrays[name]:
            record = edit_record(run, originals[row['id']], row, variant)
            changed |= row.get('edit_provenance') != record
            row['edit_provenance'] = record
        counts[name] = dict(Counter(row['edit_provenance']['status'] for row in arrays[name]))
    if not changed:
        return {'changed': False, 'edit_provenance_counts': counts, 'model_calls': 0}
    written = {}
    try:
        for name, raw in before.items():
            if (root / name).read_bytes() != raw:
                raise ValueError('RESULTS_CONCURRENT_EDIT:' + name)
        for name in names:
            if (root / name).read_bytes() != before[name]:
                raise ValueError('RESULTS_CONCURRENT_EDIT:' + name)
            old = json.loads(before[name])
            strip = lambda rows: [{k: v for k, v in row.items() if k != 'edit_provenance'} for row in rows]
            if strip(old) != strip(arrays[name]):
                raise ValueError('PROVENANCE_REFRESH_CHANGED_DATA:' + name)
            save(root / name, arrays[name])
            written[name] = (root / name).read_bytes()
            manifest['files'][name].update(sha256=sha(root / name), edit_provenance_counts=counts[name])
        manifest['edit_provenance_schema_version'] = 1
        save(root / 'manifest.json', manifest)
        written['manifest.json'] = (root / 'manifest.json').read_bytes()
        (root / 'README.md').write_text(results_readme(run.name, len(originals), manifest.get('selection_policy')))
        written['README.md'] = (root / 'README.md').read_bytes()
        log = json.loads(before.get('export-log.json', b'{}'))
        revision = {'time': datetime.now(timezone.utc).isoformat(), 'operation': 'EDIT_PROVENANCE_ONLY',
                    'existing_data_unchanged': True, 'model_calls': 0,
                    'files': {name: {'before_sha256': hashlib.sha256(before[name]).hexdigest(),
                                     'after_sha256': sha(root / name),
                                     'edit_provenance_counts': counts[name]} for name in names}}
        log.setdefault('edit_provenance_revisions', []).append(revision)
        save(root / 'export-log.json', log)
        written['export-log.json'] = (root / 'export-log.json').read_bytes()
    except Exception:
        for name, raw in written.items():
            if (root / name).read_bytes() == raw:
                if name in before:
                    (root / name).write_bytes(before[name])
                else:
                    (root / name).unlink()
        raise
    return {'changed': True, 'edit_provenance_counts': counts, 'model_calls': 0}


def complete_reference(sample, accepted_path):
    """Restore missing handoff metadata from the accepted input, never infer gold."""
    restore = __import__('finarch.dataset.90-operations.preparation_gate',
                         fromlist=['complete_reference']).complete_reference
    return restore(sample, accepted_path)


def export(run):
    run = Path(run).resolve()
    selection = read(run / 'input-selection.json')
    originals = {item['id']: item for item in read(selection['input_path'])}
    ids = selection['cases']
    if len(ids) != len(set(ids)) or any(case not in originals for case in ids):
        raise ValueError('INVALID_INPUT_SELECTION')
    report = read(run / '02-generation/result-report.json')
    reports = {(row['case'], row['type']): row for row in report['rows']}
    if len(reports) != len(report['rows']):
        raise ValueError('DUPLICATE_GENERATION_RESULT')
    output = run / 'results'
    input_rows, metadata_repairs, exclusions = [], [], []
    for case in ids:
        marker = run / '01-preparation' / case / 'run.json'
        state = read(marker) if marker.exists() else {'status': 'NOT_RUN'}
        active = state.get('active_round')
        review_root = marker.parent / str(active) if active else marker.parent
        human, human_path = export_policy.review(review_root, 'preparation')
        excluded = export_policy.exclusion(run, case, 'preparation', state, human,
                                            human_path or (marker if marker.exists() else None))
        if excluded:
            exclusions.append(excluded)
            continue
        prepared = run / '01-preparation' / case / str(active) / 'data.json' if active else None
        sample = read(prepared) if prepared and prepared.exists() else originals[case]
        if state.get('status') == 'PASS':
            accepted = prepared.parent / '02-review/accepted-input.json'
            sample, repair = complete_reference(sample, accepted)
            if repair:
                repair.update(case=case, source=str(accepted.relative_to(run)),
                              original_data_sha256=sha(prepared), original_data_unchanged=True)
                metadata_repairs.append(repair)
        input_rows.append({'id': case, 'status': state['status'], 'human_decision': export_policy.current_decision(state, human),
                           'round': active, 'input': sample, 'source': str(prepared.relative_to(run))
                           if prepared and prepared.exists() else selection['input_path']})
        if state.get('status') == 'PASS' and repair:
            input_rows[-1]['reference_metadata_source'] = repair
        input_rows[-1]['edit_provenance'] = edit_record(run, sample, input_rows[-1], 'ORIGINAL')
    input_rows, knowledge_sources = external_records(run, input_rows)
    baselines = {row['id']: row['input'] for row in input_rows}
    kept_ids = list(baselines)
    save(output / '00-input.json', input_rows)
    knowledge_counts = dict(Counter('true' if row['external_knowledge']['used'] else 'false' for row in input_rows))
    files = {'00-input.json': {'count': len(input_rows), 'sha256': sha(output / '00-input.json'),
                              'external_knowledge_counts': knowledge_counts,
                              'edit_provenance_counts': dict(Counter(row['edit_provenance']['status'] for row in input_rows))}}
    for label, folder_name in TYPES:
        rows = []
        for case in kept_ids:
            result = reports.get((case, label))
            origin = result.get('origin') if result else None
            folder = run / origin if origin else None
            if folder and (folder.name != folder_name or not folder.is_dir()):
                raise ValueError(f'INVALID_RESULT_ORIGIN:{case}:{label}')
            marker = folder / 'run.json' if folder else None
            state = read(marker) if marker and marker.exists() else {}
            human, human_path = export_policy.review(folder, 'generation') if folder else ({}, None)
            excluded = export_policy.exclusion(run, case, 'generation', state, human,
                human_path or (marker if marker and marker.exists() else None), variant=label)
            if excluded:
                exclusions.append(excluded)
                continue
            if result and state.get('status') != result['status']:
                raise ValueError(f'RESULT_STATUS_MISMATCH:{case}:{label}')
            observation = folder / '02-generate-text/04-observation.json' if folder else None
            document = read(observation) if observation and observation.exists() else None
            if result and result['status'] == 'PASS' and not document:
                raise ValueError(f'PASS_WITHOUT_OBSERVATION:{case}:{label}')
            rows.append({'id': case, 'type': label, 'status': result['status'] if result else 'NOT_RUN',
                         'reason': result.get('reason', '') if result else 'PREPARATION_NOT_PASSED',
                         'round': folder.parent.parent.name if folder else None,
                         'human_decision': export_policy.current_decision(state, human) or 'NOT_RECORDED',
                         'question': document.get('question') if document else None,
                         'context': document.get('context') if document else None,
                         'source': str(observation.relative_to(run)) if document else None,
                         'source_sha256': sha(observation) if document else None,
                         'result': origin})
            rows[-1]['edit_provenance'] = edit_record(run, baselines[case], rows[-1], label)
            if document and state.get('inverse_review_ref'):
                from importlib import import_module
                ref = state['inverse_review_ref']
                import_module('finarch.dataset.02-generation.03-validation.ea_inverse_review').verify_reference(folder, ref, document)
                rows[-1]['inverse_review_ref'] = {**ref, 'path': str((folder/ref['path']).relative_to(run))}
        name = folder_name + '.json'
        save(output / name, rows)
        files[name] = {'count': len(rows), 'status_counts': dict(Counter(row['status'] for row in rows)),
                       'edit_provenance_counts': dict(Counter(row['edit_provenance']['status'] for row in rows)),
                       'sha256': sha(output / name)}
    save(output / 'manifest.json', {'source_run': run.name, 'selected_count': len(kept_ids),
         'source_input_count': len(ids), 'result_layout_version': 2, 'exclusions': exclusions,
         'edit_provenance_schema_version': 1,
         'external_knowledge_schema_version': 1,
         'source_report_sha256': sha(run / '02-generation/result-report.json'), 'files': files,
         'selection_policy': export_policy.POLICY,
         'meaning': 'PASS is automatic validation; human approval and semantic correctness are separate.'})
    (output / 'README.md').write_text(results_readme(run.name, len(kept_ids), export_policy.POLICY))
    save(output / 'export-log.json', {'generated_at': datetime.now(timezone.utc).isoformat(),
         'source_run': run.name, 'input_count': len(ids), 'exported_input_count': len(kept_ids),
         'excluded_count': len(exclusions), 'exclusions': exclusions,
         'pass_count': sum(item['status_counts'].get('PASS', 0) for item in list(files.values())[1:]),
         'model_calls': 0, 'reference_metadata_repairs': metadata_repairs})
    log = read(output / 'export-log.json')
    log['external_knowledge_sources'] = knowledge_sources
    log['external_knowledge_counts'] = knowledge_counts
    save(output / 'export-log.json', log)
    return files


def prepare_copy(run, output):
    """Deliver existing result bytes to data/prepared without rerunning export."""
    run, output = Path(run).resolve(), Path(output).resolve()
    source = run / 'results'
    if output.exists():
        raise ValueError('PREPARED_DESTINATION_ALREADY_EXISTS')
    if output.is_relative_to(run) or run.is_relative_to(output):
        raise ValueError('PREPARED_DESTINATION_MUST_BE_SEPARATE_FROM_RUN')
    manifest = read(source / 'manifest.json')
    if manifest['source_run'] != run.name:
        raise ValueError('RESULTS_RUN_MISMATCH')
    if manifest.get('source_report_sha256') != sha(run / '02-generation/result-report.json'):
        raise ValueError('RESULTS_SOURCE_REPORT_CHANGED')
    names = ('00-input.json', *(name + '.json' for _, name in TYPES))
    arrays = {}
    for name in names:
        if sha(source / name) != manifest['files'][name]['sha256']:
            raise ValueError('RESULTS_FILE_HASH_MISMATCH:' + name)
        arrays[name] = read(source / name)
        if len(arrays[name]) != manifest['files'][name]['count']:
            raise ValueError('RESULTS_FILE_COUNT_MISMATCH:' + name)
    originals = arrays[names[0]]
    ids = [row['id'] for row in originals]
    if len(ids) != manifest['selected_count'] or len(ids) != len(set(ids)):
        raise ValueError('RESULTS_INPUT_COUNT_OR_ID_MISMATCH')
    indexes = []
    for (label, _), name in zip(TYPES, names[1:]):
        rows = arrays[name]
        sparse = manifest.get('selection_policy') == export_policy.POLICY
        if not export_policy.aligned_ids(rows, ids, sparse=sparse) or any(row['type'] != label for row in rows):
            raise ValueError('RESULTS_TYPE_ALIGNMENT_MISMATCH:' + label)
        if sparse:
            omitted = set(ids) - {row['id'] for row in rows}
            declared = {entry['case'] for entry in manifest.get('exclusions', [])
                        if entry.get('scope') == 'variant' and entry.get('variant') == label
                        and entry.get('decision') in export_policy.REJECTED}
            if omitted != declared:
                raise ValueError('RESULTS_REJECTION_EXCLUSIONS_MISMATCH:' + label)
        indexes.append({row['id']: row for row in rows})
    complete = [row['id'] for row in originals if row['status'] == 'PASS' and
                all(index.get(row['id'], {}).get('status') == 'PASS' for index in indexes)]
    paths = sorted(path for path in source.rglob('*') if path.is_file())
    if any(path.is_symlink() for path in source.rglob('*')):
        raise ValueError('RESULTS_SYMLINK_NOT_ALLOWED')
    snapshots = {path.relative_to(source).as_posix(): sha(path) for path in paths}
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=output.parent, prefix='.' + output.name + '-'))
    try:
        shutil.copytree(source, staging, dirs_exist_ok=True)
        (staging / 'README.md').rename(staging / 'SOURCE-README.md')
        copied = {('SOURCE-README.md' if name == 'README.md' else name): digest
                  for name, digest in snapshots.items()}
        for name, digest in copied.items():
            if sha(staging / name) != digest:
                raise ValueError('PREPARED_COPY_HASH_MISMATCH:' + name)
        current_paths = sorted(path for path in source.rglob('*') if path.is_file())
        if snapshots != {path.relative_to(source).as_posix(): sha(path) for path in current_paths}:
            raise ValueError('RESULTS_CHANGED_DURING_COPY')
        project = Path(__file__).resolve().parents[4]
        source_run = run.relative_to(project).as_posix() if run.is_relative_to(project) else str(run)
        record = {'kind': 'PREPARED_GENERATION_RESULTS', 'version': 1,
                  'created_at': datetime.now(timezone.utc).isoformat(), 'source_run': source_run,
                  'source_manifest_sha256': snapshots['manifest.json'], 'copied_files': copied,
                  'originals': len(originals), 'automatic_complete_seven_pass': len(complete),
                  'complete_case_ids': complete,
                  'external_knowledge_complete_counts': dict(Counter(
                      str(row.get('external_knowledge', {}).get('used'))
                      for row in originals if row['id'] in set(complete))),
                  'model_calls': 0,
                  'meaning': 'Byte-preserving delivery; automatic PASS is not human approval. Failures remain preserved.'}
        save(staging / 'prepared-results.json', record)
        with (staging / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps({'time': record['created_at'], 'action': 'PREPARED_RESULTS_DELIVERED',
                'source_run': source_run, 'source_manifest_sha256': record['source_manifest_sha256'],
                'model_calls': 0}) + '\n')
        template = project / 'src/finarch/documentation/templates/prepared-generation-results.md'
        (staging / 'README.md').write_text(template.read_text().format(
            run_name=run.name, source_run=source_run, output=str(output.relative_to(project))
            if output.is_relative_to(project) else str(output), originals=len(originals),
            complete=len(complete), incomplete=len(originals) - len(complete)))
        if output.exists():
            raise ValueError('PREPARED_DESTINATION_ALREADY_EXISTS')
        staging.rename(output)
        return {key: record[key] for key in ('kind', 'source_run', 'originals',
                'automatic_complete_seven_pass', 'source_manifest_sha256', 'model_calls')} | {'output': str(output)}
    finally:
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('--edit-provenance-only', action='store_true',
                        help='Enrich existing rows without regenerating Q/C, status, or selection.')
    parser.add_argument('--external-knowledge-only', action='store_true',
                        help='Backfill confirmed external use without regenerating Q/C, status, or variants.')
    parser.add_argument('--prepared-output', type=Path,
                        help='Copy existing results to a new prepared dataset folder without re-exporting.')
    arguments = parser.parse_args()
    if sum((arguments.edit_provenance_only, arguments.external_knowledge_only,
            arguments.prepared_output is not None)) > 1:
        parser.error('Choose one export, enrichment, or delivery operation.')
    operation = (enrich_external_existing if arguments.external_knowledge_only else
                 enrich_existing if arguments.edit_provenance_only else export)
    result = (prepare_copy(arguments.run, arguments.prepared_output) if arguments.prepared_output else
              operation(arguments.run))
    print(json.dumps(result, ensure_ascii=False))
