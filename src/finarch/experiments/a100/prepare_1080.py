"""Freeze the current 1,080-case cohort and prompts for the GPU-2 owner.

This command only writes local files. It never starts a model or sends a request.
"""
import collections
import importlib
from pathlib import Path
import shutil
from string import Template


def module(name):
    return importlib.import_module('finarch.experiments.' + name)


def prepare():
    store = module('90-operations.storage')
    layout = module('90-operations.run_layout')
    order = module('01-evaluation.02-request.request_order')
    requests = module('01-evaluation.02-request.prepare')
    assets = module('assets')
    source = store.PROJECT / 'reports/experiments-run/20260928-exp-001-luna'
    store.verify(source)
    public_path = layout.inputs(source) / 'public.jsonl'
    private_path = layout.inputs(source) / 'private.jsonl'
    public, private = store.rows(public_path), store.rows(private_path)
    selection = order.selection_from_manifests(source, public=public, require_same_items=True)
    if len(public) != 8640 or len(private) != 8640 or selection['originals'] != 1080 or selection['variants'] != 7560:
        raise ValueError('FINANCE_REASONING_1080_COHORT_REQUIRED')
    labels = collections.Counter(
        str(item['original_external_knowledge']['used']) for item in private
        if item['variant'] == 'ORIGINAL'
    )
    if sum(labels.values()) != 1080:
        raise ValueError('ORIGINAL_EXTERNAL_KNOWLEDGE_INCOMPLETE')
    prompt_sources = {
        'common.md': assets.prompt_path('solver_common'),
        'prompt-unguided.md': assets.prompt_path('solver_unguided'),
        'prompt-guided.md': assets.prompt_path('solver_guided'),
        'response.schema.json': assets.schema_path('solver_response'),
    }
    for path in prompt_sources.values():
        if not path.is_file() or not path.read_text().strip():
            raise ValueError('CURRENT_PROMPT_OR_SCHEMA_MISSING:' + str(path))
    schema = assets.schema('solver_response')
    if schema['title'] != 'FinancialAnswerV7':
        raise ValueError('FINANCIAL_ANSWER_V7_REQUIRED')
    source_dataset = layout.evaluation_config(source)['dataset']
    created = []
    for size, concurrency, memory in ((8, 16, 0.92), (14, 20, 0.90)):
        key = f'qwen3-{size}b'
        label = f'a100-financereasoning-{key}'
        day = store.now()[:10].replace('-', '')
        if any(p.name.startswith(day + '-exp-') and p.name.endswith('-' + label)
               for p in (store.PROJECT / 'reports/experiments-run').iterdir()):
            raise ValueError('TODAYS_HANDOFF_ALREADY_EXISTS:' + label)
        root = store.allocate(store.PROJECT / 'reports/experiments-run', label=label)
        model = {'key': key, 'model': f'Qwen/Qwen3-{size}B', 'transport': 'vllm_local',
                 'output_limits': {'off': 8192, 'on': 8192}}
        evaluation = {
            'dataset': source_dataset, 'schedule': {'concurrency': concurrency},
            'models': [model], 'reasoning_modes': ['off', 'on'], 'seed': 20260929,
            'output_root': 'reports/experiments-run', 'run_label': label,
            'response_contract': schema['title'],
            'cache_policy': {'mode': 'forbidden', 'scope': ['cross_request_prefix_cache',
                            'cross_run_response_reuse'], 'missing_usage': 'UNKNOWN_NOT_ZERO'},
        }
        store.write(root / 'config.json', {'layout_version': 2, 'evaluation': evaluation,
                                          'analysis': {'enabled': False},
                                          'execution_owner': '[vllm] gpu-2'})
        target_inputs = layout.inputs(root)
        target_inputs.mkdir(parents=True)
        shutil.copyfile(public_path, target_inputs / 'public.jsonl')
        shutil.copyfile(private_path, target_inputs / 'private.jsonl')
        plan = requests.prepare(root, evaluation, public, selection)
        if plan['models'][0]['requests'] != 34560 or plan['models'][0]['experiment1'] != 4320 or plan['models'][0]['experiment2'] != 30240:
            raise ValueError('REQUEST_MATRIX_MISMATCH')
        plan.update(transport='LOCAL_VLLM_CONTINUOUS_BATCHING', incremental_api_charge_usd=0,
                    infrastructure_cost='UNKNOWN', remote_owner='[vllm] gpu-2',
                    prompt_definition='CURRENT_SOURCE_AT_HANDOFF_NOT_20260928_LUNA_FROZEN_PROMPT')
        plan['models'][0]['billed_estimate'] = 'LOCAL_GPU_NO_EXTERNAL_API_CHARGE_INFRASTRUCTURE_UNKNOWN'
        store.write(layout.plan(root), plan)
        runtime = {
            'tensor_parallel_size': 4, 'dtype': 'bfloat16', 'max_num_seqs': 32,
            'max_num_batched_tokens': 8192, 'gpu_memory_utilization': memory,
            'max_model_len': 12288, 'max_output_tokens': 8192,
            'prefix_caching': False, 'chunked_prefill': True, 'cuda_graphs': True,
            'client_concurrency': concurrency,
            'sampling': {'off': {'temperature': 0.7, 'top_p': 0.8},
                         'on': {'temperature': 0.6, 'top_p': 0.95}},
            'top_k': 20, 'min_p': 0, 'seed': 20260929,
            'status': 'PENDING_TOKEN_LENGTH_AND_GPU_2_PREFLIGHT',
        }
        store.write(root / 'a100-runtime.json', runtime)
        definition = layout.definition(root)
        for name, path in prompt_sources.items():
            if store.file_hash(definition / name) != store.file_hash(path):
                raise ValueError('CURRENT_PROMPT_FREEZE_MISMATCH:' + name)
        manifest_path = layout.requests(root, key)
        frozen = {
            'source_run': str(source.relative_to(store.PROJECT)),
            'source_public_sha256': store.file_hash(public_path),
            'source_private_sha256': store.file_hash(private_path),
            'original_external_knowledge_used': dict(labels),
            'selection': {k: v for k, v in selection.items() if k != 'items'},
            'prompt_source_sha256': {name: store.file_hash(path) for name, path in prompt_sources.items()},
            'model_request_count': 34560,
            'model_calls_made_by_preparation': 0,
        }
        store.write(root / 'source-provenance.json', frozen)
        template = store.PROJECT / 'src/finarch/experiments/templates/a100-1080-handoff-readme.md'
        (root / 'README.md').write_text(Template(template.read_text()).substitute(
            run_id=root.name, model=model['model'], model_key=key, source_run=source.name))
        transfer_files = [
            'config.json', 'README.md', 'a100-runtime.json', 'source-provenance.json',
            str((target_inputs / 'public.jsonl').relative_to(root)),
            str(layout.plan(root).relative_to(root)),
            *(str((definition / name).relative_to(root)) for name in prompt_sources),
            str(manifest_path.relative_to(root)),
        ]
        store.write(root / 'transfer-manifest.json',
                    {name: store.file_hash(root / name) for name in transfer_files})
        store.write(root / 'manifest.json', {str(p.relative_to(root)): store.file_hash(p)
                                           for p in root.rglob('*') if p.is_file()})
        store.verify(root)
        recovered = order.selection_from_manifests(root, public=store.rows(target_inputs / 'public.jsonl'),
                                                    require_same_items=True)
        if recovered['originals'] != 1080 or recovered['variants'] != 7560:
            raise ValueError('PREPARED_SELECTION_MISMATCH')
        for name, expected in store.read(root / 'transfer-manifest.json').items():
            if store.file_hash(root / name) != expected:
                raise ValueError('TRANSFER_HASH_MISMATCH:' + name)
        store.write(root / 'state.json', {'status': 'TRANSFER_READY', 'evaluation': 'NOT_STARTED',
                                          'analysis': 'NOT_STARTED', 'model_calls': 0})
        store.event(root, 'TRANSFER_PACKAGE_PREPARED', source_run=source.name, model=model['model'],
                    requests=34560, originals=1080, variants=7560,
                    public_sha256=frozen['source_public_sha256'], prompt_sha256=frozen['prompt_source_sha256'],
                    private_transferred=False, model_calls=0)
        created.append(root)
    return created


if __name__ == '__main__':
    for path in prepare():
        print(path)
