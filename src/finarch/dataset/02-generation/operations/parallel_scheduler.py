"""Bounded case queues. Aggregate callbacks run under one coordinator lock."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
append = __import__('finarch.shared.run_logging.run_logs', fromlist=['append']).append
from datetime import datetime

def record_queue(path, value):
    write(path, value)
    append(path.with_suffix(".jsonl"), {"timestamp": datetime.now().astimezone().isoformat(), **value})



def limit(config, stage):
    settings = read(Path(config)) if not isinstance(config, dict) else config
    maximum = {'preparation': 10, 'generation': 2, 'feedback': 3}[stage]
    value = settings.get('parallelism', {}).get(stage, maximum)
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError('INVALID_PARALLELISM_' + stage.upper())
    return value


def completed(items, worker, workers):
    """Yield each result to the caller; never write shared summaries in workers."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(copy_context().run, worker, item): item for item in items}
        for future in as_completed(futures):
            yield futures[future], future.result()


def preparation_results(bundle, inputs, names, config, run_case):
    bundle = Path(bundle)
    workers = limit(config, 'preparation')
    results = {}
    path = bundle / '01-preparation/queue.json'
    record_queue(path, {'queue': 'preparation', 'limit': workers, 'planned': len(names), 'completed': 0, 'status': 'RUNNING'})
    try:
        for name, result in completed(names, lambda name: run_case(inputs, name, bundle / '01-preparation' / name, config), workers):
            results[name] = result
            write(bundle / '01-preparation/summary.json', {'planned': len(names), 'processed': len(results), 'results': [results[n] for n in names if n in results]})
            record_queue(path, {'queue': 'preparation', 'limit': workers, 'planned': len(names), 'completed': len(results), 'status': 'RUNNING'})
            yield name, result
    finally:
        record_queue(path, {'queue': 'preparation', 'limit': workers, 'planned': len(names), 'completed': len(results), 'status': 'COMPLETED' if len(results) == len(names) else 'ERROR'})
