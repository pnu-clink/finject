"""Register completed vLLM stages in the standard experiment layout without model calls."""
import importlib
import json
from pathlib import Path
import re
import shutil
from string import Template

store = importlib.import_module('finarch.experiments.90-operations.storage')
layout = importlib.import_module('finarch.experiments.90-operations.run_layout')


def finish_group(group):
    """Retain old recovery history inside E01 after both standard runs are complete."""
    group = Path(group).resolve()
    if group.parent != (store.PROJECT / 'reports/experiments-run').resolve() or not re.fullmatch(r'\d{8}-fino1-recovery', group.name):
        raise ValueError('UNEXPECTED_STAGE_RECOVERY_GROUP')
    verified = store.read(group / 'verification.json')['stages']
    roots = []
    for row in verified:
        root = group.parent / (group.name[:8] + '-' + row['stage'])
        store.verify(root)
        state = store.read(root / 'state.json')
        if state.get('full_pipeline', {}).get('status') != 'EVALUATION_COMPLETE' or (group / row['stage']).exists():
            raise ValueError('STANDARD_STAGE_REGISTRATION_NOT_COMPLETE:' + row['stage'])
        if store.file_hash(layout.requests(root, row['stage'])) != row['manifest_sha256']:
            raise ValueError('REGISTERED_SOURCE_MANIFEST_CHANGED:' + row['stage'])
        roots.append(root)
    for root in roots:
        model, = store.configuration(root)['models']
        suffix = model['key'].rsplit('-', 1)[1]
        for source_name, target in (
            ('registration-' + suffix + '.log', layout.execution(root, model['key']) / 'pipeline.log'),
            ('recovery-' + suffix + '.log', layout.execution(root, model['key']) / 'source-stage/recovery.log')):
            source = group / source_name
            if source.exists():
                if target.exists():
                    raise ValueError('HISTORY_TARGET_ALREADY_EXISTS:' + str(target))
                source.rename(target)
    history = layout.preparation(next(root for root in roots if root.name.endswith('-8b'))) / 'registration-history'
    if history.exists():
        raise ValueError('REGISTRATION_HISTORY_ALREADY_EXISTS')
    original_files = {path.name: store.file_hash(path) for path in group.iterdir() if path.is_file()}
    group.rename(history)
    for name, digest in original_files.items():
        if store.file_hash(history / name) != digest:
            raise ValueError('REGISTRATION_HISTORY_CHANGED:' + name)
    (history / 'README.md').rename(history / 'recovery-index.original.txt')
    template = Template((store.PROJECT / 'src/finarch/experiments/templates/a100-stage-registration-history.md').read_text())
    store.write_text(history / 'README.md', template.substitute(runs=', '.join(root.name for root in roots)))
    store.write(history / 'finalization-receipt.json', {'status': 'PASS', 'at': store.now(),
                'original_files_sha256': original_files, 'runs': [root.name for root in roots], 'model_calls': 0})
    return {'status': 'STANDARD_RUNS_REGISTERED', 'runs': [root.name for root in roots], 'model_calls': 0}


def cache_audit(stage):
    evidence = stage / 'remote-evidence'
    with (evidence / 'telemetry.jsonl').open() as stream:
        first = json.loads(next(stream))
    final = store.read(evidence / 'cache-final.json')
    initial_hits, final_hits = {}, {}
    if not final.get('engines') or set(first['vllm']) != set(final['engines']):
        raise ValueError('CACHE_ENGINE_COVERAGE_MISMATCH')
    for endpoint, metrics in first['vllm'].items():
        configurations = [line for line in metrics if line.startswith('vllm:cache_config_info{')]
        if len(configurations) != 1 or 'enable_prefix_caching="False"' not in configurations[0]:
            raise ValueError('INITIAL_CACHE_DISABLED_NOT_VERIFIED:' + endpoint)
        for name in ('prefix_cache_hits_total', 'external_prefix_cache_hits_total'):
            matches = [float(line.rsplit(' ', 1)[1]) for line in metrics if line.startswith('vllm:' + name + '{')]
            if len(matches) != 1 or matches[0] != 0:
                raise ValueError('INITIAL_CACHE_COUNTER_NOT_EXPLICIT_ZERO:' + endpoint)
            initial_hits[endpoint + '/' + name] = matches[0]
        engine = final['engines'][endpoint]
        if engine.get('enabled') is not False or any(engine.get(name) != 0 for name in ('prefix_hits', 'external_prefix_hits')):
            raise ValueError('FINAL_CACHE_DISABLED_ZERO_HITS_NOT_VERIFIED:' + endpoint)
        final_hits[endpoint] = {name: engine[name] for name in ('prefix_hits', 'external_prefix_hits')}
    if final.get('response_reuse') is not False:
        raise ValueError('RESPONSE_REUSE_POLICY_NOT_VERIFIED')
    return {'status': 'ENGINE_PREFIX_CACHE_DISABLED_ZERO_HITS_USAGE_UNKNOWN',
            'engine_prefix_caching': False, 'initial_hits': initial_hits, 'final_hits': final_hits,
            'initial_observation_at': first['utc'], 'initial_observation': 'FIRST_RECORDED_TELEMETRY_SAMPLE',
            'source_files': ['telemetry.jsonl', 'cache-final.json'], 'per_request_cached_tokens': None}


def register(root, stage, source_run):
    store.verify(source_run)
    source_manifest, = source_run.glob('01_evaluation/02_request/*/manifest.jsonl')
    prepared = store.read(stage / 'remote-evidence/prepared.json')
    receipt = store.read(stage / 'recovery-receipt.json')
    key = Path(prepared['manifest']).parent.name
    if not re.fullmatch(r'\d{8}-' + re.escape(key), root.name):
        raise ValueError('REGISTERED_STAGE_NAME_MUST_BE_DATE_AND_MODEL_KEY')
    if store.file_hash(source_manifest) != prepared['source_manifest_sha256']:
        raise ValueError('LOCAL_SOURCE_MANIFEST_HASH_MISMATCH')
    manifest = stage / 'remote-evidence/01_evaluation/02_request' / key / 'manifest.jsonl'
    if store.file_hash(manifest) != prepared['manifest_sha256'] or receipt['requests'] != prepared['requests']:
        raise ValueError('RECOVERED_STAGE_MANIFEST_CHANGED')
    hashes = store.read(stage / '_recovery/manifest.json')
    for index, (name, digest) in enumerate(hashes.items(), 1):
        if store.file_hash(store.path_in(stage, name)) != digest:
            raise ValueError('RECOVERED_STAGE_FILE_CHANGED:' + name)
        if index % 50000 == 0:
            print(json.dumps({'stage': key, 'verified_source_files': index, 'total': len(hashes)}), flush=True)
    if store.file_hash(stage / 'source-files.tar.gz') != receipt['archive_sha256']:
        raise ValueError('RECOVERED_STAGE_ARCHIVE_CHANGED')
    audit = cache_audit(stage)
    previous = {(r['item_id'], r['prompt_condition'], r['reasoning']): r for r in store.rows(source_manifest)}
    samples, modes, count = {}, set(), 0
    invariant = ('input', 'prompt', 'response_schema', 'max_output_tokens', 'reasoning',
                 'prompt_condition', 'item_id', 'case', 'experiment', 'variant', 'cache_policy')
    for request in store.rows(manifest):
        original = previous.pop((request['item_id'], request['prompt_condition'], request['reasoning']))
        if any(request[field] != original[field] for field in invariant) or request['model'] != prepared['model']:
            raise ValueError('FROZEN_STAGE_INPUT_DIFFERS_FROM_SOURCE:' + request['trial_id'])
        if not request['response_schema'].get('properties'):
            raise ValueError('NONEMPTY_RESPONSE_SCHEMA_REQUIRED')
        modes.add(request['reasoning'])
        if request['reasoning'] not in samples:
            samples[request['reasoning']] = store.read(stage / 'remote-results' / request['trial_id'] / 'provider-request.json')
        count += 1
    if previous or count != prepared['requests']:
        raise ValueError('REGISTERED_COHORT_COVERAGE_MISMATCH')
    config = store.read(source_run / 'config.json')
    evaluation = config['evaluation']
    model = {'key': key, 'model': prepared['model'], 'revision': prepared['revision'],
             'transport': 'vllm_local', 'output_limits': {mode: prepared['max_output_tokens'] for mode in modes}}
    evaluation.update(models=[model], reasoning_modes=sorted(modes), run_label=key,
                      schedule={'concurrency': prepared['profile']['concurrency']})
    config['analysis'] = {'enabled': False}
    config['execution_owner'] = '[vllm] gpu-2'
    config['registration'] = {'mode': 'COMPLETED_VLLM_STAGE', 'source_manifest_sha256': prepared['manifest_sha256']}
    store.write(root / 'config.json', config)
    for name in ('public.jsonl', 'private.jsonl'):
        target = root / '00_input' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_run / '00_input' / name, target)
    definition = layout.definition(root)
    definition.mkdir(parents=True, exist_ok=True)
    for name in ('common.md', 'prompt-unguided.md', 'prompt-guided.md', 'response.schema.json'):
        shutil.copyfile(layout.definition(source_run) / name, definition / name)
    layout.requests(root, key).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manifest, layout.requests(root, key))
    runtime = {'sampling': {mode: {field: samples[mode][field] for field in ('temperature', 'top_p')} for mode in modes},
               **{field: samples['off'][field] for field in ('top_k', 'min_p', 'seed')},
               'served_model': key, 'profile': prepared['profile'], 'revision': prepared['revision']}
    store.write(layout.preparation(root) / 'a100-runtime.json', runtime)
    store.write(layout.preparation(root) / 'cache-audit.json', audit)
    order = importlib.import_module('finarch.experiments.01-evaluation.02-request.request_order')
    selection = order.selection_from_manifests(root, public=store.rows(root / '00_input/public.jsonl'), require_same_items=True)
    summary = store.read(stage / 'remote-evidence/collection-index.json')
    store.write(layout.plan(root), {'created_at': store.now(), 'models': [{**model, 'requests': count,
                'experiment1': selection['originals'] * 4, 'experiment2': selection['variants'] * 4,
                'input_token_estimate': summary['usage_totals']['prompt_tokens'],
                'estimate_method': 'ACTUAL_REPORTED_USAGE_OF_COMPLETED_REQUESTS'}],
                'source': evaluation['dataset'], 'concurrency': prepared['profile']['concurrency'],
                'transport': 'LOCAL_VLLM_CONTINUOUS_BATCHING', 'semantic_evaluator_calls': 0,
                'incremental_api_charge_usd': 0, 'infrastructure_cost': 'UNKNOWN'})
    for name in ('model', 'run'):
        shutil.copyfile(store.PROJECT / ('src/finarch/experiments/templates/ordered-' + name + '-readme-template.md'),
                        layout.preparation(root) / (name + '-readme-template.md'))
    destination = layout.execution(root, key) / 'source-stage'
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage.rename(destination)
    store.write(root / 'recovery-receipt.json', {**receipt, 'source_stage_path': str(destination.relative_to(root))})
    store.write(layout.preparation(root) / 'registration-provenance.json', {
        'source_run': str(source_run.relative_to(store.PROJECT)), 'source_manifest_sha256': prepared['source_manifest_sha256'],
        'public_sha256': store.file_hash(root / '00_input/public.jsonl'),
        'private_sha256': store.file_hash(root / '00_input/private.jsonl'),
        'request_manifest_sha256': prepared['manifest_sha256'], 'verified_original_files': len(hashes), 'model_calls': 0})
    frozen = ['config.json', '00_input/public.jsonl', '00_input/private.jsonl'] + [
        str(p.relative_to(root)) for directory in (definition, layout.preparation(root)) for p in directory.rglob('*') if p.is_file()]
    store.write(root / 'manifest.json', {name: store.file_hash(root / name) for name in frozen})
    store.verify(root)
    store.event(root, 'COMPLETED_VLLM_STAGE_REGISTERED', model=prepared['model'], requests=count,
                source_manifest_sha256=prepared['manifest_sha256'], model_calls=0)
    return destination


def run(root, source_stage, source_run):
    root = Path(root).resolve()
    allowed = (store.PROJECT / 'reports/experiments-run').resolve()
    if root.parent != allowed or root.is_symlink():
        raise ValueError('STANDARD_RUN_MUST_BE_DIRECTLY_UNDER_EXPERIMENTS_RUN')
    root.mkdir(parents=True, exist_ok=True)
    with store.locked(root / '.pipeline.lock'):
        if (root / 'manifest.json').exists():
            store.verify(root)
            model, = store.configuration(root)['models']
            stage = layout.execution(root, model['key']) / 'source-stage'
        else:
            stage = register(root, Path(source_stage).resolve(), Path(source_run).resolve())
        collect = importlib.import_module('finarch.experiments.a100.collect')
        report = importlib.import_module('finarch.experiments.a100.summarize_recovered')
        collect.collect(root, source_stage=stage)
        summary = report.summarize(root, source_stage=stage)
        state = store.read(root / 'state.json')
        state.update(execution_control={name: {'paused': True, 'reason': 'Completed Evaluation import only; no model calls authorized.'}
                                       for name in ('evaluation', 'analysis')},
                     full_pipeline={'status': 'EVALUATION_COMPLETE', 'stage': 'WAIT_ANALYSIS', 'new_model_calls': 0})
        store.write(root / 'state.json', state)
        importlib.import_module('finarch.experiments.90-operations.run_documentation').render(root)
        store.event(root, 'COMPLETED_VLLM_STAGE_VALIDATED', responses=summary['responses'], statuses=summary['statuses'], model_calls=0)
        return {'status': 'EVALUATION_COMPLETE', 'run': root.name, 'responses': summary['responses'],
                'statuses': summary['statuses'], 'model_calls': 0}
