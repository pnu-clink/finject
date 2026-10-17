"""Freeze implementation and run one explicitly requested, bounded API wave."""
import argparse
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
PROJECT = __import__('finarch.experiments.90-operations.storage', fromlist=['PROJECT']).PROJECT
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
locked = __import__('finarch.experiments.90-operations.storage', fromlist=['locked']).locked
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
cost_from_usage = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['cost_from_usage']).cost_from_usage

MAX_NEW_CALLS = 100
MAX_ATTEMPTS = 2
QUOTA_MAX_AGE_SECONDS = 600
QUOTA_RESERVE_PERCENT = 15
USER_MANAGED_USAGE = 'USER_MANAGED_ACCOUNT_USAGE_BY_EXPLICIT_REQUEST'
README_TEMPLATE = """# {run_id} Restricted execution instructions

`improvement-status.json` → `improvement-waves/` → `00-implementation/manifest.json` → Model by model `calls/` in this order.

- `improvement-status.json`: the latest run/differentiation status and why.
- `improvement-waves/`It preserves official pre-run limit verification data, cost estimates and run results.
- `00-implementation/`At the time of preparation: Python code and related template originals and SHA-256So when you restart it, compare it to the current file.
- `events.jsonl`It's ready, running, blocking power.
- By model. `calls/`So, the raw response is the city-specific results. `viewer/experiments/`I use it.

Maximum at a time. 100The maximum of the total number of paragraphs 2The basic policy is a recent official account limit check. If the user specifies that they will verify the account usage directly and records their approval in the exclusive configuration, they do not perform an account limit check and a residual-based interruption. API cost, city, and cache checks are maintained. There are no automatic reservations or repeat executions.

The cost is an estimate of the price tag multiplied by the amount the provider uses, not the invoice. 4 So the number of input tokens is close, so it's not a strict limit on the total amount of bills. 0It doesn't count as a circle, it blocks the new call.
"""


class WaveBlocked(ValueError):
    """The saved evidence does not authorize another model call."""


def implementation_files():
    base = PROJECT / 'src/finarch/experiments'
    return sorted(p for p in base.rglob('*')
                  if p.is_file() and p.suffix in ('.py', '.md')
                  and 'checks' not in p.relative_to(base).parts
                  and 'viewer' not in p.relative_to(base).parts)


def _number(value, label, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise WaveBlocked(label)
    return value


def _config(config):
    _number(config.get('billing', {}).get('api_budget_usd'), 'EXPLICIT_API_BUDGET_REQUIRED', True)
    models = config.get('models', [])
    if len(models) != 1 or models[0].get('transport') != 'openai_responses':
        raise WaveBlocked('ONE_OPENAI_RESPONSES_MODEL_REQUIRED')
    if config.get('schedule', {}).get('max_rate_limit_attempts') != 1:
        raise WaveBlocked('AUTOMATIC_RETRIES_MUST_BE_DISABLED')
    concurrency = config.get('schedule', {}).get('concurrency')
    if type(concurrency) is not int or not 1 <= concurrency <= MAX_NEW_CALLS:
        raise WaveBlocked('CONCURRENCY_MUST_BE_BETWEEN_1_AND_100')
    rates = models[0].get('reference_price_per_million', {})
    for key in ('input', 'output', 'cached_input', 'cache_write_input'):
        _number(rates.get(key), 'EXPLICIT_VALID_RATE_REQUIRED:' + key, key in ('input', 'output'))
    return models[0]


def prepare(config_path):
    """IR01: Prepare requests, then freeze the implementation and templates."""
    _config(read(config_path)['experiments'])
    before = {str(p.relative_to(PROJECT)): file_hash(p) for p in implementation_files()}
    root = pipeline.prepare(config_path)
    try:
        directory = root / '00-implementation'
        for relative, expected in before.items():
            source, target = PROJECT / relative, directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if file_hash(target) != expected or file_hash(source) != expected:
                raise WaveBlocked('IMPLEMENTATION_CHANGED_DURING_PREPARE:' + relative)
        write(directory / 'manifest.json', {'format': 'ImplementationFreezeV1', 'created_at': now(), 'files': before})
        write_text(directory / 'README.template.md', README_TEMPLATE)
        write_text(root / 'IMPROVEMENT-README.md', README_TEMPLATE.format(run_id=root.name))
        manifest = read(root / 'manifest.json')
        for path in directory.rglob('*'):
            if path.is_file():
                manifest[str(path.relative_to(root))] = file_hash(path)
        manifest['IMPROVEMENT-README.md'] = file_hash(root / 'IMPROVEMENT-README.md')
        write(root / 'manifest.json', manifest)
        write(root / 'improvement-status.json', {'status': 'PREPARED', 'at': now(), 'new_model_calls': 0})
        event(root, 'IMPLEMENTATION_FROZEN', files=len(before), new_model_calls=0)
        return root
    except Exception as error:
        write(root / 'improvement-status.json', {'status': 'PREPARE_BLOCKED', 'at': now(), 'reason': str(error), 'new_model_calls': 0})
        event(root, 'IMPLEMENTATION_FREEZE_FAILED', reason=str(error), new_model_calls=0)
        raise


def verify_implementation(root):
    """IR02: Check frozen artifacts and reject live code or override changes."""
    pipeline.verify(root)
    if (root / 'runtime-overrides.json').exists():
        raise WaveBlocked('RUNTIME_OVERRIDES_FORBIDDEN')
    frozen = read(root / '00-implementation/manifest.json')
    if not isinstance(frozen, dict) or not frozen.get('files'):
        raise WaveBlocked('IMPLEMENTATION_FREEZE_REQUIRED')
    current = {str(p.relative_to(PROJECT)): file_hash(p) for p in implementation_files()}
    if current != frozen['files']:
        changed = sorted(k for k in set(current) | set(frozen['files']) if current.get(k) != frozen['files'].get(k))
        raise WaveBlocked('LIVE_IMPLEMENTATION_MISMATCH:' + ','.join(changed))


def quota_check(evidence, current_time=None):
    """IR03: Validate a recently saved official tool result; never fetch remotely."""
    if not isinstance(evidence, dict) or evidence.get('source') != 'mcp__codex_app__get_usage_limits':
        raise WaveBlocked('OFFICIAL_QUOTA_EVIDENCE_REQUIRED')
    try:
        observed = datetime.fromisoformat(evidence['observed_at'].replace('Z', '+00:00'))
        if observed.tzinfo is None:
            raise ValueError('timezone required')
        age = ((current_time or datetime.now(timezone.utc)) - observed).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise WaveBlocked('QUOTA_EVIDENCE_TIMESTAMP_INVALID') from None
    if not 0 <= age <= QUOTA_MAX_AGE_SECONDS:
        raise WaveBlocked('QUOTA_EVIDENCE_STALE_OR_FUTURE')
    payload = evidence.get('rateLimitsByLimitId')
    if payload is None:
        payload = evidence.get('rateLimits')
    if not isinstance(payload, dict) or not payload:
        raise WaveBlocked('QUOTA_WINDOWS_MISSING')
    windows = []
    def visit(value, path):
        if isinstance(value, dict):
            if 'usedPercent' in value:
                used = _number(value['usedPercent'], 'QUOTA_USAGE_UNKNOWN')
                if used > 100:
                    raise WaveBlocked('QUOTA_USAGE_INVALID')
                windows.append({'window': path, 'remaining_percent': 100 - used})
            else:
                for key, child in value.items():
                    if key in ('primary', 'secondary') and child is None:
                        raise WaveBlocked('QUOTA_USAGE_UNKNOWN:' + path + '.' + key)
                    visit(child, path + '.' + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + '.' + str(index))
    visit(payload, 'limits')
    if not windows:
        raise WaveBlocked('QUOTA_WINDOWS_MISSING')
    durations = set()
    def durations_in(value):
        if isinstance(value, dict):
            if 'usedPercent' in value:
                durations.add(value.get('windowDurationMins'))
            for child in value.values():
                durations_in(child)
        elif isinstance(value, list):
            for child in value:
                durations_in(child)
    durations_in(payload)
    if not {300, 10080}.issubset(durations):
        raise WaveBlocked('CORE_FIVE_HOUR_AND_WEEKLY_WINDOWS_REQUIRED')
    if min(w['remaining_percent'] for w in windows) <= QUOTA_RESERVE_PERCENT:
        raise WaveBlocked('ACCOUNT_RESERVE_STOP_AT_15_PERCENT')
    return {'status': 'VERIFIED', 'age_seconds': age, 'windows': windows, 'source': evidence['source']}


def _retryable(result, directory):
    status = result.get('status')
    schema_error = directory / 'stderr.txt'
    return (status in ('TRANSIENT_ERROR', 'RATE_LIMITED', 'QUOTA_EXHAUSTED', 'AUTH_BLOCKED') or
            (status == 'PROVIDER_ERROR' and result.get('http_status') in (500, 502, 503, 504)) or
            (status in ('TRANSPORT_ERROR', 'LOCAL_PREFLIGHT_REJECTED') and schema_error.exists() and
             schema_error.read_text().startswith('Error: --json-schema is not a valid JSON Schema:')))


def budget_check(root, max_new):
    """IR04: Count every attempt; unknown usage or delivery blocks all new calls."""
    config = read(root / 'config.json')
    model = _config(config)
    rates = model['reference_price_per_million']
    base = root / model['key']
    observed, costs, actual, attempts_count = set(), [], 0.0, 0
    state = read(root / 'state.json', {})
    if state.get('status') == 'UNKNOWN_DELIVERY' or any(v.get('status') == 'UNKNOWN_DELIVERY' for v in state.get('models', {}).values()):
        raise WaveBlocked('UNKNOWN_DELIVERY_REQUIRES_RECONCILIATION')
    for request in rows(base / '01-requests/manifest.jsonl'):
        attempts = call_layout.attempt_dirs(base, request)
        if len(attempts) > MAX_ATTEMPTS:
            raise WaveBlocked('TRIAL_ATTEMPT_CAP_EXCEEDED:' + request['trial_id'])
        last = None
        for directory in attempts:
            observed.add(directory.resolve())
            attempts_count += 1
            result = read(directory / 'result.json')
            if result is None:
                raise WaveBlocked('UNRESOLVED_ATTEMPT:' + str(directory.relative_to(root)))
            if result.get('status') == 'UNKNOWN_DELIVERY':
                raise WaveBlocked('UNKNOWN_DELIVERY_REQUIRES_RECONCILIATION:' + request['trial_id'])
            usage = result.get('usage')
            cost = cost_from_usage(usage, rates) if isinstance(usage, dict) else None
            if cost is None:
                raise WaveBlocked('USAGE_UNKNOWN_NOT_ZERO:' + str(directory.relative_to(root)))
            actual += cost
            last = result
        pending = last is None or _retryable(last, attempts[-1])
        if pending and len(attempts) >= MAX_ATTEMPTS:
            raise WaveBlocked('TRIAL_RETRY_CAP_REACHED:' + request['trial_id'])
        if pending:
            output_tokens = request.get('max_output_tokens')
            if type(output_tokens) is not int or output_tokens < 1:
                raise WaveBlocked('VALID_OUTPUT_TOKEN_CAP_REQUIRED')
            characters = len(request['prompt']) + len(json.dumps(request['input'])) + len(json.dumps(request['response_schema']))
            input_tokens = math.ceil(characters / 4)
            costs.append({'trial_id': request['trial_id'], 'input_token_estimate': input_tokens,
                          'max_output_tokens': output_tokens,
                          'reserved_cost_usd': (input_tokens * rates['input'] + output_tokens * rates['output']) / 1e6})
    all_dirs = {p.resolve() for p in base.rglob('attempt-[0-9]*') if p.is_dir()}
    if all_dirs != observed:
        raise WaveBlocked('UNTRACKED_ATTEMPT_DIRECTORY')
    highest = sorted(costs, key=lambda c: c['reserved_cost_usd'], reverse=True)[:max_new]
    reserve = sum(c['reserved_cost_usd'] for c in highest)
    report = {'known_usage_cost_estimate_usd': round(actual, 10), 'prior_attempts': attempts_count,
              'pending_trials': len(costs), 'max_new_calls': max_new,
              'next_wave_reserved_estimate_usd': round(reserve, 10),
              'projected_cost_estimate_usd': round(actual + reserve, 10),
              'api_budget_usd': config['billing']['api_budget_usd'],
              'estimate_method': 'CHARACTERS_DIVIDED_BY_FOUR_PLUS_MAX_OUTPUT_TOKENS',
              'reserve_selection': 'HIGHEST_COST_PENDING_REQUESTS',
              'strict_billing_upper_bound': False, 'billed_cost_usd': None,
              'unknown_usage_as_zero': False, 'reserved_requests': highest}
    if actual + reserve > config['billing']['api_budget_usd']:
        error = WaveBlocked('API_BUDGET_WOULD_BE_EXCEEDED')
        error.cost_report = report
        raise error
    return report


def account_usage_policy(config, evidence):
    """Use the frozen, explicitly approved account-monitoring responsibility."""
    billing = config.get('billing', {})
    if billing.get('quota_policy_confirmation') != USER_MANAGED_USAGE:
        return quota_check(evidence)
    for key in ('quota_policy_authorization_record', 'quota_policy_authorization_recorded_at'):
        if not isinstance(billing.get(key), str) or not billing[key].strip():
            raise WaveBlocked('USER_MANAGED_USAGE_AUTHORIZATION_RECORD_REQUIRED')
    return {'status': 'USER_MANAGED', 'windows': [],
            'policy': USER_MANAGED_USAGE, 'automatic_account_usage_queries': False,
            'account_remaining_percent_stop': None,
            'authorization_record': billing['quota_policy_authorization_record'],
            'authorization_recorded_at': billing['quota_policy_authorization_recorded_at']}


def run_wave(root, max_new, quota_evidence=None):
    """IR05: One bounded invocation; the caller must explicitly request each wave."""
    root = Path(root).resolve()
    if type(max_new) is not int or not 1 <= max_new <= MAX_NEW_CALLS:
        raise WaveBlocked('MAX_NEW_CALLS_MUST_BE_BETWEEN_1_AND_100')
    with locked(root / '.improvement.lock'):
        existing = list((root / 'improvement-waves').glob('wave-*'))
        sequence = max((int(p.name.split('-')[1]) for p in existing), default=0) + 1
        folder = root / 'improvement-waves' / f'wave-{sequence:04d}'
        folder.mkdir(parents=True)
        status = {'status': 'PREFLIGHT', 'at': now(), 'wave': sequence, 'max_new_calls': max_new}
        write(folder / 'status.json', status)
        def preflight():
            verify_implementation(root)
            evidence = read(quota_evidence) if isinstance(quota_evidence, (str, Path)) else quota_evidence
            write(folder / 'quota-evidence.json', evidence)
            quota = account_usage_policy(read(root / 'config.json'), evidence)
            budget = budget_check(root, max_new)
            write(folder / 'preflight.json', {'quota': quota, 'budget': budget, 'at': now()})
            event(root, 'IMPROVEMENT_WAVE_AUTHORIZED', wave=sequence, max_new_calls=max_new,
                  quota_min_remaining_percent=min((w['remaining_percent'] for w in quota['windows']), default=None),
                  account_usage_policy=quota['status'],
                  projected_cost_estimate_usd=budget['projected_cost_estimate_usd'])
        try:
            # The pipeline runs the callback while holding its own process lock.
            summary = pipeline.run(root, max_new=max_new, resume_limits=True, preflight=preflight)
            budget_after = budget_check(root, 0)
            before = read(folder / 'preflight.json')['budget']['prior_attempts']
            status.update(status='WAVE_FINISHED', ended_at=now(), budget_after=budget_after,
                          new_model_calls=budget_after['prior_attempts'] - before,
                          pipeline_status=read(root / 'state.json', {}).get('status'))
            write(folder / 'summary.json', summary)
            event(root, 'IMPROVEMENT_WAVE_FINISHED', wave=sequence, pipeline_status=status['pipeline_status'])
        except Exception as error:
            entered = (folder / 'preflight.json').exists()
            status.update(status='WAVE_STOPPED' if entered else 'PREFLIGHT_BLOCKED', ended_at=now(), reason=str(error),
                          new_model_calls=None if entered else 0)
            if hasattr(error, 'cost_report'):
                write(folder / 'cost-block.json', error.cost_report)
            event(root, 'IMPROVEMENT_WAVE_STOPPED', wave=sequence, reason=str(error),
                  new_model_calls=None if entered else 0)
            write(folder / 'status.json', status)
            write(root / 'improvement-status.json', status)
            raise
        write(folder / 'status.json', status)
        write(root / 'improvement-status.json', status)
        return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepared = commands.add_parser('prepare')
    prepared.add_argument('--config', required=True, type=Path)
    wave = commands.add_parser('run-wave')
    wave.add_argument('--run-path', required=True, type=Path)
    wave.add_argument('--max-new-calls', required=True, type=int)
    wave.add_argument('--quota-evidence', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(prepare(args.config))
    else:
        print(json.dumps(run_wave(args.run_path, args.max_new_calls, args.quota_evidence), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
