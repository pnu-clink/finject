"""Durable Gemini Batch API jobs; never resubmit an uncertain submission."""
run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
import json
import re
import time
import urllib.error
import urllib.request

from jsonschema import Draft202012Validator

cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
response_errors = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['response_errors']).response_errors
encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text

BASE = 'https://generativelanguage.googleapis.com/v1beta/'


def http(model, suffix, body=None, timeout=120):
    if body is not None:
        cache_policy.require_control(model)
    key = providers.credential(model)
    request = urllib.request.Request(BASE + suffix, data=encoded(body) if body is not None else None,
        headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode().replace(key, '[REDACTED]'))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode().replace(key, '[REDACTED]'))


def make_jobs(root, model, max_bytes=15_000_000):
    base = run_layout.execution(root, model['key'])
    requests = rows(run_layout.requests(root, model['key']))
    pending = []
    for request in requests:
        previous = call_layout.attempt_dirs(base, request)
        result = read(previous[-1] / 'result.json', {}) if previous else {}
        if result.get('status') == 'VALID':
            continue
        if previous and (not result or result.get('status') == 'UNKNOWN_DELIVERY'):
            raise ValueError('RECONCILE_UNKNOWN_DELIVERY_BEFORE_BATCH')
        if result.get('status') in ('INVALID_RESPONSE', 'OUTPUT_TRUNCATED'):
            continue
        pending.append({'request': request, 'attempt': len(previous) + 1})
    chunks, chunk, size = [], [], 0
    for trial in pending:
        wire = {'request': {'model': 'models/' + model['model'], **providers.gemini_body(trial['request'])},
                'metadata': {'key': trial['request']['trial_id']}}
        trial['wire'] = wire
        width = len(encoded(wire)) + 2
        if width > max_bytes:
            raise ValueError('SINGLE_BATCH_REQUEST_TOO_LARGE')
        if chunk and size + width > max_bytes:
            chunks.append(chunk)
            chunk, size = [], 0
        chunk.append(trial)
        size += width
    if chunk:
        chunks.append(chunk)
    for i, chunk in enumerate(chunks, 1):
        folder = run_layout.batches(root, model['key']) / f'batch-{i:03d}'
        folder.mkdir(parents=True, exist_ok=True)
        body = {'batch': {'displayName': f'{root.name}-{model["key"]}-{i:03d}',
                         'inputConfig': {'requests': {'requests': [t['wire'] for t in chunk]}}}}
        write(folder / 'request.json', body)
        write(folder / 'trials.json', [{k: v for k, v in t.items() if k != 'wire'} for t in chunk])
        write(folder / 'job.json', {'status': 'PREPARED', 'requests': len(chunk), 'created_at': now()})
    return [run_layout.batches(root, model['key']) / f'batch-{i:03d}' for i in range(1, len(chunks) + 1)]


def unwrap_responses(operation):
    output = operation.get('response', {})
    if 'output' in output:
        output = output['output']
    if not output:
        output = operation.get('metadata', {}).get('output', {})
    inline = output.get('inlinedResponses')
    if isinstance(inline, dict):
        inline = inline.get('inlinedResponses')
    if isinstance(inline, list):
        return inline
    raise ValueError('BATCH_INLINE_OUTPUT_MISSING')


def collect(root, model, folder, operation):
    raw_rows = unwrap_responses(operation)
    trials = {t['request']['trial_id']: t for t in read(folder / 'trials.json')}
    keys = [r.get('metadata', {}).get('key') for r in raw_rows]
    if len(keys) != len(set(keys)) or set(keys) != set(trials):
        raise ValueError('BATCH_RESULT_ID_SET_MISMATCH')
    for row in raw_rows:
        key = row['metadata']['key']
        trial = trials[key]
        destination = call_layout.attempt_path(run_layout.execution(root, model['key']), trial['request'], trial['attempt'])
        write(destination / 'request.json', trial['request'])
        write(destination / 'raw-response.json', row)
        raw = row.get('response', {})
        result = {'status': 'BATCH_ITEM_ERROR' if row.get('error') else 'RECEIVED',
                  'usage': raw.get('usageMetadata'), 'model_version': raw.get('modelVersion'),
                  'batch_name': operation['name'], 'transport': 'gemini_batch', 'billing_mode': 'PAID_BATCH',
                  'price_per_million': dict(model['reference_price_per_million']),
                  'error': row.get('error')}
        if result['status'] == 'RECEIVED':
            candidate = (raw.get('candidates') or [{}])[0]
            text = ''.join(p.get('text', '') for p in candidate.get('content', {}).get('parts', []) if not p.get('thought'))
            result['finish_reason'] = candidate.get('finishReason')
            try:
                parsed = json.loads(text)
                errors = response_errors(parsed, trial['request'])
                result['schema_errors'] = errors
                result.update(status='INVALID_RESPONSE' if errors else 'VALID', response=parsed)
            except Exception as error:
                result.update(status='INVALID_RESPONSE', validation_error_type=type(error).__name__)
            if result['finish_reason'] == 'MAX_TOKENS':
                result['status'] = 'OUTPUT_TRUNCATED'
        if trial['request'].get('cache_policy', {}).get('mode') == 'forbidden' and (not row.get('error') or result.get('usage') is not None):
            cache_policy.enforce_result(model, result)
        previous_result = read(destination / 'result.json')
        if previous_result and previous_result.get('status') != 'BATCH_PENDING' and previous_result != result:
            if not (destination / 'result-before-validation-v2.json').exists():
                write(destination / 'result-before-validation-v2.json', previous_result)
        write(destination / 'result.json', result)
    return len(raw_rows)


def process(root, model, state, report, poll_seconds=30, *, _submit_only=False, _collect_only=False):
    if state['models'][model['key']].get('status') in ('CACHE_POLICY_VIOLATION', 'CACHE_USAGE_UNVERIFIED'):
        return
    try:
        preflight = cache_policy.require_control(model)
        write(run_layout.execution(root, model['key']) / 'cache-preflight.json', preflight)
        state['models'][model['key']]['preflight'] = preflight
    except cache_policy.CachePolicyError as error:
        state['models'][model['key']].update(status='CACHE_POLICY_BLOCKED', reason=str(error), preflight=error.check)
        write(run_layout.execution(root, model['key']) / 'cache-preflight.json', error.check)
        write(root / 'state.json', state)
        event(root, 'CACHE_POLICY_BLOCKED', model=model['key'], reason=str(error), new_model_calls=0)
        report(root)
        return
    base = run_layout.batches(root, model['key'])
    existing = sorted(base.glob('batch-*/job.json'))
    if _collect_only:
        folders = [p.parent for p in existing if read(p).get('name')]
        if not folders:
            raise ValueError('NO_SUBMITTED_GEMINI_BATCHES')
    else:
        folders = [p.parent for p in existing] if existing else make_jobs(root, model)
    model_state = state['models'][model['key']]
    previous_limits = {k: model_state.pop(k) for k in ('requests_per_minute', 'requests_per_day') if k in model_state}
    if previous_limits:
        model_state['previous_free_key_limits'] = previous_limits
    model_state.pop('reason', None)
    model_state.update(status='BATCH_RUNNING', active_transport='gemini_batch',
                       credential_variable=model['key_variable'], free_quota_applies_to_paid_key=False)
    if model.get('submit_all_before_poll') and not _submit_only and not _collect_only:
        # Submit independent bounded jobs sequentially, then collect their existing IDs.
        process(root, model, state, report, poll_seconds, _submit_only=True)
        if model_state.get('status') != 'BATCH_PENDING':
            return
    for folder in folders:
        job = read(folder / 'job.json')
        if job['status'] == 'COLLECTED':
            continue
        if job['status'] in ('SUBMITTING', 'UNKNOWN_SUBMISSION'):
            raise ValueError('BATCH_SUBMISSION_RECONCILIATION_REQUIRED')
        if job['status'] == 'PREPARED':
            if _collect_only:
                raise ValueError('COLLECTION_ONLY_MUST_NOT_SUBMIT')
            manifest = {t['trial_id']: t for t in rows(run_layout.requests(root, model['key']))}
            trials = read(folder / 'trials.json')
            expected_wire = []
            for trial in trials:
                request = trial['request']
                if manifest.get(request['trial_id']) != request:
                    raise ValueError('BATCH_TRIAL_DIFFERS_FROM_FROZEN_MANIFEST')
                expected_wire.append({'request': {'model': 'models/' + model['model'], **providers.gemini_body(request)},
                                      'metadata': {'key': request['trial_id']}})
            if read(folder / 'request.json')['batch']['inputConfig']['requests']['requests'] != expected_wire:
                raise ValueError('BATCH_WIRE_REQUEST_CHANGED')
            job.update(status='SUBMITTING', submitted_at=now())
            write(folder / 'job.json', job)
            model_state['status'] = 'BATCH_SUBMITTING'
            write(root / 'state.json', state)
            if not _submit_only:
                report(root)
            event(root, 'BATCH_SUBMIT_STARTED', model=model['key'], requests=job['requests'])
            try:
                status, operation = http(model, 'models/' + model['model'] + ':batchGenerateContent', read(folder / 'request.json'))
            except Exception as error:
                job.update(status='UNKNOWN_SUBMISSION', error_type=type(error).__name__)
                write(folder / 'job.json', job)
                raise
            write(folder / 'submit-response.json', operation)
            if status != 200:
                job.update(status='REJECTED', http_status=status, error=operation)
                write(folder / 'job.json', job)
                model_state.update(status='BATCH_REJECTED', reason=operation)
                write(root / 'state.json', state)
                report(root)
                return
            if not re.fullmatch(r'batches/[A-Za-z0-9_-]+', operation.get('name', '')):
                raise ValueError('UNEXPECTED_BATCH_RESOURCE_NAME')
            job.update(status='SUBMITTED', name=operation['name'])
            write(folder / 'job.json', job)
            for trial in read(folder / 'trials.json'):
                destination = call_layout.attempt_path(run_layout.execution(root, model['key']), trial['request'], trial['attempt'])
                write(destination / 'request.json', trial['request'])
                write(destination / 'started.json', {'at': now(), 'batch_name': job['name'], 'transport': 'gemini_batch'})
                write(destination / 'result.json', {'status': 'BATCH_PENDING', 'usage': None, 'batch_name': job['name'], 'billing_mode': 'PAID_BATCH'})
            event(root, 'BATCH_SUBMITTED', model=model['key'], name=job['name'], requests=job['requests'])
        if job['status'] == 'REJECTED':
            model_state['status'] = 'BATCH_REJECTED'
            return
        if job['status'] == 'FAILED':
            model_state.update(status='BATCH_FAILED', reason=job.get('error'))
            return
        if _submit_only:
            model_state.update(status='BATCH_SUBMITTING',
                submitted_batches=sum(bool(read(p / 'job.json').get('name')) for p in folders),
                planned_batches=len(folders))
            write(root / 'state.json', state)
            continue
        while True:
            status, operation = http(model, job['name'])
            write(folder / 'latest-provider-state.json', operation)
            if status != 200:
                model_state.update(status='BATCH_POLL_ERROR', reason=operation)
                write(root / 'state.json', state)
                report(root)
                return
            remote_state = operation.get('metadata', {}).get('state', 'PENDING')
            model_state.update(status='BATCH_RUNNING', batch_name=job['name'], provider_batch_state=remote_state,
                               batch_stats=operation.get('metadata', {}).get('batchStats'))
            write(root / 'state.json', state)
            event(root, 'GEMINI_BATCH_PROGRESS', model=model['key'], batch_name=job['name'],
                  provider_status=remote_state, batch_stats=model_state['batch_stats'])
            report(root)
            if operation.get('done'):
                if operation.get('error'):
                    job.update(status='FAILED', error=operation['error'])
                    model_state.update(status='BATCH_FAILED', reason=operation['error'])
                    write(folder / 'job.json', job)
                    return
                write(folder / 'raw-results.json', operation)
                count = collect(root, model, folder, operation)
                job.update(status='COLLECTED', collected_at=now(), results=count)
                write(folder / 'job.json', job)
                event(root, 'BATCH_COLLECTED', model=model['key'], name=job['name'], results=count)
                rejected = [read(call_layout.attempt_path(run_layout.execution(root, model['key']), t['request'], t['attempt']) / 'result.json')
                            for t in read(folder / 'trials.json')]
                rejected = [r for r in rejected if r['status'] in cache_policy.STOP_STATUSES]
                if rejected:
                    model_state.update(status=rejected[0]['status'], reason=rejected[0]['error'])
                    write(root / 'state.json', state)
                    report(root)
                    return
                break
            time.sleep(min(poll_seconds, 60))
    model_state['status'] = 'BATCH_PENDING' if _submit_only else 'FINISHED'
    write(root / 'state.json', state)


def collect_submitted(root, model, state, report):
    """Collect accepted IDs after rejection; preserve the unsubmitted failure status."""
    model_state = state['models'][model['key']]
    previous = {k: model_state[k] for k in ('status', 'reason') if k in model_state}
    root_status = state['status']
    model_state.update(submission_status=previous.get('status'),
                       submission_reason=previous.get('reason'),
                       submitted_collection_status='RUNNING')
    event(root, 'GEMINI_SUBMITTED_COLLECTION_STARTED', model=model['key'], new_model_calls=0)
    try:
        process(root, model, state, report, _collect_only=True)
        model_state['submitted_collection_status'] = model_state['status']
    except BaseException:
        model_state['submitted_collection_status'] = 'NEEDS_REVIEW'
        raise
    finally:
        model_state.update(previous)
        state['status'] = root_status
        write(root / 'state.json', state)
        report(root)
