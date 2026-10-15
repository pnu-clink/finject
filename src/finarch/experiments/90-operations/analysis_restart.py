"""Archive paused Analysis before an explicitly authorized model change."""
import os
from pathlib import Path
import shutil
import subprocess

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
settings = __import__('finarch.experiments.90-operations.settings', fromlist=['*'])
configuration = __import__('finarch.experiments.02-analysis.configuration', fromlist=['*'])
backend = __import__('finarch.experiments.02-analysis.llm_backend', fromlist=['*'])


def run(root, path, authorization):
    """Accept a paused run and config; preserve old calls and prepare new identities."""
    root, path = Path(root).resolve(), Path(path).resolve()
    if not isinstance(authorization, str) or not authorization.strip():
        raise ValueError('ANALYSIS_RESTART_AUTHORIZATION_REQUIRED')
    store.verify(root)
    _, selected = settings.load_file(path)
    mode = selected.get('backend')
    if mode not in ('codex', 'api') or mode not in selected.get('backends', {}):
        raise ValueError('CONFIGURED_ANALYSIS_BACKEND_REQUIRED')
    with store.locked(root / '.analysis-restart.lock'), store.locked(root / '.full-pipeline.lock'), store.locked(root / '.analysis.lock'):
        saved = store.read(root / 'state.json')
        if not saved.get('execution_control', {}).get('analysis', {}).get('paused'):
            raise ValueError('ANALYSIS_RESTART_REQUIRES_PAUSED_RUN')
        models = saved.get('models', {})
        if not models or any(m.get('status') != 'FINISHED' for m in models.values()):
            raise ValueError('ANALYSIS_RESTART_REQUIRES_FINISHED_EVALUATION')
        base = root / '02_analysis'
        previous = configuration.read(root)
        for record in ('scheduler.json', 'sequence-state.json'):
            pid = store.read(base / record, {}).get('pid')
            if isinstance(pid, int) and pid != os.getpid():
                cmd = subprocess.run(['ps', '-p', str(pid), '-o', 'args='], capture_output=True, text=True).stdout
                if root.name in cmd and ('finarch.experiments.pipeline' in cmd or 'analysis_sequence' in cmd):
                    raise ValueError('ANALYSIS_RESTART_COORDINATOR_STILL_RUNNING')
        workdirs = set()
        for p in base.glob('*/calls/*/attempt-*/provider-request.json'):
            cmd = store.read(p).get('command', [])
            if '-C' in cmd:
                workdirs.add(str(Path(cmd[cmd.index('-C') + 1]).resolve()))
        inventory = subprocess.run(['lsof', '-a', '-d', 'cwd', '-c', 'codex', '-F', 'n'],
                                   capture_output=True, text=True, timeout=30).stdout
        if any(line[1:] in workdirs for line in inventory.splitlines() if line.startswith('n')):
            raise ValueError('ANALYSIS_RESTART_CODEX_STILL_RUNNING')
        old_requests = store.rows(base / '02_comparison/manifest.jsonl')
        hashes = {str(p.relative_to(base)): store.file_hash(p) for p in base.rglob('*')
                  if p.is_file() and p.name not in ('history-manifest.json', 'state-at-restart.json')}
        stamp = store.now().replace(':', '').replace('+', '-').replace('T', '-')
        archive = root / '02_analysis-history' / stamp
        archive.parent.mkdir(exist_ok=True)
        if archive.exists():
            raise ValueError('ANALYSIS_RESTART_HISTORY_ALREADY_EXISTS')
        base.rename(archive)
        store.write(archive / 'state-at-restart.json', saved)
        store.write(archive / 'history-manifest.json', hashes)
        base.mkdir()
        # Reuse only Python aggregation inputs, never the previous model's judgments.
        if (archive / '01_results').exists():
            shutil.copytree(archive / '01_results', base / '01_results')
        config_record = {'analysis': selected, 'analysis_sha256': store.digest(selected),
                         'source_path': str(path), 'source_sha256': store.file_hash(path),
                         'frozen_at': store.now()}
        store.write(base / 'config.json', config_record)
        if old_requests:
            requests = [backend.request(root, row['stage'], row['item_id'], row['prompt'],
                        row['response_schema'], row['input']) for row in old_requests]
            backend.freeze(root, '02_comparison', requests)
        record = {'authorization': authorization, 'previous_analysis_sha256': store.digest(previous),
                  'analysis_sha256': store.digest(selected), 'archive': str(archive.relative_to(root)),
                  'preserved_file_count': len(hashes), 'new_model_calls': 0,
                  'previous_judgments_reused': False, 'frozen_evaluation_unchanged': True,
                  'comparison_definitions_preserved': bool(old_requests), 'updated_at': store.now()}
        store.write(base / 'restart.json', record)
        saved['execution_control']['analysis'] = {'paused': False, 'reason': 'Authorized Analysis model change.',
                                                'updated_at': store.now()}
        saved['analysis'] = {'status': 'PREPARED', 'backend': mode,
                            'model': selected['backends'][mode]['model'],
                            'reasoning_effort': selected['backends'][mode]['reasoning_effort'],
                            'requests': len(old_requests), 'completed': 0, 'valid': 0,
                            'updated_at': store.now()}
        saved['full_pipeline'] = {**saved.get('full_pipeline', {}), 'status': 'WAIT_ANALYSIS',
                                  'stage': 'ANALYSIS', 'execution_scope': 'ANALYSIS_ONLY',
                                  'analysis_execution': 'PREPARED', 'updated_at': store.now()}
        store.write(root / 'state.json', saved)
        store.event(root, 'ANALYSIS_RESTART_PREPARED', **record, model=selected['backends'][mode]['model'])
        store.verify(root)
        return record


def restore(root, history, authorization):
    """Restore a preserved Analysis while retaining the current stopped attempt."""
    root = Path(root).resolve()
    if not authorization or not authorization.strip():
        raise ValueError('ANALYSIS_RESTORE_AUTHORIZATION_REQUIRED')
    source = store.path_in(root / '02_analysis-history', history)
    if source.parent != root / '02_analysis-history' or not source.is_dir():
        raise ValueError('ANALYSIS_RESTORE_HISTORY_REQUIRED')
    with store.locked(root / '.analysis-restart.lock'), store.locked(root / '.full-pipeline.lock'), store.locked(root / '.analysis.lock'):
        store.verify(root)
        saved = store.read(root / 'state.json')
        if not saved.get('execution_control', {}).get('analysis', {}).get('paused'):
            raise ValueError('ANALYSIS_RESTORE_REQUIRES_PAUSED_RUN')
        base = root / '02_analysis'
        for record in ('scheduler.json', 'sequence-state.json'):
            pid = store.read(base / record, {}).get('pid')
            if isinstance(pid, int) and pid != os.getpid():
                cmd = subprocess.run(['ps', '-p', str(pid), '-o', 'args='], capture_output=True, text=True).stdout
                if root.name in cmd and ('finarch.experiments.pipeline' in cmd or 'analysis_sequence' in cmd):
                    raise ValueError('ANALYSIS_RESTORE_COORDINATOR_STILL_RUNNING')
        workdirs = set()
        for path in base.glob('*/calls/*/attempt-*/provider-request.json'):
            cmd = store.read(path).get('command', [])
            if '-C' in cmd:
                workdirs.add(str(Path(cmd[cmd.index('-C') + 1]).resolve()))
        inventory = subprocess.run(['lsof', '-a', '-d', 'cwd', '-c', 'codex', '-F', 'n'],
                                   capture_output=True, text=True, timeout=30).stdout
        if any(str(Path(line[1:]).resolve()) in workdirs for line in inventory.splitlines() if line.startswith('n')):
            raise ValueError('ANALYSIS_RESTORE_CODEX_STILL_RUNNING')
        hashes = store.read(source / 'history-manifest.json')
        previous_state = store.read(source / 'state-at-restart.json')
        if not isinstance(hashes, dict) or not isinstance(previous_state, dict):
            raise ValueError('ANALYSIS_RESTORE_HISTORY_RECORD_REQUIRED')
        for relative, expected in hashes.items():
            if store.file_hash(store.path_in(source, relative)) != expected:
                raise ValueError('ANALYSIS_HISTORY_CHANGED:' + relative)
        current_hashes = {str(p.relative_to(base)): store.file_hash(p) for p in base.rglob('*')
                          if p.is_file() and p.name not in ('history-manifest.json', 'state-at-restart.json')}
        stamp = store.now().replace(':', '').replace('+', '-').replace('T', '-') + '-before-restore'
        archived = root / '02_analysis-history' / stamp
        if archived.exists():
            raise ValueError('ANALYSIS_RESTORE_HISTORY_ALREADY_EXISTS')
        base.rename(archived)
        store.write(archived / 'history-manifest.json', current_hashes)
        store.write(archived / 'state-at-restart.json', saved)
        source.rename(base)
        saved['analysis'] = {**previous_state.get('analysis', {}), 'status': 'PAUSED_BY_USER',
                             'reason': 'Preserved original Analysis restored; tagged variant is separate.',
                             'updated_at': store.now()}
        saved['full_pipeline'] = {**previous_state.get('full_pipeline', {}), 'status': 'PAUSED_BY_USER',
                                  'updated_at': store.now()}
        store.write(root / 'state.json', saved)
        record = {'restored_from': str(source.relative_to(root)), 'preserved_current': str(archived.relative_to(root)),
                  'authorization': authorization, 'new_model_calls': 0, 'restored_files_verified': len(hashes)}
        store.event(root, 'ORIGINAL_ANALYSIS_RESTORED', **record)
        store.verify(root)
        return record
