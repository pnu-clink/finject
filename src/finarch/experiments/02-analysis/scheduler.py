"""Bound in-flight Codex calls and grow the limit from measured host CPU usage."""
import math
import os
from collections import Counter
from pathlib import Path
import time

import psutil

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
DEFAULT_ADAPTIVE = {'enabled': False, 'interval_seconds': 60,
                    'cpu_threshold_percent': 60, 'growth_percent': 10}


def validate(schedule):
    for key, default in (('concurrency', 4), ('timeout_seconds', 600)):
        value = schedule.get(key, default)
        if type(value) is not int or value < 1:
            raise ValueError('ANALYSIS_POSITIVE_SCHEDULE_REQUIRED:' + key)
    adaptive = {**DEFAULT_ADAPTIVE, **schedule.get('adaptive', {})}
    if set(adaptive) != set(DEFAULT_ADAPTIVE) or type(adaptive['enabled']) is not bool:
        raise ValueError('ANALYSIS_ADAPTIVE_POLICY_INVALID')
    for key in ('interval_seconds', 'cpu_threshold_percent', 'growth_percent'):
        value = adaptive[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('ANALYSIS_ADAPTIVE_POSITIVE_VALUE_REQUIRED:' + key)
    if adaptive['cpu_threshold_percent'] > 100 or adaptive['growth_percent'] > 100:
        raise ValueError('ANALYSIS_ADAPTIVE_PERCENT_OUT_OF_RANGE')
    return {'concurrency': schedule.get('concurrency', 4),
            'timeout_seconds': schedule.get('timeout_seconds', 600), 'adaptive': adaptive}


def policy(root, config):
    """Only scheduling controls may override a frozen run, never model inputs."""
    saved = store.read(Path(root) / '02_analysis/runtime-schedule.json')
    schedule = dict(config.get('schedule', {}))
    if saved is not None:
        if saved.get('analysis_sha256') != store.digest(config):
            raise ValueError('ANALYSIS_RUNTIME_SCHEDULE_BASE_CHANGED')
        overrides = saved['schedule']
        if set(overrides) - {'concurrency', 'adaptive', 'timeout_seconds'}:
            raise ValueError('ANALYSIS_RUNTIME_SCHEDULE_FIELDS_INVALID')
        schedule.update(overrides)
    return validate(schedule)


class Controller:
    def __init__(self, root, stage, config, total, *, clock=time.monotonic, cpu=None):
        self.root, self.stage, self.config = Path(root), stage, config
        self.clock, self.cpu = clock, cpu or psutil.cpu_percent
        self.total = total
        self.policy = policy(root, config)
        self.limit = min(self.policy['concurrency'], total)
        self.checked = self.clock()
        self.sample = None
        self.published = None
        self.primed = False
        self.prime()

    def prime(self):
        try:
            self.cpu(interval=None)
            self.primed = True
        except Exception as error:
            self.sample = {'cpu_percent': None, 'error_type': type(error).__name__}

    def tick(self, remaining, *, stopped=False):
        incoming = policy(self.root, self.config)
        now = self.clock()
        if incoming != self.policy:
            before = self.limit
            self.policy = incoming
            self.limit = min(incoming['concurrency'], remaining)
            self.checked, self.sample, self.primed = now, None, False
            self.prime()
            store.event(self.root, 'ANALYSIS_CONCURRENCY_CHANGED', stage=self.stage,
                        previous_limit=before, current_limit=self.limit, reason='RUNTIME_POLICY_CHANGED')
        rule = self.policy['adaptive']
        elapsed = now - self.checked
        if stopped or elapsed < rule['interval_seconds']:
            return
        self.checked = now
        before = self.limit
        usage, error = None, None
        if not self.primed:
            self.prime()
            error = 'CPU_SAMPLE_WARMUP'
        else:
            try:
                usage = self.cpu(interval=None)
                if type(usage) not in (int, float) or not math.isfinite(usage) or not 0 <= usage <= 100:
                    raise ValueError('CPU_SAMPLE_INVALID')
            except Exception as problem:
                usage, error, self.primed = None, type(problem).__name__, False
        if rule['enabled'] and usage is not None and usage <= rule['cpu_threshold_percent'] and remaining > self.limit:
            self.limit = min(remaining, self.limit + math.ceil(self.limit * rule['growth_percent'] / 100))
        self.sample = {'cpu_percent': usage, 'interval_seconds': elapsed,
                       'sampled_at': store.now(), 'error_type': error}
        store.event(self.root, 'ANALYSIS_CPU_SAMPLE', stage=self.stage, **self.sample,
                    previous_limit=before, current_limit=self.limit)

    def publish(self, active, queued, status='RUNNING', *, deferred=None):
        value = {'schema_version': 1, 'pid': os.getpid(),
                 'stage': self.stage, 'status': status, 'policy': self.policy,
                 'current_limit': self.limit, 'active_calls': active, 'queued_calls': queued,
                 'last_cpu_sample': self.sample, 'cpu_scope': 'HOST_TOTAL_PERCENT_0_TO_100'}
        if deferred is not None:
            value.update(deferred_failure_count=len(deferred), deferred_trial_ids=sorted(deferred),
                         deferred_statuses=dict(Counter(deferred.values())))
        if value == self.published:
            return value
        self.published = value
        value = {**value, 'updated_at': store.now()}
        folder = self.root / '02_analysis'
        store.write(folder / 'scheduler.json', value)
        template = (store.PROJECT / 'src/finarch/experiments/templates/analysis-scheduler-template.md').read_text()
        sample = self.sample or {}
        cpu = 'Measuring the atmosphere' if sample.get('cpu_percent') is None else f"{sample['cpu_percent']:.1f}%"
        store.write_text(folder / 'scheduler.md', template.format(**value, cpu=cpu,
            **({'deferred_failure_count': 'Not recorded'} if 'deferred_failure_count' not in value else {}),
            interval=self.policy['adaptive']['interval_seconds'],
            threshold=self.policy['adaptive']['cpu_threshold_percent'],
            growth=self.policy['adaptive']['growth_percent'],
            mode='Automatic increase' if self.policy['adaptive']['enabled'] else 'Fixed'))
        return value
