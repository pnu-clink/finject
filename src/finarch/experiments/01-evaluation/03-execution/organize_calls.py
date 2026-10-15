"""Migrate saved call records without changing model inputs or invoking a model."""
import shutil
from contextlib import ExitStack
from pathlib import Path
from finarch.paths import SOURCE

call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])
configuration = __import__('finarch.experiments.90-operations.storage', fromlist=['configuration']).configuration
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
locked = __import__('finarch.experiments.90-operations.storage', fromlist=['locked']).locked
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_rows = __import__('finarch.experiments.90-operations.storage', fromlist=['write_rows']).write_rows
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text

METRICS = ('planned', 'statuses', 'attempts', 'input_tokens', 'output_tokens_including_thinking',
           'cache_read_tokens', 'cache_creation_tokens', 'attempts_without_usage',
           'api_equivalent_usd', 'paid_batch_usage_cost_estimate_usd')


def consolidate_root(source, target):
    """Rename the experiment root on its existing volume, verifying every file."""
    source, target = Path(source), Path(target)
    if not source.exists():
        if target.exists():
            return read(target / 'root-migration-verification.json', {'status': 'ALREADY_AT_TARGET'})
        raise ValueError('EXPERIMENT_ROOT_MISSING')
    if target.exists():
        raise ValueError('EXPERIMENT_ROOT_COLLISION')
    with ExitStack() as stack:
        stack.enter_context(locked(source / '.sequence.lock'))
        for root in sorted(source.glob('*-exp-*')):
            stack.enter_context(locked(root / '.pipeline.lock'))
        hashes = {str(p.relative_to(source)): file_hash(p) for p in source.rglob('*') if p.is_file()}
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        for relative, expected in hashes.items():
            if file_hash(target / relative) != expected:
                raise ValueError('ROOT_MOVE_HASH_MISMATCH:' + relative)
        result = {'status': 'VERIFIED', 'from': str(source), 'to': str(target),
                  'verified_at': now(), 'preserved_files': len(hashes), 'new_model_calls': 0}
        write(target / 'root-migration-hashes.json', hashes)
        write(target / 'root-migration-verification.json', result)
        if not any(source.parent.iterdir()):
            source.parent.rmdir()
        return result


def metrics(summary):
    return {m['model']: {k: m[k] for k in METRICS} for m in summary['models']}


def check_sources(root):
    """The before/after names refer to the value parent, not attribution semantics."""
    private = rows(root / '01-input/private.jsonl')
    by_id = {x['item_id']: x for x in private}
    expected = {'IC_SOURCE_A_ONLY': 'IC_VALUE_01_BEFORE', 'IC_SOURCE_B_ONLY': 'IC_VALUE_01_AFTER'}
    counts = {k: 0 for k in expected}
    for item in private:
        if item['variant'] not in expected:
            continue
        parents = item.get('matched_value_parent_ids', [])
        if len(parents) != 1 or by_id.get(parents[0], {}).get('variant') != expected[item['variant']]:
            raise ValueError('SOURCE_POSITION_MAPPING_NOT_CONFIRMED:' + item['case'])
        counts[item['variant']] += 1
    return counts


def make_plan(root):
    mapping, files = [], []
    for model in configuration(root)['models']:
        base = root / model['key']
        requests = rows(base / '01-requests/manifest.jsonl')
        call_layout.check_manifest(base, requests)
        by_id = {r['trial_id']: r for r in requests}
        for old in sorted((base / '02-calls').glob('*')):
            if not old.is_dir() or old.name not in by_id:
                raise ValueError('UNMAPPED_LEGACY_CALL:' + str(old))
            request = by_id[old.name]
            new = call_layout.record_dir(base, request)
            if new.exists():
                raise ValueError('CALL_DESTINATION_EXISTS:' + str(new))
            mapping.append({'model': model['key'], 'case': request['case'], 'variant': request['variant'],
                            'trial_id': old.name, 'old': str(old.relative_to(root)),
                            'new': str(new.relative_to(root)),
                            'call_path': str(call_layout.call_path(base, request).relative_to(root))})
            for path in sorted(old.rglob('*')):
                if path.is_symlink():
                    raise ValueError('UNEXPECTED_RECORD_SYMLINK:' + str(path))
                if path.is_file():
                    files.append({'old': str(path.relative_to(root)),
                                  'new': str((new / path.relative_to(old)).relative_to(root)),
                                  'sha256': file_hash(path)})
    return mapping, files


def organize(root):
    verify = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['verify']).verify
    root = Path(root).resolve()
    with locked(root / '.pipeline.lock'):
        verify(root)
        layout = root / 'layout'
        plan_path = layout / 'plan.json'
        if not plan_path.exists():
            source_mapping = check_sources(root)
            mapping, files = make_plan(root)
            saved = [root / p for p in ('summary.json', 'REPORT.md', 'README.md', 'ANALYSIS.md', 'CASE-STUDIES.md')]
            for model in configuration(root)['models']:
                saved.extend((root / model['key'] / '03-results').glob('*'))
                saved.append(root / model['key'] / 'README.md')
            saved.extend((root / 'analysis').glob('*'))
            for path in saved:
                if path.is_file():
                    dest = layout / 'before' / path.relative_to(root)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, dest)
            write_rows(layout / 'mapping.jsonl', mapping)
            write_rows(layout / 'record-hashes.jsonl', files)
            write(plan_path, {'created_at': now(), 'old_layout': '02-calls/<hash>/attempt-xxx',
                              'new_layout': 'calls/<case>/<type>/_records/<hash>/attempt-xxx',
                              'source_position_mapping': source_mapping,
                              'metrics_before': metrics(read(root / 'summary.json'))})
        plan = read(plan_path)
        mapping, files = rows(layout / 'mapping.jsonl'), rows(layout / 'record-hashes.jsonl')
        # Preflight every saved file before the first move, including recovery after interruption.
        for item in files:
            old, new = root / item['old'], root / item['new']
            if old.exists() == new.exists():
                raise ValueError('AMBIGUOUS_OR_MISSING_MIGRATION_RECORD:' + item['old'])
            if file_hash(old if old.exists() else new) != item['sha256']:
                raise ValueError('MIGRATION_RECORD_CHANGED:' + item['old'])
        event(root, 'CALL_LAYOUT_STARTED', records=len(mapping), files=len(files), new_model_calls=0)
        for item in mapping:
            old, new = root / item['old'], root / item['new']
            if old.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                old.rename(new)
        for model in configuration(root)['models']:
            old = root / model['key'] / '02-calls'
            if old.exists():
                old.rmdir()
        summary = reporting.build(root)
        if metrics(summary) != plan['metrics_before']:
            raise ValueError('MIGRATION_CHANGED_COUNTS_OR_COSTS')
        if (root / 'ANALYSIS.md').exists() and root.name == '20260920-exp-003':
            analyze = __import__('finarch.experiments.02-analysis.legacy.content-analysis.analysis', fromlist=['main']).main
            analyze(root)
        verify(root)
        for item in files:
            if file_hash(root / item['new']) != item['sha256']:
                raise ValueError('MIGRATION_HASH_MISMATCH:' + item['new'])
        result = {'status': 'VERIFIED', 'run_id': root.name, 'verified_at': now(),
                  'moved_trial_folders': len(mapping), 'preserved_files': len(files),
                  'readable_call_files': sum(len(list((root / m['key'] / 'calls').glob('*/*/*.json')))
                                             for m in configuration(root)['models']),
                  'frozen_manifest_unchanged': True, 'counts_and_costs_unchanged': True,
                  'new_model_calls': 0}
        write(layout / 'verification.json', result)
        template = SOURCE / 'experiments/templates/call-layout-readme-template.md'
        write_text(layout / 'README.md', template.read_text().format(**result))
        event(root, 'CALL_LAYOUT_VERIFIED', **result)
        return result
