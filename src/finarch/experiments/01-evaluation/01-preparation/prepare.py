"""E01: resolve configuration, select inputs and freeze one independent run."""
from pathlib import Path

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
settings = __import__('finarch.experiments.90-operations.settings', fromlist=['*'])
layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
inputs = __import__('finarch.experiments.00-input.pipeline', fromlist=['*'])
requests = __import__('finarch.experiments.01-evaluation.02-request.prepare', fromlist=['*'])
policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])


def prepare(config_path, reserved_root=None, allocator=None):
    source_config, profile_path = settings.read_source(config_path)
    config, analysis_config = settings.load(source_config, profile_path=profile_path)
    config['cache_policy'] = policy.snapshot()
    if config['schedule'].get('concurrency', 1) < 1 or config['dataset']['count'] < 1:
        raise ValueError('POSITIVE_COUNT_AND_CONCURRENCY_REQUIRED')
    public, private, selection = inputs.prepare(config)
    previous = None
    if config.get('definition_source_run'):
        previous = (store.PROJECT / config['definition_source_run']).resolve()
        store.verify(previous)
    root = Path(reserved_root) if reserved_root is not None else (allocator or store.allocate)(
        store.PROJECT / config['output_root'], label=config.get('run_label'))
    if reserved_root is not None and any(root.iterdir()):
        raise ValueError('RESERVED_RUN_MUST_BE_EMPTY')
    store.command(root)
    store.event(root, 'PREPARE_STARTED')
    try:
        saved = {'layout_version': 2, 'evaluation': config, 'analysis': analysis_config} if 'evaluation' in source_config else config
        store.write(root / 'config.json', saved)
        store.event(root, 'INPUT_SELECTION', **{k:v for k,v in selection.items() if k != 'items'})
        store.write_rows(layout.inputs(root) / 'public.jsonl', public)
        store.write_rows(layout.inputs(root) / 'private.jsonl', private)
        if selection.get('generated_format'):
            store.write(layout.inputs(root) / 'selection.json', selection)
        plan = requests.prepare(root, config, public, selection, previous)
        tracked = [p for p in root.rglob('*') if p.is_file() and p.name not in ('events.jsonl', 'pipeline.log')]
        store.write(root / 'manifest.json', {str(p.relative_to(root)):store.file_hash(p) for p in tracked})
        store.write(root / 'state.json', {'status':'PREPARED','models':{m['key']:{'status':'PENDING'} for m in config['models']}})
        reporting.build(root)
        store.event(root, 'PREPARED', originals=selection['originals'], variants=selection['variants'], plan=plan)
        return root
    except Exception as error:
        store.event(root, 'PREPARE_FAILED', error_type=type(error).__name__, error=str(error))
        store.write(root / 'failure.json', {'status':'PREPARE_FAILED','error':str(error)})
        raise
