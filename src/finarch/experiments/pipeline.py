"""Continue approved Evaluation -> Analysis runs with durable state and no re-solving."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
import time

import psutil

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
evaluation = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
analysis = __import__('finarch.experiments.02-analysis.pipeline', fromlist=['*'])
timing = __import__('finarch.experiments.02-analysis.timing', fromlist=['*'])


def progress(root, **fields):
    current = store.read(root / 'state.json')
    previous = current.get('full_pipeline', {})
    updated = {**previous, **fields, 'updated_at': store.now()}
    if fields.get('status') in ('RUNNING', 'COMPLETE', 'EVALUATION_COMPLETE'):
        for name in ('error', 'error_type', 'analysis_status', 'reason'):
            if name not in fields:
                updated.pop(name, None)
    current['full_pipeline'] = updated
    store.write(root / 'state.json', current)
    if any(previous.get(k) != v for k, v in fields.items()):
        store.event(root, 'FULL_PIPELINE_PROGRESS', **fields)
    return updated


def collect_when_ready(root, *, resume_limits=False):
    state = store.read(root / 'state.json')
    if state.get('status') == 'FINISHED':
        return True
    if state.get('status') not in ('PREPARED', 'RUNNING', 'BATCH_PENDING') and not (
            resume_limits and state.get('status') == 'INCOMPLETE'):
        raise ValueError('EVALUATION_REQUIRES_REVIEW:' + str(state.get('status')))
    with timing.measure(root, 'evaluation_collection'):
        evaluation.run(root, resume_limits=True) if resume_limits else evaluation.run(root)
    status = store.read(root / 'state.json')['status']
    if status == 'FINISHED':
        return True
    if status not in ('PREPARED', 'RUNNING', 'BATCH_PENDING'):
        raise ValueError('EVALUATION_REQUIRES_REVIEW:' + status)
    return False


def next_run(root, dataset):
    current = store.read(root / 'state.json')
    checkpoint = current.get('full_pipeline', {})
    if checkpoint.get('next_run'):
        target = root.parent / checkpoint['next_run']
        evaluation.verify(target)
        return target
    source = store.read(root / 'config.json')
    config = {'evaluation': deepcopy(source['evaluation']),
              'analysis': deepcopy(analysis.backend.analysis_config.read(root))}
    config['evaluation']['dataset'] = {**config['evaluation']['dataset'], **dataset}
    config['evaluation']['definition_source_run'] = str(root)
    reserved = checkpoint.get('reserved_next_run')
    target = root.parent / reserved if reserved else store.allocate(root.parent)
    progress(root, reserved_next_run=target.name, status='PREPARING_NEXT')
    if (target / 'state.json').exists() and (target / 'manifest.json').exists():
        evaluation.verify(target)
    else:
        evaluation.prepare(config, reserved_root=target)
    progress(root, next_run=target.name, status='NEXT_PREPARED')
    plan = store.read(layout.plan(target))
    store.event(root, 'NEXT_EVALUATION_PREPARED', run=target.name, models=plan['models'])
    return target


@timing.recorded('pipeline_total')
def run(root, *, following=None, interval=60, evaluation_only=False, resume_limits=False):
    if resume_limits and not evaluation_only:
        raise ValueError('RESUME_LIMITS_REQUIRES_EVALUATION_ONLY')
    root = Path(root).resolve()
    coordinator = root
    with store.locked(root / '.full-pipeline.lock'):
        previous = store.read(root / 'state.json').get('full_pipeline', {})
        sequence = previous.get('sequence', [root.name])
        if previous.get('following') != following and 'following' in previous:
            raise ValueError('CONTINUATION_PLAN_CHANGED')
        if resume_limits:
            store.verify(root)
            state = store.read(root / 'state.json')
            old_queue = state.get('queued_execution', {})
            authorizations = [m['output_budget']['authorization'] for m in store.configuration(root)['models']
                              if m.get('output_budget')]
            state['queued_execution'] = {**old_queue, 'status': 'STARTED',
                'execution_scope': 'EVALUATION_ONLY', 'resume_scope': 'UNSENT_REJECTED_AND_AUTHORIZED_LENGTH_RETRIES',
                'authorization': '\n'.join(authorizations) if authorizations else old_queue.get('authorization'),
                'previous_pid': old_queue.get('pid'), 'pid': os.getpid(),
                'process_started_at': psutil.Process().create_time(), 'cwd': str(Path.cwd().resolve()),
                'command': list(sys.orig_argv), 'updated_at': store.now()}
            store.write(root / 'state.json', state)
            store.event(root, 'EVALUATION_RESUMED', pid=os.getpid(), previous_pid=old_queue.get('pid'),
                        execution_scope='EVALUATION_ONLY', preserve_prior_attempts=True)
        progress(coordinator, status='RUNNING', sequence=sequence, following=following,
                 execution_scope='EVALUATION_ONLY' if evaluation_only else 'EVALUATION_AND_ANALYSIS')
        if len(sequence) > 1:
            root = coordinator.parent / sequence[-1]
        try:
            while True:
                controls = store.read(root / 'state.json').get('execution_control', {})
                blocked = next((stage for stage in ('evaluation', 'analysis')
                    if controls.get(stage, {}).get('paused') and
                    (stage == 'evaluation' or not evaluation_only)), None)
                if blocked:
                    progress(coordinator, status='PAUSED_BY_USER', stage=blocked.upper(),
                             reason=controls[blocked].get('reason'), new_model_calls=0)
                    return {'status': 'PAUSED_BY_USER', 'new_model_calls': 0}
                if store.read(root / 'state.json').get('analysis', {}).get('status') != 'COMPLETE':
                    progress(coordinator, stage='EVALUATION', active_run=root.name)
                    ready = (collect_when_ready(root, resume_limits=True)
                             if resume_limits and root == coordinator else collect_when_ready(root))
                    if not ready:
                        time.sleep(interval)
                        continue
                    if evaluation_only:
                        numeric = __import__('finarch.experiments.01-evaluation.04-validation.numeric_validation', fromlist=['*'])
                        numeric.build(root)
                        progress(coordinator, status='EVALUATION_COMPLETE', stage='WAIT_ANALYSIS',
                                 analysis_execution='PAUSED_BY_USER')
                        return
                    progress(coordinator, stage='ANALYSIS', active_run=root.name)
                    result = analysis.run(root)
                    if result['status'] == 'ASSESSMENTS_COLLECTED_NO_PATTERNS':
                        progress(coordinator, status='COMPLETE_NO_PATTERN_FINDINGS',
                                 stage='DONE', analysis_status=result['status'], sequence=sequence)
                        return
                    if result['status'] not in ('COLLECTED', 'RUNNING'):
                        progress(coordinator, status='NEEDS_REVIEW', analysis_status=result['status'])
                        return
                    if result['status'] == 'RUNNING':
                        time.sleep(interval)
                        continue
                if (not evaluation_only
                        and store.read(root / '02_analysis/03_research/state.json', {}).get('status') == 'COLLECTED'
                        and store.read(root / '02_analysis/04_quadrant/state.json', {}).get('status') != 'COLLECTED'):
                    progress(coordinator, stage='A04', active_run=root.name)
                    result = analysis.run_postprocessing(root)
                    if result['status'] != 'COLLECTED':
                        progress(coordinator, status='RUNNING' if result['status'] == 'RUNNING' else 'NEEDS_REVIEW', analysis_status=result['status'])
                        if result['status'] == 'RUNNING':
                            time.sleep(interval)
                            continue
                        return
                if following and len(sequence) == 1:
                    root = next_run(coordinator, following)
                    sequence.append(root.name)
                    progress(coordinator, status='RUNNING', sequence=sequence, active_run=root.name)
                    evaluation.run(root)
                    continue
                progress(coordinator, status='COMPLETE', stage='DONE', sequence=sequence)
                return
        except BaseException as error:
            progress(coordinator, status='FAILED', error_type=type(error).__name__, error=str(error))
            raise
        finally:
            if resume_limits:
                state = store.read(coordinator / 'state.json')
                queue = state.get('queued_execution', {})
                if queue.get('pid') == os.getpid():
                    queue.update(status=state.get('full_pipeline', {}).get('status', 'ENDED'),
                                 ended_at=store.now())
                    store.write(coordinator / 'state.json', state)
                    store.event(coordinator, 'EVALUATION_COORDINATOR_EXIT', pid=os.getpid(), status=queue['status'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'evaluation', 'analysis', 'analysis-sequence', 'analysis-postprocess', 'prepare-analysis-variant', 'restore-analysis', 'restart-analysis', 'pair-outcomes', 'rq1-materials', 'run', 'pause', 'resume-analysis', 'report', 'recover-a100', 'recover-a100-stage', 'register-a100-stage', 'report-a100-stages', 'configure-analysis', 'configure-analysis-retries', 'configure-schedule', 'configure-output-budget', 'authorize-analysis-retry', 'retry-analysis-requests', 'authorize-gemini-cache', 'authorize-orca-cache', 'collect-gemini-batches', 'config', 'a100-sync', 'a100-verify', 'a100-evaluation'])
    parser.add_argument('--run', dest='run_path')
    parser.add_argument('--analysis-run', action='append', default=[], help='Following approved run for analysis-sequence; Evaluation is never called.')
    parser.add_argument('--after-analysis-run', type=Path, help='Wait for this run Analysis and full_pipeline to be COMPLETE before analysis-sequence.')
    parser.add_argument('--analysis-tag', help='Tag for a fresh Analysis-only variant; must match the run suffix.')
    parser.add_argument('--analysis-history', help='Saved Analysis history folder to restore while paused.')
    parser.add_argument('--config')
    parser.add_argument('--sync-action', choices=['check', 'push', 'pull', 'cycle', 'watch'], default='check')
    parser.add_argument('--sync-force', action='store_true', help='Rehash every published remote response.')
    parser.add_argument('--sync-interval', type=int)
    parser.add_argument('--sync-cycles', type=int)
    parser.add_argument('--endpoint', action='append', default=[], help='Already running local GPU endpoint for a100-evaluation.')
    parser.add_argument('--model-path', help='Pinned model snapshot served by the GPU owner.')
    parser.add_argument('--remote-root', help='Existing completed A100 project root.')
    parser.add_argument('--host', default='a100')
    parser.add_argument('--recovery-output', type=Path)
    parser.add_argument('--retry-validation-failures', action='store_true')
    parser.add_argument('--retry-research', action='store_true')
    parser.add_argument('--retry-quadrant', action='store_true', help='Extend the bounded Analysis retry policy to A04.')
    parser.add_argument('--relocate-from', type=Path, help='Move a recovered experiment folder into experiments-run; use with report-a100-stages.')
    parser.add_argument('--source-stage', type=Path, help='Recovered completed vLLM stage for registration.')
    parser.add_argument('--source-run', type=Path, help='Verified local run containing the matching frozen input cohort.')
    parser.add_argument('--evaluation-only', action='store_true')
    parser.add_argument('--resume-limits', action='store_true', help='Resume rejected Evaluation requests with approved runtime policies; requires run --evaluation-only.')
    parser.add_argument('--base-output-tokens', type=int, default=8194)
    parser.add_argument('--max-output-tokens', type=int, default=384000)
    parser.add_argument('--aggregate-only', action='store_true', help='Refresh saved Analysis counts without model calls; use with analysis.')
    parser.add_argument('--stage', choices=['02_comparison', '03_research', '04_quadrant'])
    parser.add_argument('--trial-id', action='append', default=[])
    parser.add_argument('--model-key', help='Frozen model key for a run-scoped cache exception.')
    parser.add_argument('--authorization', help='Exact user authorization for the requested exception or retry.')
    parser.add_argument('--reason', default='User explicitly requested all current experiment execution to stop.')
    args = parser.parse_args()
    if args.resume_limits and (args.command != 'run' or not args.evaluation_only):
        parser.error('--resume-limits requires run --evaluation-only')
    if args.aggregate_only and args.command != 'analysis':
        parser.error('--aggregate-only requires analysis')
    if args.analysis_run and args.command != 'analysis-sequence':
        parser.error('--analysis-run requires analysis-sequence')
    if args.after_analysis_run and args.command != 'analysis-sequence':
        parser.error('--after-analysis-run requires analysis-sequence')
    if args.relocate_from and args.command != 'report-a100-stages':
        parser.error('--relocate-from requires report-a100-stages')
    settings = evaluation.settings
    if args.command == 'a100-sync':
        sync = __import__('finarch.experiments.a100.sync', fromlist=['*'])
        if args.sync_interval is not None and args.sync_interval < 10:
            parser.error('--sync-interval must be at least 10 seconds')
        print(store.encoded(sync.execute(args.sync_action, args.config or sync.DEFAULT_CONFIG,
              args.sync_force, args.sync_interval, args.sync_cycles)).decode())
        return
    if args.command == 'a100-verify':
        gate = __import__('finarch.experiments.a100.sync_gate', fromlist=['*'])
        if not args.run_path:
            parser.error('a100-verify requires --run')
        print(store.encoded(gate.verify(Path(args.run_path).resolve())).decode())
        return
    if args.command == 'a100-evaluation':
        if not args.run_path or not args.model_path or not args.endpoint or not args.authorization:
            parser.error('a100-evaluation requires --run, --endpoint, --model-path and --authorization')
        worker = __import__('finarch.experiments.a100.worker', fromlist=['*'])
        print(store.encoded(worker.run(Path(args.run_path), args.endpoint, args.model_path, args.authorization)).decode())
        return
    if args.command == 'config':
        evaluation_config, analysis_config = settings.load_file(args.config or settings.DEFAULT_CONFIG)
        print(store.encoded({'evaluation': evaluation_config, 'analysis': analysis_config}).decode())
        return
    if args.command == 'prepare':
        print(evaluation.prepare(args.config or settings.DEFAULT_CONFIG))
        return
    if not args.run_path:
        parser.error('--run is required')
    root = Path(args.run_path).resolve()
    if root.is_dir():
        store.command(root)
    if args.command == 'register-a100-stage':
        if not args.source_stage or not args.source_run:
            parser.error('register-a100-stage requires --source-stage and --source-run')
        registration = __import__('finarch.experiments.a100.register_stage', fromlist=['*'])
        print(store.encoded(registration.run(root, args.source_stage, args.source_run)).decode())
    elif args.command == 'report-a100-stages':
        recovery = __import__('finarch.experiments.a100.recover_stage', fromlist=['*'])
        print(store.encoded(recovery.index(root, args.relocate_from)).decode())
    elif args.command == 'recover-a100-stage':
        if not args.remote_root:
            parser.error('recover-a100-stage requires --remote-root pointing to the completed stage')
        recovery = __import__('finarch.experiments.a100.recover_stage', fromlist=['*'])
        print(store.encoded(recovery.run(root, args.remote_root, args.host)).decode())
    elif args.command == 'recover-a100':
        if not args.remote_root:
            parser.error('recover-a100 requires --remote-root')
        recovery = __import__('finarch.experiments.a100.import_completed', fromlist=['*'])
        print(store.encoded(recovery.run(root, args.remote_root, args.host, args.recovery_output)).decode())
    elif args.command == 'prepare-analysis-variant':
        if not args.source_run or not args.analysis_tag or not args.authorization:
            parser.error('prepare-analysis-variant requires --source-run, --analysis-tag and --authorization')
        variant = __import__('finarch.experiments.90-operations.analysis_variant', fromlist=['*'])
        print(store.encoded(variant.prepare(args.source_run, root, args.config or settings.DEFAULT_CONFIG,
              args.analysis_tag, args.authorization)).decode())
    elif args.command == 'restore-analysis':
        if not args.analysis_history or not args.authorization:
            parser.error('restore-analysis requires --analysis-history and --authorization')
        restart = __import__('finarch.experiments.90-operations.analysis_restart', fromlist=['*'])
        print(store.encoded(restart.restore(root, args.analysis_history, args.authorization)).decode())
    elif args.command == 'analysis-postprocess':
        final_stage = ('PYTHON_OUTCOMES' if store.read(root / '02_analysis/finalization-policy.json', {}).get('skip_a04') else 'A04')
        progress(root, status='RUNNING', stage=final_stage, active_run=root.name, execution_scope=final_stage)
        try:
            result = analysis.run_postprocessing(root)
        except BaseException as error:
            progress(root, status='FAILED', stage=final_stage, error_type=type(error).__name__, error=str(error))
            raise
        progress(root, status='COMPLETE' if result['status'] == 'COLLECTED' else 'RUNNING' if result['status'] == 'RUNNING' else 'NEEDS_REVIEW', stage='DONE' if result['status'] == 'COLLECTED' else final_stage, analysis_status=result['status'])
        print(store.encoded(result).decode())
    elif args.command == 'analysis-sequence':
        sequence = __import__('finarch.experiments.90-operations.analysis_sequence', fromlist=['*'])
        sequence.run([root, *args.analysis_run], after_run=args.after_analysis_run)
    elif args.command == 'restart-analysis':
        if not args.authorization:
            parser.error('restart-analysis requires --authorization')
        restart = __import__('finarch.experiments.90-operations.analysis_restart', fromlist=['*'])
        print(store.encoded(restart.run(root, args.config or settings.DEFAULT_CONFIG, args.authorization)).decode())
    elif args.command == 'pause':
        control = __import__('finarch.experiments.90-operations.execution_control', fromlist=['*'])
        print(store.encoded(control.pause(root, args.reason)).decode())
    elif args.command == 'resume-analysis':
        if not args.authorization:
            parser.error('resume-analysis requires --authorization')
        control = __import__('finarch.experiments.90-operations.execution_control', fromlist=['*'])
        print(store.encoded(control.resume_analysis(root, args.authorization)).decode())
    elif args.command == 'authorize-gemini-cache':
        if not args.model_key or not args.authorization:
            parser.error('authorize-gemini-cache requires --model-key and --authorization')
        policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
        print(store.encoded(policy.authorize_gemini(root, args.model_key, args.authorization)).decode())
        evaluation.reporting.build(root)
    elif args.command == 'authorize-orca-cache':
        if not args.model_key or not args.authorization:
            parser.error('authorize-orca-cache requires --model-key and --authorization')
        policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
        print(store.encoded(policy.authorize_orca(root, args.model_key, args.authorization)).decode())
        evaluation.reporting.build(root)
    elif args.command == 'collect-gemini-batches':
        if not args.model_key:
            parser.error('collect-gemini-batches requires --model-key')
        with store.locked(root / '.full-pipeline.lock'), store.locked(root / '.pipeline.lock'):
            store.verify(root)
            model = next((m for m in store.configuration(root)['models']
                          if m['key'] == args.model_key and m['transport'] == 'gemini_batch'), None)
            if model is None:
                raise ValueError('GEMINI_BATCH_MODEL_REQUIRED')
            control = store.read(root / 'state.json').get('execution_control', {}).get('evaluation', {})
            if control.get('paused'):
                raise ValueError('EVALUATION_PAUSED_BY_USER')
            batch = __import__('finarch.experiments.01-evaluation.03-execution.gemini_batch', fromlist=['*'])
            batch.collect_submitted(root, model, store.read(root / 'state.json'), evaluation.reporting.build)
            numeric = __import__('finarch.experiments.01-evaluation.04-validation.numeric_validation', fromlist=['*'])
            numeric.build(root)
    elif args.command == 'authorize-analysis-retry':
        if not args.stage or not args.trial_id or not args.authorization:
            parser.error('authorize-analysis-retry requires --stage, --trial-id and --authorization')
        print(store.encoded(analysis.backend.analysis_config.authorize_unknown_delivery_retry(
            root, args.stage, args.trial_id, args.authorization)).decode())
    elif args.command == 'retry-analysis-requests':
        if not args.stage or not args.trial_id or not args.authorization:
            parser.error('retry-analysis-requests requires --stage, --trial-id and --authorization')
        control = __import__('finarch.experiments.90-operations.execution_control', fromlist=['*'])
        print(store.encoded(control.retry_analysis_requests(
            root, args.stage, args.trial_id, args.authorization)).decode())
    elif args.command == 'configure-schedule':
        print(store.encoded(analysis.backend.analysis_config.configure_schedule(root, args.config or settings.DEFAULT_CONFIG)).decode())
    elif args.command == 'configure-output-budget':
        if not args.model_key or not args.authorization:
            parser.error('configure-output-budget requires --model-key and --authorization')
        budget = __import__('finarch.experiments.01-evaluation.03-execution.output_budget', fromlist=['*'])
        print(store.encoded(budget.configure(root, args.model_key, args.authorization,
              args.base_output_tokens, args.max_output_tokens)).decode())
    elif args.command == 'configure-analysis-retries':
        if not args.authorization:
            parser.error('configure-analysis-retries requires --authorization')
        recovery = __import__('finarch.experiments.02-analysis.recovery', fromlist=['*'])
        print(store.encoded(recovery.configure(root, args.authorization,
            include_validation_failures=args.retry_validation_failures, include_research=args.retry_research,
            include_quadrant=args.retry_quadrant, validation_trial_ids=args.trial_id,
            validation_stage=args.stage)).decode())
    elif args.command == 'configure-analysis':
        snapshot = analysis.backend.analysis_config.freeze(root, args.config or settings.DEFAULT_CONFIG)
        print(store.encoded({'backend': snapshot['analysis']['backend'], 'new_model_calls': 0}).decode())
    elif args.command == 'rq1-materials':
        materials = __import__('finarch.experiments.02-analysis.01-results.rq1_materials', fromlist=['build'])
        result = materials.build(root)
        print(store.encoded({'status': result['status'], 'groups': len(result['groups']), 'new_model_calls': 0}).decode())
    elif args.command == 'pair-outcomes':
        pair_outcomes = __import__('finarch.experiments.02-analysis.02-comparison.pair_outcomes', fromlist=['build'])
        print(store.encoded(pair_outcomes.build(root)).decode())
    elif args.command == 'evaluation':
        print(store.encoded(evaluation.run(root)).decode())
    elif args.command == 'analysis':
        if args.config:
            analysis.backend.analysis_config.freeze(root, args.config)
        print(store.encoded(analysis.run(root, aggregate_only=True) if args.aggregate_only else analysis.run(root)).decode())
    elif args.command == 'report':
        print(store.encoded(evaluation.reporting.build(root)).decode())
    else:
        if args.config:
            analysis.backend.analysis_config.freeze(root, args.config)
        run(root, evaluation_only=args.evaluation_only, resume_limits=args.resume_limits)


if __name__ == '__main__':
    main()
