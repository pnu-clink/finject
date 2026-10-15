"""Analysis transports and the separate historical current-conversation recorder."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from collections import Counter
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from finarch.experiments import assets

collect = __import__('finarch.experiments.02-analysis.01-results.results', fromlist=['*'])
store = collect.store
contracts = __import__('finarch.experiments.02-analysis.contracts', fromlist=['*'])
analysis_config = __import__('finarch.experiments.02-analysis.configuration', fromlist=['*'])
codex = __import__('finarch.experiments.02-analysis.backends.codex', fromlist=['*'])
batch = __import__('finarch.experiments.01-evaluation.03-execution.openai_batch', fromlist=['*'])
timing = __import__('finarch.experiments.02-analysis.timing', fromlist=['*'])
scheduler = __import__('finarch.experiments.02-analysis.scheduler', fromlist=['*'])
INSTRUCTIONS = assets.prompt_text('analysis_common')
STAGE_LABELS = {'02_comparison': 'A02', '03_research': 'A03', '04_quadrant': 'A04'}
ADMISSION_BLOCKERS = {'AUTH_BLOCKED', 'QUOTA_EXHAUSTED', 'RATE_LIMITED',
                      'LOCAL_PREFLIGHT_REJECTED', 'CACHE_POLICY_ERROR', 'CACHE_HASH_MISMATCH'}


def record(root, stage, schema, output, evidence_files, response_ids):
    root = Path(root).resolve()
    config = store.read(root / 'config.json')['analysis']
    if config.get('backend') != 'codex' or config.get('execution_mode') != 'current_session':
        raise ValueError('THIS_RECORDER_REQUIRES_CURRENT_CODEX_SESSION')
    folder = root / collect.ANALYSIS / stage
    prompt = ('# Current-session analysis instructions\n\n'
              'Audit record of this conversation; no separate model request was sent.\n\n' + INSTRUCTIONS)
    store.write_text(folder / 'prompt.md', prompt)
    store.write(folder / 'schema.json', schema)
    record_path = 'calls/current-session.json'
    store.write(folder / record_path, {'record_kind': 'CURRENT_CODEX_CONVERSATION_ANALYSIS',
        'recorded_at': store.now(), 'separate_model_invocation': False, 'actual_model_id': None,
        'external_model_calls': 0, 'api_usage': None, 'output': output})
    store.write_rows(folder / 'manifest.jsonl', [{'analysis_id': root.name + ':' + stage,
        'method': collect.METHOD, 'backend': 'codex', 'execution_mode': 'current_session',
        'prompt': 'prompt.md', 'schema': 'schema.json', 'record': record_path,
        'response_ids': sorted(set(response_ids)),
        'evidence_files': {p: store.file_hash(collect.source_file(root, p)) for p in evidence_files},
        'prompt_sha256': store.file_hash(folder / 'prompt.md'),
        'schema_sha256': store.file_hash(folder / 'schema.json'),
        'record_sha256': store.file_hash(folder / record_path)}])


def configuration(root):
    config = analysis_config.read(root)
    backend = config.get('backend')
    if backend not in ('codex', 'api') or backend not in config.get('backends', {}):
        raise ValueError('CONFIGURED_ANALYSIS_BACKEND_REQUIRED')
    return config, config['backends'][backend]


def request(root, stage, item_id, prompt, schema, payload):
    config, model = configuration(root)
    Draft202012Validator.check_schema(schema)
    if not schema.get('properties') or not prompt.strip():
        raise ValueError('ANALYSIS_PROMPT_AND_SCHEMA_REQUIRED')
    body = {'stage': stage, 'item_id': item_id, 'model': model['model'],
            'reasoning_effort': model['reasoning_effort'], 'prompt': prompt,
            'response_schema': schema, 'input': payload,
            'max_output_tokens': model.get('max_output_tokens')}
    if config['backend'] == 'codex':
        body['codex_config'] = model.get('profile', {}).get('config_overrides', {})
    body['trial_id'] = store.digest({'backend': config['backend'], 'request': body})[:32]
    return body


def freeze(root, stage, requests):
    folder = Path(root) / collect.ANALYSIS / stage
    manifest = folder / 'manifest.jsonl'
    if manifest.exists():
        if store.rows(manifest) != requests:
            raise ValueError('ANALYSIS_MANIFEST_CHANGED:' + stage)
    else:
        store.write_rows(manifest, requests)
        if requests:
            store.write_text(folder / 'prompt.md', requests[0]['prompt'])
            store.write(folder / 'schema.json', requests[0]['response_schema'])
    return folder


def attempts(folder, req):
    return sorted((folder / 'calls' / req['trial_id']).glob('attempt-*/result.json'))


def latest(folder, req):
    paths = attempts(folder, req)
    if not paths:
        return None
    value = store.read(paths[-1])
    if store.read(paths[-1].with_name('request.json')) != req:
        raise ValueError('ANALYSIS_REQUEST_CHANGED_AFTER_EXECUTION')
    return value


def recoverable_schema_rejection(folder, req, saved):
    """Retry only a proven rejected request after a concrete wire-schema correction."""
    if not saved or saved['status'] != 'LOCAL_PREFLIGHT_REJECTED':
        return False
    error = saved.get('error', '')
    corrected_reason = (all(marker in error for marker in ('invalid_json_schema', 'uniqueItems', 'not permitted'))
                        or all(marker in error for marker in ('invalid_json_schema', "must have a 'type' key")))
    if not corrected_reason:
        return False
    previous = attempts(folder, req)[-1].parent
    wire = store.read(previous / 'provider-request.json', {}).get('response_schema')
    corrected = codex.wire_schema.for_openai(req['response_schema'])
    # The prior wire schema may already contain other provider-only adaptations
    # (for example, uniqueItems removal). A retry is safe when the corrected wire
    # schema is demonstrably different from that preserved provider request.
    if wire == corrected:
        return False
    store.write(previous / 'recovery.json', {
        'status': 'SCHEMA_REJECTED_BEFORE_GENERATION_WIRE_ADAPTER_CORRECTED',
        'previous_schema_sha256': store.digest(wire), 'corrected_schema_sha256': store.digest(corrected),
        'canonical_schema_unchanged': True, 'original_attempt_preserved': True})
    return True


@timing.recorded('state_persistence')
def write_state(root, folder, requests, backend):
    saved = [(req, r) for req in requests if (r := latest(folder, req)) is not None]
    results = [r for _, r in saved]
    valid = sum(r['status'] == 'VALID' for r in results)
    state = {'status': 'COLLECTED' if valid == len(requests) else 'PARTIAL' if len(results) == len(requests) else 'RUNNING',
             'requests': len(requests), 'completed': len(results), 'valid': valid,
             'pending': len(requests)-len(results), 'statuses': dict(Counter(r['status'] for r in results)),
             'unresolved_trial_ids': [req['trial_id'] for req, r in saved if r['status'] == 'UNKNOWN_DELIVERY'],
             'backend': backend, 'execution_mode': 'codex_cli' if backend == 'codex' else 'openai_batch',
             'model': requests[0]['model'] if requests else None,
             'reasoning_effort': requests[0]['reasoning_effort'] if requests else None,
             'new_target_model_calls': 0, 'updated_at': store.now()}
    store.write(folder / 'state.json', state)
    store.write_rows(folder / 'results.jsonl', results)
    return state


def run_codex(root, folder, requests, config, *, recovery_retry_ids=None):
    """Resume complete calls and replay an uncertain timeout only with saved authorization."""
    retryable = {'INVALID_RESPONSE', 'OUTPUT_TRUNCATED', 'TRANSIENT_ERROR'}
    limit = config.get('technical_retry_limit', 1)
    authorized_timeouts = analysis_config.authorized_unknown_delivery_retries(root, folder.name, config)
    recovery = __import__('finarch.experiments.02-analysis.recovery', fromlist=['*'])
    policy = store.read(Path(root) / '02_analysis/retry-policy.json', {})
    managed_recovery = policy.get('enabled') and folder.name in policy.get('stages', [])
    reviews = __import__('finarch.experiments.02-analysis.02-comparison.response_assessments', fromlist=['*'])
    review_ids = reviews.recheck_trials(requests, __import__(__name__, fromlist=['*']), folder) if folder.name == '02_comparison' else None
    pending = []
    deferred = {}
    for req in requests:
        saved = latest(folder, req)
        if saved and review_ids is not None and req['trial_id'] not in review_ids:
            # Completed reviews and unavailable target outputs never trigger re-review.
            continue
        if recovery_retry_ids is not None and req['trial_id'] not in recovery_retry_ids:
            # A recovery wave admits only its recorded failed-request IDs.
            continue
        if saved and saved['status'] != 'VALID':
            deferred[req['trial_id']] = saved['status']
        if (managed_recovery and recovery_retry_ids is None
                and recovery.reason(folder, req, saved, recovery.allowed_statuses(policy, folder, req))):
            # Existing eligible failures must enter the stage backoff, not bypass it.
            deferred[req['trial_id']] = saved['status']
            continue
        recovery_replay = False
        if req['trial_id'] in (recovery_retry_ids or set()):
            recovery_replay = bool(recovery.reason(folder, req, saved, recovery.allowed_statuses(policy, folder, req)))
        if saved and saved.get('status') == 'UNKNOWN_DELIVERY' and saved.get('error') == 'INTERRUPTED':
            interruption = store.read(attempts(folder, req)[-1].with_name('interruption.json'), {})
            if (interruption.get('stopped_at') and interruption.get('automatic_replay') is False
                    and req['trial_id'] not in authorized_timeouts):
                deferred[req['trial_id']] = saved['status']
                continue
        schema_recovery = recoverable_schema_rejection(folder, req, saved)
        if saved and saved.get('status') == 'UNKNOWN_DELIVERY' and saved.get('error') == 'TIMEOUT':
            process = store.read(attempts(folder, req)[-1].with_name('process.json'), {})
            if process.get('state') == 'TIMEOUT' and process.get('ended_at') and process.get('exit_code') is not None:
                if req['trial_id'] not in authorized_timeouts and not recovery_replay:
                    # Preserve the uncertain request; unrelated unsent work can continue.
                    deferred[req['trial_id']] = saved['status']
                    continue
                store.event(root, 'ANALYSIS_UNKNOWN_DELIVERY_RETRY_STARTED', stage=folder.name,
                            trial_id=req['trial_id'], previous_attempt=len(attempts(folder, req)))
        timeout_replay = bool(saved and saved.get('status') == 'UNKNOWN_DELIVERY'
                              and saved.get('error') in ('TIMEOUT', 'INTERRUPTED')
                              and req['trial_id'] in authorized_timeouts)
        if managed_recovery and recovery_retry_ids is None and saved and saved['status'] in retryable:
            # Saved item failures stay deferred even when their retry scope is not authorized.
            continue
        if saved and saved['status'] not in retryable | {'VALID'} and not schema_recovery and not timeout_replay and not recovery_replay:
            if saved['status'] in ADMISSION_BLOCKERS:
                state = write_state(root, folder, requests, 'codex') | {'status': 'BLOCKED', 'reason': saved['status']}
                store.write(folder / 'state.json', state)
                return state
            # A failed item is retained, not replayed, while unrelated fresh work continues.
            deferred[req['trial_id']] = saved['status']
            continue
        if saved and (saved['status'] == 'VALID' or (saved['status'] not in retryable and not schema_recovery and not timeout_replay and not recovery_replay)
                      or (len(attempts(folder, req)) > limit and not timeout_replay and not recovery_replay)):
            continue
        pending.append(req)
    if not pending:
        state = write_state(root, folder, requests, 'codex')
        if deferred:
            state.update(status='BLOCKED', reason='UNKNOWN_DELIVERY' if
                         'UNKNOWN_DELIVERY' in deferred.values() else 'DEFERRED_REQUEST_FAILURES')
            store.write(folder / 'state.json', state)
        return state
    with timing.measure(root, 'codex_auth', stage=folder.name):
        auth = codex.preflight()
    store.event(root, 'ANALYSIS_CODEX_STARTED', stage=folder.name, pending=len(pending), **auth)
    mark_running(root, folder, requests)
    timeout = scheduler.policy(root, config)['timeout_seconds']

    def execute(req):
        while True:
            number = len(attempts(folder, req)) + 1
            dest = folder / 'calls' / req['trial_id'] / f'attempt-{number:03d}'
            if dest.exists():
                raise ValueError('ANALYSIS_DELIVERY_UNKNOWN:' + req['trial_id'])
            with timing.measure(root, 'model_call', stage=folder.name, trial_id=req['trial_id'],
                                attempt=number, backend='codex') as measured:
                try:
                    result = codex.call(req, dest, timeout, validator=contracts.validate_response)
                except Exception as error:
                    # Preserve an uncertain invocation; never replay it automatically.
                    store.write(dest / 'request.json', req)
                    result = {'trial_id': req['trial_id'], 'status': 'UNKNOWN_DELIVERY',
                              'error': str(error), 'usage': None, 'transport': 'codex_cli'}
                    store.write(dest / 'result.json', result)
                measured['result_status'] = result['status']
            if result['status'] not in retryable or number > limit or managed_recovery:
                # Managed stages accumulate failures for the recovery wave after fresh work.
                return result

    control = scheduler.Controller(root, folder.name, config, len(pending))
    # Submit the configured concurrency immediately; validate every returned response.
    remaining = iter(pending)
    queued = len(pending)
    stopped = None
    try:
        # Threads are created lazily; only current_limit requests are submitted.
        with ThreadPoolExecutor(max_workers=1) as persistence, ThreadPoolExecutor(max_workers=len(pending)) as pool:
            futures = {}
            saved_state = None
            def refill():
                nonlocal queued
                while not stopped and queued and len(futures) < control.limit:
                    req = next(remaining)
                    futures[pool.submit(execute, req)] = req
                    queued -= 1
            while futures or (queued and not stopped):
                control.tick(queued + len(futures), stopped=bool(stopped))
                refill()
                control.publish(len(futures), queued, 'DRAINING' if stopped else 'RUNNING', deferred=deferred)
                completed, _ = wait(futures, timeout=1, return_when=FIRST_COMPLETED)
                responses = []
                for future in completed:
                    futures.pop(future)
                    result = future.result()
                    if result['status'] != 'VALID':
                        deferred[result['trial_id']] = result['status']
                    else:
                        deferred.pop(result['trial_id'], None)
                    if result['status'] in ADMISSION_BLOCKERS:
                        stopped = result['status']
                    responses.append(result)
                # Refill freed slots before disk aggregation; its cost must not throttle admission.
                refill()
                control.publish(len(futures), queued, 'DRAINING' if stopped else 'RUNNING', deferred=deferred)
                for result in responses:
                    store.event(root, 'ANALYSIS_RESPONSE', stage=folder.name,
                                trial_id=result['trial_id'], status=result['status'])
                if saved_state is not None and saved_state.done():
                    saved_state.result()
                    saved_state = None
                if completed:
                    if saved_state is None:
                        saved_state = persistence.submit(write_state, root, folder, requests, 'codex')
            if saved_state is not None:
                saved_state.result()
    except BaseException:
        control.publish(0, queued, 'INTERRUPTED')
        raise
    control.publish(0, queued, 'BLOCKED' if stopped or deferred else 'COMPLETE', deferred=deferred)
    state = write_state(root, folder, requests, 'codex')
    if stopped or deferred:
        state.update(status='BLOCKED', reason=stopped or
                     ('UNKNOWN_DELIVERY' if 'UNKNOWN_DELIVERY' in deferred.values() else 'DEFERRED_REQUEST_FAILURES'))
        store.write(folder / 'state.json', state)
    return state


def mark_running(root, folder, requests):
    """Publish resumed state before the first potentially long model call."""
    state = write_state(root, folder, requests, 'codex') | {'status': 'RUNNING'}
    store.write(folder / 'state.json', state)
    current = store.read(root / 'state.json')
    current['analysis'] = {**current.get('analysis', {}), **state, 'stage': STAGE_LABELS[folder.name],
                           'method': collect.METHOD, 'model_call_status': 'RUNNING'}
    current['analysis'].pop('reason', None)
    store.write(root / 'state.json', current)
    collect.render(root, 'analysis', source=root.name,
        status=f"{current['analysis']['stage']}: RUNNING · {state['valid']}/{state['requests']}")
    return state


def api_body(model, req):
    schema = codex.wire_schema.for_openai({k: v for k, v in req['response_schema'].items() if k not in ('$schema', 'title')})
    return {'model': req['model'], 'instructions': req['prompt'],
        'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': store.encoded(req['input']).decode()}]}],
        'reasoning': {'effort': req['reasoning_effort']},
        'text': {'format': {'type': 'json_schema', 'name': 'experiment_relationships', 'strict': True, 'schema': schema}},
        'max_output_tokens': req['max_output_tokens'], 'store': False, 'tools': [],
        'truncation': 'disabled', 'prompt_cache_options': {'mode': 'explicit'}}


def run_api(root, folder, requests, model):
    """Native Batch only, with bounded retries of fully collected technical failures."""
    wire_model = {**model, 'transport': 'openai_batch'}
    config, _ = configuration(root)
    retryable = {'INVALID_RESPONSE', 'OUTPUT_TRUNCATED', 'TRANSIENT_ERROR'}
    for attempt in range(1, config.get('technical_retry_limit', 1) + 2):
        selected = requests if attempt == 1 else [req for req in requests if
            store.read(folder / 'calls' / req['trial_id'] / f'attempt-{attempt-1:03d}' / 'result.json', {}).get('status') in retryable]
        chunks, current, size = [], [], 0
        for req in selected:
            incoming = len(batch.api.wire_encoded(api_body(wire_model, req))) + 200
            if incoming > 180_000_000:
                raise ValueError('ANALYSIS_SINGLE_REQUEST_TOO_LARGE')
            if current and (size + incoming > 180_000_000 or len(current) == 50000):
                chunks.append(current); current, size = [], 0
            current.append(req); size += incoming
        if current:
            chunks.append(current)
        waiting = False
        for index, chunk in enumerate(chunks, 1):
            destination = folder / 'batches' / f'attempt-{attempt:03d}-batch-{index:03d}'
            batch.prepare_job(wire_model, folder / 'manifest.jsonl', destination, chunk, api_body)
            batch.submit(wire_model, destination)
            job = batch.poll(wire_model, destination)
            if job['provider']['status'] not in batch.TERMINAL:
                waiting = True
                continue
            records = batch.outputs(destination, {req['trial_id'] for req in chunk})
            for req in chunk:
                call = folder / 'calls' / req['trial_id'] / f'attempt-{attempt:03d}'
                if (call / 'result.json').exists():
                    if store.read(call / 'request.json') != req:
                        raise ValueError('ANALYSIS_REQUEST_CHANGED_AFTER_EXECUTION')
                    continue
                store.write(call / 'request.json', req)
                if req['trial_id'] in records:
                    record, raw = records[req['trial_id']]
                    store.write_text(call / 'raw-response.jsonl', raw)
                    result = batch.interpret(wire_model, req, record, contracts.validate_response)
                else:
                    result = {'status': 'BATCH_RESULT_MISSING', 'usage': None}
                store.write(call / 'result.json', result | {'trial_id': req['trial_id'], 'batch_id': job['batch_id']})
            job['status'] = 'COLLECTED'
            store.write(destination / 'job.json', job)
        if waiting:
            state = write_state(root, folder, requests, 'api') | {'status': 'RUNNING'}
            store.write(folder / 'state.json', state)
            return state
    return write_state(root, folder, requests, 'api')


def run(root, stage, requests, *, recovery_retry_ids=None):
    control = store.read(Path(root) / 'state.json', {}).get('execution_control', {}).get('analysis', {})
    if control.get('paused'):
        return {'status': 'PAUSED_BY_USER', 'reason': control.get('reason'), 'new_model_calls': 0}
    config, model = configuration(root)
    folder = freeze(root, stage, requests)
    startup = __import__('finarch.experiments.90-operations.execution_start', fromlist=['*'])
    task = ('Analyze original/variant and solving-condition relationships.' if stage == '02_comparison'
            else 'Group research findings only and compare their four solving conditions.' if stage == '04_quadrant'
            else 'Synthesize research findings, counterexamples, and limitations.')
    startup.announce(root, STAGE_LABELS[stage], task,
                     processor='LLM', requests=len(recovery_retry_ids) if recovery_retry_ids is not None else len(requests))
    state = ((run_codex(root, folder, requests, config, recovery_retry_ids=recovery_retry_ids)
              if recovery_retry_ids is not None else run_codex(root, folder, requests, config)) if config['backend'] == 'codex'
             else run_api(root, folder, requests, model))
    return state
