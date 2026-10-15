"""Run an authorized ordered Analysis queue without invoking Evaluation."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import importlib
import os
from pathlib import Path
import time
import traceback

analysis = importlib.import_module('finarch.experiments.02-analysis.pipeline')
store = analysis.store
TERMINAL = {'COLLECTED', 'COMPLETE', 'ASSESSMENTS_COLLECTED_NO_PATTERNS'}


def run(roots, interval=30, *, after_run=None):
    roots = [Path(root).resolve() for root in roots]
    after_run = Path(after_run).resolve() if after_run else None
    if after_run and (after_run in roots or not (after_run / 'state.json').is_file()):
        raise ValueError('ANALYSIS_PREDECESSOR_INVALID')
    folder = roots[0] / '02_analysis'
    state = {'pid': os.getpid(), 'runs': [str(root) for root in roots], 'status': 'RUNNING', 'completed': []}
    def publish(status, root, **detail):
        pipeline = importlib.import_module('finarch.experiments.pipeline')
        final_status = ('COMPLETE_NO_PATTERN_FINDINGS' if detail.get('result', {}).get('status') ==
                        'ASSESSMENTS_COLLECTED_NO_PATTERNS' else 'COMPLETE')
        progress_status = {'ANALYZING': 'RUNNING', 'RUN_COMPLETED': final_status,
                           'NEEDS_REVIEW': 'NEEDS_REVIEW', 'FAILED': 'FAILED',
                           'PAUSED_BY_USER': 'PAUSED_BY_USER', 'WAIT_EVALUATION': 'WAIT_EVALUATION'}
        if status in progress_status:
            pipeline.progress(root, status=progress_status[status], stage='DONE' if status ==
                              'RUN_COMPLETED' else 'ANALYSIS', execution_scope='ANALYSIS_ONLY',
                              analysis_execution=detail.get('result', {}).get('status', status),
                              **({'error': detail['error']} if 'error' in detail else {}))
        state.update(status=status, active_run=root.name, updated_at=store.now(), **detail)
        store.write(folder / 'sequence-state.json', state)
        print(store.encoded(state).decode(), flush=True)
    with store.locked(folder / '.sequence.lock'):
        if after_run or len(roots) > 1:
            for position, root in enumerate(roots):
                queued = store.read(root / 'state.json')
                queued['queued_execution'] = {'status': 'WAITING_FOR_ANALYSIS', 'execution_scope': 'ANALYSIS_ONLY',
                    'after_run': (after_run.name if after_run else None) if position == 0 else roots[position - 1].name,
                    'sequence': [r.name for r in roots], 'queue_pid': os.getpid(), 'updated_at': store.now()}
                store.write(root / 'state.json', queued)
                store.event(root, 'ANALYSIS_QUEUED', **queued['queued_execution'])
        if after_run:
            publish('WAIT_PRECEDING_ANALYSIS', roots[0], after_run=after_run.name)
            while True:
                previous = store.read(after_run / 'state.json', {})
                if previous.get('analysis', {}).get('status') == 'COMPLETE' and previous.get('full_pipeline', {}).get('status') == 'COMPLETE':
                    break
                if store.read(roots[0] / 'state.json').get('execution_control', {}).get('analysis', {}).get('paused'):
                    publish('PAUSED_BY_USER', roots[0])
                    return
                # A failed or paused predecessor remains a completion gate. Never replay its calls.
                time.sleep(interval)
        for root in roots:
            store.command(root)
            publish('WAIT_EVALUATION', root)
            try:
                while True:
                    saved = store.read(root / 'state.json', {})
                    controls = saved.get('execution_control', {})
                    if controls.get('analysis', {}).get('paused'):
                        publish('PAUSED_BY_USER', root)
                        return
                    models = saved.get('models', {})
                    if models and all(m.get('status') == 'FINISHED' for m in models.values()):
                        break
                    if controls.get('evaluation', {}).get('paused'):
                        publish('PAUSED_BY_USER', root)
                        return
                    time.sleep(interval)
                output = root / '02_analysis/execution.log'
                output.parent.mkdir(parents=True, exist_ok=True)
                saved = store.read(root / 'state.json')
                if (saved.get('queued_execution') or {}).get('execution_scope') == 'ANALYSIS_ONLY':
                    saved['queued_execution']['status'] = 'STARTED'
                    saved['queued_execution']['updated_at'] = store.now()
                    store.write(root / 'state.json', saved)
                store.event(root, 'ANALYSIS_SEQUENCE_STARTED', sequence=state['runs'], pid=os.getpid())
                publish('ANALYZING', root)
                with output.open('a', buffering=1) as handle, redirect_stdout(handle), redirect_stderr(handle):
                    while True:
                        print(f'[{store.now()}] ANALYSIS_START {root.name}', flush=True)
                        result = analysis.run(root)
                        print(store.encoded(result).decode(), flush=True)
                        if result['status'] != 'RUNNING':
                            break
                        time.sleep(interval)
                if result['status'] not in TERMINAL:
                    publish('NEEDS_REVIEW', root, result=result)
                    return
                state['completed'].append(root.name)
                store.event(root, 'ANALYSIS_SEQUENCE_RUN_COMPLETED', status=result['status'])
                publish('RUN_COMPLETED', root, result=result)
            except Exception as error:
                traceback.print_exc()
                store.event(root, 'ANALYSIS_SEQUENCE_FAILED', error=str(error), error_type=type(error).__name__)
                publish('FAILED', root, error=str(error))
                return
        publish('COMPLETE', roots[-1])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', required=True)
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--after-run')
    args = parser.parse_args()
    run(args.run, args.interval, after_run=args.after_run)
