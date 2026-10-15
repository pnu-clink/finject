"""Freeze current delivered inputs and private external-knowledge annotations."""
import collections
import importlib
from pathlib import Path


def module(name):
    return importlib.import_module('finarch.experiments.' + name)


def main():
    store = module('90-operations.storage')
    layout = module('90-operations.run_layout')
    settings = module('90-operations.settings')
    inputs = module('00-input.pipeline')
    requests = module('01-evaluation.02-request.prepare')
    previous = store.PROJECT / 'reports/experiments-run/20260927-exp-007-luna'
    original = store.read(previous / 'config.json')['evaluation']
    config = {k: original[k] for k in ('dataset', 'seed', 'reasoning_modes', 'output_root')}
    public, private, selection = inputs.prepare(config)
    assert len(public) == 4456 and selection['originals'] == 557
    assert public == store.rows(layout.inputs(previous) / 'public.jsonl'), 'PUBLIC_COHORT_CHANGED'
    delivered = store.PROJECT / config['dataset']['source_run'] / 'results'
    labels = {r['id']: r['external_knowledge'] for r in store.read(delivered / '00-input.json')}
    for row in private:
        row['original_external_knowledge'] = labels[row['case']]
        row['external_knowledge_scope'] = 'Original production dependency; not revalidated for edited variants.'
    _, analysis = settings.load_file()
    for size, concurrency, memory in ((8, 16, .92), (14, 20, .90)):
        key = f'qwen3-{size}b'
        root = store.PROJECT / 'reports/experiments-run' / f'20260928-a100-{key}'
        root.mkdir(parents=True, exist_ok=True)
        if any(root.iterdir()):
            raise ValueError('NONEMPTY_RUN:' + str(root))
        model = {'key': key, 'model': f'Qwen/Qwen3-{size}B', 'transport': 'vllm_local',
                 'output_limits': {'off': 8192, 'on': 8192}}
        evaluation = {**config, 'models': [model], 'schedule': {'concurrency': concurrency},
                      'definition_source_run': str(previous.relative_to(store.PROJECT))}
        runtime = {'tensor_parallel_size': 4, 'dtype': 'bfloat16', 'max_num_seqs': 32,
                   'max_num_batched_tokens': 8192, 'gpu_memory_utilization': memory,
                   'max_model_len': 10240, 'prefix_caching': False, 'chunked_prefill': True,
                   'cuda_graphs': True, 'client_concurrency': concurrency,
                   'sampling': {'off': {'temperature': .7, 'top_p': .8},
                                'on': {'temperature': .6, 'top_p': .95}},
                   'top_k': 20, 'min_p': 0, 'seed': 20260927,
                   'status': 'PENDING_TOKEN_LENGTH_PREFLIGHT'}
        store.write(root / 'config.json', {'layout_version': 2, 'evaluation': evaluation, 'analysis': analysis})
        store.write_rows(layout.inputs(root) / 'public.jsonl', public)
        store.write_rows(layout.inputs(root) / 'private.jsonl', private)
        plan = requests.prepare(root, evaluation, public, selection, previous)
        assert plan['models'][0]['requests'] == 17824
        plan.update(transport='LOCAL_VLLM_CONTINUOUS_BATCHING', incremental_api_charge_usd=0,
                    infrastructure_cost='UNKNOWN', runtime=runtime)
        plan['models'][0]['billed_estimate'] = 'LOCAL_GPU_NO_EXTERNAL_API_CHARGE_INFRASTRUCTURE_UNKNOWN'
        store.write(layout.plan(root), plan)
        store.write(root / 'a100-runtime.json', runtime)
        store.write(root / 'source-provenance.json', {
            'source_manifest': store.read(delivered / 'manifest.json'),
            'public_equal_to_luna': True, 'external_knowledge_scope': 'PRIVATE_ORIGINAL_LABELS',
            'original_label_counts': dict(collections.Counter(str(labels[r['case']]) for r in private if r['variant'] == 'ORIGINAL'))})
        store.write(root / 'manifest.json', {str(p.relative_to(root)): store.file_hash(p)
                     for p in root.rglob('*') if p.is_file()})
        store.write(root / 'state.json', {'status': 'PREPARED', 'models': {key: {'status': 'PENDING'}}})
        store.event(root, 'A100_PREPARED', requests=17824, original_cases=557, public_equal_to_luna=True)
        print(root)


if __name__ == '__main__':
    main()
