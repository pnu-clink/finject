"""Single-attempt Claude Messages transport for a frozen experiment request."""

import json
import urllib.error
import urllib.request

providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
schema_in_output_order = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['schema_in_output_order']).schema_in_output_order

ENDPOINT = 'https://api.anthropic.com/v1/messages'
API_VERSION = '2023-06-01'
UNSUPPORTED_SCHEMA_CONSTRAINTS = {'minLength', 'maxLength', 'maxItems', 'minItems', 'minimum', 'maximum', 'pattern'}


def transport_schema(value):
    """Remove grammar-unsupported constraints; the original schema stays locally enforced."""
    if isinstance(value, list):
        return [transport_schema(child) for child in value]
    if not isinstance(value, dict):
        return value
    result = {key: transport_schema(child) for key, child in value.items()
              if key not in UNSUPPORTED_SCHEMA_CONSTRAINTS}
    constraints = {key: value[key] for key in UNSUPPORTED_SCHEMA_CONSTRAINTS if key in value}
    if constraints:
        suffix = 'Local validation constraints: ' + ', '.join(
            f'{key}={constraints[key]}' for key in sorted(constraints)) + '.'
        result['description'] = ((result.get('description', '') + ' ' + suffix).strip())
    # Claude's grammar rejects an enum paired with a JSON Schema type array.
    # Keep the frozen local schema unchanged and express nullable fields as
    # supported anyOf branches in the provider-only schema.
    kinds = result.get('type')
    if isinstance(kinds, list):
        nonnull = [kind for kind in kinds if kind != 'null']
        if len(kinds) != 2 or len(nonnull) != 1:
            raise ValueError('UNSUPPORTED_ANTHROPIC_UNION')
        result.pop('type')
        options = result.pop('enum', None)
        branch = {'type': nonnull[0]}
        if options is not None:
            branch['enum'] = [option for option in options if option is not None]
        branches = [branch]
        if options is None or None in options:
            branches.append({'type': 'null'})
        result['anyOf'] = branches
    return result


def body_for(model, request):
    providers.validate_request(request)
    if request['model'] != model['model']:
        raise ValueError('ANTHROPIC_MODEL_OR_REASONING_MISMATCH')
    schema = {key: value for key, value in request['response_schema'].items()
              if key not in ('$schema', 'title')}
    body = {'model': model['model'], 'max_tokens': request['max_output_tokens'],
            'system': request['prompt'],
            'messages': [{'role': 'user', 'content': encoded(request['input']).decode()}],
            'output_config': {'format': {'type': 'json_schema',
                                         'schema': transport_schema(schema_in_output_order(schema))}}}
    if model['model'] == 'claude-haiku-5-5':
        if request['reasoning_effort'] != model.get('reasoning_efforts', {}).get(request['reasoning']):
            raise ValueError('ANTHROPIC_EFFORT_MISMATCH')
        body['output_config']['effort'] = request['reasoning_effort']
        body['thinking'] = {'type': request['thinking_type']}
    elif request['reasoning'] == 'on':
        budget = request.get('thinking_budget')
        if type(budget) is not int or budget < 1024 or budget >= body['max_tokens']:
            raise ValueError('ANTHROPIC_THINKING_BUDGET_INVALID')
        body['thinking'] = {'type': 'enabled', 'budget_tokens': budget}
    return body


def call(model, request, folder, timeout):
    """Save exact provider body and raw response before returning parsed transport status."""
    body = body_for(model, request)
    write(folder / 'provider-request.json', body)
    workspace_id = model.get('workspace_id')
    if not isinstance(workspace_id, str) or not workspace_id.startswith('wrkspc_'):
        raise ValueError('ANTHROPIC_WORKSPACE_ID_REQUIRED')
    key = providers.credential(model)
    wire = urllib.request.Request(ENDPOINT, data=encoded(body),
        headers={'content-type': 'application/json', 'x-api-key': key,
                 'anthropic-version': API_VERSION, 'anthropic-workspace-id': workspace_id})
    try:
        with urllib.request.urlopen(wire, timeout=timeout) as response:
            raw, status, headers = response.read().decode(), response.status, response.headers
    except urllib.error.HTTPError as error:
        raw, status, headers = error.read().decode(), error.code, error.headers
    write_text(folder / 'raw-response.json', raw.replace(key, '[REDACTED]'))
    obj = json.loads(raw)
    result = {'http_status': status, 'usage': obj.get('usage'),
              'response_id': obj.get('id'), 'model_version': obj.get('model'),
              'request_id': headers.get('request-id'),
              'workspace_id': headers.get('anthropic-workspace-id'),
              'billing_mode': 'PAID_ANTHROPIC_API',
              'price_per_million': model['reference_price_per_million']}
    if status != 200:
        error = obj.get('error', {})
        result.update(status=('AUTH_BLOCKED' if status in (401, 403) else
                              'RATE_LIMITED' if status == 429 else
                              'TRANSIENT_ERROR' if status in (500, 502, 503, 504) else
                              'PROVIDER_ERROR'), error=error)
        return result
    usage = result['usage'] or {}
    if all(type(usage.get(key)) is int for key in ('input_tokens', 'output_tokens',
                                                  'cache_read_input_tokens', 'cache_creation_input_tokens')):
        rates = model['reference_price_per_million']
        result['reported_equivalent_usd'] = round((
            usage['input_tokens'] * rates['input'] + usage['output_tokens'] * rates['output']
            + usage['cache_read_input_tokens'] * rates.get('cached_input', rates['input'])
            + usage['cache_creation_input_tokens'] * rates.get('cache_write_input', rates['input'])) / 1e6, 10)
    return {**result, 'status': 'RECEIVED',
            'text': ''.join(part.get('text', '') for part in obj.get('content', [])
                          if part.get('type') == 'text'),
            'finish_reason': obj.get('stop_reason')}
