"""Analysis-only Codex subscription runner, independent from solver controls."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
contract = __import__('finarch.experiments.02-analysis.contracts', fromlist=['*'])
cli = __import__('finarch.experiments.01-evaluation.03-execution.codex_cli', fromlist=['*'])
wire_schema = __import__('finarch.experiments.02-analysis.backends.schema', fromlist=['*'])
retry_feedback = __import__('finarch.experiments.02-analysis.retry_feedback', fromlist=['*'])


def preflight():
    binary = shutil.which('codex')
    if not binary:
        raise ValueError('CODEX_CLI_NOT_FOUND')
    result = subprocess.run([binary, 'login', 'status'], env=cli.environment(),
                            capture_output=True, text=True, timeout=30)
    if result.returncode or 'Logged in using ChatGPT' not in result.stdout + result.stderr:
        raise ValueError('ANALYSIS_REQUIRES_CODEX_CHATGPT_LOGIN_NO_API_FALLBACK')
    return {'auth': 'chatgpt_subscription', 'api_fallback': False,
            'cli_version': subprocess.check_output([binary, '--version'], text=True).strip()}


def call(request, destination, timeout, validator=None):
    from jsonschema import Draft202012Validator
    from finarch.shared.providers.cli import build_command, run_process
    schema = request.get('response_schema')
    if not isinstance(schema, dict) or not schema.get('properties') or not request.get('prompt'):
        raise ValueError('ANALYSIS_PROMPT_AND_NONEMPTY_SCHEMA_REQUIRED')
    Draft202012Validator.check_schema(schema)
    feedback = retry_feedback.build(request, destination)
    effective_prompt = retry_feedback.prompt(request['prompt'], feedback)
    destination.mkdir(parents=True, exist_ok=True)
    if feedback is not None:
        store.write(destination / 'retry-feedback.json', feedback)
    with tempfile.TemporaryDirectory(prefix='finarch-analysis-codex-') as temporary:
        work = Path(temporary)
        schema_file, policy, audit = (work / name for name in ('schema.json', 'policy.json', 'tool-events.jsonl'))
        provider_schema = wire_schema.for_openai(schema)
        store.write(schema_file, provider_schema)
        store.write(policy, {'tools': [], 'skills': []})
        command = build_command({'provider': 'codex', 'model': request['model'],
                                 'effort': request['reasoning_effort']}, shutil.which('codex'),
                                work, schema_file, policy, audit)
        from finarch.shared.providers.profiles import CONFIG_KEYS
        overrides = []
        for key, value in sorted(request.get('codex_config', {}).items()):
            if key not in CONFIG_KEYS or type(value) not in (str, int):
                raise ValueError('UNSUPPORTED_ANALYSIS_CODEX_SETTING')
            if key == 'model_reasoning_effort' and value != request['reasoning_effort']:
                raise ValueError('ANALYSIS_CODEX_EFFORT_MISMATCH')
            overrides += ['-c', key + '=' + json.dumps(value)]
        command[-1:] = overrides + ['-c', 'developer_instructions=' + json.dumps(effective_prompt), '-']
        store.write(destination / 'request.json', request)
        store.write(destination / 'provider-request.json', {
            'command': command, 'input': request['input'], 'response_schema': provider_schema,
            'canonical_response_schema': schema,
            'effective_prompt': effective_prompt, 'effective_prompt_sha256': store.digest(effective_prompt),
            'retry_feedback_file': 'retry-feedback.json' if feedback is not None else None,
            'schema_adaptation': 'Unique array items are described to the model and enforced by the canonical Python validator.',
            'auth': 'chatgpt_subscription', 'api_key_fallback': False,
            'requested_model': request['model'], 'reasoning_effort_requested': request['reasoning_effort'],
            'max_output_tokens_applied': False, 'cache_control': 'PROVIDER_MANAGED_NOT_DISABLED',
            'role': 'ANALYSIS_NOT_TARGET_MODEL_EVALUATION'})
        process = run_process(command, store.encoded(request['input']).decode(), work, timeout, audit)
        store.write_text(destination / 'raw-response.jsonl', process['stdout'])
        store.write_text(destination / 'stderr.txt', process['stderr'])
        store.write(destination / 'process.json', {k: v for k, v in process.items() if k not in ('stdout', 'stderr')})
        if audit.exists():
            shutil.copyfile(audit, destination / 'tool-events.jsonl')
        result = cli.parse(process['stdout'], process['stderr'], process['exit_code']) if process['state'] == 'EXITED' else {
            'status': 'UNKNOWN_DELIVERY', 'error': process['state'], 'usage': None}
        if result['status'] == 'RECEIVED':
            try:
                response = json.loads(result.pop('text'))
                errors = (validator or contract.validate_response)(response, request)
                result.update(status='INVALID_RESPONSE' if errors else 'VALID', response=response, schema_errors=errors)
            except (ValueError, TypeError) as error:
                result.update(status='INVALID_RESPONSE', error=str(error))
        result.update(trial_id=request['trial_id'], item_id=request['item_id'], stage=request['stage'],
                      identity_map=request.get('identity_map', {}), requested_model=request['model'],
                      reasoning_effort_requested=request['reasoning_effort'], transport='codex_cli',
                      billing_mode='CODEX_SUBSCRIPTION', incremental_api_charge_usd=0,
                      token_cost_estimate_usd=None, cache_control='PROVIDER_MANAGED_NOT_DISABLED',
                      elapsed_seconds=process['elapsed_seconds'])
        store.write(destination / 'result.json', result)
        return result
