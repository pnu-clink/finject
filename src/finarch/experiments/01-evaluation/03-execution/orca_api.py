"""Orca Chat Completions transport for frozen DeepSeek V4.1 Flash requests."""
import hashlib
import http.client
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
ENDPOINT = 'https://api.orcarouter.ai/v1/chat/completions'
MODEL = 'deepseek/deepseek-v4.1-flash'
DATED_MODEL = 'deepseek-v4-1-flash-260910'


def accepted_returned_models(model=None):
    """OR07: Permit one dated identifier only under this run's explicit approval."""
    accepted = (MODEL, 'deepseek-v4.1-flash')
    policy = (model or {}).get('returned_model_policy')
    if policy is None:
        return accepted
    exception = cache_policy.implicit_cache_exception(model) or {}
    if (policy.get('version') != 1 or not policy.get('run_id')
            or policy.get('run_id') != exception.get('run_id')
            or policy.get('model_key') != model.get('key')
            or policy.get('requested_model') != MODEL
            or policy.get('accepted_additional_identifiers') != [DATED_MODEL]):
        raise ValueError('ORCA_RETURNED_MODEL_POLICY_SCOPE_MISMATCH')
    if not isinstance(policy.get('authorization'), str) or not policy['authorization'].strip():
        raise ValueError('ORCA_RETURNED_MODEL_AUTHORIZATION_REQUIRED')
    return (*accepted, DATED_MODEL)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_model(model):
    """OR01: Reject alternative routes, models, or reasoning conditions."""
    if model.get('model') != MODEL or model.get('endpoint', ENDPOINT) != ENDPOINT:
        raise ValueError('ORCA_DEEPSEEK_V41_FLASH_TARGET_REQUIRED')
    if model.get('reasoning_efforts') != {'off': 'none', 'on': 'max'}:
        raise ValueError('ORCA_REQUIRES_OFF_NONE_ON_MAX')
    accepted_returned_models(model)
    for mode in ('off', 'on'):
        limit = model.get('output_limits', {}).get(mode)
        if type(limit) is not int or not 1 <= limit <= 384000:
            raise ValueError('ORCA_OUTPUT_LIMIT_REQUIRED')


def body_for(model, request):
    """OR02: Build one fresh public-only request with a nonempty response schema."""
    validate_model(model)
    cache_policy.require_control(model)
    providers.validate_request(request)
    mode = request['reasoning']
    if request['model'] != model['model']:
        raise ValueError('REQUEST_MODEL_MISMATCH')
    if request['max_output_tokens'] != model['output_limits'][mode]:
        raise ValueError('REQUEST_OUTPUT_LIMIT_MISMATCH')
    schema = {k: v for k, v in request['response_schema'].items() if k not in ('$schema', 'title')}
    body = {'model': MODEL, 'stream': False,
            'messages': [{'role': 'system', 'content': request['prompt'] + '\nResponse JSON schema:\n' + store.encoded(request['response_schema']).decode()},
                         {'role': 'user', 'content': store.encoded(request['input']).decode()}],
            'max_tokens': request['max_output_tokens'],
            'thinking': {'type': 'disabled' if mode == 'off' else 'enabled'},
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'financial_answer', 'strict': True, 'schema': schema}}}
    if mode == 'on':
        body['reasoning_effort'] = 'max'
    return body


def rates_at(model, at):
    """OR05: Keep the published UTC peak multiplier separate from reported cost."""
    instant = datetime.fromisoformat(at.replace('Z', '+00:00')).astimezone(timezone.utc)
    peak = instant.weekday() < 5 and (1 <= instant.hour < 4 or 6 <= instant.hour < 10)
    multiplier = model.get('peak_price_multiplier', 2) if peak else 1
    return {k: v * multiplier for k, v in model['reference_price_per_million'].items()}, peak


def cost_from_usage(usage, rates):
    usage = usage if isinstance(usage, dict) else {}
    incoming, outgoing = usage.get('prompt_tokens'), usage.get('completion_tokens')
    cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')
    if not all(type(x) is int and x >= 0 for x in (incoming, outgoing, cached)) or cached > incoming:
        return None
    return round(((incoming - cached) * rates['input'] + cached * rates['cached_input']
                  + outgoing * rates['output']) / 1e6, 10)


def parse_response(obj, status, headers, request, model=None):
    """OR04: Preserve usage and reason trace without treating either as a gold label."""
    obj = obj if isinstance(obj, dict) else {}
    usage = obj.get('usage')
    result = {'http_status': status, 'usage': usage, 'response_id': obj.get('id'),
              'model_version': obj.get('model'), 'response_headers': headers,
              'provider_request_id': headers.get('x-orca-request-id')}
    if status != 200:
        # Only explicit throttling rejections are retried by the existing scheduler.
        result.update(status='RATE_LIMITED' if status == 429 else
                      'AUTH_BLOCKED' if status in (401, 403) else
                      'QUOTA_EXHAUSTED' if status == 402 else
                      'UNKNOWN_DELIVERY' if status >= 500 else 'PROVIDER_ERROR',
                      error=obj.get('error') or {'message': 'Orca HTTP ' + str(status)},
                      delivery_status='REJECTED' if status < 500 else 'UNKNOWN')
        try:
            delay = float(headers.get('retry-after', 60))
            result['retry_after_seconds'] = delay if math.isfinite(delay) and delay >= 0 else 60
        except (TypeError, ValueError):
            result['retry_after_seconds'] = 60
        return result
    if obj.get('model') not in accepted_returned_models(model):
        return {**result, 'status': 'PROVIDER_ERROR', 'error': 'RETURNED_MODEL_MISMATCH'}
    if obj.get('model') == DATED_MODEL:
        result.update(returned_model_accepted_by='USER_AUTHORIZED_RUN_POLICY',
                      returned_model_policy_sha256=store.digest(model['returned_model_policy']))
    choices = obj.get('choices')
    if not isinstance(choices, list) or len(choices) != 1:
        return {**result, 'status': 'TRANSPORT_ERROR', 'error': 'EXPECTED_ONE_CHAT_COMPLETION'}
    choice = choices[0]
    message = choice.get('message') or {}
    text = message.get('content')
    reasoning = (usage or {}).get('completion_tokens_details', {}).get('reasoning_tokens')
    result.update(finish_reason=choice.get('finish_reason'), reasoning_content=message.get('reasoning_content'),
                  thinking_tokens=reasoning, reasoning_effort_requested=request['reasoning_effort'],
                  reasoning_observation='PROVIDER_USAGE_AND_RAW_TRACE_NOT_INDEPENDENT_EFFORT_VERIFICATION')
    if request['reasoning'] == 'off' and (isinstance(reasoning, int) and reasoning > 0 or message.get('reasoning_content')):
        return {**result, 'status': 'PROVIDER_ERROR', 'error': 'REASONING_OFF_RETURNED_REASONING'}
    if not isinstance(text, str):
        return {**result, 'status': 'TRANSPORT_ERROR', 'error': 'CHAT_CONTENT_MISSING'}
    if result['finish_reason'] not in ('stop', 'length'):
        return {**result, 'status': 'PROVIDER_ERROR', 'error': 'UNEXPECTED_FINISH_REASON'}
    reported = (usage or {}).get('cost_usd')
    try:
        reported = float(reported) if reported is not None and not isinstance(reported, bool) else None
    except (TypeError, ValueError):
        reported = None
    if reported is not None and (not math.isfinite(reported) or reported < 0):
        reported = None
    result.update(status='RECEIVED', text=text, provider_reported_cost_usd=reported,
                  billed_cost_usd=None, cost_status='INLINE_PROVIDER_REPORTED_NOT_SETTLEMENT_VERIFIED')
    return result


def call(model, request, folder, timeout):
    """OR03: Send exactly once, disable redirects, and preserve the full raw envelope."""
    body = body_for(model, request)
    wire_bytes = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
    store.write(folder / 'provider-request.json', body)
    store.write_text(folder / 'provider-request-wire.json', wire_bytes.decode())
    key = providers.credential(model)
    wire = urllib.request.Request(ENDPOINT, data=wire_bytes, headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
        'Accept': 'application/json', 'X-OrcaRouter-Include-Cost': 'true'})
    started, began = store.now(), time.monotonic()
    status, headers = None, {}
    try:
        with urllib.request.build_opener(NoRedirect()).open(wire, timeout=timeout) as response:
            status, headers = response.status, dict(response.headers)
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        raw, status, headers = error.read().decode(), error.code, dict(error.headers)
    except (ConnectionError, http.client.RemoteDisconnected) as error:
        # A closed connection does not prove the provider rejected the request.
        ended = store.now()
        visible = {k.lower(): str(v).replace(key, '[REDACTED]') for k, v in headers.items()
                   if k.lower().startswith(('x-orca', 'x-ratelimit-')) or k.lower() in ('x-request-id', 'retry-after')}
        store.write(folder / 'http.json', {'endpoint': ENDPOINT, 'status': status, 'headers': visible,
            'started_at': started, 'ended_at': ended, 'delivery_status': 'UNKNOWN',
            'error_type': type(error).__name__, 'request_sha256': hashlib.sha256(wire_bytes).hexdigest()})
        return {'status': 'UNKNOWN_DELIVERY', 'delivery_status': 'UNKNOWN', 'usage': None,
                'error_type': type(error).__name__, 'error': str(error).replace(key, '[REDACTED]'),
                'response_unavailable_reason': 'NETWORK_DISCONNECT', 'http_status': status,
                'response_headers': visible, 'transport': 'orca_api', 'billing_mode': 'PAID_ORCA_API',
                'requested_model': MODEL, 'started_at': started, 'ended_at': ended,
                'elapsed_seconds': time.monotonic() - began, 'automatic_transport_retries': 0}
    raw = raw.replace(key, '[REDACTED]')
    store.write_text(folder / 'raw-response.json', raw)
    visible = {k.lower(): str(v).replace(key, '[REDACTED]') for k, v in headers.items()
               if k.lower().startswith(('x-orca', 'x-ratelimit-')) or k.lower() in ('x-request-id', 'retry-after')}
    ended = store.now()
    store.write(folder / 'http.json', {'endpoint': ENDPOINT, 'status': status, 'headers': visible,
        'started_at': started, 'ended_at': ended, 'request_sha256': hashlib.sha256(wire_bytes).hexdigest()})
    try:
        obj = json.loads(raw)
    except ValueError:
        obj = {}
    result = parse_response(obj, status, visible, request, model)
    rates, peak = rates_at(model, started)
    result.update(transport='orca_api', billing_mode='PAID_ORCA_API', requested_model=MODEL,
                  started_at=started, ended_at=ended, elapsed_seconds=time.monotonic() - began,
                  price_per_million=rates, peak_pricing_at_request_start=peak,
                  price_source=model.get('price_source'), automatic_transport_retries=0,
                  token_cost_estimate_usd=cost_from_usage(result.get('usage'), rates))
    return result


def configure_returned_model(root, model_key, authorization):
    """OR07.1: Record response-ID approval without rewriting frozen requests."""
    root = Path(root).resolve()
    with store.locked(root / '.full-pipeline.lock'), store.locked(root / '.pipeline.lock'):
        store.verify(root)
        model = next(m for m in store.configuration(root)['models'] if m['key'] == model_key)
        policy = {'version': 1, 'run_id': root.name, 'model_key': model_key,
                  'requested_model': MODEL, 'accepted_additional_identifiers': [DATED_MODEL],
                  'authorized_at': store.now(), 'authorization': authorization,
                  'scope': 'ALLOW_RETURNED_IDENTIFIER_FOR_THIS_RUN',
                  'exact_weights_equivalence': 'NOT_INDEPENDENTLY_VERIFIED',
                  'provider_route_pinned': False,
                  'frozen_config_sha256': store.file_hash(root / 'config.json'),
                  'frozen_manifest_sha256': store.file_hash(root / 'manifest.json')}
        validate_model({**model, 'returned_model_policy': policy})
        overrides = store.read(root / 'runtime-overrides.json', {'models': {}})
        prior = overrides.setdefault('models', {}).setdefault(model_key, {}).get('returned_model_policy')
        if prior:
            accepted_returned_models({**model, 'returned_model_policy': prior})
            return prior
        overrides['models'][model_key]['returned_model_policy'] = policy
        store.write(root / 'runtime-overrides.json', overrides)
        state = store.read(root / 'state.json')
        state['models'][model_key]['returned_model_policy'] = policy
        store.write(root / 'state.json', state)
        store.event(root, 'ORCA_RETURNED_MODEL_POLICY_CONFIGURED', model=model_key,
                    policy=policy, new_model_calls=0, preserve_frozen_requests=True)
        return policy


def revalidate_returned_models(root, model_key, trial_ids):
    """OR07.2: Recheck named HTTP-200 responses, preserving raw bytes and old errors."""
    root = Path(root).resolve()
    layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
    calls = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
    with store.locked(root / '.full-pipeline.lock'), store.locked(root / '.pipeline.lock'):
        store.verify(root)
        model = next(m for m in store.configuration(root)['models'] if m['key'] == model_key)
        if DATED_MODEL not in accepted_returned_models(model):
            raise ValueError('ORCA_RETURNED_MODEL_APPROVAL_REQUIRED')
        frozen = {r['trial_id']: r for r in store.rows(layout.requests(root, model_key))}
        recovered = []
        for trial in dict.fromkeys(trial_ids):
            folder = calls.attempt_dirs(layout.execution(root, model_key), frozen[trial])[-1]
            old = store.read(folder / 'result.json')
            if old.get('error') != 'RETURNED_MODEL_MISMATCH':
                continue
            request = store.read(folder / 'request.json')
            raw, http = store.read(folder / 'raw-response.json'), store.read(folder / 'http.json')
            wire = store.read(folder / 'provider-request.json')
            effective = {**model, 'output_limits': {**model['output_limits'],
                         request['reasoning']: request['max_output_tokens']}}
            if (http.get('status') != 200 or raw.get('model') != DATED_MODEL
                    or wire != body_for(effective, request)):
                raise ValueError('ORCA_RETURNED_MODEL_RECOVERY_SOURCE_MISMATCH')
            raw_hash = store.file_hash(folder / 'raw-response.json')
            backup = folder / 'result-before-returned-model-recovery.json'
            if backup.exists() and store.read(backup) != old:
                raise ValueError('ORCA_RETURNED_MODEL_RECOVERY_BACKUP_EXISTS')
            parsed = parse_response(raw, 200, http.get('headers', {}), request, model)
            result = {k: v for k, v in old.items() if k not in ('error', 'error_type')}
            result.update(parsed)
            if result['status'] == 'RECEIVED':
                try:
                    response = json.loads(result.pop('text'))
                    errors = providers.response_errors(response, request)
                    result.update(response=response, schema_errors=errors,
                                  status='OUTPUT_TRUNCATED' if result.get('finish_reason') == 'length'
                                  else 'INVALID_RESPONSE' if errors else 'VALID')
                except Exception as error:
                    result.update(status='OUTPUT_TRUNCATED' if result.get('finish_reason') == 'length'
                                  else 'INVALID_RESPONSE', validation_error_type=type(error).__name__)
            cache_policy.enforce_result(model, result)
            recovery = {'at': store.now(), 'trial_id': trial, 'previous_status': old['status'],
                        'previous_error': old['error'], 'status': result['status'],
                        'raw_response_sha256': raw_hash, 'new_model_calls': 0,
                        'policy_sha256': store.digest(model['returned_model_policy']),
                        'original_result': backup.name}
            result['returned_model_recovery'] = recovery
            store.write(backup, old)
            store.write(folder / 'result.json', result)
            store.write(folder / 'returned-model-recovery.json', recovery)
            if store.file_hash(folder / 'raw-response.json') != raw_hash:
                raise ValueError('ORCA_RETURNED_MODEL_RECOVERY_RAW_CHANGED')
            store.event(root, 'ORCA_SAVED_RESPONSE_REVALIDATED', model=model_key, **recovery)
            recovered.append(recovery)
        return recovered
