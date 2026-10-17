"""A01: reuse an Evaluation snapshot and collect existing observations only."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import re
import shutil

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
METHOD = 'results-focused-v1'
VARIANTS = ('ORIGINAL', 'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER',
            'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')
ANALYSIS = Path('02_analysis')


def source_file(root, relative):
    """Read only regular, non-symlink files within a named run."""
    root = Path(root).resolve()
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('INVALID_RUN_REFERENCE:' + str(relative))
    path = root / relative
    cursor = root
    for segment in relative.parts:
        cursor = cursor / segment
        if cursor.is_symlink():
            raise ValueError('SYMLINK_NOT_ALLOWED:' + str(relative))
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError('RUN_FILE_MISSING:' + str(relative))
    return path


def snapshot(root):
    return {str(p.relative_to(root)): store.file_hash(p) for p in sorted(Path(root).rglob('*')) if p.is_file()}


def key(row):
    return row['model'] + ':' + row['trial_id']


def unique(rows, field, label):
    result = {}
    for row in rows:
        value = row[field]
        if value in result:
            raise ValueError('DUPLICATE_' + label + ':' + value)
        result[value] = row
    return result


def render(root, stage, **values):
    text = (store.PROJECT / 'src/finarch/experiments/templates' / ('results-' + stage + '-readme.md')).read_text()
    target = root / ('README.md' if stage == 'run' else '02_analysis/README.md' if stage == 'analysis' else '02_analysis/' + stage + '/README.md')
    store.write_text(target, text.format(run=root.name, **values))


def prepare(source, target, *, analysis=None, tag=None):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source.parent != target.parent or not all(store.RUN_NAME.fullmatch(p.name) for p in (source, target)):
        raise ValueError('EXPERIMENT_RUN_SIBLINGS_REQUIRED')
    if target.exists():
        raise ValueError('TARGET_ALREADY_EXISTS')
    frozen = store.read(source / 'manifest.json')
    for relative, expected in frozen.items():
        if store.file_hash(source_file(source, relative)) != expected:
            raise ValueError('SOURCE_MANIFEST_CHANGED:' + relative)
    hashes = (snapshot(source) if analysis is None else
              {str(p.relative_to(source)): store.file_hash(p) for name in ('00_input', '01_evaluation')
               for p in sorted((source / name).rglob('*')) if p.is_file()})
    source_config = store.read(source / 'config.json')
    if source_config.get('layout_version') != 2:
        raise ValueError('ORDERED_EVALUATION_REQUIRED')
    target.mkdir()
    for name in ('00_input', '01_evaluation'):
        # Copy bytes rather than linking writable Evaluation artifacts across runs.
        for p in (source / name).rglob('*'):
            if p.is_symlink():
                raise ValueError('SOURCE_SYMLINK_NOT_ALLOWED')
        shutil.copytree(source / name, target / name, copy_function=shutil.copyfile)
    config = deepcopy(source_config)
    config['run_kind'] = 'ANALYSIS_ONLY'
    config['evaluation_reuse'] = {
        'source_run': source.name, 'mode': 'BYTE_IDENTICAL_SNAPSHOT',
        'independent_evaluation': False, 'new_target_model_calls': 0,
        'source_manifest_sha256': store.file_hash(source / 'manifest.json'),
        'source_tree_sha256': store.digest(hashes),
        'source_file_count': len(hashes),
        'numeric_observations_path': '02_analysis/01_response_review/response-diagnostics.jsonl'}
    config['analysis'] = {'enabled': True, 'method': METHOD, 'backend': 'codex',
        'execution_mode': 'current_session', 'actual_model_id': None,
        'model_identity_note': 'Current Codex conversation; no separate CLI model invocation or inferred model identity.',
        'independent_input_review': False, 'automatic_experiment_improvements': False}
    if analysis is not None:
        config['analysis'] = deepcopy(analysis)
        config['analysis_tag'] = tag
        config['evaluation_reuse'].update(mode='PIPELINE_ANALYSIS_VARIANT',
            numeric_observations_path='01_evaluation/04_validation/numeric-comparisons.jsonl',
            source_hashes=hashes)
    store.write(target / 'config.json', config)
    manifest = {name: digest for name, digest in hashes.items() if name.startswith(('00_input/', '01_evaluation/'))}
    manifest['config.json'] = store.file_hash(target / 'config.json')
    store.write(target / 'manifest.json', manifest)
    saved = {'status': 'FINISHED', 'evaluation': {'status': 'REUSED',
        'source_run': source.name, 'new_target_model_calls': 0}, 'analysis': {'status': 'PREPARED', 'method': METHOD}}
    if analysis is not None:
        saved.update(models=deepcopy(store.read(source / 'state.json')['models']),
                     execution_control={'evaluation': {'paused': True, 'reason': 'Analysis-only snapshot.'},
                                        'analysis': {'paused': False}}, analysis_tag=tag)
    store.write(target / 'state.json', saved)
    store.event(target, 'EVALUATION_REUSED_FOR_ANALYSIS', source_run=source.name,
                copied_files=len(manifest)-1, new_target_model_calls=0, independent_evaluation=False)
    verify_reuse(target)
    render(target, 'run', source=source.name, status='Ready for the analysis.', planned=0)
    render(target, 'analysis', source=source.name, status='Ready for the analysis.')
    return target


def verify_reuse(root):
    root = Path(root).resolve()
    config = store.read(root / 'config.json')
    if 'evaluation_reuse' not in config:
        pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
        pipeline.verify(root)
        return True
    reuse = config['evaluation_reuse']
    source = root.parent / reuse['source_run']
    if reuse.get('mode') == 'PIPELINE_ANALYSIS_VARIANT':
        store.verify(source)
        if store.file_hash(source / 'manifest.json') != reuse['source_manifest_sha256']:
            raise ValueError('SOURCE_MANIFEST_CHANGED_AFTER_REUSE')
        for relative, expected in reuse['source_hashes'].items():
            if store.file_hash(source_file(source, relative)) != expected:
                raise ValueError('SOURCE_EVALUATION_CHANGED_AFTER_REUSE:' + relative)
    elif store.digest(snapshot(source)) != reuse['source_tree_sha256']:
        raise ValueError('SOURCE_RUN_CHANGED_AFTER_REUSE')
    for relative, expected in store.read(root / 'manifest.json').items():
        if store.file_hash(source_file(root, relative)) != expected:
            raise ValueError('REUSED_EVALUATION_CHANGED:' + relative)
    return True


def build(root):
    root = Path(root).resolve()
    verify_reuse(root)
    config = store.read(root / 'config.json')
    reuse = config.get('evaluation_reuse', {'source_run': root.name,
                        'numeric_observations_path': '01_evaluation/04_validation/numeric-comparisons.jsonl'})
    source = root.parent / reuse['source_run']
    private = unique(store.rows(root / '00_input/private.jsonl'), 'item_id', 'PRIVATE_ITEM')
    public = unique(store.rows(root / '00_input/public.jsonl'), 'item_id', 'PUBLIC_ITEM')
    diagnostic_path = source_file(source, reuse['numeric_observations_path'])
    diagnostic_hash = store.file_hash(diagnostic_path)
    diagnostics = {key(r): r for r in store.rows(diagnostic_path)}
    output = []
    for model in config['evaluation']['models']:
        model_key = model['key']
        relative = f'01_evaluation/02_request/{model_key}/manifest.jsonl'
        requests = store.rows(source_file(root, relative))
        unique(requests, 'trial_id', 'REQUEST')
        results_path = f'01_evaluation/04_validation/{model_key}/results.jsonl'
        results = unique(store.rows(source_file(root, results_path)), 'trial_id', 'RESULT')
        if set(results) - {r['trial_id'] for r in requests}:
            raise ValueError('UNPLANNED_RESULT')
        for request in requests:
            result = results.get(request['trial_id'], {})
            for field in ('item_id', 'case', 'variant', 'prompt_condition', 'reasoning'):
                if result and request[field] != result[field]:
                    raise ValueError('RESULT_IDENTITY_MISMATCH:' + field)
            response = result.get('response')
            saved = {}
            if result.get('result_path'):
                saved = store.read(source_file(root, result['result_path']))
                if response is not None and saved.get('response') != response:
                    raise ValueError('SAVED_RESPONSE_MISMATCH')
                response = saved.get('response', response)
            row = {**result, **{k:request[k] for k in ('trial_id','item_id','case','variant','prompt_condition','reasoning','experiment')},
                   'model': model_key, 'response': response, 'status': result.get('status', 'NOT_RUN')}
            row['response_id'] = key(row)
            item = private[row['item_id']]
            if row['item_id'] not in public:
                raise ValueError('PUBLIC_ITEM_MISSING')
            diagnostic = diagnostics.get(key(row))
            if diagnostic and any(diagnostic[f] != row[f] for f in ('case','item_id') if f in diagnostic):
                raise ValueError('DIAGNOSTIC_IDENTITY_MISMATCH')
            row['checks'] = {**result.get('checks', {}), **(diagnostic or {}).get('checks', {})}
            row['tags'] = (diagnostic or {}).get('tags', [])
            numeric = (diagnostic or {}).get('numeric_comparison')
            row['numeric_comparison'] = numeric
            row['original_result'] = ('MATCH' if numeric['matches'] else 'MISMATCH') if row['variant']=='ORIGINAL' and numeric and type(numeric.get('matches')) is bool else 'UNEVALUATED' if row['variant']=='ORIGINAL' else 'NOT_ORIGINAL'
            row['reference'] = item.get('reference', {})
            if 'original_external_knowledge' in item:
                row['original_external_knowledge'] = item['original_external_knowledge']
                row['external_knowledge_scope'] = item['external_knowledge_scope']
            row['alternative_answer'] = item.get('alternative_answer')
            row['original_item_id'] = item.get('original_item_id', row['item_id'])
            row['matched_value_parent_ids'] = item.get('matched_value_parent_ids', [])
            row['schema_title'] = request.get('response_schema', {}).get('title')
            row['evaluation_source'] = {'run': source.name, 'results': results_path, 'request_manifest': relative,
                'result_path': result.get('result_path'), 'numeric_observations': reuse['numeric_observations_path'] if diagnostic else None,
                'numeric_observations_sha256': diagnostic_hash if diagnostic else None}
            output.append(row)
    unique(output, 'response_id', 'RESPONSE')
    folder = root / ANALYSIS / '01_results'
    store.write_rows(folder / 'responses.jsonl', output)
    state = {'status': 'COLLECTED', 'method': METHOD, 'planned': len(output),
             'statuses': dict(Counter(r['status'] for r in output)), 'source_run': source.name,
             'new_target_model_calls': 0, 'independent_question_reviews': 0}
    if 'evaluation_reuse' not in config or reuse.get('mode') == 'PIPELINE_ANALYSIS_VARIANT':
        sources = ['00_input/public.jsonl', '00_input/private.jsonl', reuse['numeric_observations_path']]
        for model in config['evaluation']['models']:
            sources += [f"01_evaluation/02_request/{model['key']}/manifest.jsonl",
                        f"01_evaluation/04_validation/{model['key']}/results.jsonl"]
        sources += [r['result_path'] for r in output if r.get('result_path')]
        state['source_hashes'] = {p: store.file_hash(source_file(root, p)) for p in sources}
    store.write(folder / 'state.json', state)
    render(root, '01_results', source=source.name, planned=len(output), statuses=state['statuses'])
    if 'evaluation_reuse' in config:
        render(root, 'run', source=source.name, status='A01 Complete the merger', planned=len(output))
    store.event(root, 'A01_RESULTS_COLLECTED', **state)
    verify_reuse(root)
    materials = __import__('finarch.experiments.02-analysis.01-results.rq1_materials', fromlist=['build'])
    materials.build(root)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--reuse-evaluation')
    args = parser.parse_args()
    if args.reuse_evaluation:
        prepare(args.reuse_evaluation, args.run)
    print(build(args.run))
