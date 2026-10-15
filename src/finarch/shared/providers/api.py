"""Responses transport inside the existing role/schema/recording boundary."""
import copy
import hashlib
import re
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from finarch.shared.providers.structured import ProviderFailure
record_usage = __import__('finarch.shared.run_logging.logging', fromlist=['record_usage']).record_usage

ENDPOINT = 'https://api.openai.com/v1/responses'
ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()

def api_key():
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        env = ROOT / '.env'
        if env.exists():
            for line in env.read_text().splitlines():
                name, sep, value = line.strip().removeprefix('export ').partition('=')
                if sep and name.strip() == 'OPENAI_API_KEY':
                    key = value.strip().strip('\"\'')
    if not key:
        raise ProviderFailure('OPENAI_API_KEY_MISSING')
    return key

def wire_schema(schema):
    # Native strict output requires every property to be present, including nullable ones.
    result = copy.deepcopy(schema)
    def visit(node):
        if isinstance(node, dict):
            node.pop('default', None)
            if node.get('type') == 'object':
                node['required'] = list(node.get('properties', {}))
                node['additionalProperties'] = False
            for child in node.values(): visit(child)
        elif isinstance(node, list):
            for child in node: visit(child)
    visit(result)
    return result

def schema_transport_name(role):
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', role)
    if len(name) > 64:
        name = name[:51] + '_' + hashlib.sha256(role.encode()).hexdigest()[:12]
    return name

def _post(endpoint, body, key, timeout):
    from finarch.shared.providers.api_limits import request_slot
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'})
    with request_slot():
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            return reply.read().decode('utf-8')


def complete_api(*, settings, role, payload, response_schema, instruction, prompt_selection, save):
    from uuid import uuid4
    from finarch.shared.providers.profiles import purpose_for_role
    from finarch.shared.providers.roles import resolve_role
    usage_module = __import__('finarch.shared.run_logging.api_usage', fromlist=['usage_record'])
    if not settings['execution_enabled']:
        raise ProviderFailure('MODEL_EXECUTION_DISABLED')
    if settings['policy'] != {'tools': [], 'skills': []}:
        raise ProviderFailure('API_CAPABILITY_NOT_IMPLEMENTED')
    if not response_schema:
        raise ProviderFailure('RESPONSE_SCHEMA_REQUIRED')
    purpose = settings['profile'].get('purpose') or purpose_for_role(role)
    body = {'model': settings['model'], 'reasoning': {'effort': settings['effort']},
            'instructions': instruction, 'input': json.dumps(payload, ensure_ascii=False),
            'text': {'format': {'type': 'json_schema', 'name': schema_transport_name(role),
                               'strict': True, 'schema': wire_schema(response_schema)}},
            'max_output_tokens': settings['profile']['max_output_tokens'], 'store': False,
            'truncation': 'disabled', 'tools': []}
    attempt_id = str(uuid4())
    metadata = {'role': role, 'purpose': purpose, 'provider': 'openai', 'transport': 'api',
                'model': settings['model'], 'effort': settings['effort'], 'attempt_id': attempt_id,
                'profile': settings['profile'], 'prompt': instruction,
                'prompt_selection': prompt_selection, 'response_schema': response_schema,
                'request': body, 'automatic_retries': 0, 'fresh_session': True}
    save('01-input/request-draft.json', metadata)
    key = api_key()
    # The exact prompt and response schema participate in the official input count.
    # The budget is a POT invariant, independent of the selected model profile.
    is_pot = resolve_role(role) == '01-preparation.03-calculation.pot'
    budget = settings['profile'].get('total_token_budget')
    if is_pot:
        budget = min(budget, 500000) if budget is not None else 500000
    count = None
    if budget is not None:
        count_body = {k: v for k, v in body.items() if k not in ('max_output_tokens', 'store')}
        save('01-input/token-count-request.json', count_body)
        try:
            count_text = _post(ENDPOINT+'/input_tokens', count_body, key, settings['timeout_seconds'])
            save('01-input/token-count-response.json', {'text': count_text})
            counted = json.loads(count_text)
            count = counted.get('input_tokens')
            if type(count) is not int or count < 0:
                raise ValueError('INVALID_INPUT_TOKEN_COUNT')
        except (OSError, ValueError, AttributeError) as error:
            # Never store exception text that could include request credentials.
            save('01-input/token-budget.json', {'status': 'FAIL', 'reason': 'INPUT_TOKEN_COUNT_FAILED',
                 'error_type': type(error).__name__, 'generation_requests': 0})
            raise ProviderFailure('INPUT_TOKEN_COUNT_FAILED') from None
        remaining = budget-count
        if remaining <= 0:
            save('01-input/token-budget.json', {'status': 'FAIL', 'input_tokens': count,
                 'total_token_budget': budget, 'generation_requests': 0})
            raise ProviderFailure('POT_TOKEN_BUDGET_EXHAUSTED')
        body['max_output_tokens'] = min(body['max_output_tokens'], remaining)
        save('01-input/token-budget.json', {'status': 'PASS', 'input_tokens': count,
             'max_output_tokens': body['max_output_tokens'], 'total_token_budget': budget,
             'output_includes_reasoning': True, 'count_endpoint': ENDPOINT+'/input_tokens'})
    save('01-input.json', metadata)
    started = time.monotonic()
    save('01-input/api-start.json', {'role': role, 'purpose': purpose, 'attempt_id': attempt_id,
         'timestamp': time.time()})

    def record(envelope=None, status=None):
        row = usage_module.usage_record(role=role, purpose=purpose or 'unmapped', model=settings['model'],
            attempt_id=attempt_id, envelope=envelope, status=status,
            elapsed_seconds=time.monotonic()-started)
        if budget is not None:
            actual = row['tokens']['total_tokens']
            row['token_budget'] = {'limit': budget, 'counted_input_tokens': count,
                'max_output_tokens': body['max_output_tokens'],
                'actual_within_budget': actual <= budget if actual is not None else None}
        save('03-result/usage.json', row)
        record_usage(role=role, model=settings['model'], provider='openai', usage=row['reported_usage'],
            reason=row['cost_status'], cli_invocations=0, estimated_cost=row['estimated_cost'],
            currency=row['currency'], price_basis=row['price_basis'],
            artifacts=['02-raw-response/api-execution.json', '03-result/usage.json'])
        return row

    try:
        text = _post(ENDPOINT, body, key, settings['timeout_seconds'])
    except urllib.error.HTTPError as error:
        save('02-raw-response/api-http-error.json', {'status': error.code})
        record(status='http_error_'+str(error.code))
        raise ProviderFailure('API_HTTP_'+str(error.code)) from None
    except (OSError, ValueError):
        record(status='connection_failed')
        raise ProviderFailure('API_CONNECTION_FAILED') from None
    save('02-raw-response/api-execution.json', {'text': text, 'elapsed_seconds': time.monotonic()-started})
    try:
        envelope = json.loads(text)
        if not isinstance(envelope, dict):
            raise ValueError('API_RESPONSE_NOT_OBJECT')
    except ValueError:
        record(status='invalid_envelope')
        raise ProviderFailure('API_INVALID_ENVELOPE') from None
    row = record(envelope)
    if budget is not None and row['token_budget']['actual_within_budget'] is False:
        raise ProviderFailure('API_REPORTED_TOKEN_BUDGET_EXCEEDED')
    if envelope.get('status') != 'completed':
        raise ProviderFailure('API_RESPONSE_INCOMPLETE')
    parts = [c['text'] for item in envelope.get('output', []) if item.get('type') == 'message'
             for c in item.get('content', []) if c.get('type') == 'output_text']
    if len(parts) != 1:
        raise ProviderFailure('API_RESPONSE_TEXT_REQUIRED')
    return parts[0]
