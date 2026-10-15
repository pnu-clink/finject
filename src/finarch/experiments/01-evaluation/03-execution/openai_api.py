"""Uncached Luna Responses requests for the frozen financial experiments."""
import json
import time
import urllib.error
import urllib.request

cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text

ENDPOINT = 'https://api.openai.com/v1/responses'


def accounting(model):
    """Reporting-only estimates, independent of research hyperparameters."""
    if 'reference_price_per_million' in model:
        return model['reference_price_per_million'], model.get('price_source')
    # Verified on 2026-09-27; usage estimates are not provider invoices.
    standard = {'gpt-6-luna': (.1, .5, .01, .125), 'gpt-6-sol': (2., 10., .2, 2.5)}
    values = standard.get(model['model'])
    if values is None:
        return None, None
    factor = .5 if model.get('transport') == 'openai_batch' else 1.
    return dict(zip(('input', 'output', 'cached_input', 'cache_write_input'),
                    (value * factor for value in values))), 'https://developers.openai.com/api/docs/pricing'


def schema_in_output_order(value):
    """Restore the declared required-field order after canonical manifest storage."""
    if isinstance(value, list):
        return [schema_in_output_order(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: schema_in_output_order(child) for key, child in value.items()}
    properties, required = result.get('properties'), result.get('required')
    if isinstance(properties, dict) and isinstance(required, list):
        names = [name for name in required if name in properties]
        names.extend(name for name in properties if name not in names)
        result['properties'] = {name: properties[name] for name in names}
    return result


def wire_encoded(body):
    """Keep schema field order in the actual HTTP bytes, independently of hashes."""
    return json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')


def body_for(model, request):
    """OA01: Validate the frozen request before constructing the exact API body."""
    cache_policy.require_control(model)
    providers.validate_request(request)
    if request['model'] != model['model']:
        raise ValueError('REQUEST_MODEL_MISMATCH')
    effort = model['reasoning_efforts'][request['reasoning']]
    if request.get('reasoning_effort') != effort:
        raise ValueError('REQUEST_REASONING_EFFORT_MISMATCH')
    schema = schema_in_output_order({k: v for k, v in request['response_schema'].items() if k not in ('$schema', 'title')})
    body = {'model': model['model'], 'instructions': request['prompt'],
            'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': encoded(request['input']).decode()}]}],
            'reasoning': {'effort': effort},
            'text': {'format': {'type': 'json_schema', 'name': 'financial_answer', 'strict': True, 'schema': schema}},
            'max_output_tokens': request['max_output_tokens'], 'store': False,
            'truncation': 'disabled', 'tools': [], 'service_tier': 'default',
            'prompt_cache_options': {'mode': 'explicit'}}
    validate_cache_body(body)
    return body


def validate_cache_body(body):
    """OA02: Reject implicit caching, any breakpoint, or prior response replay."""
    if body.get('prompt_cache_options') != {'mode': 'explicit'}:
        raise ValueError('EXPLICIT_ONLY_CACHE_MODE_REQUIRED')
    if any(key in body for key in ('previous_response_id', 'conversation', 'prompt_cache_key', 'prompt_cache_retention')):
        raise ValueError('FRESH_UNCACHED_REQUEST_REQUIRED')
    def visit(value):
        if isinstance(value, dict):
            if 'prompt_cache_breakpoint' in value:
                raise ValueError('CACHE_BREAKPOINT_FORBIDDEN')
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(body)


def cost_from_usage(usage, rates):
    """OA05: Record all returned tokens, including failed-response usage."""
    details = usage.get('input_tokens_details') or {}
    values = [usage.get('input_tokens'), usage.get('output_tokens'),
              details.get('cached_tokens'), details.get('cache_write_tokens')]
    if not all(type(value) is int and value >= 0 for value in values):
        return None
    incoming, outgoing, cached, written = values
    if cached + written > incoming:
        return None
    return round(((incoming - cached - written) * rates['input'] + cached * rates['cached_input']
                  + written * rates['cache_write_input'] + outgoing * rates['output']) / 1e6, 10)


def parse_response(obj, http_status=200, headers=None):
    """OA04: Extract output text without rewriting the provider response or usage."""
    headers = headers or {}
    usage = obj.get('usage')
    result = {'usage': usage, 'http_status': http_status, 'response_id': obj.get('id'),
              'model_version': obj.get('model'), 'service_tier': obj.get('service_tier'),
              'provider_status': obj.get('status'), 'response_headers': headers,
              'returned_cache_options': obj.get('prompt_cache_options')}
    if http_status != 200:
        error = obj.get('error') or {}
        code = error.get('code') if isinstance(error, dict) else None
        error_type = error.get('type') if isinstance(error, dict) else None
        if http_status in (401, 403):
            status = 'AUTH_BLOCKED'
        elif code in ('insufficient_quota', 'billing_hard_limit_reached', 'billing_not_active',
                      'credit_balance_exhausted') or error_type == 'insufficient_quota':
            status = 'QUOTA_EXHAUSTED'
        elif http_status == 429:
            status = 'RATE_LIMITED'
        elif http_status in (500, 502, 503, 504):
            status = 'TRANSIENT_ERROR'
        else:
            status = 'PROVIDER_ERROR'
        try:
            delay = max(0, float(headers.get('retry-after', 0)))
        except (TypeError, ValueError):
            delay = 0
        return {**result, 'status': status, 'error': error, 'retry_after_seconds': delay}
    chunks, refusals = [], []
    messages = [item for item in obj.get('output', []) if item.get('type') == 'message']
    finals = [item for item in messages if item.get('phase') == 'final_answer']
    # Preserve auxiliary messages in the raw envelope, not inside the final JSON.
    for item in finals or messages:
        if item.get('type') != 'message':
            continue
        for part in item.get('content', []):
            if part.get('type') == 'output_text':
                chunks.append(part.get('text', ''))
            elif part.get('type') == 'refusal':
                refusals.append(part.get('refusal', ''))
    if obj.get('status') == 'incomplete':
        return {**result, 'status': 'OUTPUT_TRUNCATED', 'finish_reason': 'max_tokens',
                'incomplete_details': obj.get('incomplete_details'), 'partial_text': ''.join(chunks)}
    if refusals:
        return {**result, 'status': 'REFUSAL', 'error': refusals, 'finish_reason': 'refusal'}
    if obj.get('status') != 'completed':
        return {**result, 'status': 'PROVIDER_ERROR', 'error': obj.get('error') or 'RESPONSE_NOT_COMPLETED'}
    return {**result, 'status': 'RECEIVED', 'text': ''.join(chunks), 'finish_reason': 'completed'}


def call(model, request, folder, timeout):
    """OA03: One HTTP attempt, with no SDK retries and no response reuse."""
    body = body_for(model, request)
    write(folder / 'provider-request.json', body)
    body_bytes = wire_encoded(body)
    write_text(folder / 'provider-request-wire.json', body_bytes.decode('utf-8'))
    key = providers.credential(model)
    wire = urllib.request.Request(ENDPOINT, data=body_bytes,
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    started, elapsed = now(), time.monotonic()
    try:
        with urllib.request.urlopen(wire, timeout=timeout) as response:
            raw, status, headers = response.read().decode(), response.status, dict(response.headers)
    except urllib.error.HTTPError as error:
        raw, status, headers = error.read().decode(), error.code, dict(error.headers)
    raw = raw.replace(key, '[REDACTED]')
    write_text(folder / 'raw-response.json', raw)
    visible_headers = {k.lower(): v for k, v in headers.items()
                       if k.lower() in ('x-request-id', 'retry-after') or k.lower().startswith('x-ratelimit-')}
    write(folder / 'http.json', {'endpoint': ENDPOINT, 'status': status, 'headers': visible_headers,
                               'started_at': started, 'ended_at': now()})
    try:
        result = parse_response(json.loads(raw), status, visible_headers)
    except (ValueError, TypeError, AttributeError):
        result = {'status': 'TRANSPORT_ERROR', 'usage': None, 'http_status': status,
                  'error': 'PROVIDER_RESPONSE_NOT_A_JSON_OBJECT'}
    rates, price_source = accounting(model)
    result.update(transport='openai_responses', billing_mode='PAID_OPENAI_API',
                  requested_model=model['model'], reasoning_effort_requested=request['reasoning_effort'],
                  started_at=started, ended_at=now(), elapsed_seconds=time.monotonic() - elapsed,
                  price_per_million=rates, price_source=price_source,
                  token_cost_estimate_usd=cost_from_usage(result['usage'], rates) if result.get('usage') and rates else None,
                  billed_cost_usd=None, automatic_transport_retries=0)
    return result
