"""Prepare, run, resume and report experiments through one Python entry point."""
import argparse
import concurrent.futures
import json
import time
from pathlib import Path

run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
settings = __import__('finarch.experiments.90-operations.settings', fromlist=['*'])
from finarch.paths import SOURCE

answer_format = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['*'])
cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
output_budget = __import__('finarch.experiments.01-evaluation.03-execution.output_budget', fromlist=['*'])
dataset = __import__('finarch.experiments.00-input.dataset', fromlist=['*'])
request_order = __import__('finarch.experiments.01-evaluation.02-request.request_order', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])
PROJECT = __import__('finarch.experiments.90-operations.storage', fromlist=['PROJECT']).PROJECT
allocate = __import__('finarch.experiments.90-operations.storage', fromlist=['allocate']).allocate
configuration = __import__('finarch.experiments.90-operations.storage', fromlist=['configuration']).configuration
digest = __import__('finarch.experiments.90-operations.storage', fromlist=['digest']).digest
encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
locked = __import__('finarch.experiments.90-operations.storage', fromlist=['locked']).locked
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_rows = __import__('finarch.experiments.90-operations.storage', fromlist=['write_rows']).write_rows


def prepare(config_path, reserved_root=None):
    preparation = __import__('finarch.experiments.01-evaluation.01-preparation.prepare', fromlist=['*'])
    return preparation.prepare(config_path, reserved_root=reserved_root, allocator=allocate)


def verify(root):
    storage = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
    storage.verify(root)


def recover_local_parser_errors(root):
    """Recover a known CLI envelope error from saved bytes without another model call."""
    config = configuration(root)
    for model in config['models']:
        if model['transport'] != 'claude_code':
            continue
        for path in call_layout.all_results(run_layout.execution(root, model['key'])):
            old = read(path)
            raw = path.parent / 'raw-response.json'
            if old.get('status') == 'LOCAL_ERROR' and old.get('error_type') == 'AttributeError' and raw.exists():
                result = providers.parse_claude_response(raw.read_text())
                if result['status'] == 'RECEIVED':
                    from jsonschema import Draft202012Validator
                    try:
                        parsed = json.loads(result.pop('text'))
                        errors = answer_format.response_errors(parsed, read(path.parent / 'request.json'))
                        result.update(status='INVALID_RESPONSE' if errors else 'VALID', response=parsed, schema_errors=errors)
                    except Exception as error:
                        result.update(status='INVALID_RESPONSE', validation_error_type=type(error).__name__)
                write(path.parent / 'result-before-parser-recovery.json', old)
                write(path, result)
                event(root, 'LOCAL_PARSER_RECOVERY', model=model['key'], path=str(path.relative_to(root)),
                      status=result['status'], new_model_calls=0)


def observed_provider_limits(root, model_key):
    limits = {}
    for path in call_layout.all_results(run_layout.execution(root, model_key)):
        error = read(path).get('error')
        if not isinstance(error, dict):
            continue
        for detail in error.get('details', []):
            for item in detail.get('violations', []):
                value = item.get('quotaValue', '')
                if not str(value).isdigit():
                    continue
                for marker, key in [('RequestsPerMinute', 'requests_per_minute'), ('RequestsPerDay', 'requests_per_day')]:
                    if marker in item.get('quotaId', ''):
                        limits[key] = int(value)
    return limits


def run(root, selected=None, resume_limits=False, max_new=None, preflight=None):
    root = Path(root).resolve()
    if read(root / 'config.json').get('run_kind') == 'ANALYSIS_ONLY':
        raise ValueError('ANALYSIS_ONLY_RUN_CANNOT_EXECUTE_EVALUATION')
    with locked(root / '.pipeline.lock'):
        control = read(root / 'state.json').get('execution_control', {}).get('evaluation', {})
        if control.get('paused'):
            return {'run_id': root.name, 'status': 'PAUSED_BY_USER', 'models': [],
                    'reason': control.get('reason'), 'new_model_calls': 0}
        verify(root)
        if preflight is not None:
            preflight()
        recover_local_parser_errors(root)
        config, state = configuration(root), read(root / 'state.json')
        schedule = config['schedule']
        state['status'] = 'RUNNING'
        write(root / 'state.json', state)
        completed = 0
        for model in config['models']:
            key = model['key']
            if selected and key not in selected:
                continue
            model_state = state['models'][key]
            budget = output_budget.policy_for(root, model)
            if model_state.get('status') in ('CACHE_POLICY_VIOLATION', 'CACHE_USAGE_UNVERIFIED'):
                continue
            if model['transport'] in ('openai_responses', 'orca_api') and model_state.get('status') == 'UNKNOWN_DELIVERY':
                continue
            if model['transport'] == 'codex_cli':
                run_model = __import__('finarch.experiments.01-evaluation.03-execution.local_schedule', fromlist=['run_model']).run_model
                completed += run_model(root, model, state, schedule, max_new, resume_limits)
                write(root / 'state.json', state)
                continue
            if model['transport'] == 'gemini_batch':
                process = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['process']).process
                process(root, model, state, reporting.build)
                write(root / 'state.json', state)
                continue
            if model['transport'] == 'openai_batch':
                process = __import__('finarch.experiments.01-evaluation.03-execution.openai_batch', fromlist=['process']).process
                process(root, model, state)
                write(root / 'state.json', state)
                continue
            if model['transport'] == 'anthropic_batch':
                process = __import__('finarch.experiments.01-evaluation.03-execution.anthropic_batch', fromlist=['process']).process
                process(root, model, state)
                write(root / 'state.json', state)
                continue
            model_state.update(observed_provider_limits(root, key))
            if model_state.get('requests_per_minute'):
                model_state['concurrency'] = min(model_state.get('concurrency', schedule['concurrency']),
                                                 model_state['requests_per_minute'], schedule['fallback_group_size'])
            requests = rows(run_layout.requests(root, key))
            latest_results = [read(paths[-1]) for request in requests
                              if (paths := call_layout.result_paths(run_layout.execution(root, key), request))]
            auth_blocked = [r for r in latest_results if r.get('status') == 'AUTH_BLOCKED']
            if auth_blocked and not resume_limits:
                model_state.update(status='AUTH_BLOCKED', reason=auth_blocked[-1]['error'])
                continue
            if auth_blocked and resume_limits:
                model_state['first_call_checked'] = False
            if model_state.get('status') in ('QUOTA_EXHAUSTED', 'PAUSED_RATE_LIMIT') and not resume_limits:
                continue
            if model_state.get('status') in ('QUOTA_EXHAUSTED', 'PAUSED_RATE_LIMIT') and resume_limits:
                model_state['first_call_checked'] = False
            try:
                model_state['preflight'] = providers.preflight(model)
            except cache_policy.CachePolicyError as error:
                model_state.update(status='CACHE_POLICY_BLOCKED', reason=str(error), preflight=error.check)
                write(run_layout.execution(root, key) / 'cache-preflight.json', error.check)
                event(root, 'CACHE_POLICY_BLOCKED', model=key, reason=str(error), new_model_calls=0)
                write(root / 'state.json', state)
                continue
            except Exception as error:
                model_state.update(status='PREFLIGHT_BLOCKED', reason=str(error))
                event(root, 'PREFLIGHT_BLOCKED', model=key, reason=str(error))
                write(root / 'state.json', state)
                continue
            requests = rows(run_layout.requests(root, key))
            pending = []
            for request in requests:
                attempts = call_layout.attempt_dirs(run_layout.execution(root, key), request)
                last = read(attempts[-1] / 'result.json') if attempts else None
                if attempts and last is None:
                    # A previous process may have transmitted this request before stopping.
                    write(attempts[-1] / 'result.json', {'status': 'UNKNOWN_DELIVERY', 'usage': None})
                    continue
                local_schema_failure = (last is not None and last['status'] in ('TRANSPORT_ERROR', 'LOCAL_PREFLIGHT_REJECTED')
                    and (attempts[-1] / 'stderr.txt').exists()
                    and (attempts[-1] / 'stderr.txt').read_text().startswith('Error: --json-schema is not a valid JSON Schema:'))
                if local_schema_failure:
                    write(attempts[-1] / 'recovery.json', {'status': 'SAFE_TO_RETRY_LOCAL_PREFLIGHT_FAILURE',
                        'reason': 'CLI rejected the schema dialect before a model request; original artifacts preserved.',
                        'at': now()})
                retry_transient = last and (last['status'] == 'TRANSIENT_ERROR' or
                    (last['status'] == 'PROVIDER_ERROR' and last.get('http_status') in (500, 502, 503, 504)))
                if model['transport'] == 'orca_api' and last and last.get('delivery_status') in ('UNKNOWN', 'UNCONFIRMED'):
                    continue
                retry_length = output_budget.retry_truncated(budget, request, attempts)
                retry_auth = (resume_limits and last and last['status'] == 'AUTH_BLOCKED'
                              and (model['transport'] != 'orca_api' or last.get('delivery_status') == 'REJECTED'))
                if last is None or local_schema_failure or retry_transient or retry_length or last['status'] in ('RATE_LIMITED', 'QUOTA_EXHAUSTED') or retry_auth:
                    pending.append((request, len(attempts)))
            if not pending:
                model_state['status'] = 'FINISHED'
                continue
            width = model_state.get('concurrency', min(schedule['concurrency'], model.get('local_concurrency_cap', schedule['concurrency'])))
            model_state.update(status='RUNNING', concurrency=width)
            if resume_limits:
                model_state.pop('reason', None)
            local_attempts = {}
            while pending:
                remaining = model_state.get('next_wave_not_before', 0) - time.time()
                while remaining > 0:
                    time.sleep(min(1, remaining))
                    remaining = model_state.get('next_wave_not_before', 0) - time.time()
                if max_new is not None and completed >= max_new:
                    model_state['status'] = 'PAUSED_CALL_CAP'
                    break
                size = min(width, max_new - completed) if max_new is not None else width
                # Probe one actual request before a broad wave on a new provider run.
                if (model['transport'] == 'openai_responses' and
                        set(model_state.get('cache_verified_reasoning_modes', [])) != set(config['reasoning_modes'])):
                    size = 1
                elif (model['transport'] == 'orca_api' and
                      set(model_state.get('validated_reasoning_modes', [])) != set(config['reasoning_modes'])):
                    size = 1
                elif not model_state.get('first_call_checked'):
                    size = 1
                wave, pending = pending[:size], pending[size:]
                retries = []
                length_retries = []
                event(root, 'WAVE_START', model=key, requests=len(wave), concurrency=width)
                stopped = None
                preserved_disconnects, received_responses = [], 0
                retry_delay = schedule['retry_delay_seconds']
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(wave)) as pool:
                    futures = {}
                    for request, previous in wave:
                        folder = call_layout.attempt_path(run_layout.execution(root, key), request, previous + 1)
                        prior_attempts = call_layout.attempt_dirs(run_layout.execution(root, key), request)
                        call_model, call_request = output_budget.prepare_attempt(model, request, budget, prior_attempts)
                        write(folder / 'request.json', call_request)
                        implementation = {str(p.relative_to(PROJECT)): file_hash(p) for p in (SOURCE / 'experiments').rglob('*.py')}
                        if model['transport'] == 'openai_responses':
                            adapter = PROJECT / 'src/finarch/experiments/01-evaluation/03-execution/openai_api.py'
                            implementation[str(adapter.relative_to(PROJECT))] = file_hash(adapter)
                        if model['transport'] == 'anthropic_api':
                            adapter = PROJECT / 'src/finarch/experiments/01-evaluation/03-execution/anthropic_api.py'
                            implementation[str(adapter.relative_to(PROJECT))] = file_hash(adapter)
                        write(folder / 'started.json', {'at': now(), 'status': 'STARTED',
                            'transport': model['transport'], 'implementation_sha256': implementation,
                            'max_output_tokens': call_request['max_output_tokens'],
                            **({'output_budget': call_request['output_budget']} if budget else {})})
                        if budget:
                            event(root, 'OUTPUT_BUDGET_ATTEMPT', model=key, trial_id=request['trial_id'],
                                  attempt=previous + 1, max_output_tokens=call_request['max_output_tokens'],
                                  reason=call_request['output_budget']['reason'])
                        futures[pool.submit(providers.call, call_model, call_request, folder, schedule['timeout_seconds'])] = (request, previous)
                    for future in concurrent.futures.as_completed(futures):
                        request, previous = futures[future]
                        result = future.result()
                        completed += 1
                        trial = request['trial_id']
                        local_attempts[trial] = local_attempts.get(trial, 0) + 1
                        event(root, 'CALL_END', model=key, trial_id=trial, status=result['status'], attempt=previous + 1)
                        if result['status'] in ('VALID', 'INVALID_RESPONSE', 'OUTPUT_TRUNCATED'):
                            received_responses += 1
                        attempts = call_layout.attempt_dirs(run_layout.execution(root, key), request)
                        retry_length = output_budget.retry_truncated(budget, request, attempts)
                        if retry_length:
                            length_retries.append((request, previous + 1))
                            event(root, 'OUTPUT_BUDGET_INCREASED', model=key, trial_id=trial,
                                  previous_attempt=previous + 1,
                                  max_output_tokens=output_budget.next_limit(budget, request, attempts)[0])
                        if model['transport'] == 'orca_api':
                            modes = set(model_state.get('validated_reasoning_modes', []))
                            if result['status'] == 'VALID':
                                modes.add(request['reasoning'])
                                model_state['validated_reasoning_modes'] = sorted(modes)
                            elif (set(config['reasoning_modes']) != modes
                                  and result['status'] in ('INVALID_RESPONSE', 'OUTPUT_TRUNCATED') and not retry_length):
                                stopped = stopped or 'PROVIDER_BLOCKED'
                                model_state['reason'] = 'ORCA_REASONING_PROBE_VALIDATION_FAILED'
                        if model['transport'] == 'openai_responses' and result.get('cache_check', {}).get('status') == 'VERIFIED_ZERO':
                            modes = set(model_state.get('cache_verified_reasoning_modes', []))
                            modes.add(request['reasoning'])
                            model_state['cache_verified_reasoning_modes'] = sorted(modes)
                        if result['status'] in ('QUOTA_EXHAUSTED', 'RATE_LIMITED', 'TRANSIENT_ERROR'):
                            retries.append((request, previous + 1))
                            width = min(width, schedule['fallback_group_size'])
                            model_state['concurrency'] = width
                            retry_delay = max(retry_delay, result.get('retry_after_seconds', 0))
                            if result.get('requests_per_minute'):
                                model_state['requests_per_minute'] = result['requests_per_minute']
                                width = min(width, result['requests_per_minute'])
                                model_state['concurrency'] = width
                            if result['status'] == 'QUOTA_EXHAUSTED':
                                stopped = 'QUOTA_EXHAUSTED'
                                model_state['reason'] = result.get('error', {}).get('message', 'Daily or subscription quota exhausted.') if isinstance(result.get('error'), dict) else str(result.get('error'))
                            elif local_attempts[trial] >= schedule['max_rate_limit_attempts']:
                                stopped = stopped or 'PAUSED_RATE_LIMIT'
                        elif result['status'] == 'AUTH_BLOCKED':
                            stopped = 'AUTH_BLOCKED'
                            model_state['reason'] = result['error']
                        elif result['status'] in cache_policy.STOP_STATUSES:
                            stopped = result['status']
                            model_state['reason'] = result.get('error', stopped)
                        elif result['status'] in ('LOCAL_ERROR', 'PROVIDER_ERROR', 'TRANSPORT_ERROR', 'LOCAL_PREFLIGHT_REJECTED'):
                            stopped = stopped or 'PROVIDER_BLOCKED'
                        elif model['transport'] in ('openai_responses', 'orca_api') and result['status'] == 'UNKNOWN_DELIVERY':
                            policy = model_state.get('disconnect_recovery', {})
                            authorization = policy.get('authorization')
                            if (model['transport'] == 'orca_api' and
                                    result.get('response_unavailable_reason') == 'NETWORK_DISCONNECT' and
                                    policy.get('continue_unsubmitted') is True and
                                    isinstance(authorization, str) and authorization.strip() and
                                    set(model_state.get('validated_reasoning_modes', [])) == set(config['reasoning_modes'])):
                                preserved_disconnects.append(trial)
                            else:
                                stopped = stopped or 'UNKNOWN_DELIVERY'
                        model_state['first_call_checked'] = True
                if preserved_disconnects:
                    # Continue fresh requests only while this wave proves the provider is responding.
                    if not received_responses:
                        stopped = stopped or 'UNKNOWN_DELIVERY'
                    event(root, 'NETWORK_DISCONNECTS_PRESERVED', model=key,
                          trial_ids=preserved_disconnects, received_responses=received_responses,
                          continue_unsubmitted=stopped is None, automatic_retries=0)
                pending = retries + length_retries + pending
                if retries or model_state.get('requests_per_minute'):
                    delay = retry_delay if retries else 60 * len(wave) / model_state['requests_per_minute'] + 5
                    model_state['next_wave_not_before'] = time.time() + delay
                model_state['last_updated'] = now()
                if stopped:
                    model_state['status'] = stopped
                write(root / 'state.json', state)
                reporting.build(root)
                if stopped:
                    break
                if retries:
                    event(root, 'RATE_LIMIT_BACKOFF', model=key, seconds=retry_delay, concurrency=width)
                elif model.get('group_interval_seconds', 0):
                    time.sleep(model['group_interval_seconds'])
            if not pending and model_state.get('status') == 'RUNNING':
                model_state['status'] = 'FINISHED'
            write(root / 'state.json', state)
        states = [s['status'] for s in state['models'].values()]
        state['status'] = ('FINISHED' if all(s == 'FINISHED' for s in states) else
                           'CACHE_POLICY_BLOCKED' if 'CACHE_POLICY_BLOCKED' in states else
                           'BATCH_REJECTED' if 'BATCH_REJECTED' in states else
                           'BATCH_FAILED' if 'BATCH_FAILED' in states else
                           'BATCH_POLL_ERROR' if 'BATCH_POLL_ERROR' in states else
                           'BATCH_PENDING' if 'BATCH_PENDING' in states else 'INCOMPLETE')
        write(root / 'state.json', state)
        summary = reporting.build(root)
        if state['status'] == 'FINISHED' and any(m['transport'] in ('codex_cli', 'openai_responses', 'openai_batch', 'anthropic_batch') for m in config['models']):
            module = 'numeric_validation' if run_layout.ordered(root) else 'numeric_analysis'
            analyze_numeric = __import__('finarch.experiments.01-evaluation.04-validation.' + module, fromlist=['build']).build
            analyze_numeric(root)
        event(root, 'PIPELINE_EXIT', status=state['status'], new_attempts=completed)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'report', 'recover', 'use-paid-gemini', 'batch-plan', 'revalidate-batch', 'organize-calls', 'consolidate-root', 'select-backend'])
    parser.add_argument('--backend', choices=['codex', 'gemini', 'openai'])
    parser.add_argument('--config', default=str(settings.DEFAULT_CONFIG))
    parser.add_argument('--run', dest='run_path')
    parser.add_argument('--models', nargs='+')
    parser.add_argument('--max-new-calls', type=int)
    parser.add_argument('--resume-limits', action='store_true')
    args = parser.parse_args()
    if args.command == 'select-backend':
        if not args.backend:
            parser.error('--backend is required')
        config = read(args.config)
        if 'run' in run_layout.split_config(config)[0]:
            parser.error('Set evaluation.run.models profiles directly; analysis.run.backend selects api or codex.')
        run_layout.split_config(config)[0]['models'] = run_layout.split_config(config)[0]['backend_presets'][args.backend]
        run_layout.split_config(config)[0]['active_backend'] = args.backend
        run_layout.split_config(config)[0]['billing']['native_gemini_batch'] = args.backend == 'gemini'
        run_layout.split_config(config)[0]['billing']['active_mode'] = {'codex': 'CODEX_SUBSCRIPTION', 'gemini': 'PAID_GEMINI_BATCH', 'openai': 'PAID_OPENAI_API'}[args.backend]
        write(args.config, config)
        print(json.dumps({'backend': args.backend, 'new_model_calls': 0, 'applies_to': 'NEW_PREPARE_ONLY'}))
        return
    if args.command == 'consolidate-root':
        consolidate_root = __import__('finarch.experiments.01-evaluation.03-execution.organize_calls', fromlist=['consolidate_root']).consolidate_root
        result = consolidate_root(PROJECT / 'report/experiments-run', PROJECT / 'reports/experiments-run')
        config = read(args.config)
        if 'run' not in run_layout.split_config(config)[0]:
            run_layout.split_config(config)[0]['output_root'] = 'reports/experiments-run'
            write(args.config, config)
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.command == 'prepare':
        print(prepare(args.config))
    else:
        if not args.run_path:
            parser.error('--run is required')
        if args.command == 'organize-calls':
            organize = __import__('finarch.experiments.01-evaluation.03-execution.organize_calls', fromlist=['organize']).organize
            print(json.dumps(organize(Path(args.run_path)), ensure_ascii=False))
            return
        if args.command == 'revalidate-batch':
            collect = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['collect']).collect
            root = Path(args.run_path)
            with locked(root / '.pipeline.lock'):
                for model in configuration(root)['models']:
                    if model['transport'] != 'gemini_batch':
                        continue
                    for path in (run_layout.batches(root, model['key'])).glob('batch-*/raw-results.json'):
                        count = collect(root, model, path.parent, read(path))
                        event(root, 'SAVED_BATCH_REVALIDATED', model=model['key'], responses=count, new_model_calls=0)
                summary = reporting.build(root)
                print(json.dumps({'status': summary['status'], 'new_model_calls': 0}))
            return
        if args.command == 'batch-plan':
            make_jobs = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['make_jobs']).make_jobs
            root = Path(args.run_path)
            with locked(root / '.pipeline.lock'):
                model = next(m for m in configuration(root)['models'] if m['transport'] == 'gemini_batch')
                existing = sorted((run_layout.batches(root, model['key'])).glob('batch-*/job.json'))
                folders = [p.parent for p in existing] if existing else make_jobs(root, model)
                trials = [t for p in folders for t in read(p / 'trials.json')]
                incoming = sum(math.ceil(len(encoded(providers.gemini_body(t['request']))) / 4) for t in trials)
                plan = {'requests': len(trials), 'jobs': len(folders), 'input_tokens_estimated': incoming,
                        'estimated_usd_at_1000_output_tokens': (incoming * 0.05 + len(trials) * 1000 * 0.2) / 1e6,
                        'estimated_usd_at_output_cap': (incoming * 0.05 + sum(t['request']['max_output_tokens'] for t in trials) * 0.2) / 1e6,
                        'input_estimate_method': 'BYTES_DIVIDED_BY_FOUR_NOT_TOKENIZER',
                        'output_cap_is_not_a_precise_billing_upper_bound': True,
                        'provider_batch_discount_applied': True, 'created_at': now()}
                write(root / 'paid-batch-plan.json', plan)
                event(root, 'PAID_BATCH_PREPARED', **plan)
                print(json.dumps(plan))
            return
        if args.command == 'use-paid-gemini':
            root = Path(args.run_path)
            with locked(root / '.pipeline.lock'):
                overrides = read(root / 'runtime-overrides.json', {'models': {}})
                overrides['models']['gemini-2.5-flash-lite'] = {
                    'transport': 'gemini_batch', 'key_variable': 'GEMINI_API_KEY_PAID', 'key_file': '~/.zshrc',
                    'reference_price_per_million': {'input': 0.05, 'output': 0.2}}
                overrides.update(authorized_at=now(), authorization='USER_EXPLICITLY_REQUESTED_REGISTERED_PAID_KEY')
                write(root / 'runtime-overrides.json', overrides)
                event(root, 'ACCESS_MODE_CHANGED', model='gemini-2.5-flash-lite', transport='gemini_batch',
                      credential_variable='GEMINI_API_KEY_PAID', preserve_successful_responses=True)
                reporting.build(root)
            print('Paid Gemini Batch override recorded; existing responses preserved.')
            return
        if args.command == 'recover':
            recover_local_parser_errors(Path(args.run_path))
        result = reporting.build(Path(args.run_path)) if args.command in ('report', 'recover') else run(
            args.run_path, args.models, args.resume_limits, args.max_new_calls)
        print(json.dumps({'run_id': result['run_id'], 'status': result['status'],
                          'models': [{k: m[k] for k in ('model', 'statuses', 'api_equivalent_usd')} for m in result['models']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
