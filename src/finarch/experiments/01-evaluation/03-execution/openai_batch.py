"""Native OpenAI Batch transport with durable submission and exact ID matching."""
import json
from pathlib import Path

run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
import urllib.error
import urllib.parse
import urllib.request
import uuid

storage = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
api = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['*'])
policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
answer_format = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['*'])
BASE = 'https://api.openai.com/v1/'
TERMINAL = {'completed', 'failed', 'expired', 'cancelled'}


def http(model, suffix, *, body=None, content_type='application/json', raw=False):
    """One request only; uncertain POSTs are reconciled, never blindly repeated."""
    key = api.providers.credential(model)
    data = body if isinstance(body, bytes) else api.wire_encoded(body) if body is not None else None
    request = urllib.request.Request(BASE + suffix, data=data,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': content_type})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            text = response.read().decode('utf-8').replace(key, '[REDACTED]')
    except urllib.error.HTTPError as error:
        text = error.read().decode('utf-8', errors='replace').replace(key, '[REDACTED]')
        raise ValueError(f'OPENAI_BATCH_HTTP_{error.code}: {text[:4000]}') from None
    return text if raw else json.loads(text)


def prepare_job(model, manifest, folder, requests, body_builder):
    """E03.02: Freeze the native wire file, referencing the existing manifest."""
    policy.require_control(model)
    manifest, folder = Path(manifest), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    job_path = folder / 'job.json'
    source_hash = storage.file_hash(manifest)
    if job_path.exists():
        job = storage.read(job_path)
        if job['manifest_sha256'] != source_hash or storage.file_hash(folder / 'input.jsonl') != job['input_sha256']:
            raise ValueError('FROZEN_BATCH_INPUT_CHANGED')
        return job
    if not requests or len(requests) > 50000:
        raise ValueError('BATCH_REQUEST_COUNT_OUT_OF_RANGE')
    ids, lines = set(), []
    for request in requests:
        custom_id = request['trial_id']
        if custom_id in ids:
            raise ValueError('DUPLICATE_BATCH_CUSTOM_ID')
        ids.add(custom_id)
        body = body_builder(model, request)
        if body.get('model') != model['model']:
            raise ValueError('BATCH_MODEL_MISMATCH')
        if not body.get('text', {}).get('format', {}).get('schema'):
            raise ValueError('BATCH_RESPONSE_SCHEMA_REQUIRED')
        api.validate_cache_body(body)
        lines.append(api.wire_encoded({'custom_id': custom_id, 'method': 'POST',
                                      'url': '/v1/responses', 'body': body}).decode('utf-8'))
    text = '\n'.join(lines) + '\n'
    if len(text.encode('utf-8')) > 200_000_000:
        raise ValueError('BATCH_FILE_EXCEEDS_200_MB')
    storage.write_text(folder / 'input.jsonl', text)
    job = {'status': 'PREPARED', 'created_at': storage.now(), 'model': model['model'],
           'manifest_sha256': source_hash, 'input_sha256': storage.file_hash(folder / 'input.jsonl'),
           'requests': len(requests), 'endpoint': '/v1/responses', 'completion_window': '24h',
           'token_cost_estimate_usd': None, 'billed_cost_usd': None}
    storage.write(job_path, job)
    return job


def submit(model, folder):
    """E03.02: Upload then create exactly one native Batch job."""
    folder = Path(folder)
    job = storage.read(folder / 'job.json')
    if job.get('batch_id') or job['status'] == 'COLLECTED':
        return job
    if job['status'] in ('SUBMITTING', 'UNKNOWN_SUBMISSION'):
        # A saved input file ID uniquely identifies this submission during reconciliation.
        suffix = 'batches?limit=100'
        while suffix:
            page = http(model, suffix)
            matches = [batch for batch in page.get('data', []) if batch.get('input_file_id') == job.get('input_file_id')]
            if len(matches) > 1:
                raise ValueError('DUPLICATE_REMOTE_BATCH_REQUIRES_RECONCILIATION')
            if matches:
                batch = matches[0]
                job.update(status='SUBMITTED', batch_id=batch['id'], provider=batch)
                storage.write(folder / 'job.json', job)
                return job
            suffix = ('batches?limit=100&after=' + urllib.parse.quote(page['last_id'])) if page.get('has_more') else None
        raise ValueError('UNKNOWN_BATCH_SUBMISSION_NOT_RESUBMITTED')
    if job['status'] == 'UPLOADING':
        raise ValueError('UNKNOWN_FILE_UPLOAD_NOT_REPEATED')
    if not job.get('input_file_id'):
        boundary = 'finarch-' + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nbatch\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input.jsonl"\r\n'
                'Content-Type: application/jsonl\r\n\r\n').encode()
        body += (folder / 'input.jsonl').read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
        job['status'] = 'UPLOADING'
        storage.write(folder / 'job.json', job)
        uploaded = http(model, 'files', body=body, content_type='multipart/form-data; boundary=' + boundary)
        storage.write(folder / 'uploaded-file.json', uploaded)
        job.update(status='UPLOADED', input_file_id=uploaded['id'])
        storage.write(folder / 'job.json', job)
    request = {'input_file_id': job['input_file_id'], 'endpoint': '/v1/responses', 'completion_window': '24h',
               'metadata': {'manifest_sha256': job['manifest_sha256'], 'project': 'fin-arch'}}
    storage.write(folder / 'request.json', request)
    job.update(status='SUBMITTING', submitted_at=storage.now())
    storage.write(folder / 'job.json', job)
    try:
        batch = http(model, 'batches', body=request)
    except Exception:
        job['status'] = 'UNKNOWN_SUBMISSION'
        storage.write(folder / 'job.json', job)
        raise
    job.update(status='SUBMITTED', batch_id=batch['id'], provider=batch)
    storage.write(folder / 'job.json', job)
    return job


def poll(model, folder):
    """Retrieve current status and persist both output and error files verbatim."""
    folder = Path(folder)
    job = storage.read(folder / 'job.json')
    if job['status'] == 'COLLECTED':
        return job
    batch = http(model, 'batches/' + urllib.parse.quote(job['batch_id']))
    if batch.get('input_file_id') != job['input_file_id']:
        raise ValueError('BATCH_INPUT_FILE_ID_MISMATCH')
    job.update(provider=batch, checked_at=storage.now())
    storage.write(folder / 'job.json', job)
    if batch['status'] in TERMINAL:
        for key, name in [('output_file_id', 'output.jsonl'), ('error_file_id', 'errors.jsonl')]:
            if batch.get(key) and not (folder / name).exists():
                raw = http(model, 'files/' + urllib.parse.quote(batch[key]) + '/content', raw=True)
                storage.write_text(folder / name, raw)
    return job


def outputs(folder, expected_ids):
    """Validate every returned ID before writing any per-item result."""
    folder = Path(folder)
    records = {}
    for name in ('output.jsonl', 'errors.jsonl'):
        if not (folder / name).exists():
            continue
        with (folder / name).open() as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                key = record.get('custom_id')
                if key not in expected_ids or key in records:
                    raise ValueError('BATCH_CUSTOM_ID_SET_MISMATCH')
                records[key] = (record, line)
    return records


def interpret(model, request, record, validate):
    """Keep errors and unknown usage separate from semantic outcomes."""
    response = record.get('response')
    if not response:
        return {'status': 'BATCH_REQUEST_ERROR', 'error': record.get('error'), 'usage': None,
                'transport': 'openai_batch', 'billing_mode': 'PAID_OPENAI_BATCH', 'token_cost_estimate_usd': None}
    result = api.parse_response(response['body'], response['status_code'], {'x-request-id': response.get('request_id')})
    received = result['status'] == 'RECEIVED'
    if received:
        try:
            parsed = json.loads(result.pop('text'))
            errors = validate(parsed, request)
            result.update(response=parsed, schema_errors=errors, status='INVALID_RESPONSE' if errors else 'VALID')
        except (ValueError, TypeError, KeyError) as error:
            result.update(status='INVALID_RESPONSE', validation_error_type=type(error).__name__)
    if received or result.get('usage') is not None or result.get('http_status') == 200:
        policy.enforce_result(model, result)
    rates, price_source = api.accounting(model)
    result.update(transport='openai_batch', billing_mode='PAID_OPENAI_BATCH',
                  requested_model=model['model'], reasoning_effort_requested=request['reasoning_effort'],
                  price_per_million=rates, price_source=price_source,
                  token_cost_estimate_usd=api.cost_from_usage(result['usage'], rates) if result.get('usage') and rates else None,
                  billed_cost_usd=None, elapsed_seconds=None, timing_note='Batch does not return per-request latency.',
                  automatic_transport_retries=0)
    return result


def split_requests(model, requests, max_bytes=190_000_000, max_count=50000):
    """Split only transport files; keep experimental IDs and ordering unchanged."""
    chunks, current, size = [], [], 0
    for request in requests:
        length = len(api.wire_encoded({'custom_id': request['trial_id'], 'method': 'POST',
                                      'url': '/v1/responses', 'body': api.body_for(model, request)})) + 1
        if length > max_bytes:
            raise ValueError('SINGLE_BATCH_REQUEST_EXCEEDS_FILE_LIMIT')
        if current and (size + length > max_bytes or len(current) >= max_count):
            chunks.append(current)
            current, size = [], 0
        current.append(request)
        size += length
    if current:
        chunks.append(current)
    return chunks


def process(root, model, state):
    """Submit bounded files and join their statuses without duplicate requests."""
    root = Path(root)
    base = run_layout.execution(root, model['key'])
    requests = storage.rows(run_layout.requests(root, model['key']))
    layout.check_manifest(base, requests)
    chunks = split_requests(model, requests)
    jobs = []
    for index, chunk in enumerate(chunks, 1):
        folder = run_layout.batches(root, model['key']) / f'batch-{index:03d}'
        jobs.append(process_chunk(root, model, state, chunk, folder))
    if len(jobs) == 1:
        return jobs[0]
    statuses = [j.get('result_status', 'BATCH_PENDING') for j in jobs]
    failures = [s for s in statuses if s not in ('FINISHED', 'BATCH_PENDING')]
    status = failures[0] if failures else 'FINISHED' if all(s == 'FINISHED' for s in statuses) else 'BATCH_PENDING'
    counts = {k: sum(j.get('provider', {}).get('request_counts', {}).get(k, 0) for j in jobs)
              for k in ('total', 'completed', 'failed')}
    state['models'][model['key']].update(status=status, batch_ids=[j['batch_id'] for j in jobs],
        request_counts=counts, provider_status='completed' if status=='FINISHED' else 'multiple_batches',
        last_updated=storage.now())
    return {'status': status, 'jobs': jobs}


def process_chunk(root, model, state, requests, folder):
    """Prepare/submit/poll/collect once; subsequent calls never duplicate a job."""
    root = Path(root)
    base = run_layout.execution(root, model['key'])
    manifest = run_layout.requests(root, model['key'])
    prepare_job(model, manifest, folder, requests, api.body_for)
    before = storage.read(folder / 'job.json')
    job = submit(model, folder)
    if not before.get('batch_id'):
        storage.event(root, 'OPENAI_BATCH_SUBMITTED', model=model['key'], batch_id=job['batch_id'], requests=len(requests))
    job = poll(model, folder)
    provider_status = job['provider']['status']
    model_state = state['models'][model['key']]
    model_state.update(status='BATCH_PENDING', batch_id=job['batch_id'], provider_status=provider_status,
                       request_counts=job['provider'].get('request_counts'), last_updated=storage.now())
    storage.event(root, 'OPENAI_BATCH_PROGRESS', model=model['key'], batch_id=job['batch_id'],
                  provider_status=provider_status, request_counts=job['provider'].get('request_counts'))
    if job['status'] == 'COLLECTED':
        model_state['status'] = job['result_status']
        return job
    if provider_status not in TERMINAL:
        return job
    records = outputs(folder, {request['trial_id'] for request in requests})
    stops, cost, usage_missing = set(), 0.0, 0
    for processed, request in enumerate(requests, 1):
        attempt = layout.attempt_path(base, request, 1)
        existing = storage.read(attempt / 'result.json', {})
        if existing and existing.get('batch_id') != job['batch_id']:
            raise ValueError('BATCH_ATTEMPT_ALREADY_OWNED_BY_OTHER_EXECUTION')
        if existing:
            result = existing
        else:
            storage.write(attempt / 'request.json', request)
            storage.write(attempt / 'provider-request.json', api.body_for(model, request))
            if request['trial_id'] in records:
                record, raw = records[request['trial_id']]
                storage.write_text(attempt / 'raw-response.json', raw)
                result = interpret(model, request, record, answer_format.response_errors)
            else:
                result = {'status': 'BATCH_REQUEST_MISSING', 'provider_batch_status': provider_status,
                          'usage': None, 'token_cost_estimate_usd': None, 'transport': 'openai_batch'}
            result['batch_id'] = job['batch_id']
            storage.write(attempt / 'result.json', result)
        if result['status'] in policy.STOP_STATUSES:
            stops.add(result['status'])
        if result.get('token_cost_estimate_usd') is None:
            usage_missing += 1
        else:
            cost += result['token_cost_estimate_usd']
        layout.publish(root, base, request, {})
        if processed % 250 == 0 or processed == len(requests):
            storage.event(root, 'OPENAI_BATCH_VALIDATION_PROGRESS', model=model['key'],
                          batch_id=job['batch_id'], processed=processed, requests=len(requests))
    status = sorted(stops)[0] if stops else 'FINISHED' if provider_status == 'completed' else 'BATCH_' + provider_status.upper()
    job.update(status='COLLECTED', result_status=status, collected_at=storage.now(),
               returned_records=len(records), token_cost_estimate_usd=round(cost, 10), requests_without_known_cost=usage_missing)
    storage.write(folder / 'job.json', job)
    model_state['status'] = status
    storage.event(root, 'OPENAI_BATCH_COLLECTED', model=model['key'], batch_id=job['batch_id'],
                  status=status, returned_records=len(records), requests_without_known_cost=usage_missing,
                  token_cost_estimate_usd=round(cost, 10))
    return job
