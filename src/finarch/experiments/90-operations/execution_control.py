"""Pause an approved run and stop only processes linked to its saved requests."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])


def pause(root, reason):
    root = Path(root).resolve()
    state = store.read(root / 'state.json')
    state['execution_control'] = {**state.get('execution_control', {}), **{
        stage: {'paused': True, 'reason': reason, 'updated_at': store.now()}
        for stage in ('evaluation', 'analysis')}}
    store.write(root / 'state.json', state)
    # Stop the coordinator before inspecting its independent CLI process groups.
    scheduler = store.read(root / '02_analysis/scheduler.json', {})
    sequence_record = store.read(root / '02_analysis/sequence-state.json', {})
    parent = scheduler.get('pid') or sequence_record.get('pid')
    if isinstance(parent, int):
        command = subprocess.run(['ps', '-p', str(parent), '-o', 'args='], capture_output=True, text=True).stdout
        coordinator = ('finarch.experiments.pipeline' in command or
                       'finarch.experiments.90-operations.analysis_sequence' in command)
        if coordinator and root.name in command:
            try:
                os.kill(parent, signal.SIGTERM)
            except ProcessLookupError:
                pass
            sequence_path = root / '02_analysis/sequence-state.json'
            sequence = store.read(sequence_path, {})
            if sequence.get('pid') == parent:
                store.write(sequence_path, {**sequence, 'status': 'PAUSED_BY_USER',
                            'reason': reason, 'updated_at': store.now()})
    work_to_attempt = {}
    for p in (root / '02_analysis').glob('*/calls/*/attempt-*/provider-request.json'):
        command = store.read(p).get('command', [])
        if '-C' in command:
            work_to_attempt[str(Path(command[command.index('-C') + 1]).resolve())] = p.parent
    inventory = subprocess.run(['lsof', '-a', '-d', 'cwd', '-c', 'codex', '-F', 'pn'],
                               capture_output=True, text=True, timeout=30).stdout
    targets = {}
    pid = None
    for line in inventory.splitlines():
        if line.startswith('p'):
            pid = int(line[1:])
        elif line.startswith('n'):
            work = str(Path(line[1:]).resolve())
            if pid and work in work_to_attempt:
                targets[pid] = (Path(work), work_to_attempt[work])
    for pid in targets:
        try:
            if os.getpgid(pid) == pid:
                os.killpg(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if targets:
        time.sleep(1)
    for pid, (work, attempt) in targets.items():
        try:
            os.kill(pid, 0)
            if os.getpgid(pid) == pid:
                os.killpg(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for name in ('stdout.txt', 'stderr.txt', 'tool-events.jsonl'):
            source = work / name
            if source.exists():
                destination = attempt / ('interrupted-' + name)
                if not destination.exists():
                    shutil.copyfile(source, destination)
        store.write(attempt / 'interruption.json', {
            'status': 'STOPPED_BY_USER', 'pid': pid, 'stopped_at': store.now(),
            'reason': reason, 'delivery_status': 'UNCONFIRMED', 'automatic_replay': False})
    state = store.read(root / 'state.json')
    state['analysis'] = {**state.get('analysis', {}), 'status': 'PAUSED_BY_USER', 'reason': reason, 'updated_at': store.now()}
    state['full_pipeline'] = {**state.get('full_pipeline', {}), 'status': 'PAUSED_BY_USER', 'reason': reason, 'updated_at': store.now()}
    store.write(root / 'state.json', state)
    for stage in ('02_comparison', '03_research', '04_quadrant'):
        path = root / '02_analysis' / stage / 'state.json'
        if path.exists():
            previous = store.read(path)
            if previous.get('status') not in ('COLLECTED', 'COMPLETE'):
                store.write(path, {**previous, 'status': 'PAUSED_BY_USER', 'reason': reason, 'updated_at': store.now()})
    if scheduler:
        store.write(root / '02_analysis/scheduler.json', {**scheduler, 'status': 'PAUSED_BY_USER',
                    'active_calls': 0, 'updated_at': store.now()})
    result = {'status': 'PAUSED_BY_USER', 'stopped_codex_processes': len(targets), 'new_model_calls': 0}
    store.event(root, 'EXPERIMENT_PAUSED_BY_USER', reason=reason, **result)
    return result


def resume_analysis(root, authorization):
    """Resume unsent Analysis work while preserving interrupted delivery uncertainty."""
    if not isinstance(authorization, str) or not authorization.strip():
        raise ValueError('ANALYSIS_RESUME_AUTHORIZATION_REQUIRED')
    root = Path(root).resolve()
    with store.locked(root / '.analysis.lock'), store.locked(root / '02_analysis/.sequence.lock'):
        state = store.read(root / 'state.json')
        if not state.get('execution_control', {}).get('analysis', {}).get('paused'):
            raise ValueError('ANALYSIS_RESUME_REQUIRES_PAUSED_RUN')
        if not state.get('models') or any(m.get('status') != 'FINISHED' for m in state['models'].values()):
            raise ValueError('ANALYSIS_RESUME_REQUIRES_COMPLETE_EVALUATION')
        preserved = []
        for record in (root / '02_analysis').glob('*/calls/*/attempt-*/interruption.json'):
            interruption = store.read(record)
            if (record.parent / 'result.json').exists():
                continue
            try:
                os.kill(interruption['pid'], 0)
            except ProcessLookupError:
                pass
            else:
                raise ValueError('INTERRUPTED_PROCESS_STILL_ALIVE')
            req = store.read(record.parent / 'request.json')
            store.write(record.parent / 'result.json', {
                'trial_id': req['trial_id'], 'item_id': req.get('item_id'), 'stage': req['stage'],
                'status': 'UNKNOWN_DELIVERY', 'error': 'INTERRUPTED', 'usage': None,
                'requested_model': req['model'], 'reasoning_effort_requested': req['reasoning_effort'],
                'transport': 'codex_cli', 'automatic_replay': False,
                'interruption_record': 'interruption.json'})
            preserved.append(req['trial_id'])
        state['execution_control']['analysis'] = {'paused': False, 'reason': authorization, 'updated_at': store.now()}
        state['analysis'] = {**state.get('analysis', {}), 'status': 'PREPARED', 'updated_at': store.now()}
        state['full_pipeline'] = {**state.get('full_pipeline', {}), 'status': 'WAIT_ANALYSIS', 'updated_at': store.now()}
        store.write(root / 'state.json', state)
        result = {'status': 'ANALYSIS_RESUMED', 'preserved_unknown_trial_ids': preserved,
                  'new_model_calls': 0, 'evaluation_control_unchanged': True}
        store.event(root, 'ANALYSIS_RESUMED', authorization=authorization, **result)
        return result


def retry_analysis_requests(root, stage, trial_ids, authorization):
    """Replay only explicitly selected, terminated uncertain calls via the pipeline."""
    backend = __import__('finarch.experiments.02-analysis.llm_backend', fromlist=['*'])
    root = Path(root).resolve()
    with store.locked(root / '.analysis.lock'), store.locked(root / '02_analysis/.sequence.lock'):
        store.verify(root)
        if store.read(root / 'state.json').get('execution_control', {}).get('analysis', {}).get('paused'):
            raise ValueError('SCOPED_RETRY_REQUIRES_RESUMED_ANALYSIS')
        config, _ = backend.configuration(root)
        if config['backend'] != 'codex':
            raise ValueError('SCOPED_RETRY_REQUIRES_CODEX_BACKEND')
        folder = root / '02_analysis' / stage
        requests = store.rows(folder / 'manifest.jsonl')
        selected = set(trial_ids)
        if not selected or selected - {r['trial_id'] for r in requests}:
            raise ValueError('SCOPED_RETRY_IDS_NOT_IN_MANIFEST')
        backend.write_state(root, folder, requests, 'codex')
        backend.analysis_config.authorize_unknown_delivery_retry(
            root, stage, trial_ids, authorization, config=config)
        store.event(root, 'ANALYSIS_SCOPED_RETRY_STARTED', stage=stage,
                    trial_ids=sorted(selected), authorization=authorization,
                    other_requests_preserved=True)
        state = backend.run(root, stage, requests, recovery_retry_ids=selected)
        state = {**state, 'status': 'COLLECTED' if state['valid'] == state['requests'] else 'BLOCKED',
                 'reason': 'SCOPED_RETRY_FINISHED_OTHER_WORK_PRESERVED'}
        store.write(folder / 'state.json', state)
        current = store.read(root / 'state.json')
        current['analysis'] = {**current.get('analysis', {}), **state,
                               'stage': backend.STAGE_LABELS[stage]}
        current['full_pipeline'] = {**current.get('full_pipeline', {}),
            'status': 'WAIT_ANALYSIS' if state['status'] == 'COLLECTED' else 'NEEDS_REVIEW',
            'analysis_execution': state['status'], 'updated_at': store.now()}
        store.write(root / 'state.json', current)
        schedule_path = root / '02_analysis/scheduler.json'
        schedule = store.read(schedule_path, {})
        store.write(schedule_path, {**schedule, 'status': state['status'], 'active_calls': 0,
                    'queued_calls': state['pending'], 'updated_at': store.now()})
        outcomes = {r['trial_id']: backend.latest(folder, r)['status']
                    for r in requests if r['trial_id'] in selected}
        store.event(root, 'ANALYSIS_SCOPED_RETRY_FINISHED', stage=stage,
                    outcomes=outcomes, other_requests_preserved=True)
        return {**state, 'retried_outcomes': outcomes}
