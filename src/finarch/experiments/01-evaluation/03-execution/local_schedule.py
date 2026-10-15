"""Bounded local CLI processes with a separate two-second resource monitor."""
import concurrent.futures as futures
import threading
import time
from collections import deque
from pathlib import Path

run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])

import psutil

cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])
encoded = __import__('finarch.experiments.90-operations.storage', fromlist=['encoded']).encoded
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write

TERMINAL = {'VALID', 'INVALID_RESPONSE', 'OUTPUT_TRUNCATED'}


def next_limit(current, sample, settings):
    pressure = (sample['memory_percent'] >= settings['memory_threshold_percent'] or
                sample['available_memory_bytes'] < settings['minimum_available_memory_gb'] * 1024 ** 3)
    if pressure:
        return max(1, current - settings['increase_by']), True
    if sample['cpu_percent'] < settings['cpu_threshold_percent']:
        return min(settings['concurrency'], current + settings['increase_by']), False
    return current, False


class Monitor:
    def __init__(self, root, model, settings):
        self.folder = root / model
        self.settings = settings
        self.limit = min(settings['initial_concurrency'], settings['concurrency'])
        self.active, self.completed = 0, 0
        self.memory_blocked = False
        self.growth_enabled = False
        self.provider_limited = False
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.error = None

    def loop(self):
        psutil.cpu_percent(interval=None)
        while not self.stop_event.wait(self.settings['monitor_interval_seconds']):
            try:
                memory = psutil.virtual_memory()
                sample = {'at': now(), 'cpu_percent': psutil.cpu_percent(interval=None),
                          'memory_percent': memory.percent, 'available_memory_bytes': memory.available,
                          'total_memory_bytes': memory.total}
                with self.lock:
                    previous = self.limit
                    proposed, self.memory_blocked = next_limit(self.limit, sample, self.settings)
                    if self.memory_blocked or (self.growth_enabled and not self.provider_limited):
                        self.limit = proposed
                    sample.update(previous_limit=previous, concurrency_limit=self.limit, active=self.active,
                                  completed_this_process=self.completed, memory_blocked=self.memory_blocked)
                with (self.folder / 'resources.jsonl').open('a') as handle:
                    handle.write(encoded(sample).decode() + '\n')
                write(self.folder / 'resources-latest.json', sample)
            except Exception as error:
                self.error = error
                return


def run_model(root, model, state, settings, max_new=None, resume_limits=False):
    base = run_layout.execution(root, model['key'])
    model_state = state['models'][model['key']]
    if model_state.get('status') in ('CACHE_POLICY_VIOLATION', 'CACHE_USAGE_UNVERIFIED'):
        return 0
    if model_state.get('status') in ('QUOTA_EXHAUSTED', 'AUTH_BLOCKED', 'PAUSED_RATE_LIMIT') and not resume_limits:
        return 0
    model_state.pop('reason', None)
    try:
        model_state['preflight'] = providers.preflight(model)
    except cache_policy.CachePolicyError as error:
        model_state.update(status='CACHE_POLICY_BLOCKED', reason=str(error), preflight=error.check,
                           active=0, completed_this_process=0)
        write(base / 'cache-preflight.json', error.check)
        event(root, 'CACHE_POLICY_BLOCKED', model=model['key'], reason=str(error), new_model_calls=0)
        return 0
    except Exception as error:
        model_state.update(status='PREFLIGHT_BLOCKED', reason=str(error))
        event(root, 'PREFLIGHT_BLOCKED', model=model['key'], reason=str(error))
        return 0
    requests = rows(run_layout.requests(root, model['key']))
    pending, unresolved = deque(), []
    for request in requests:
        attempts = call_layout.attempt_dirs(base, request)
        last = read(attempts[-1] / 'result.json', {'status': 'UNKNOWN_DELIVERY'}) if attempts else None
        if last and last['status'] in TERMINAL:
            continue
        if attempts and (not last or last['status'] == 'UNKNOWN_DELIVERY'):
            unresolved.append(request['trial_id'])
            continue
        if last and last['status'] not in ('RATE_LIMITED', 'QUOTA_EXHAUSTED', 'TRANSIENT_ERROR', 'AUTH_BLOCKED') and not last.get('safe_retry_local_preflight'):
            unresolved.append(request['trial_id'])
            continue
        pending.append((request, len(attempts) + 1))
    monitor = Monitor(root, model['key'], settings)
    monitor.growth_enabled = model_state.get('first_call_checked', False)
    if model_state.get('provider_concurrency_cap'):
        monitor.limit = min(monitor.limit, model_state['provider_concurrency_cap'])
        monitor.provider_limited = True
    thread = threading.Thread(target=monitor.loop, daemon=True)
    thread.start()
    count, sent, stopped, next_wave, reported = 0, 0, None, 0, 0
    model_state.update(status='RUNNING', concurrency=monitor.limit)
    active = {}
    try:
        with futures.ThreadPoolExecutor(max_workers=settings['concurrency']) as pool:
            while pending or active:
                if monitor.error:
                    stopped = 'RESOURCE_MONITOR_FAILED'
                with monitor.lock:
                    width = monitor.limit
                    blocked = monitor.memory_blocked
                    monitor.active, monitor.completed = len(active), count
                # A first real response verifies auth/schema/effort before broad dispatch.
                if not model_state.get('first_call_checked'):
                    width = 1
                while pending and not stopped and not blocked and len(active) < width and time.monotonic() >= next_wave:
                    if max_new is not None and sent >= max_new:
                        stopped = 'PAUSED_CALL_CAP'
                        break
                    request, number = pending.popleft()
                    folder = call_layout.attempt_path(base, request, number)
                    write(folder / 'request.json', request)
                    write(folder / 'started.json', {'at': now(), 'transport': model['transport'], 'attempt': number})
                    future = pool.submit(providers.call, model, request, folder, settings['timeout_seconds'])
                    active[future] = (request, number)
                    with monitor.lock:
                        monitor.active = len(active)
                    sent += 1
                if not active and stopped:
                    break
                done, _ = futures.wait(active, timeout=.2, return_when=futures.FIRST_COMPLETED) if active else (set(), set())
                if not active and not done:
                    time.sleep(.2)
                for future in done:
                    request, number = active.pop(future)
                    result = future.result()
                    count += 1
                    status = result['status']
                    if status in TERMINAL:
                        model_state['first_call_checked'] = True
                        monitor.growth_enabled = True
                    event(root, 'CALL_END', model=model['key'], trial_id=request['trial_id'], status=status, attempt=number)
                    if status in cache_policy.STOP_STATUSES or status in ('QUOTA_EXHAUSTED', 'AUTH_BLOCKED', 'LOCAL_ERROR', 'LOCAL_PREFLIGHT_REJECTED', 'PROVIDER_ERROR', 'TRANSPORT_ERROR'):
                        stopped = status
                        model_state['reason'] = result.get('error', status)
                    elif status in ('RATE_LIMITED', 'TRANSIENT_ERROR'):
                        with monitor.lock:
                            monitor.limit = min(monitor.limit, settings['fallback_group_size'])
                            monitor.provider_limited = True
                        model_state['provider_concurrency_cap'] = settings['fallback_group_size']
                        next_wave = time.monotonic() + max(settings['retry_delay_seconds'], result.get('retry_after_seconds', 0))
                        if number < settings['max_rate_limit_attempts']:
                            pending.append((request, number + 1))
                        else:
                            stopped = 'PAUSED_RATE_LIMIT'
                    elif status == 'UNKNOWN_DELIVERY':
                        unresolved.append(request['trial_id'])
                model_state.update(concurrency=monitor.limit, active=len(active), completed_this_process=count,
                                   queued=len(pending), last_updated=now())
                if time.monotonic() - reported >= settings.get('report_interval_seconds', 20):
                    write(root / 'state.json', state)
                    reporting.build(root)
                    reported = time.monotonic()
            model_state.update(status=stopped or ('INCOMPLETE' if unresolved else 'FINISHED'), active=0,
                               unresolved_trial_ids=unresolved, completed_this_process=count)
    finally:
        monitor.stop_event.set()
        thread.join(timeout=5)
        write(root / 'state.json', state)
    return count
