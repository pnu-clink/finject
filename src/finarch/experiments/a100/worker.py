"""Canonical E03 worker using the same frozen payload code on PC and A100.

The GPU owner supplies an already configured local vLLM endpoint. This worker
never starts servers, retries unclear requests, or performs local Analysis.
"""
import concurrent.futures
import importlib
import json
from pathlib import Path
import time
import urllib.request
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator
from .sync_gate import verify
from .sync_protocol import sha
from .sync_agent import write
from .wire import body


def read(path):
    return json.loads(Path(path).read_text())


def cache(endpoint):
    with urllib.request.urlopen(endpoint + '/metrics', timeout=10) as response:
        text = response.read().decode()
    lines = text.splitlines()
    config = [line for line in lines if line.startswith('vllm:cache_config_info')]
    if not config or any('enable_prefix_caching="False"' not in line for line in config):
        raise ValueError('CACHE_DISABLED_NOT_VERIFIED')
    hits = {}
    for name in ('vllm:prefix_cache_hits_total', 'vllm:external_prefix_cache_hits_total'):
        values = [float(line.rsplit(' ', 1)[1]) for line in lines if line.startswith(name + '{') or line.startswith(name + ' ')]
        hits[name] = sum(values) if values else None
        if hits[name] != 0:
            raise ValueError('CACHE_HITS_NOT_VERIFIED_ZERO:' + name)
    return {'enabled': False, 'hits': hits, 'endpoint': endpoint,
            'resolved_config': config, 'per_request_cached_tokens': None}


def call(base, request, runtime, endpoint):
    folder = base / 'remote-results' / request['trial_id']
    folder.mkdir(parents=True, exist_ok=False)
    payload = body(request, runtime)
    write(folder / 'provider-request.json', payload)
    write(folder / 'delivery.json', {'status': 'SENDING', 'at': time.time()})
    start = time.monotonic()
    try:
        wire = urllib.request.Request(endpoint + '/v1/chat/completions',
              data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(wire, timeout=1800) as response:
            raw = response.read()
        (folder / 'raw-response.json').write_bytes(raw)
        obj = json.loads(raw)
        try:
            parsed = json.loads(obj['choices'][0]['message']['content'])
            errors = [e.message for e in Draft202012Validator(request['response_schema']).iter_errors(parsed)]
        except (ValueError, TypeError, KeyError, IndexError) as error:
            errors = [str(error)]
        write(folder / 'format-check.json', {'status': 'INVALID_RESPONSE' if errors else 'VALID', 'errors': errors})
        write(folder / 'delivery.json', {'status': 'RECEIVED', 'elapsed_seconds': time.monotonic() - start,
              'usage': obj.get('usage'), 'finish_reason': obj['choices'][0]['finish_reason'],
              'response_sha256': sha(folder / 'raw-response.json')})
        return 'RECEIVED'
    except Exception as error:
        write(folder / 'delivery.json', {'status': 'UNKNOWN_DELIVERY', 'elapsed_seconds': time.monotonic() - start,
              'error': str(error), 'error_type': type(error).__name__})
        return 'UNKNOWN_DELIVERY'


def run(root, endpoints, model_path, authorization):
    root = Path(root).resolve()
    gate = verify(root)
    if not authorization or not authorization.strip():
        raise ValueError('EXPLICIT_EXECUTION_AUTHORIZATION_REQUIRED')
    pc_state = read(root / 'pc-state.json')
    if pc_state.get('evaluation', {}).get('status') == 'EVALUATION_COMPLETE' or pc_state.get('status') == 'FINISHED':
        raise ValueError('COMPLETED_RUN_CANNOT_BE_RESUBMITTED')
    controls = pc_state.get('execution_control', {})
    if controls.get('evaluation', {}).get('paused'):
        raise ValueError('EVALUATION_PAUSED_BY_USER')
    config = read(root / 'config.json')['evaluation']
    model, = config['models']
    if model['transport'] != 'vllm_local':
        raise ValueError('VLLM_LOCAL_RUN_REQUIRED')
    snapshot = Path(model_path).resolve()
    if not model.get('revision') or snapshot.name != model['revision'] or not (snapshot / 'config.json').is_file():
        raise ValueError('PINNED_MODEL_SNAPSHOT_REQUIRED')
    if not endpoints or any(urlsplit(endpoint).scheme != 'http' or urlsplit(endpoint).hostname != '127.0.0.1'
                           or not urlsplit(endpoint).port or urlsplit(endpoint).username
                           or urlsplit(endpoint).path or urlsplit(endpoint).query for endpoint in endpoints):
        raise ValueError('LOCAL_GPU_ENDPOINTS_REQUIRED')
    runtime = read(root / '01_evaluation/01_preparation/a100-runtime.json')
    requests = [json.loads(line) for line in (root / '01_evaluation/02_request' / model['key'] / 'manifest.jsonl').read_text().splitlines()]
    identities = {row['trial_id'] for row in requests}
    if len(identities) != len(requests):
        raise ValueError('DUPLICATE_REQUEST_ID')
    for row in requests:
        if row['model'] != model['model'] or row['prompt_condition'] not in ('guided', 'unguided') or row['reasoning'] not in ('off', 'on'):
            raise ValueError('FROZEN_CONDITION_MISMATCH')
        body(row, runtime)
        Draft202012Validator.check_schema(row['response_schema'])
    base = root / '01_evaluation/03_execution' / model['key']
    base.mkdir(parents=True, exist_ok=True)
    store = importlib.import_module('finarch.experiments.90-operations.storage')
    with store.locked(base / 'worker.lock'):
        if (base / 'remote-results').exists() and any((base / 'remote-results').iterdir()):
            raise ValueError('EXISTING_ATTEMPTS_REQUIRE_REVIEW_NO_AUTO_RETRY')
        for endpoint in endpoints:
            with urllib.request.urlopen(endpoint + '/v1/models', timeout=10) as response:
                models = json.load(response)['data']
            if not any(item.get('id') == runtime.get('served_model', model['model'])
                       and Path(item.get('root', '')).resolve() == snapshot for item in models):
                raise ValueError('SERVING_ALIAS_OR_MODEL_SNAPSHOT_MISMATCH')
        write(base / 'runtime-provenance.json', {**gate, 'authorization': authorization, 'runtime': runtime,
              'endpoints': endpoints, 'model_path': str(snapshot), 'model_revision': model['revision'],
              'entrypoint': 'finarch.experiments.pipeline a100-evaluation'})
        initial = [cache(endpoint) for endpoint in endpoints]
        write(base / 'cache-initial.json', {'engines': initial, 'enabled': False})
        pending_rows = iter(enumerate(requests))
        concurrency = int(runtime.get('profile', {}).get('concurrency', config['schedule']['concurrency']))
        completed, unknown = 0, 0
        started = time.time()
        def progress(status):
            write(base / 'remote-state.json', {'status': status, 'total': len(requests), 'completed': completed,
                  'unknown_delivery': unknown, 'started_at': started, 'elapsed_seconds': time.time() - started,
                  'remaining_unstarted': len(requests) - completed - unknown - len(futures),
                  'running': len(futures), 'code_release': gate['code_release']})
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = set()
            for _ in range(min(concurrency, len(requests))):
                index, request = next(pending_rows)
                futures.add(pool.submit(call, base, request, runtime, endpoints[index % len(endpoints)]))
            progress('RUNNING')
            while futures:
                done, futures = concurrent.futures.wait(futures, timeout=5,
                                   return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    if future.result() == 'RECEIVED':
                        completed += 1
                    else:
                        unknown += 1
                paused = read(root / 'pc-state.json').get('execution_control', {}).get('evaluation', {}).get('paused')
                if not unknown and not paused:
                    for _ in done:
                        pair = next(pending_rows, None)
                        if pair:
                            index, request = pair
                            futures.add(pool.submit(call, base, request, runtime, endpoints[index % len(endpoints)]))
                progress('NEEDS_REVIEW' if unknown else 'DRAINING' if paused else 'RUNNING')
        final = [cache(endpoint) for endpoint in endpoints]
        write(base / 'cache-final.json', {'engines': final, 'enabled': False})
        progress('EVALUATION_RECEIVED' if completed == len(requests) else 'NEEDS_REVIEW' if unknown else 'PAUSED_BY_USER')
        return read(base / 'remote-state.json')
