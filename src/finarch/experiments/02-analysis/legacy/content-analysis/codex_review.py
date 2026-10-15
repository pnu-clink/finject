"""Analysis-only Codex subscription runner, independent from solver controls."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
contract = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_contract', fromlist=['*'])
cli = __import__('finarch.experiments.01-evaluation.03-execution.codex_cli', fromlist=['*'])


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
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='finarch-analysis-codex-') as temporary:
        work = Path(temporary)
        schema_file, policy, audit = (work / name for name in ('schema.json', 'policy.json', 'tool-events.jsonl'))
        store.write(schema_file, schema)
        store.write(policy, {'tools': [], 'skills': []})
        command = build_command({'provider': 'codex', 'model': request['model'],
                                 'effort': request['reasoning_effort']}, shutil.which('codex'),
                                work, schema_file, policy, audit)
        command[-1:] = ['-c', 'developer_instructions=' + json.dumps(request['prompt']), '-']
        store.write(destination / 'request.json', request)
        store.write(destination / 'provider-request.json', {
            'command': command, 'input': request['input'], 'response_schema': schema,
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
                errors = (validator or contract.validate)(response, request)
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


def run(root, folder, requests, config):
    from collections import Counter
    auth = preflight()
    results = {}
    pending = []
    for request in requests:
        destination = folder / 'calls' / request['trial_id']
        saved = store.read(destination / 'result.json')
        if saved is not None:
            if store.read(destination / 'request.json') != request:
                raise ValueError('ANALYSIS_REQUEST_CHANGED_AFTER_EXECUTION')
            results[request['trial_id']] = saved
        elif (destination / 'request.json').exists():
            raise ValueError('ANALYSIS_DELIVERY_UNKNOWN_REVIEW_BEFORE_RETRY:' + request['trial_id'])
        else:
            pending.append((request, destination))
    store.event(root, 'CODEX_ANALYSIS_STARTED', stage=folder.name, requests=len(requests),
                pending=len(pending), model=config['model'], reasoning=config['reasoning_effort'], **auth)
    schedule = config.get('schedule', {})
    store.write(folder / 'state.json', {'status': 'RUNNING', 'requests': len(requests),
                 'completed': len(results), 'model': config['model'], 'transport': 'codex_cli'})
    if pending and not results:
        request, destination = pending.pop(0)
        first = call(request, destination, schedule.get('timeout_seconds', 600))
        results[request['trial_id']] = first
        store.event(root, 'CODEX_ANALYSIS_RESPONSE', stage=folder.name, trial_id=request['trial_id'],
                    status=first['status'], completed=1, total=len(requests))
        if first['status'] not in ('VALID', 'INVALID_RESPONSE', 'OUTPUT_TRUNCATED'):
            state = {'status': 'PREFLIGHT_FAILED', 'requests': len(requests), 'completed': 1,
                     'model': config['model'], 'transport': 'codex_cli', 'first_status': first['status']}
            store.write(folder / 'state.json', state)
            return state
    with ThreadPoolExecutor(max_workers=schedule.get('concurrency', 4)) as pool:
        futures = {pool.submit(call, request, destination, schedule.get('timeout_seconds', 600)): request
                   for request, destination in pending}
        for future in as_completed(futures):
            request = futures[future]
            result = future.result()
            results[request['trial_id']] = result
            store.event(root, 'CODEX_ANALYSIS_RESPONSE', stage=folder.name, trial_id=request['trial_id'],
                        status=result['status'], completed=len(results), total=len(requests))
            store.write(folder / 'state.json', {'status': 'RUNNING', 'requests': len(requests),
                         'completed': len(results), 'model': config['model'], 'transport': 'codex_cli'})
    ordered = [results[request['trial_id']] for request in requests]
    store.write_rows(folder / 'results.jsonl', ordered)
    outputs = [p for p in folder.rglob('*') if p.is_file() and p.name != 'state.json']
    state = {'status': 'COLLECTED', 'requests': len(requests), 'completed': len(ordered),
             'statuses': dict(Counter(r['status'] for r in ordered)), 'model': config['model'],
             'reasoning_effort': config['reasoning_effort'], 'transport': 'codex_cli',
             'billing_mode': 'CODEX_SUBSCRIPTION', 'incremental_api_charge_usd': 0,
             'token_cost_estimate_usd': None, 'cache_control': 'PROVIDER_MANAGED_NOT_DISABLED',
             'output_hashes': {str(p.relative_to(folder)): store.file_hash(p) for p in outputs}}
    store.write(folder / 'state.json', state)
    store.event(root, 'CODEX_ANALYSIS_COLLECTED', stage=folder.name, **{k: state[k] for k in ('requests', 'statuses', 'model')})
    return state
