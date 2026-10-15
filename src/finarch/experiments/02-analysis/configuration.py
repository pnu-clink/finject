"""Freeze the selected Analysis backend without editing frozen Evaluation settings."""
import os
from pathlib import Path

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
settings = __import__('finarch.experiments.90-operations.settings', fromlist=['*'])
scheduler = __import__('finarch.experiments.02-analysis.scheduler', fromlist=['*'])


def configure_schedule(root, path=settings.DEFAULT_CONFIG):
    """Record an explicit operational change while preserving frozen requests."""
    root = Path(root).resolve()
    store.verify(root)
    config = read(root)
    _, incoming = settings.load_file(path)
    schedule = scheduler.validate(incoming.get('schedule', {}))
    schedule = {k: schedule[k] for k in ('concurrency', 'timeout_seconds', 'adaptive')}
    with store.locked(root / '.analysis-schedule.lock'):
        previous = scheduler.policy(root, config)
        value = {'analysis_sha256': store.digest(config), 'schedule': schedule,
                 'source_path': str(Path(path).resolve()), 'source_sha256': store.file_hash(path),
                 'updated_at': store.now(), 'scope': 'CODEX_RUNTIME_SCHEDULE_ONLY'}
        store.write(root / '02_analysis/runtime-schedule.json', value)
        store.event(root, 'ANALYSIS_SCHEDULE_CONFIGURED', previous=previous,
                    schedule=schedule, frozen_analysis_unchanged=True, new_model_calls=0)
    return value


def authorize_unknown_delivery_retry(root, stage, trial_ids, authorization, config=None):
    """Record a one-time, explicit replay authorization without changing frozen inputs."""
    root = Path(root).resolve()
    config = config or read(root)
    if stage not in ('02_comparison', '03_research', '04_quadrant'):
        raise ValueError('ANALYSIS_RETRY_STAGE_INVALID')
    if not isinstance(authorization, str) or not authorization.strip():
        raise ValueError('ANALYSIS_RETRY_AUTHORIZATION_REQUIRED')
    requested = sorted(set(trial_ids))
    state = store.read(root / '02_analysis' / stage / 'state.json', {})
    unresolved = set(state.get('unresolved_trial_ids', []))
    if not requested or set(requested) - unresolved:
        raise ValueError('ANALYSIS_RETRY_IDS_NOT_CURRENTLY_UNRESOLVED')
    authorized_after_attempt = {}
    for trial_id in requested:
        call = root / '02_analysis' / stage / 'calls' / trial_id
        attempts = sorted(call.glob('attempt-*/result.json'))
        if not attempts:
            raise ValueError('ANALYSIS_RETRY_REQUIRES_FINISHED_TIMEOUT:' + trial_id)
        result = store.read(attempts[-1])
        process = store.read(attempts[-1].with_name('process.json'), {})
        ended = (process.get('state') == 'TIMEOUT' and process.get('ended_at')
                 and process.get('exit_code') is not None and result.get('error') == 'TIMEOUT')
        if result.get('error') == 'INTERRUPTED':
            interruption = store.read(attempts[-1].with_name('interruption.json'), {})
            pid = interruption.get('pid')
            ended = False
            if (type(pid) is int and pid > 0 and interruption.get('stopped_at')
                    and interruption.get('automatic_replay') is False):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    ended = True
                except PermissionError:
                    pass
        if result.get('status') != 'UNKNOWN_DELIVERY' or not ended:
            raise ValueError('ANALYSIS_RETRY_REQUIRES_CONFIRMED_PROCESS_END:' + trial_id)
        authorized_after_attempt[trial_id] = len(attempts)
    record = {'analysis_sha256': store.digest(config), 'stage': stage,
              'trial_ids': requested, 'authorization': authorization,
              'authorized_at': store.now(), 'scope': 'ONE_ADDITIONAL_CODEX_ATTEMPT_PER_ENDED_REQUEST',
              'authorized_after_attempt': authorized_after_attempt}
    with store.locked(root / '.analysis-retry.lock'):
        # Retry authority is scoped to the Analysis stage.  A completed
        # comparison-stage authorization must not prevent a later, explicitly
        # approved research-stage retry.
        base = root / '02_analysis' / stage
        target = base / 'unknown-delivery-retry.json'
        if target.exists():
            number = 2
            while (base / f'unknown-delivery-retry-{number:03d}.json').exists():
                number += 1
            target = base / f'unknown-delivery-retry-{number:03d}.json'
        store.write(target, record)
        store.event(root, 'ANALYSIS_UNKNOWN_DELIVERY_RETRY_AUTHORIZED',
                    stage=stage, trial_ids=requested, count=len(requested),
                    frozen_analysis_unchanged=True, authorization=authorization,
                    authorization_file=str(target.relative_to(root)))
    return record


def authorized_unknown_delivery_retries(root, stage, config):
    """Return only the frozen-config-bound IDs explicitly authorized for one replay."""
    root = Path(root)
    # Accept the earlier root-level record so existing approved retries remain
    # reproducible, while new records are isolated by stage.
    base = root / '02_analysis' / stage
    paths = [base / 'unknown-delivery-retry.json']
    paths += sorted(base.glob('unknown-delivery-retry-[0-9][0-9][0-9].json'))
    if not any(path.exists() for path in paths):
        paths = [root / '02_analysis' / 'unknown-delivery-retry.json']
    authorized = set()
    for path in paths:
        record = store.read(path, {})
        if record.get('analysis_sha256') != store.digest(config) or record.get('stage') != stage:
            continue
        values = record.get('trial_ids', [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            continue
        counts = record.get('authorized_after_attempt')
        if counts is None:
            authorized.update(values)  # Earlier authorization records predate attempt-count binding.
        elif isinstance(counts, dict):
            authorized.update(trial_id for trial_id in values
                if type(counts.get(trial_id)) is int
                and len(list((base / 'calls' / trial_id).glob('attempt-*/result.json')))
                == counts[trial_id])
    return authorized


def read(root):
    path = Path(root) / '02_analysis/config.json'
    snapshot = store.read(path)
    if snapshot is None:
        return store.read(Path(root) / 'config.json')['analysis']
    if store.digest(snapshot['analysis']) != snapshot['analysis_sha256']:
        raise ValueError('ANALYSIS_CONFIGURATION_CHANGED')
    return snapshot['analysis']


def freeze(root, path=settings.DEFAULT_CONFIG):
    root = Path(root).resolve()
    path = Path(path).resolve()
    store.verify(root)
    _, analysis = settings.load_file(path)
    if analysis.get('backend') not in ('codex', 'api'):
        raise ValueError('CONFIGURED_ANALYSIS_BACKEND_REQUIRED')
    target = root / '02_analysis/config.json'
    with store.locked(root / '.analysis.lock'):
        previous = store.read(target)
        if previous:
            if read(root) != analysis:
                raise ValueError('FROZEN_ANALYSIS_CONFIGURATION_MISMATCH')
            return previous
        if any((root / '02_analysis').glob('*/manifest.jsonl')):
            raise ValueError('ANALYSIS_ALREADY_STARTED_CANNOT_CHANGE_CONFIGURATION')
        snapshot = {'analysis': analysis, 'analysis_sha256': store.digest(analysis),
                    'source_path': str(path), 'source_sha256': store.file_hash(path),
                    'frozen_at': store.now()}
        store.write(target, snapshot)
        store.event(root, 'ANALYSIS_CONFIGURATION_FROZEN', backend=analysis['backend'],
                    model=analysis['backends'][analysis['backend']]['model'],
                    source_sha256=snapshot['source_sha256'], new_model_calls=0)
        return snapshot
