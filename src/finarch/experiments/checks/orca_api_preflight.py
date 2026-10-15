"""Bounded OrcaRouter API preflight using one existing public financial input."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from jsonschema import Draft202012Validator

BASE = 'https://api.orcarouter.ai/v1'
MODEL = 'deepseek/deepseek-v4.1-flash'
ROOT = Path(__file__).resolve().parents[4]
PROVIDERS = importlib.import_module('finarch.experiments.01-evaluation.03-execution.providers')


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded(value))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http(key, url, folder, body=None):
    """PF03: Perform one attempt, preserve raw response, and never retry inference."""
    assert url.startswith(BASE + '/')
    folder.mkdir(parents=True, exist_ok=False)
    headers = {'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
               'Content-Type': 'application/json', 'X-OrcaRouter-Include-Cost': 'true'}
    data = encoded(body).encode() if body is not None else None
    write(folder / 'request.json', {'url': url, 'method': 'POST' if data else 'GET',
                                  'headers': {k: v for k, v in headers.items() if k != 'Authorization'},
                                  'body': body})
    if data:
        (folder / 'request-wire.json').write_bytes(data)
    start = now()
    write(folder / 'started.json', {'started_at': start, 'delivery_status': 'IN_FLIGHT',
                                  'request_sha256': hashlib.sha256(data or url.encode()).hexdigest()})
    began = time.monotonic()
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as response:
            raw, status, response_headers = response.read().decode(), response.status, dict(response.headers)
    except urllib.error.HTTPError as error:
        raw, status, response_headers = error.read().decode(), error.code, dict(error.headers)
    except Exception as error:
        result = {'started_at': start, 'ended_at': now(), 'elapsed_seconds': time.monotonic() - began,
                  'delivery_status': 'UNKNOWN_DELIVERY', 'http_status': None,
                  'error': str(error).replace(key, '[REDACTED]')}
        write(folder / 'result.json', result)
        return result, {}
    raw = raw.replace(key, '[REDACTED]')
    (folder / 'raw-response.json').write_text(raw)
    response_headers = json.loads(json.dumps(response_headers).replace(key, '[REDACTED]'))
    write(folder / 'response-headers.json', response_headers)
    try:
        obj = json.loads(raw)
    except ValueError:
        obj = {}
    result = {'started_at': start, 'ended_at': now(), 'elapsed_seconds': round(time.monotonic() - began, 3),
              'delivery_status': 'RECEIVED', 'http_status': status,
              'request_id': next((v for k, v in response_headers.items() if k.lower() == 'x-orca-request-id'), None),
              'response_id': obj.get('id'), 'returned_model': obj.get('model'),
              'error': obj.get('error')}
    write(folder / 'result.json', result)
    return result, obj


def assess(obj, schema, public_input):
    """PF04: Validate the final JSON separately from provider reasoning/cache evidence."""
    choices = obj.get('choices') or []
    choice = choices[0] if choices else {}
    message = choice.get('message') or {}
    content = message.get('content')
    usage = obj.get('usage') or {}
    trace = message.get('reasoning_content')
    if trace is None:
        trace = message.get('reasoning')
    details = usage.get('completion_tokens_details') or {}
    prompt_details = usage.get('prompt_tokens_details') or {}
    errors, answer = [], None
    try:
        answer = json.loads(content)
        errors = [e.message for e in Draft202012Validator(schema).iter_errors(answer)]
    except (TypeError, ValueError) as error:
        errors = [str(error)]
    quotes = answer.get('evidence', []) if isinstance(answer, dict) else []
    exact_quotes = (not errors and all(isinstance(q, str) and q in public_input['context'] for q in quotes))
    hit = usage.get('prompt_cache_hit_tokens', prompt_details.get('cached_tokens'))
    miss = usage.get('prompt_cache_miss_tokens')
    written = usage.get('cache_creation_input_tokens', prompt_details.get('cache_write_tokens'))
    return {'finish_reason': choice.get('finish_reason'), 'usage': usage,
            'reasoning_trace_present': isinstance(trace, (str, list)) and len(trace) > 0,
            'reasoning_trace_characters': len(trace) if isinstance(trace, str) else None,
            'reasoning_tokens': details.get('reasoning_tokens', usage.get('reasoning_tokens')),
            'cache_read_tokens': hit, 'cache_miss_tokens': miss, 'cache_write_tokens': written,
            'cache_write_status': 'UNKNOWN' if written is None else 'OBSERVED',
            'schema_status': 'PASS' if not errors else 'FAIL', 'schema_errors': errors,
            'evidence_exact_substrings': bool(exact_quotes),
            'answer': answer.get('answer') if isinstance(answer, dict) else None,
            'classification': answer.get('classification') if isinstance(answer, dict) else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--authorization', required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    with args.manifest.open() as f:
        frozen = json.loads(next(f))
    prompt, public_input, schema = frozen.get('prompt'), frozen.get('input'), frozen.get('response_schema')
    if not prompt or not schema or not public_input:
        raise ValueError('NONEMPTY_PROMPT_SCHEMA_AND_PUBLIC_INPUT_REQUIRED')
    if set(public_input) != {'question', 'context', 'answer_format'}:
        raise ValueError('PUBLIC_INPUT_ONLY_REQUIRED')
    Draft202012Validator.check_schema(schema)
    key = PROVIDERS.credential({'key_file': str(ROOT / '.env'), 'key_variable': 'ORCA_API_KEY'})
    if not key.startswith('sk-orca-'):
        raise ValueError('KEY_DOES_NOT_MATCH_DOCUMENTED_ORCAROUTER_FORMAT')
    probe = {'checked_at': now(), 'status': 'RUNNING', 'authorization': args.authorization,
             'scope': 'API_PREFLIGHT_ONLY', 'model': MODEL, 'base_url': BASE,
             'case': frozen['case'], 'variant': frozen['variant'], 'prompt_condition': frozen['prompt_condition'],
             'source_manifest': str(args.manifest.resolve()), 'source_trial_id': frozen['trial_id'],
             'public_input_sha256': hashlib.sha256(encoded(public_input).encode()).hexdigest(),
             'source_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'max_inference_requests': 4, 'max_tokens_per_request': 8192, 'concurrency': 1,
             'reasoning_on_effort': 'low', 'local_inference_retries': 0,
             'cache_off_control': 'NOT_VERIFIED', 'cache_write_usage': 'UNKNOWN_IF_ABSENT',
             'cache_test': 'Two identical requests per reasoning mode; automatic provider caching may occur.',
             'pricing_usd_per_million': {'off_peak': {'input_miss': .15, 'output': .6, 'input_hit': .003},
                                         'peak': {'input_miss': .3, 'output': 1.2, 'input_hit': .006}},
             'sources': ['https://www.orcarouter.ai/models/deepseek/deepseek-v4.1-flash',
                         'https://docs.orcarouter.ai/api-reference/chat/create-a-chat-completion',
                         'https://docs.orcarouter.ai/advanced/reasoning',
                         'https://docs.orcarouter.ai/operations/per-request-cost',
                         'https://api-docs.deepseek.com/guides/thinking_mode/',
                         'https://api-docs.deepseek.com/guides/kv_cache/'], 'requests': []}
    write(root / 'summary.json', probe)
    write(root / 'public-input.json', public_input)
    write(root / 'response-schema.json', schema)
    (root / 'prompt.txt').write_text(prompt)
    catalog_result, catalog = http(key, BASE + '/models', root / 'catalog')
    selected = next((x for x in catalog.get('data', []) if x.get('id') == MODEL), None)
    write(root / 'model.json', selected)
    if catalog_result['http_status'] != 200 or not selected:
        probe.update(status='CATALOG_BLOCKED', catalog_result=catalog_result)
    else:
        response_schema = {k: v for k, v in schema.items() if k not in ('$schema', 'title')}
        messages = [{'role': 'system', 'content': prompt + '\nResponse JSON schema:\n' + encoded(schema)},
                    {'role': 'user', 'content': encoded(public_input)}]
        for index, (mode, repeat) in enumerate([('off', 1), ('off', 2), ('on', 1), ('on', 2)], 1):
            body = {'model': MODEL, 'messages': deepcopy(messages), 'max_tokens': 8192,
                    'stream': False, 'thinking': {'type': 'disabled' if mode == 'off' else 'enabled'},
                    'response_format': {'type': 'json_schema', 'json_schema': {
                        'name': 'financial_answer', 'strict': True, 'schema': response_schema}}}
            if mode == 'on':
                body['reasoning_effort'] = 'low'
            folder = root / ('%02d-%s-%d' % (index, mode, repeat))
            with (root / 'execution.log').open('a') as log:
                log.write(encoded({'event': 'REQUEST_START', 'at': now(), 'request': folder.name,
                                   'model': MODEL, 'reasoning': mode, 'repeat': repeat}))
            result, obj = http(key, BASE + '/chat/completions', folder, body)
            result.update(reasoning=mode, repeat=repeat, artifact=folder.name,
                          **assess(obj, schema, public_input))
            write(folder / 'result.json', result)
            probe['requests'].append(result)
            write(root / 'summary.json', probe)
            with (root / 'execution.log').open('a') as log:
                log.write(encoded({'event': 'REQUEST_END', 'at': now(), 'result': result}))
            print(encoded(result), flush=True)
            if result['http_status'] != 200 or result['finish_reason'] != 'stop':
                probe['status'] = 'STOPPED_AFTER_API_FAILURE'
                break
            if index < 4:
                time.sleep(3)
        else:
            probe['status'] = 'API_REQUESTS_COMPLETE'
    settled = []
    for result in probe['requests']:
        request_id = result.get('request_id')
        if not request_id:
            continue
        receipt_result, receipt = http(key, BASE + '/generation?' + urllib.parse.urlencode({'id': request_id}),
                                       root / 'receipts' / result['artifact'])
        data = receipt.get('data') or {}
        result['settled_cost_http_status'] = receipt_result['http_status']
        result['settled_cost_usd'] = data.get('total_cost')
        if receipt_result['http_status'] == 200 and data.get('total_cost') is not None:
            settled.append(Decimal(str(data['total_cost'])))
        write(root / result['artifact'] / 'result.json', result)
    probe['finished_at'] = now()
    probe['inference_requests_sent'] = len(probe['requests'])
    probe['settled_cost_usd'] = str(sum(settled, Decimal(0))) if len(settled) == len(probe['requests']) else None
    write(root / 'summary.json', probe)
    template = (ROOT / 'src/finarch/experiments/templates/api-preflight-readme-template.md').read_text()
    (root / 'README.md').write_text(template.format(model=MODEL, status=probe['status'],
        checked_at=probe['finished_at'], requests=probe['inference_requests_sent'], cost=probe['settled_cost_usd']))
    print(encoded({'output': str(root), 'status': probe['status'],
                   'requests': probe['inference_requests_sent'], 'settled_cost_usd': probe['settled_cost_usd']}))


if __name__ == '__main__':
    main()
