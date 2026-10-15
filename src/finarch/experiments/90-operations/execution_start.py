"""Announce the actual configured work before stage execution or model calls."""
from pathlib import Path

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
configuration = __import__('finarch.experiments.02-analysis.configuration', fromlist=['*'])
scheduler = __import__('finarch.experiments.02-analysis.scheduler', fromlist=['*'])


def announce(root, stage, task, *, processor, requests):
    root = Path(root).resolve()
    config = configuration.read(root)
    model = config['backends'][config['backend']]
    schedule = scheduler.policy(root, config)
    value = {'run': root.name, 'analysis_tag': store.read(root / 'config.json').get('analysis_tag'),
             'stage': stage, 'task': task, 'processor': processor, 'backend': config['backend'],
             'model': model['model'], 'reasoning_effort': model['reasoning_effort'],
             'requests': requests, 'concurrency': schedule['concurrency'],
             'adaptive_enabled': schedule['adaptive']['enabled'],
             'evaluation_source': store.read(root / 'config.json').get('evaluation_reuse', {}).get('source_run', root.name)}
    print(f'[{store.now()}] TASK_START {store.encoded(value).decode()}', flush=True)
    store.event(root, 'TASK_START', **value)
    return value
