"""Bounded, authorized retries after a completed Analysis wave; preserve every attempt."""
import os
from pathlib import Path
import re
import time

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
configuration = __import__('finarch.experiments.02-analysis.configuration', fromlist=['*'])
CAPACITY = re.compile(r'at capacity|overload|server.?busy|temporarily unavailable|\b50[234]\b', re.I)


def reason(folder, request, result, allowed_statuses=()):
    """Retry only known temporary failures or a timeout whose process has ended."""
    if not result:
        return None
    status = result.get('status')
    if status in ('RATE_LIMITED', 'AUTH_BLOCKED') and status in allowed_statuses:
        paths = sorted((Path(folder) / 'calls' / request['trial_id']).glob('attempt-*/result.json'))
        process = store.read(paths[-1].with_name('process.json'), {}) if paths else {}
        if process.get('ended_at') and process.get('exit_code') is not None:
            return 'ENDED_RATE_LIMIT' if status == 'RATE_LIMITED' else 'ENDED_AUTH_BLOCK'
    if status in allowed_statuses and status in ('INVALID_RESPONSE', 'OUTPUT_TRUNCATED', 'TRANSIENT_ERROR'):
        return status
    if status == 'PROVIDER_ERROR' and CAPACITY.search(str(result.get('error', ''))):
        return 'SERVER_CAPACITY'
    if status != 'UNKNOWN_DELIVERY' or result.get('error') != 'TIMEOUT':
        return None
    paths = sorted((Path(folder) / 'calls' / request['trial_id']).glob('attempt-*/result.json'))
    if not paths:
        return None
    process = store.read(paths[-1].with_name('process.json'), {})
    if process.get('state') == 'TIMEOUT' and process.get('ended_at') and process.get('exit_code') is not None:
        return 'ENDED_TIMEOUT'
    return None


def allowed_statuses(policy, folder, request):
    """Consume a scoped validation authorization after one additional saved attempt."""
    statuses = list(policy.get('additional_retry_statuses', []))
    claim = policy.get('validation_retry_claims', {}).get(Path(folder).name, {}).get(request['trial_id'])
    if claim and len(list((Path(folder) / 'calls' / request['trial_id']).glob('attempt-*/result.json'))) == claim['after_attempt']:
        statuses.append(claim.get('status', 'INVALID_RESPONSE'))
    return statuses


def configure(root, authorization, *, include_validation_failures=False, include_research=False, include_quadrant=False,
              validation_trial_ids=(), validation_stage=None):
    if not isinstance(authorization, str) or not authorization.strip():
        raise ValueError('ANALYSIS_RETRY_AUTHORIZATION_REQUIRED')
    root = Path(root).resolve()
    with store.locked(root / '.analysis.lock'):
        config = configuration.read(root)
        if config['backend'] != 'codex':
            raise ValueError('ANALYSIS_RECOVERY_REQUIRES_CODEX_BACKEND')
        target = root / '02_analysis/retry-policy.json'
        previous = store.read(target)
        if validation_trial_ids:
            if not include_validation_failures or validation_stage not in ('02_comparison', '03_research', '04_quadrant'):
                raise ValueError('SCOPED_VALIDATION_RETRY_REQUIRES_STAGE_AND_FLAG')
            folder = root / '02_analysis' / validation_stage
            claims = {}
            manifest_ids = {r['trial_id'] for r in store.rows(folder / 'manifest.jsonl')}
            for trial_id in sorted(set(validation_trial_ids)):
                paths = sorted((folder / 'calls' / trial_id).glob('attempt-*/result.json'))
                process = store.read(paths[-1].with_name('process.json'), {}) if paths else {}
                status = store.read(paths[-1]).get('status') if paths else None
                if (trial_id not in manifest_ids or not paths or status not in ('INVALID_RESPONSE', 'RATE_LIMITED', 'AUTH_BLOCKED')
                        or not process.get('ended_at') or process.get('exit_code') is None):
                    raise ValueError('SCOPED_VALIDATION_RETRY_REQUIRES_ENDED_INVALID_RESPONSE:' + trial_id)
                claims[trial_id] = {'after_attempt': len(paths), 'status': status, 'authorization': authorization, 'authorized_at': store.now()}
            if not previous or previous['analysis_sha256'] != store.digest(config):
                raise ValueError('SCOPED_VALIDATION_RETRY_REQUIRES_EXISTING_MATCHING_POLICY')
            number = len(list(target.parent.glob('retry-policy-extension-*.json'))) + 1
            scopes = {**previous.get('validation_retry_claims', {})}
            scopes[validation_stage] = {**scopes.get(validation_stage, {}), **claims}
            store.write(target.parent / f'retry-policy-extension-{number:03d}.json',
                        {'previous': previous, 'validation_retry_claims': scopes, 'authorization': authorization,
                         'updated_at': store.now(), 'budget_reset': False})
            previous = {**previous, 'validation_retry_claims': scopes}
            store.write(target, previous)
            store.event(root, 'ANALYSIS_SCOPED_VALIDATION_RETRY_AUTHORIZED', stage=validation_stage,
                        trial_ids=sorted(claims), authorization=authorization, additional_attempts_per_id=1,
                        budget_reset=False, new_model_calls=0)
            # Stage-wide validation retries remain unchanged; only the selected IDs are added.
            include_validation_failures = False
        if previous:
            if previous['analysis_sha256'] != store.digest(config):
                raise ValueError('ANALYSIS_RETRY_POLICY_CONFIG_CHANGED')
            stages = list(previous['stages'])
            if include_research and '03_research' not in stages:
                stages.append('03_research')
            if include_quadrant and '04_quadrant' not in stages:
                stages.append('04_quadrant')
            statuses = list(previous.get('additional_retry_statuses', []))
            if include_validation_failures:
                statuses = ['INVALID_RESPONSE', 'OUTPUT_TRUNCATED', 'TRANSIENT_ERROR']
            if stages != previous['stages'] or statuses != previous.get('additional_retry_statuses', []):
                # Keep the same budget identity and completed rounds; extend scope explicitly.
                number = len(list(target.parent.glob('retry-policy-extension-*.json'))) + 1
                change = {'previous': previous, 'stages': stages, 'additional_retry_statuses': statuses,
                          'authorization': authorization, 'updated_at': store.now(), 'budget_reset': False}
                store.write(target.parent / f'retry-policy-extension-{number:03d}.json', change)
                previous = {**previous, 'stages': stages, 'additional_retry_statuses': statuses,
                            'extension_authorization': authorization, 'updated_at': change['updated_at']}
                store.write(target, previous)
                store.event(root, 'ANALYSIS_RETRY_POLICY_EXTENDED', stages=stages,
                            additional_retry_statuses=statuses, budget_reset=False, new_model_calls=0)
            return previous
        policy = {'enabled': True, 'stages': ['02_comparison'] + (['03_research'] if include_research else []) + (['04_quadrant'] if include_quadrant else []), 'max_rounds': 3,
                  'backoff_seconds': [60, 120, 240], 'authorization': authorization,
                  'analysis_sha256': store.digest(config), 'configured_at': store.now(),
                  'scope': 'FAILED_ANALYSIS_ONLY_NO_EVALUATION_OR_SUCCESS_REPLAY'}
        if include_validation_failures:
            policy['additional_retry_statuses'] = ['INVALID_RESPONSE', 'OUTPUT_TRUNCATED', 'TRANSIENT_ERROR']
        policy['policy_id'] = store.digest(policy)
        store.write(target, policy)
        store.event(root, 'ANALYSIS_RETRY_POLICY_CONFIGURED', **policy, new_model_calls=0)
        return policy


def paused(root):
    return store.read(Path(root) / 'state.json', {}).get('execution_control', {}).get('analysis', {}).get('paused', False)


def publish_wait(root, folder, state, record):
    state = {**state, 'status': 'RETRY_WAIT', 'retry_round': record['round'],
             'retry_count': len(record['trial_ids']), 'retry_not_before': record['not_before_epoch'],
             'updated_at': store.now()}
    store.write(folder / 'state.json', state)
    current = store.read(root / 'state.json')
    current['analysis'] = {**state, 'stage': {'02_comparison': 'A02', '03_research': 'A03', '04_quadrant': 'A04'}[folder.name]}
    store.write(root / 'state.json', current)
    schedule_path = root / '02_analysis/scheduler.json'
    schedule = store.read(schedule_path, {})
    store.write(schedule_path, {**schedule, 'pid': os.getpid(), 'stage': folder.name,
        'status': 'RETRY_WAIT', 'active_calls': 0, 'queued_calls': len(record['trial_ids']),
        'retry_round': record['round'], 'retry_not_before': record['not_before_epoch'], 'updated_at': store.now()})


def recover(root, stage, requests, state, backend):
    """Drain -> classify -> bounded retries -> let the caller refresh coverage and enter A03."""
    root = Path(root)
    policy = store.read(root / '02_analysis/retry-policy.json', {})
    if not policy.get('enabled') or stage not in policy.get('stages', []) or state['status'] == 'COLLECTED':
        return state
    if policy['analysis_sha256'] != store.digest(configuration.read(root)):
        raise ValueError('ANALYSIS_RETRY_POLICY_CONFIG_CHANGED')
    folder = root / '02_analysis' / stage
    schedule = store.read(root / '02_analysis/scheduler.json', {})
    if state.get('pending', 0) or (schedule.get('stage') == stage and
                                 (schedule.get('active_calls', 0) or
                                  (schedule.get('status') != 'RETRY_WAIT' and schedule.get('queued_calls', 0)))):
        # Never spend recovery rounds while fresh work or an existing call remains.
        return state
    if state.get('reason') in backend.ADMISSION_BLOCKERS:
        return state
    for number in range(1, policy['max_rounds'] + 1):
        if paused(root):
            return {**state, 'status': 'PAUSED_BY_USER'}
        record_path = folder / 'retry-rounds' / f'round-{number:03d}.json'
        record = store.read(record_path)
        if record:
            if record['policy_id'] != policy['policy_id']:
                raise ValueError('ANALYSIS_RETRY_ROUND_POLICY_CHANGED')
            if record['status'] == 'FINISHED':
                continue
            if record['status'] == 'STARTED':
                # An interrupted coordinator must not cause uncertain delivery to be replayed.
                return {**state, 'status': 'BLOCKED', 'reason': 'RETRY_ROUND_DELIVERY_UNCONFIRMED'}
        eligible = {}
        reviews = __import__('finarch.experiments.02-analysis.02-comparison.response_assessments', fromlist=['*'])
        review_ids = reviews.recheck_trials(requests, backend, folder) if stage == '02_comparison' else None
        for request in requests:
            if review_ids is not None and request['trial_id'] not in review_ids:
                continue
            saved = backend.latest(folder, request)
            failure = reason(folder, request, saved, allowed_statuses(policy, folder, request))
            if failure:
                eligible[request['trial_id']] = {'reason': failure,
                    'after_attempt': len(backend.attempts(folder, request)), 'request_sha256': store.digest(request)}
        if not eligible:
            return state
        if record is None:
            delay = policy['backoff_seconds'][number - 1]
            record = {'policy_id': policy['policy_id'], 'round': number, 'stage': stage,
                'status': 'WAITING', 'trial_ids': sorted(eligible), 'claims': eligible,
                'delay_seconds': delay, 'not_before_epoch': time.time() + delay, 'planned_at': store.now()}
            store.write(record_path, record)
            store.event(root, 'ANALYSIS_RETRY_PLANNED', stage=stage, round=number,
                        requests=len(eligible), delay_seconds=delay, trial_ids=record['trial_ids'])
        publish_wait(root, folder, state, record)
        while time.time() < record['not_before_epoch']:
            if paused(root):
                return {**state, 'status': 'PAUSED_BY_USER'}
            time.sleep(max(0, min(1, record['not_before_epoch'] - time.time())))
        if paused(root):
            return {**state, 'status': 'PAUSED_BY_USER'}
        # Recheck immediately before transmission; newly saved valid responses are excluded.
        ids = set(record['trial_ids']) & set(eligible)
        for request in requests:
            if request['trial_id'] not in ids:
                continue
            saved = backend.latest(folder, request)
            if not reason(folder, request, saved, allowed_statuses(policy, folder, request)):
                ids.remove(request['trial_id'])
            elif (len(backend.attempts(folder, request)) != record['claims'][request['trial_id']]['after_attempt']
                  or store.digest(request) != record['claims'][request['trial_id']]['request_sha256']):
                raise ValueError('ANALYSIS_RETRY_ATTEMPT_CHANGED')
        if not ids:
            record.update(status='FINISHED', finished_at=store.now(), requested=0)
            store.write(record_path, record)
            state = backend.write_state(root, folder, requests, 'codex')
            if state['status'] == 'COLLECTED':
                return state
            continue
        record.update(status='STARTED', started_at=store.now(), submitted_trial_ids=sorted(ids))
        store.write(record_path, record)
        store.event(root, 'ANALYSIS_RETRY_STARTED', stage=stage, round=number, requests=len(ids), trial_ids=sorted(ids))
        state = backend.run(root, stage, requests, recovery_retry_ids=ids)
        record.update(status='FINISHED', finished_at=store.now(), result=state)
        store.write(record_path, record)
        store.event(root, 'ANALYSIS_RETRY_FINISHED', stage=stage, round=number, status=state['status'],
                    valid=state.get('valid'), requests=len(ids))
        if state['status'] in ('COLLECTED', 'PAUSED_BY_USER'):
            return state
    return {**state, 'status': 'BLOCKED', 'reason': 'ANALYSIS_RETRY_LIMIT_REACHED'}
