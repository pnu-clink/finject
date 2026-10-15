"""Validate recovered raw GPU responses before the existing local Analysis pipeline."""
import argparse
from collections import Counter
import importlib
import json
from pathlib import Path
import shutil
from .wire import body


def require_complete(state, planned):
    received = state.get('completed', state.get('attempt_records'))
    if (state.get('status') != 'EVALUATION_RECEIVED' or received != planned
            or state.get('total', planned) != planned or state.get('remaining_unstarted', 0) != 0):
        raise ValueError('REMOTE_EVALUATION_INCOMPLETE')


def response_result(request, raw, delivery, cache_check):
    fmt = mod('01-evaluation.04-validation.answer_format')
    usage = raw.get('usage')
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int for k in ('prompt_tokens', 'completion_tokens')):
        raise ValueError('GPU_USAGE_MISSING_NOT_ZERO')
    finish = raw.get('choices', [{}])[0].get('finish_reason') or delivery.get('finish_reason')
    result = {'status': 'INVALID_RESPONSE', 'usage': {
        'input_tokens': usage['prompt_tokens'], 'output_tokens': usage['completion_tokens']},
        'provider_usage': usage, 'elapsed_seconds': delivery['elapsed_seconds'],
        'cache_check': cache_check, 'finish_reason': finish, 'billing_mode': 'LOCAL_GPU'}
    differences = {key: {'delivery': delivery.get(key), 'raw_response': value}
                   for key, value in (('usage', usage), ('finish_reason', finish))
                   if delivery.get(key) != value}
    if differences:
        result['delivery_metadata_discrepancies'] = differences
    reasoning = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
    if type(reasoning) is int:
        result['usage']['reasoning_output_tokens'] = reasoning
    try:
        parsed = json.loads(raw['choices'][0]['message']['content'])
        errors = fmt.response_errors(parsed, request)
        result.update(response=parsed, schema_errors=errors, status='INVALID_RESPONSE' if errors else 'VALID')
    except (ValueError, TypeError, KeyError, IndexError) as error:
        result['validation_error'] = str(error)
    if finish == 'length':
        result['status'] = 'OUTPUT_TRUNCATED'
    return result


def mod(name):
    return importlib.import_module('finarch.experiments.' + name)


def collect(root, *, repair_delivery_metadata=False, source_stage=None):
    root = Path(root).resolve()
    store, layout = mod('90-operations.storage'), mod('90-operations.run_layout')
    calls = mod('01-evaluation.03-execution.call_layout')
    store.verify(root)
    model, = store.configuration(root)['models']
    source_stage = Path(source_stage).resolve() if source_stage else None
    source = source_stage or root
    evidence = source / 'remote-evidence'
    state = store.read(evidence / 'state.json') if source_stage else store.read(root / 'remote-state.json')
    requests = store.rows(layout.requests(root, model['key']))
    require_complete(state, len(requests))
    expected = {r['trial_id'] for r in requests}
    if {p.name for p in (source / 'remote-results').iterdir()} != expected:
        raise ValueError('RECEIVED_TRIAL_SET_MISMATCH')
    statuses = Counter()
    recovered = evidence.exists()
    preparation = layout.preparation(root)
    runtime = store.read(preparation / 'a100-runtime.json') if source_stage else store.read(root / ('remote-evidence/a100-runtime.json' if recovered else 'a100-runtime.json'))
    cache_check = {'status': 'ENGINE_CACHE_DISABLED_USAGE_NOT_FULLY_REPORTED'}
    if source_stage:
        cache_check = store.read(preparation / 'cache-audit.json')
        if cache_check.get('status') != 'ENGINE_PREFIX_CACHE_DISABLED_ZERO_HITS_USAGE_UNKNOWN':
            raise ValueError('GPU_PREFIX_CACHE_AUDIT_NOT_VERIFIED')
    elif recovered:
        initial = store.read(root / 'remote-evidence/cache-initial.json')
        final = store.read(root / 'remote-evidence/cache-final.json')
        disabled = all(x.get('enabled') is False and x.get('hits')
                       and all(value == 0 for value in x['hits'].values()) for x in (initial, final))
        if not disabled:
            raise ValueError('GPU_PREFIX_CACHE_AUDIT_NOT_VERIFIED')
        cache_check = {'status': 'ENGINE_PREFIX_CACHE_DISABLED_ZERO_HITS_USAGE_UNKNOWN',
                       'engine_prefix_caching': False, 'initial_hits': initial['hits'],
                       'final_hits': final['hits'], 'per_request_cached_tokens': None}
    for request in requests:
        src = source / 'remote-results' / request['trial_id']
        delivery = store.read(src / 'delivery.json')
        if delivery['status'] != 'RECEIVED':
            raise ValueError('UNCONFIRMED_DELIVERY')
        if recovered and store.read(src / 'provider-request.json') != body(request, runtime):
            raise ValueError('PROVIDER_REQUEST_DIFFERS_FROM_FROZEN_INPUT:' + request['trial_id'])
        if delivery.get('response_sha256') and store.file_hash(src / 'raw-response.json') != delivery['response_sha256']:
            raise ValueError('RAW_RESPONSE_CHANGED:' + request['trial_id'])
        raw = store.read(src / 'raw-response.json')
        result = response_result(request, raw, delivery, cache_check)
        base = layout.execution(root, model['key'])
        folder = calls.attempt_path(base, request, 1)
        if (folder / 'result.json').exists():
            previous = store.read(folder / 'result.json')
            if previous != result:
                legacy = dict(result)
                legacy.pop('delivery_metadata_discrepancies', None)
                legacy['finish_reason'] = delivery.get('finish_reason')
                if result['status'] == 'OUTPUT_TRUNCATED' and delivery.get('finish_reason') != 'length':
                    legacy['status'] = 'INVALID_RESPONSE' if result.get('schema_errors') or 'response' not in result else 'VALID'
                if not repair_delivery_metadata or previous != legacy:
                    raise ValueError('IMPORTED_RESULT_CHANGED')
                backup = folder / 'result-before-delivery-metadata-repair.json'
                if backup.exists() and store.read(backup) != previous:
                    raise ValueError('METADATA_REPAIR_HISTORY_CHANGED')
                store.write(backup, previous)
                store.write(folder / 'result.json', result)
                store.event(root, 'A100_LOCAL_DELIVERY_METADATA_REPAIRED', trial_id=request['trial_id'],
                            previous_status=previous['status'], status=result['status'],
                            discrepancies=result['delivery_metadata_discrepancies'],
                            preserved_previous=str(backup.relative_to(root)), model_calls=0)
        else:
            folder.mkdir(parents=True, exist_ok=True)
            for name in ('provider-request.json', 'raw-response.json', 'delivery.json'):
                shutil.copyfile(src / name, folder / name)
            store.write(folder / 'request.json', request)
            store.write(folder / 'result.json', result)
        statuses[result['status']] += 1
        if sum(statuses.values()) % 5000 == 0:
            print(json.dumps({'imported': sum(statuses.values()), 'planned': len(requests), 'statuses': dict(statuses)}), flush=True)
    complete_state = {'status': 'FINISHED', 'models': {model['key']: {'status': 'FINISHED'}},
                      'evaluation': {'status': 'EVALUATION_COMPLETE', 'responses': len(requests), 'statuses': dict(statuses)},
                      'analysis': {'status': 'NOT_STARTED'}}
    store.write(root / 'state.json', {**complete_state, 'status': 'COLLECTING',
                'evaluation': {**complete_state['evaluation'], 'status': 'VALIDATING'}})
    mod('01-evaluation.04-validation.reporting').build(root, final_status='FINISHED')
    mod('01-evaluation.04-validation.numeric_validation').build(root)
    store.event(root, 'A100_RESULTS_IMPORTED', responses=len(requests), statuses=dict(statuses))
    if not recovered:
        template = (store.PROJECT / 'src/finarch/experiments/templates/a100-readme-template.md').read_text()
        store.write_text(root / 'README.md', template.format(model=model['model'], run=root.name))
    store.verify(root)
    store.write(root / 'state.json', complete_state)
    print(json.dumps(dict(statuses)))
    return complete_state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--repair-delivery-metadata', action='store_true')
    args = parser.parse_args()
    collect(args.run, repair_delivery_metadata=args.repair_delivery_metadata)


if __name__ == '__main__':
    main()
