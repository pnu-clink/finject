"""Durable per-problem START/END records; no prompts or arguments in events."""
import contextvars
import functools
import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from finarch.shared.run_logging.run_logs import RunLogs, append

_CURRENT = contextvars.ContextVar('finarch_journal', default=None)
_SPAN = contextvars.ContextVar('finarch_span', default=None)


def timestamp():
    return datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds")


class Journal:
    def __init__(self, root, case_id=None):
        self.path = Path(root) / 'events.jsonl'
        self.path.touch(exist_ok=False)
        self.case_id = case_id
        self.run_id = uuid.uuid4().hex
        self.events = []
        self.lock = threading.RLock()
        self.files = RunLogs.for_case(root)

    @classmethod
    def resume(cls, root, case_id=None):
        """Append a later stage to the same saved problem journal."""
        obj=cls.__new__(cls);obj.path=Path(root)/'events.jsonl'
        obj.events=[json.loads(line) for line in obj.path.read_text().splitlines() if line.strip()]
        if not obj.events:raise ValueError('EXISTING_JOURNAL_REQUIRED')
        if any(e.get('problem_id')!=case_id for e in obj.events):raise ValueError('JOURNAL_CASE_MISMATCH')
        obj.case_id=case_id;obj.run_id=obj.events[-1]['run_id'];obj.lock=threading.RLock()
        obj.files=RunLogs.for_case(root)
        return obj

    def emit(self, *, detail=None, **event):
        # LG01: write and fsync before work starts; logging failure stops execution.
        with self.lock:
            value = {'format': 'finarch-event-v1', 'sequence': len(self.events) + 1,
                     'run_id': self.run_id, 'problem_id': self.case_id,
                     'timestamp': timestamp(), **event}
            line = json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n'
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
            self.events.append(value)
            self.files.event(value, value=detail)
            return value

    @contextmanager
    def activate(self):
        token = _CURRENT.set(self)
        parent_token = _SPAN.set(None) if token.old_value is not self else None
        try:
            yield self
        finally:
            if parent_token is not None:
                _SPAN.reset(parent_token)
            _CURRENT.reset(token)

    @contextmanager
    def span(self, function, *, kind='python', pipeline=True, **metadata):
        # LG02: each function inherits the current stage/role/candidate and parent.
        parent = _SPAN.get()
        inherited = {k: parent[k] for k in ('stage', 'step', 'role', 'candidate', 'attempt', 'axis')
                     if parent and k in parent}
        common = {'call_id': uuid.uuid4().hex, 'parent_call_id': parent['call_id'] if parent else None,
                  'function': function, 'hook': function, 'kind': kind, 'stage': 'pipeline',
                  'step': function, 'role': function, 'candidate': None, 'attempt': 1,
                  **inherited, **metadata}
        common.update(pipeline=pipeline, pipeline_function=function if pipeline or not parent else parent['pipeline_function'])
        outcome = {'status': 'PASS', 'reason': 'Completed'}
        started = time.monotonic()
        start = self.emit(**common, phase='START', status='RUNNING', reason='Started', elapsed_seconds=None)
        token = _SPAN.set({**common, 'outcome': outcome})
        try:
            yield outcome
        except BaseException as error:
            result = getattr(error, 'result', None)
            outcome.update(status=getattr(result, 'status', 'CANCELLED' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'FAIL'),
                           reason=getattr(result, 'reason', type(error).__name__), error_type=type(error).__name__)
            raise
        finally:
            _SPAN.reset(token)
            # LG03: catchable exits have END; hard kills leave START pending.
            self.emit(**common, phase='END', started_at=start['timestamp'], ended_at=timestamp(),
                      elapsed_seconds=time.monotonic() - started, **outcome)

    def update(self, **outcome):
        span = _SPAN.get()
        if span is not None:
            span['outcome'].update(outcome)

    def artifact(self, relative, value=None):
        span = _SPAN.get()
        if _CURRENT.get() is self and span is not None:
            self.emit(phase='ARTIFACT', call_id=span['call_id'], parent_call_id=span['parent_call_id'],
                      stage=span['stage'], step=span['step'], role=span['role'],
                      function=span['function'], pipeline_function=span['pipeline_function'],
                      kind=span['kind'], axis=span.get('axis'), detail=value,
                      status='SAVED', reason='Artifact saved', path=str(relative))
        else:
            self.files.event({'function':'artifact.save','phase':'ARTIFACT','problem_id':self.case_id,
                              'path':str(relative),'kind':'python'}, value=value)

    def summary(self):
        return summarize(self.events)


def summarize(events):
    # LG04: unknown usage/cost stays unknown; never fabricate a finished call.
    started = {e['call_id']: e for e in events if e.get('phase') == 'START'}
    ended = {e['call_id'] for e in events if e.get('phase') == 'END'}
    usage = [e for e in events if e.get('phase') == 'USAGE']
    pending = [k for k in started if k not in ended]
    estimates = [e.get('estimated_cost') for e in usage]
    currencies = {e.get('currency') for e in usage}
    costs_complete = bool(usage) and all(type(v) in (int, float) for v in estimates) and len(currencies) == 1 and None not in currencies
    return {'event_count': len(events), 'pending_call_ids': pending,
            'cli_invocations': sum(e.get('cli_invocations') or 0 for e in usage),
            'invocation_count_complete': not pending and all(e.get('cli_invocations') is not None for e in usage),
            'usage_records': usage, 'estimated_cost': sum(estimates) if costs_complete else None,
            'currency': next(iter(currencies)) if costs_complete else None,
            'cost_status': 'ESTIMATED' if costs_complete else 'UNAVAILABLE',
            'actual_billed_cost': None}


def read_summary(path):
    """A killed process may leave its last line incomplete; preserve that warning."""
    events, damaged = [], []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError('INVALID_EVENT')
            events.append(value)
        except ValueError:
            damaged.append(number)
    return {**summarize(events), 'damaged_lines': damaged}


def traced(kind='python'):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            journal = _CURRENT.get()
            if journal is None:
                return function(*args, **kwargs)
            with journal.span(function.__module__ + '.' + function.__qualname__, kind=kind, pipeline=False):
                result = function(*args, **kwargs)
                status = getattr(result, 'status', None)
                if status is not None:
                    journal.update(status=status, reason=getattr(result, 'reason', 'Completed'))
                if isinstance(result, dict) and result.get('state') in ('TIMEOUT', 'TOOL_DENIED', 'CANCELLED'):
                    journal.update(status='FAIL', reason=result['state'])
                return result
        return wrapped
    return decorate


def record_cli(argv, cwd):
    """Actual process arguments, recorded immediately before process creation."""
    journal, span = _CURRENT.get(), _SPAN.get()
    function = span['pipeline_function'] if span else 'cli.run_process'
    value = {'argv':list(argv),'cwd':str(cwd)}
    if journal is not None:
        journal.files.write('cli.log', function, value=value, phase='START',
                            call_id=span.get('call_id') if span else None,
                            problem_id=journal.case_id)
    else:
        append((Path(__file__).resolve().parent / '../../../..').resolve()/'log/cli.log',
               {'timestamp':timestamp(),'function':function,'run_id':None,'phase':'START',function:value})


def record_usage(*, role, model, provider, usage, reason, cli_invocations=1,
                 estimated_cost=None, currency=None, price_basis=None, artifacts=None):
    journal, parent = _CURRENT.get(), _SPAN.get()
    if journal is None:
        return
    # LG05: report only CLI-provided usage and an explicitly supplied price basis.
    journal.emit(phase='USAGE', call_id=parent['call_id'] if parent else None,
                 function=parent.get('function') if parent else role,
                 pipeline_function=parent.get('pipeline_function') if parent else role,
                 kind='llm', axis=parent.get('axis') if parent else None,
                 parent_call_id=parent.get('parent_call_id') if parent else None,
                 stage=parent.get('stage') if parent else 'pipeline',
                 step=parent.get('step') if parent else role, role=role,
                 model=model, provider=provider, reported_usage=usage, reason=reason,
                 cli_invocations=cli_invocations, estimated_cost=estimated_cost,
                 currency=currency, price_basis=price_basis, actual_billed_cost=None,
                 artifacts=artifacts or [])


def estimate_cost(usage, pricing):
    """Optional documented per-million-token rates; no default price or token count."""
    import math
    unknown = {'estimated_cost': None, 'currency': None, 'price_basis': pricing,
               'cost_status': 'Usage or documented price basis unavailable.'}
    if not isinstance(usage, dict) or not isinstance(pricing, dict):
        return unknown
    if any(not isinstance(pricing.get(k), str) or not pricing[k].strip()
           for k in ('currency', 'source', 'as_of')):
        return unknown
    tokens = [usage.get('input_tokens'), usage.get('output_tokens')]
    if any(type(v) is not int or v < 0 for v in tokens):
        return unknown
    rates = [pricing.get('input_per_million'), pricing.get('output_per_million')]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in rates):
        return unknown
    cached = usage.get('cached_input_tokens', 0)
    if type(cached) is not int or not 0 <= cached <= tokens[0]:
        return unknown
    cache_rate = pricing.get('cached_input_per_million')
    if cached and (type(cache_rate) not in (int, float) or not math.isfinite(cache_rate) or cache_rate < 0):
        return unknown
    value = ((tokens[0] - cached) * rates[0] + tokens[1] * rates[1] + cached * (cache_rate or 0)) / 1_000_000
    return {'estimated_cost': value, 'currency': pricing['currency'], 'price_basis': pricing,
            'cost_status': 'ESTIMATED_FROM_REPORTED_TOKENS_NOT_ACTUAL_BILL'}
