"""Coordinate case submission independently of case completion."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextvars import copy_context
import time
import psutil


def adjusted_limit(current, total, cpu_percent, *, threshold, increase_by):
    return min(total, current + increase_by) if cpu_percent < threshold else current


def run(items, worker, *, settings, monitor, cpu_reader=None):
    initial=settings["initial_concurrency"]
    fixed=settings.get('mode')=='fixed'
    interval=settings["monitor_interval_seconds"]
    threshold=settings["cpu_threshold_percent"]
    increase_by=settings["increase_by"]
    items = list(items)
    if type(initial) is not int or initial < 1:
        raise ValueError('INVALID_INITIAL_CONCURRENCY')
    if interval <= 0: raise ValueError('INVALID_MONITOR_INTERVAL')
    total = len(items)
    if not total:
        monitor({'status':'COMPLETED','planned':0,'completed':0,'active':0,'pending':0,'limit':0})
        return
    reader = cpu_reader or (lambda: psutil.cpu_percent(interval=None))
    if not fixed:reader()  # API concurrency is independent of local CPU load.
    limit = min(initial, total)
    submitted = completed = failed = 0
    active = {}
    started = time.monotonic()
    next_tick = started + interval
    cpu = None
    def report(status):
        elapsed = time.monotonic() - started
        monitor({'status':status,'planned':total,'submitted':submitted,'completed':completed,
                 'failed':failed,'active':len(active),'active_cases':[str(x) for x in active.values()],
                 'pending':total-submitted,'limit':limit,'cpu_percent':cpu,
                 'elapsed_seconds':elapsed,'cases_per_minute':completed*60/elapsed if elapsed else 0,
                 'monitor_interval_seconds':interval,'increase_by':increase_by,'cpu_threshold_percent':threshold,'settings':settings})
    with ThreadPoolExecutor(max_workers=limit if fixed else total) as pool:
        try:
            while completed < total:
                now = time.monotonic()
                if now >= next_tick:
                    if not fixed:
                        cpu = float(reader())
                        limit = adjusted_limit(limit, total, cpu, threshold=threshold, increase_by=increase_by)
                    next_tick = now + interval
                while submitted < total and len(active) < limit:
                    item = items[submitted]
                    active[pool.submit(copy_context().run, worker, item)] = item
                    submitted += 1
                report('RUNNING')
                done, _ = wait(active, timeout=max(0,next_tick-time.monotonic()), return_when=FIRST_COMPLETED)
                for future in done:
                    item = active.pop(future)
                    try: result = future.result()
                    except Exception as error:
                        result = {'status':'FAIL','worker_exception':True,
                                  'reason':type(error).__name__+': '+str(error)}
                    completed += 1
                    failed += result.get('status') == 'FAIL' if isinstance(result,dict) else 0
                    yield item, result
            report('COMPLETED')
        except BaseException:
            report('ERROR')
            for future in active: future.cancel()
            raise
