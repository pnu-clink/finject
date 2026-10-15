"""Validated experiment requests through explicit provider transports."""
import json
import os
import re
import shlex
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from functools import lru_cache

from jsonschema import Draft202012Validator

encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
validate_input = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['validate_input']).validate_input
response_errors = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['response_errors']).response_errors
cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])


def credential(settings):
    name = settings['key_variable']
    if settings.get('key_file'):
        path = Path(settings['key_file']).expanduser()
        for line in path.read_text().splitlines():
            match = re.match(r'\s*(?:export\s+)?' + re.escape(name) + r'\s*=\s*(.*)$', line)
            if match:
                parts = shlex.split(match[1], comments=True)
                if len(parts) != 1 or any(x in parts[0] for x in ('$', '`')):
                    raise ValueError('CREDENTIAL_MUST_BE_A_LITERAL_ASSIGNMENT')
                return parts[0]
        raise ValueError('CREDENTIAL_VARIABLE_NOT_FOUND')
    if not os.environ.get(name):
        raise ValueError('CREDENTIAL_VARIABLE_NOT_SET')
    return os.environ[name]


def subscription_environment():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('ANTHROPIC_', 'CLAUDE_CODE_USE_')) or key in ('CLAUDECODE', 'CLAUDE_CODE_OAUTH_TOKEN'):
            env.pop(key, None)
    env.update(CLAUDE_CODE_MAX_RETRIES='0', MAX_STRUCTURED_OUTPUT_RETRIES='0',
               CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', CLAUDE_CODE_DISABLE_ATTACHMENTS='1',
               DISABLE_PROMPT_CACHING='1')
    return env


def preflight(model):
    cache_policy.require_control(model)
    if model['transport'] == 'orca_api':
        orca = __import__('finarch.experiments.01-evaluation.03-execution.orca_api', fromlist=['*'])
        orca.validate_model(model)
        credential(model)
        return {'status': 'READY', 'credential_variable': model['key_variable'],
                'billing_mode': 'PAID_ORCA_API', 'cache_control': cache_policy.control(model)}
    if model['transport'] in ('anthropic_api', 'anthropic_batch'):
        credential(model)
        if not str(model.get('workspace_id', '')).startswith('wrkspc_'):
            raise ValueError('ANTHROPIC_WORKSPACE_ID_REQUIRED')
        return {'status': 'READY', 'credential_variable': model['key_variable'],
                'billing_mode': 'PAID_ANTHROPIC_BATCH' if model['transport'] == 'anthropic_batch' else 'PAID_ANTHROPIC_API', 'workspace_id': model['workspace_id'],
                'cache_control': cache_policy.control(model)}
    if model['transport'] == 'openai_responses':
        credential(model)
        if model.get('reasoning_efforts') != {'off': 'none', 'on': 'medium'}:
            raise ValueError('FROZEN_LUNA_REASONING_CONDITIONS_REQUIRED')
        return {'status': 'READY', 'credential_variable': model['key_variable'],
                'billing_mode': 'PAID_OPENAI_API', 'cache_control': cache_policy.control(model)}
    if model['transport'] == 'codex_cli':
        codex_preflight = __import__('finarch.experiments.01-evaluation.03-execution.codex_cli', fromlist=['preflight']).preflight
        return codex_preflight(model)
    if model['transport'].startswith('gemini'):
        credential(model)
        return {'status': 'READY', 'credential_variable': model['key_variable'],
                'billing_mode': 'PAID_BATCH' if model['transport'] == 'gemini_batch' else 'USER_DESIGNATED_FREE_KEY'}
    result = subprocess.run(['claude', 'auth', 'status'], env=subscription_environment(),
                            capture_output=True, text=True, timeout=30)
    auth = json.loads(result.stdout)
    if not auth.get('loggedIn') or auth.get('authMethod') != 'claude.ai' or auth.get('apiProvider') != 'firstParty':
        raise ValueError('CLAUDE_SUBSCRIPTION_AUTH_REQUIRED')
    return {'status': 'READY', 'auth_method': auth['authMethod'], 'subscription_type': auth.get('subscriptionType'),
            'cli_version': subprocess.check_output(['claude', '--version'], text=True).strip()}


@lru_cache(maxsize=32)
def validate_schema_definition(schema_bytes):
    """Reuse only successful checks of identical schema bytes, never model results."""
    Draft202012Validator.check_schema(json.loads(schema_bytes))


def validate_request(request):
    schema = request.get('response_schema')
    if not isinstance(schema, dict) or not schema or not schema.get('properties'):
        raise ValueError('MISSING_NONEMPTY_RESPONSE_SCHEMA')
    validate_schema_definition(encoded(schema))
    if not isinstance(request.get('prompt'), str) or not request['prompt'].strip():
        raise ValueError('MISSING_PROMPT')
    validate_input(request)
    if request['reasoning'] not in ('off', 'on'):
        raise ValueError('INVALID_REASONING_MODE')
    if request.get('model') == 'deepseek/deepseek-v4.1-flash':
        expected = 'none' if request['reasoning'] == 'off' else 'max'
        if request.get('reasoning_effort') != expected or 'thinking_budget' in request:
            raise ValueError('DEEPSEEK_V41_REQUIRES_OFF_NONE_ON_MAX')
        limit = request.get('max_output_tokens')
        if type(limit) is not int or not 1 <= limit <= 384000:
            raise ValueError('DEEPSEEK_V41_OUTPUT_LIMIT_INVALID')
    if request.get('model') == 'claude-haiku-5-5':
        effort = request.get('reasoning_effort')
        if effort not in ('low', 'medium', 'high', 'xhigh', 'max'):
            raise ValueError('HAIKU_55_SUPPORTED_EFFORT_REQUIRED')
        if 'thinking_budget' in request:
            raise ValueError('HAIKU_55_REQUIRES_EFFORT_NOT_THINKING_BUDGET')
        expected = 'adaptive' if request['reasoning'] == 'on' else 'disabled'
        if request.get('thinking_type') != expected:
            raise ValueError('HAIKU_55_THINKING_TYPE_MISMATCH')
        if request['reasoning'] == 'off' and effort in ('xhigh', 'max'):
            raise ValueError('HAIKU_55_REASONING_OFF_UNSUPPORTED_AT_XHIGH_OR_MAX')
        limit = request.get('max_output_tokens')
        if type(limit) is not int or not 1 <= limit <= 128000:
            raise ValueError('HAIKU_55_OUTPUT_LIMIT_INVALID')
    if request.get('model') in ('gemini-3.8-flash', 'gemini-3.5-flash-lite'):
        if request['reasoning'] != 'on':
            raise ValueError('GEMINI_LEVEL_MODEL_HAS_NO_REASONING_OFF')
        levels = ('minimal', 'low', 'medium', 'high') if request['model'] == 'gemini-3.5-flash-lite' else ('low', 'medium', 'high')
        if request.get('thinking_level') not in levels:
            raise ValueError('GEMINI_LEVEL_MODEL_REQUIRES_SUPPORTED_THINKING_LEVEL')
        if 'thinking_budget' in request:
            raise ValueError('GEMINI_LEVEL_MODEL_REQUIRES_LEVEL_NOT_BUDGET')


def gemini_body(request):
    validate_request(request)
    schema = {k: v for k, v in request['response_schema'].items() if k not in ('$schema', 'title')}
    thinking = ({'thinkingLevel': request['thinking_level']} if 'thinking_level' in request else
                {'thinkingBudget': request['thinking_budget'] if request['reasoning'] == 'on' else 0})
    return {'systemInstruction': {'parts': [{'text': request['prompt']}]},
            'contents': [{'role': 'user', 'parts': [{'text': encoded(request['input']).decode()}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'responseJsonSchema': schema,
                'maxOutputTokens': request['max_output_tokens'],
                'thinkingConfig': thinking}}


def gemini_call(model, request, folder, timeout):
    cache_policy.require_control(model)
    body = gemini_body(request)
    write(folder / 'provider-request.json', body)
    key = credential(model)
    url = 'https://generativelanguage.googleapis.com/v1beta/models/' + model['model'] + ':generateContent'
    wire = urllib.request.Request(url, data=encoded(body), headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    try:
        with urllib.request.urlopen(wire, timeout=timeout) as response:
            raw = response.read().decode()
            status = response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read().decode(), error.code
    raw = raw.replace(key, '[REDACTED]')
    write_text(folder / 'raw-response.json', raw)
    obj = json.loads(raw)
    if status != 200:
        message = encoded(obj).decode()
        daily = bool(re.search(r'per.?day|per_day|daily', message, re.I))
        delay = max([float(s) for s in re.findall(r'"retryDelay"\s*:\s*"([\d.]+)s"', message)] or [60])
        per_minute = [int(v['quotaValue']) for detail in obj.get('error', {}).get('details', [])
                      for v in detail.get('violations', [])
                      if 'RequestsPerMinute' in v.get('quotaId', '') and str(v.get('quotaValue', '')).isdigit()]
        return {'status': 'QUOTA_EXHAUSTED' if daily else 'RATE_LIMITED' if status == 429 else
                         'TRANSIENT_ERROR' if status in (500, 502, 503, 504) else 'PROVIDER_ERROR',
                'http_status': status, 'retry_after_seconds': delay,
                'requests_per_minute': min(per_minute) if per_minute else None,
                'error': obj.get('error'), 'usage': None}
    usage = obj.get('usageMetadata')
    candidates = obj.get('candidates', [])
    candidate = candidates[0] if candidates else {}
    parts = candidate.get('content', {}).get('parts', [])
    text = ''.join(part.get('text', '') for part in parts if not part.get('thought'))
    return {'status': 'RECEIVED', 'text': text, 'usage': usage,
            'finish_reason': candidate.get('finishReason'), 'model_version': obj.get('modelVersion'),
            'response_id': obj.get('responseId'), 'thinking_tokens': (usage or {}).get('thoughtsTokenCount', 0)}


def claude_command(request):
    validate_request(request)
    wire_schema = {k: v for k, v in request['response_schema'].items() if k not in ('$schema', 'title')}
    return ['claude', '--print', '--model', request['model'], '--output-format', 'json',
            '--json-schema', encoded(wire_schema).decode(),
            '--system-prompt', request['prompt'], '--tools', '', '--disable-slash-commands',
            '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
            '--no-session-persistence', '--safe-mode', '--setting-sources', '']


def claude_call(model, request, folder, timeout):
    cache_policy.require_control(model)
    env = subscription_environment()
    env.update(MAX_THINKING_TOKENS=str(request['thinking_budget'] if request['reasoning'] == 'on' else 0),
               CLAUDE_CODE_MAX_OUTPUT_TOKENS=str(request['max_output_tokens']),
               CLAUDE_CODE_DISABLE_THINKING='0' if request['reasoning'] == 'on' else '1')
    command = claude_command(request)
    write(folder / 'provider-request.json', {'command': command, 'stdin': request['input'],
        'environment': {k: env[k] for k in ('MAX_THINKING_TOKENS', 'CLAUDE_CODE_MAX_OUTPUT_TOKENS', 'CLAUDE_CODE_DISABLE_THINKING', 'DISABLE_PROMPT_CACHING')},
        'auth': 'claude.ai_subscription', 'external_tools': [], 'structured_output_transport': 'CLAUDE_CODE_JSON_SCHEMA'})
    with tempfile.TemporaryDirectory(prefix='finarch-experiment-') as cwd:
        result = subprocess.run(command, input=encoded(request['input']).decode(), env=env,
                                cwd=cwd, capture_output=True, text=True, timeout=timeout)
    write_text(folder / 'raw-response.json', result.stdout)
    write_text(folder / 'stderr.txt', result.stderr)
    return parse_claude_response(result.stdout, result.stderr, result.returncode)


def parse_claude_response(stdout, stderr='', returncode=0):
    try:
        obj = json.loads(stdout)
        if isinstance(obj, list):
            messages = [row for row in obj if isinstance(row, dict) and row.get('type') == 'result']
            if len(messages) != 1:
                return {'status': 'TRANSPORT_ERROR', 'usage': None, 'error': 'EXPECTED_ONE_CLI_RESULT_MESSAGE'}
            obj = messages[0]
    except ValueError:
        before_call = stderr.startswith('Error: --json-schema is not a valid JSON Schema:')
        return {'status': 'LOCAL_PREFLIGHT_REJECTED' if before_call else 'TRANSPORT_ERROR',
                'returncode': returncode, 'usage': None, 'delivery_status': 'NOT_SENT' if before_call else 'UNKNOWN'}
    if obj.get('is_error') or returncode:
        error = str(obj.get('result', obj.get('errors', obj.get('subtype'))))
        quota = bool(re.search(r'hit your limit|usage limit|out of extra usage|resets?\b', error, re.I))
        limited = bool(re.search(r'rate.limit|429|overloaded', error, re.I))
        auth = bool(re.search(r'disabled Claude subscription access|not logged in|authentication|login required', error, re.I))
        return {'status': 'AUTH_BLOCKED' if auth else 'QUOTA_EXHAUSTED' if quota else 'RATE_LIMITED' if limited else 'PROVIDER_ERROR',
                'error': error, 'usage': obj.get('usage'), 'reported_equivalent_usd': obj.get('total_cost_usd'),
                'retry_after_seconds': 60, 'model_usage': obj.get('modelUsage')}
    parsed = obj.get('structured_output')
    return {'status': 'RECEIVED', 'text': encoded(parsed).decode() if parsed is not None else obj.get('result', ''),
            'usage': obj.get('usage'), 'model_usage': obj.get('modelUsage'),
            'model_version': ','.join((obj.get('modelUsage') or {}).keys()),
            'reported_equivalent_usd': obj.get('total_cost_usd'), 'finish_reason': obj.get('stop_reason', 'success'),
            'cli_subtype': obj.get('subtype'), 'cli_turns': obj.get('num_turns'),
            'reasoning_observation': 'CLI_ENVIRONMENT_REQUESTED_NOT_INDEPENDENTLY_VERIFIED'}


def call(model, request, folder, timeout):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        validate_request(request)
        control = cache_policy.control(model)
        write(folder / 'cache-control.json', control)
        cache_policy.require_control(model)
        if model['transport'] == 'codex_cli':
            codex_call = __import__('finarch.experiments.01-evaluation.03-execution.codex_cli', fromlist=['call']).call
            result = codex_call(model, request, folder, timeout)
        elif model['transport'] == 'gemini_free_api':
            result = gemini_call(model, request, folder, timeout)
        elif model['transport'] == 'claude_code':
            result = claude_call(model, request, folder, timeout)
        elif model['transport'] == 'anthropic_api':
            anthropic_call = __import__('finarch.experiments.01-evaluation.03-execution.anthropic_api', fromlist=['call']).call
            result = anthropic_call(model, request, folder, timeout)
        elif model['transport'] == 'openai_responses':
            openai_call = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['call']).call
            result = openai_call(model, request, folder, timeout)
        elif model['transport'] == 'orca_api':
            orca_call = __import__('finarch.experiments.01-evaluation.03-execution.orca_api', fromlist=['call']).call
            result = orca_call(model, request, folder, timeout)
        else:
            raise ValueError('UNKNOWN_EXPERIMENT_TRANSPORT')
    except cache_policy.CachePolicyError as error:
        result = {'status': 'CACHE_POLICY_BLOCKED', 'delivery_status': 'NOT_SENT',
                  'error': str(error), 'cache_control': error.check, 'usage': None}
    except subprocess.TimeoutExpired as error:
        for name, value in [('raw-response.partial.txt', error.stdout), ('stderr.partial.txt', error.stderr)]:
            if value:
                write_text(folder / name, value.decode(errors='replace') if isinstance(value, bytes) else value)
        result = {'status': 'UNKNOWN_DELIVERY', 'error_type': type(error).__name__, 'usage': None}
    except (TimeoutError, urllib.error.URLError) as error:
        result = {'status': 'UNKNOWN_DELIVERY', 'error_type': type(error).__name__, 'usage': None}
    except Exception as error:
        result = {'status': 'LOCAL_ERROR', 'error_type': type(error).__name__, 'error': str(error), 'usage': None}
    received = result['status'] == 'RECEIVED'
    if received:
        try:
            parsed = json.loads(result.pop('text'))
            errors = response_errors(parsed, request)
            result.update(response=parsed, schema_errors=errors)
            if result.get('finish_reason') in ('MAX_TOKENS', 'max_tokens', 'length'):
                result['status'] = 'OUTPUT_TRUNCATED'
            else:
                result.update(status='INVALID_RESPONSE' if errors else 'VALID')
        except Exception as error:
            result.update(status='OUTPUT_TRUNCATED' if result.get('finish_reason') == 'length' else 'INVALID_RESPONSE', validation_error_type=type(error).__name__)
    if received or result.get('usage') is not None or (model['transport'] == 'openai_responses' and result.get('http_status') == 200):
        cache_policy.enforce_result(model, result)
    if request.get('output_budget'):
        result.update(max_output_tokens=request['max_output_tokens'], output_budget=request['output_budget'])
    write(folder / 'result.json', result)
    return result
