"""Qwen chat payloads; private labels and reference answers never enter messages."""
import json


def body(request, runtime):
    mode = request['reasoning']
    schema = request['response_schema']
    if not schema or not schema.get('properties'):
        raise ValueError('NONEMPTY_RESPONSE_SCHEMA_REQUIRED')
    return {'model': runtime.get('served_model', request['model']), 'messages': [
        {'role': 'system', 'content': request['prompt'] + '\n\nResponse JSON Schema:\n' + json.dumps(schema, ensure_ascii=False)},
        {'role': 'user', 'content': json.dumps(request['input'], ensure_ascii=False)}],
        'max_tokens': request['max_output_tokens'], **runtime['sampling'][mode],
        'top_k': runtime['top_k'], 'min_p': runtime['min_p'], 'seed': runtime['seed'],
        'chat_template_kwargs': {'enable_thinking': mode == 'on'},
        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'financial_answer', 'schema': schema}}}
