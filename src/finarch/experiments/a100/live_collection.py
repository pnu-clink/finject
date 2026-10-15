"""Publish newly synchronized E03 responses through the existing PC E04 code."""
import json
from pathlib import Path
import shutil
from .collect import mod, response_result
from .wire import body


def cache_verified(metadata, phase):
    value = metadata.get('cache-' + phase + '.json', {})
    engines = value.get('engines', [])
    if not engines or any(engine.get('enabled') is not False or not engine.get('hits')
                          or any(hit != 0 for hit in engine['hits'].values()) for engine in engines):
        raise ValueError('LIVE_CACHE_AUDIT_NOT_VERIFIED:' + phase)
    return value


def collect(root, snapshot):
    root = Path(root)
    store, layout, calls = (mod(name) for name in (
        '90-operations.storage', '90-operations.run_layout', '01-evaluation.03-execution.call_layout'))
    with store.locked(root / 'pipeline.lock'):
        store.verify(root)
        model, = store.configuration(root)['models']
        base = layout.execution(root, model['key'])
        runtime = store.read(layout.preparation(root) / 'a100-runtime.json')
        initial = cache_verified(snapshot['metadata'], 'initial')
        requests = store.rows(layout.requests(root, model['key']))
        changed = 0
        for request in requests:
            source = base / 'remote-results' / request['trial_id']
            delivery = store.read(source / 'delivery.json')
            if not delivery:
                continue
            folder = calls.attempt_path(base, request, 1)
            if (folder / 'result.json').exists():
                continue
            if store.read(source / 'provider-request.json') != body(request, runtime):
                raise ValueError('LIVE_PAYLOAD_DIFFERS_FROM_FROZEN_INPUT:' + request['trial_id'])
            if delivery['status'] == 'RECEIVED':
                if store.file_hash(source / 'raw-response.json') != delivery['response_sha256']:
                    raise ValueError('LIVE_RAW_RESPONSE_HASH_MISMATCH')
                result = response_result(request, store.read(source / 'raw-response.json'), delivery,
                         {'status': 'ENGINE_PREFIX_CACHE_DISABLED_ZERO_HITS_USAGE_UNKNOWN', 'initial': initial,
                          'per_request_cached_tokens': None})
            else:
                result = {'status': 'UNKNOWN_DELIVERY', 'usage': None, 'elapsed_seconds': delivery.get('elapsed_seconds'),
                          'error': delivery.get('error'), 'delivery_status': delivery['status']}
            folder.mkdir(parents=True, exist_ok=True)
            for name in ('provider-request.json', 'raw-response.json', 'delivery.json'):
                if (source / name).exists():
                    shutil.copyfile(source / name, folder / name)
            store.write(folder / 'request.json', request)
            store.write(folder / 'result.json', result)
            changed += 1
        remote = snapshot['state'] or {}
        complete = remote.get('status') == 'EVALUATION_RECEIVED' and remote.get('completed') == len(requests)
        if complete:
            cache_verified(snapshot['metadata'], 'final')
        current = store.read(root / 'state.json')
        if changed or current.get('evaluation', {}).get('responses') != remote.get('completed'):
            status = 'FINISHED' if complete else 'RUNNING'
            mod('01-evaluation.04-validation.reporting').build(root, final_status=status)
            mod('01-evaluation.04-validation.numeric_validation').build(root)
            current = store.read(root / 'state.json')
            # Preserve controls, frozen analysis and unrelated run fields.
            current.update(status=status, evaluation={'status': 'EVALUATION_COMPLETE' if complete else 'RUNNING',
                          'responses': remote.get('completed'), 'remote_status': remote.get('status')})
            current.setdefault('models', {})[model['key']] = {'status': status}
            current['full_pipeline'] = {**current.get('full_pipeline', {}),
                 'status': 'EVALUATION_COMPLETE' if complete else 'NEEDS_REVIEW' if remote.get('unknown_delivery') else 'RUNNING',
                 'stage': 'WAIT_ANALYSIS' if complete else 'EVALUATION',
                 'analysis_execution': 'NOT_STARTED_BY_SYNC', 'updated_at': store.now(), 'new_model_calls': 0}
            store.write(root / 'state.json', current)
            store.event(root, 'A100_INCREMENTAL_E04_PUBLISHED', new_records=changed, remote_status=remote.get('status'),
                        code_release=remote.get('code_release'), new_model_calls=0)
        store.verify(root)
        return {'new_records': changed, 'evaluation_complete': complete, 'new_model_calls': 0}
