"""One isolated Codex subscription process per experimental request."""
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
require_control = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['require_control']).require_control


def environment():
    return {k: v for k, v in os.environ.items() if k not in ('OPENAI_API_KEY', 'CODEX_API_KEY')}


def preflight(model):
    require_control(model)
    binary = shutil.which('codex')
    if not binary:
        raise ValueError('CODEX_CLI_NOT_FOUND')
    auth = subprocess.run([binary, 'login', 'status'], env=environment(), capture_output=True, text=True, timeout=30)
    if auth.returncode or 'Logged in using ChatGPT' not in auth.stdout + auth.stderr:
        raise ValueError('CODEX_CHATGPT_SUBSCRIPTION_REQUIRED')
    return {'status': 'READY', 'auth_method': 'chatgpt', 'billing_mode': 'CODEX_SUBSCRIPTION',
            'api_key_fallback': False, 'cli_version': subprocess.check_output([binary, '--version'], text=True).strip()}


def parse(stdout, stderr='', returncode=0):
    try:
        events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    except ValueError:
        return {'status': 'TRANSPORT_ERROR', 'usage': None, 'error': 'INVALID_CODEX_EVENT_STREAM'}
    completed = [e for e in events if e.get('type') == 'turn.completed']
    usage = completed[-1].get('usage') if len(completed) == 1 else None
    text = '\n'.join(str(e.get('message') or e.get('error') or '') for e in events) + '\n' + stderr
    if returncode or any(e.get('type') == 'turn.failed' for e in events):
        quota = re.search(r'usage limit|hit your limit|quota exceeded|insufficient_quota', text, re.I)
        limited = re.search(r'rate.?limit|429|too many requests', text, re.I)
        unsupported = re.search(r'unsupported|not supported|invalid value|unknown field|invalid_json_schema|Error loading config.toml', text, re.I)
        auth = re.search(r'not logged in|authentication|401|login required', text, re.I)
        return {'status': 'QUOTA_EXHAUSTED' if quota else 'RATE_LIMITED' if limited else
                         'AUTH_BLOCKED' if auth else 'LOCAL_PREFLIGHT_REJECTED' if unsupported else 'PROVIDER_ERROR',
                'error': text[-4000:], 'usage': usage, 'returncode': returncode, 'retry_after_seconds': 60}
    from finarch.shared.providers.cli import parse_output
    try:
        final, usage, _ = parse_output('codex', stdout)
    except Exception as error:
        return {'status': 'TRANSPORT_ERROR', 'usage': usage, 'error': str(error)}
    return {'status': 'RECEIVED', 'text': final, 'usage': usage, 'finish_reason': 'turn.completed'}


def call(model, request, folder, timeout):
    require_control(model)
    validate_request = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['validate_request']).validate_request
    from finarch.shared.providers.cli import build_command, run_process
    validate_request(request)
    effort = request['reasoning_effort']
    with tempfile.TemporaryDirectory(prefix='finarch-experiment-codex-') as temporary:
        work = Path(temporary)
        schema = work / 'response-schema.json'
        policy, audit = work / 'policy.json', work / 'tool-events.jsonl'
        write(schema, request['response_schema'])
        write(policy, {'tools': [], 'skills': []})
        command = build_command({'provider': 'codex', 'model': request['model'], 'effort': effort},
                                shutil.which('codex'), work, schema, policy, audit)
        command[-1:] = ['-c', 'developer_instructions=' + json.dumps(request['prompt']), '-']
        write(folder / 'provider-request.json', {'command': command, 'stdin': request['input'],
              'response_schema': request['response_schema'], 'requested_model': request['model'],
              'reasoning_effort_requested': effort, 'auth': 'chatgpt_subscription',
              'external_tools': [], 'max_output_tokens_applied': False,
              'output_limit_note': 'CLI has no verified per-request output-token cap; configured API cap is not claimed here.'})
        result = run_process(command, encoded(request['input']).decode(), work, timeout, audit)
        write_text(folder / 'raw-response.jsonl', result['stdout'])
        write_text(folder / 'stderr.txt', result['stderr'])
        write(folder / 'process.json', {k: v for k, v in result.items() if k not in ('stdout', 'stderr')})
        try:
            write(folder / 'raw-response.json', [json.loads(s) for s in result['stdout'].splitlines() if s.strip()])
        except ValueError:
            write_text(folder / 'raw-response.json', result['stdout'])
        if audit.exists():
            shutil.copyfile(audit, folder / 'tool-events.jsonl')
        parsed = parse(result['stdout'], result['stderr'], result['exit_code']) if result['state'] == 'EXITED' else {
            'status': 'UNKNOWN_DELIVERY', 'usage': None, 'error': result['state']}
        parsed.update(transport='codex_cli', billing_mode='CODEX_SUBSCRIPTION',
                      incremental_api_charge_usd=0, reasoning_effort_requested=effort,
                      elapsed_seconds=result['elapsed_seconds'], requested_model=request['model'])
        return parsed
