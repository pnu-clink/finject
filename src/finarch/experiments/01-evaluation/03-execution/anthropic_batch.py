"""Native Claude Message Batches with a configured-condition pilot and durable results."""

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

storage = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
api = __import__('finarch.experiments.01-evaluation.03-execution.anthropic_api', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
answers = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['*'])

BASE = 'https://api.anthropic.com/v1/messages/batches'
MAX_BATCH_BYTES = 200_000_000  # Below the provider's 256 MB limit.
MAX_BATCH_REQUESTS = 5000


class BatchRejected(ValueError):
    """Provider explicitly rejected the create request; delivery is known absent."""


def headers(model):
    workspace = model.get('workspace_id')
    if not isinstance(workspace, str) or not workspace.startswith('wrkspc_'):
        raise ValueError('ANTHROPIC_WORKSPACE_ID_REQUIRED')
    return {'content-type': 'application/json', 'x-api-key': providers.credential(model),
            'anthropic-version': api.API_VERSION, 'anthropic-workspace-id': workspace}


def http(model, url, body=None):
    if not (url == BASE or url.startswith(BASE + '/')):
        raise ValueError('UNEXPECTED_ANTHROPIC_BATCH_URL')
    auth = headers(model)
    request = urllib.request.Request(url, data=storage.encoded(body) if body is not None else None,
                                     headers=auth)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        raw = error.read().decode('utf-8', errors='replace')
        raise BatchRejected(f'ANTHROPIC_BATCH_HTTP_{error.code}: {raw.replace(auth["x-api-key"], "[REDACTED]")[:4000]}') from None
    return json.loads(raw)


def download_results(model, batch_id, results_url, destination):
    expected = BASE + '/' + batch_id + '/results'
    if results_url != expected:
        raise ValueError('UNEXPECTED_ANTHROPIC_RESULTS_URL')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(expected, headers=headers(model))
    fd, temporary = tempfile.mkstemp(prefix='.results-', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as output, urllib.request.urlopen(request, timeout=300) as response:
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def ensure_no_cache_control(value):
    if isinstance(value, dict):
        if 'cache_control' in value or 'tools' in value:
            raise ValueError('ANTHROPIC_BATCH_CACHE_OR_TOOLS_NOT_ALLOWED')
        for child in value.values():
            ensure_no_cache_control(child)
    elif isinstance(value, list):
        for child in value:
            ensure_no_cache_control(child)


def wire_record(model, request):
    custom_id = request['trial_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', custom_id):
        raise ValueError('INVALID_ANTHROPIC_BATCH_CUSTOM_ID')
    body = api.body_for(model, request)
    if not body.get('output_config', {}).get('format', {}).get('schema'):
        raise ValueError('BATCH_RESPONSE_SCHEMA_REQUIRED')
    ensure_no_cache_control(body)
    return {'custom_id': custom_id, 'params': body}


def split_requests(model, requests):
    """Pilot each configured condition, then bounded chunks of the remaining IDs."""
    pilot = []
    modes = (tuple(mode for mode in ('off', 'on') if mode in model.get('reasoning_efforts', {}))
             if model['model'] == 'claude-haiku-5-5' else ('off', 'on'))
    if not modes:
        raise ValueError('ANTHROPIC_BATCH_REASONING_MODES_REQUIRED')
    for prompt in run_layout.PROMPT_FILES:
        for reasoning in modes:
            match = next((r for r in requests if r['experiment'] == 1 and
                          r['prompt_condition'] == prompt and r['reasoning'] == reasoning), None)
            if match is None:
                raise ValueError('CONFIGURED_CONDITION_BATCH_PILOT_REQUIRED')
            pilot.append(match)
    used = {r['trial_id'] for r in pilot}
    chunks, current, size = [pilot], [], 0
    for request in requests:
        if request['trial_id'] in used:
            continue
        length = len(storage.encoded(wire_record(model, request))) + 1
        if length > MAX_BATCH_BYTES:
            raise ValueError('SINGLE_ANTHROPIC_BATCH_REQUEST_TOO_LARGE')
        if current and (size + length > MAX_BATCH_BYTES or len(current) >= MAX_BATCH_REQUESTS):
            chunks.append(current)
            current, size = [], 0
        current.append(request)
        size += length
    if current:
        chunks.append(current)
    return chunks


def prepare_job(model, manifest, folder, requests):
    policy.require_control(model)
    manifest, folder = Path(manifest), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    job_path = folder / 'job.json'
    source_hash = storage.file_hash(manifest)
    ids = [r['trial_id'] for r in requests]
    if len(ids) != len(set(ids)) or not ids or len(ids) > MAX_BATCH_REQUESTS:
        raise ValueError('ANTHROPIC_BATCH_REQUEST_COUNT_OR_ID_INVALID')
    if job_path.exists():
        job = storage.read(job_path)
        if (job['manifest_sha256'] != source_hash or job['custom_ids'] != ids or
                storage.file_hash(folder / 'input.json') != job['input_sha256']):
            raise ValueError('FROZEN_ANTHROPIC_BATCH_INPUT_CHANGED')
        return job
    payload = {'requests': [wire_record(model, request) for request in requests]}
    data = storage.encoded(payload)
    if len(data) > MAX_BATCH_BYTES:
        raise ValueError('ANTHROPIC_BATCH_EXCEEDS_SAFE_SIZE')
    storage.write_text(folder / 'input.json', data.decode() + '\n')
    job = {'status': 'PREPARED', 'created_at': storage.now(), 'model': model['model'],
           'manifest_sha256': source_hash, 'input_sha256': storage.file_hash(folder / 'input.json'),
           'custom_ids': ids, 'requests': len(ids), 'batch_id': None,
           'token_cost_estimate_usd': None, 'billed_cost_usd': None}
    storage.write(job_path, job)
    return job


def submit(model, folder):
    folder = Path(folder)
    job = storage.read(folder / 'job.json')
    if job.get('batch_id'):
        return job
    if job['status'] in ('SUBMITTING', 'UNKNOWN_SUBMISSION'):
        raise ValueError('UNKNOWN_ANTHROPIC_BATCH_SUBMISSION_NOT_REPEATED')
    if job['status'] != 'PREPARED':
        raise ValueError('UNEXPECTED_ANTHROPIC_BATCH_JOB_STATUS')
    job.update(status='SUBMITTING', submitted_at=storage.now())
    storage.write(folder / 'job.json', job)
    try:
        response = http(model, BASE, storage.read(folder / 'input.json'))
    except BatchRejected as error:
        job.update(status='SUBMISSION_REJECTED', rejection=str(error))
        storage.write(folder / 'job.json', job)
        raise
    except Exception:
        job['status'] = 'UNKNOWN_SUBMISSION'
        storage.write(folder / 'job.json', job)
        raise
    if response.get('type') != 'message_batch' or not response.get('id'):
        job.update(status='UNKNOWN_SUBMISSION', provider=response)
        storage.write(folder / 'job.json', job)
        raise ValueError('ANTHROPIC_BATCH_CREATE_RESPONSE_UNEXPECTED')
    job.update(status='SUBMITTED', batch_id=response['id'], provider=response)
    storage.write(folder / 'job.json', job)
    return job


def poll(model, folder):
    folder = Path(folder)
    job = storage.read(folder / 'job.json')
    if job['status'] == 'COLLECTED':
        return job
    batch = http(model, BASE + '/' + job['batch_id'])
    if batch.get('id') != job['batch_id']:
        raise ValueError('ANTHROPIC_BATCH_ID_MISMATCH')
    job.update(provider=batch, checked_at=storage.now())
    storage.write(folder / 'job.json', job)
    if batch.get('processing_status') == 'ended' and not (folder / 'results.jsonl').exists():
        if not batch.get('results_url'):
            raise ValueError('ENDED_ANTHROPIC_BATCH_WITHOUT_RESULTS_URL')
        download_results(model, job['batch_id'], batch['results_url'], folder / 'results.jsonl')
    return job


def result_records(folder, ids):
    records = {}
    with (Path(folder) / 'results.jsonl').open() as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            custom_id = record.get('custom_id')
            if custom_id not in ids or custom_id in records:
                raise ValueError('ANTHROPIC_BATCH_RESULT_ID_MISMATCH')
            records[custom_id] = (record, line)
    return records


def interpret(model, request, record):
    outcome = record.get('result') or {}
    if outcome.get('type') != 'succeeded':
        return {'status': 'BATCH_REQUEST_ERROR', 'error': outcome, 'usage': None,
                'transport': 'anthropic_batch', 'billing_mode': 'PAID_ANTHROPIC_BATCH',
                'token_cost_estimate_usd': None, 'billed_cost_usd': None}
    message = outcome.get('message') or {}
    usage = message.get('usage')
    text = ''.join(part.get('text', '') for part in message.get('content', []) if part.get('type') == 'text')
    result = {'status': 'RECEIVED', 'usage': usage, 'response_id': message.get('id'),
              'model_version': message.get('model'), 'finish_reason': message.get('stop_reason'),
              'transport': 'anthropic_batch', 'billing_mode': 'PAID_ANTHROPIC_BATCH',
              'requested_model': model['model'], 'thinking_budget_requested': request.get('thinking_budget') if request['reasoning'] == 'on' else None,
              'price_per_million': model['reference_price_per_million'],
              'billed_cost_usd': None, 'elapsed_seconds': None,
              'timing_note': 'Batch does not return per-request latency.',
              'automatic_transport_retries': 0}
    if model['model'] == 'claude-haiku-5-5':
        result.update(reasoning_effort_requested=request['reasoning_effort'],
                      thinking_type_requested=request['thinking_type'])
    if message.get('model') != model['model']:
        result.update(status='PROVIDER_MODEL_MISMATCH', error='RESPONSE_MODEL_MISMATCH')
    elif message.get('stop_reason') == 'max_tokens':
        result.update(status='OUTPUT_TRUNCATED', raw_text=text)
    else:
        try:
            parsed = json.loads(text)
            errors = answers.response_errors(parsed, request)
            result.update(status='INVALID_RESPONSE' if errors else 'VALID', response=parsed,
                          schema_errors=errors)
        except (ValueError, TypeError, KeyError) as error:
            result.update(status='INVALID_RESPONSE', validation_error_type=type(error).__name__, raw_text=text)
    rates = model['reference_price_per_million']
    if usage and all(type(usage.get(k)) is int for k in ('input_tokens', 'output_tokens')):
        cost = (usage['input_tokens'] * rates['input'] + usage['output_tokens'] * rates['output']) / 1e6
        result['token_cost_estimate_usd'] = round(cost, 10)
        result['reported_equivalent_usd'] = round(cost, 10)
    else:
        result['token_cost_estimate_usd'] = None
    return policy.enforce_result(model, result)


def process_chunk(root, model, state, requests, folder, *, pilot=False):
    manifest = run_layout.requests(root, model['key'])
    prepare_job(model, manifest, folder, requests)
    before = storage.read(folder / 'job.json')
    job = submit(model, folder)
    if not before.get('batch_id'):
        storage.event(root, 'ANTHROPIC_BATCH_SUBMITTED', model=model['key'], batch_id=job['batch_id'], requests=len(requests))
    job = poll(model, folder)
    batch = job['provider']
    state['models'][model['key']].update(status='BATCH_PENDING', batch_id=job['batch_id'],
        provider_status=batch.get('processing_status'), request_counts=batch.get('request_counts'),
        last_updated=storage.now())
    if job['status'] == 'COLLECTED' or batch.get('processing_status') != 'ended':
        return job
    records = result_records(folder, {r['trial_id'] for r in requests})
    if len(records) != len(requests):
        raise ValueError('ANTHROPIC_BATCH_RESULT_COUNT_MISMATCH')
    base = run_layout.execution(root, model['key'])
    statuses, cost, missing_cost = [], 0.0, 0
    for request in requests:
        attempt = layout.attempt_path(base, request, 1)
        existing = storage.read(attempt / 'result.json')
        if existing:
            if existing.get('batch_id') != job['batch_id']:
                raise ValueError('ANTHROPIC_BATCH_ATTEMPT_OWNED_BY_OTHER_JOB')
            result = existing
        else:
            record, raw = records[request['trial_id']]
            storage.write(attempt / 'request.json', request)
            storage.write(attempt / 'provider-request.json', api.body_for(model, request))
            storage.write_text(attempt / 'raw-response.json', raw)
            result = interpret(model, request, record)
            result['batch_id'] = job['batch_id']
            storage.write(attempt / 'result.json', result)
        statuses.append(result['status'])
        if result.get('token_cost_estimate_usd') is None:
            missing_cost += 1
        else:
            cost += result['token_cost_estimate_usd']
        layout.publish(root, base, request, {})
    stop = next((s for s in statuses if s in policy.STOP_STATUSES), None)
    result_status = stop or ('BATCH_INCOMPLETE' if 'BATCH_REQUEST_ERROR' in statuses else
                             'PILOT_INVALID' if pilot and any(s != 'VALID' for s in statuses) else
                             'FINISHED')
    job.update(status='COLLECTED', result_status=result_status, collected_at=storage.now(),
               returned_records=len(records), token_cost_estimate_usd=round(cost, 10),
               requests_without_known_cost=missing_cost)
    storage.write(folder / 'job.json', job)
    storage.event(root, 'ANTHROPIC_BATCH_COLLECTED', model=model['key'], batch_id=job['batch_id'],
                  status=result_status, returned_records=len(records), requests_without_known_cost=missing_cost,
                  token_cost_estimate_usd=round(cost, 10))
    return job


def process(root, model, state):
    root = Path(root)
    base = run_layout.execution(root, model['key'])
    requests = storage.rows(run_layout.requests(root, model['key']))
    layout.check_manifest(base, requests)
    chunks = split_requests(model, requests)
    jobs = []
    for index, chunk in enumerate(chunks, 1):
        folder = run_layout.batches(root, model['key']) / f'batch-{index:03d}'
        job = process_chunk(root, model, state, chunk, folder, pilot=index == 1)
        jobs.append(job)
        if index == 1 and job.get('result_status') != 'FINISHED':
            break  # Provider shape, schema and cache counters must pass before full dispatch.
    statuses = [job.get('result_status', 'BATCH_PENDING') for job in jobs]
    stop = next((status for status in statuses if status in policy.STOP_STATUSES), None)
    status = stop or ('BATCH_INCOMPLETE' if 'BATCH_INCOMPLETE' in statuses else
                      'PILOT_INVALID' if 'PILOT_INVALID' in statuses else
                      'FINISHED' if len(jobs) == len(chunks) and all(s == 'FINISHED' for s in statuses) else
                      'BATCH_PENDING')
    counts = {key: sum(job.get('provider', {}).get('request_counts', {}).get(key, 0) for job in jobs)
              for key in ('processing', 'succeeded', 'errored', 'canceled', 'expired')}
    state['models'][model['key']].update(status=status, batch_ids=[job['batch_id'] for job in jobs],
        request_counts=counts, submitted_batches=len(jobs), planned_batches=len(chunks),
        provider_status='ended' if status == 'FINISHED' else 'multiple_batches',
        last_updated=storage.now())
    return {'status': status, 'jobs': jobs}
