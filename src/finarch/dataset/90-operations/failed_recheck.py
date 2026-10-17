scheduler_owned = __import__('finarch.dataset.90-operations.schedule_lock', fromlist=['scheduler_owned']).scheduler_owned
"""Snapshot failed targets and dispatch existing schedulers within one run."""
import fcntl
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write


_PROCESSES = {}


def now():
    return datetime.now(timezone.utc).isoformat()


def targets(bundle, phase):
    bundle = Path(bundle)
    result = []
    if phase == 'preparation':
        for path in sorted((bundle/'01-preparation').glob('test-*/run.json')):
            item = read(path)
            if item.get('status') != 'FAIL':
                continue
            root = path.parent / item['active_round'] if item.get('active_round') else path.parent
            result.append({'case': path.parent.name, 'path': str(root.relative_to(bundle)),
                           'step': item.get('stopped_at', '01-source'), 'previous': item})
    elif phase == 'generation':
        latest = {}
        for path in sorted((bundle/'02-generation').glob('*-round/test-*/*/run.json')):
            item = read(path)
            latest[(path.parent.parent.name, path.parent.name)] = (path, item)
        for (case, variant), (path, item) in sorted(latest.items()):
            if item.get('status') == 'FAIL':
                result.append({'case': case, 'variant': variant, 'path': str(path.parent.relative_to(bundle)),
                               'step': item.get('restart', '01-perturbation'), 'previous': item})
    else:
        raise ValueError('INVALID_RECHECK_PHASE')
    return result


def overview(bundle, *, counts=None):
    bundle = Path(bundle)
    jobs = []
    for path in sorted((bundle/'retry-history').glob('*/job.json')):
        job = read(path)
        process_path = path.parent/'process.json'
        if job['status'] in ('QUEUED','RUNNING') and process_path.exists():
            pid = read(process_path)['pid']
            process = _PROCESSES.get(pid)
            try:
                os.kill(pid,0)
                alive = process is None or process.poll() is None
            except ProcessLookupError:
                alive = False
            if not alive:
                # Re-read after the process exits to avoid replacing its final result.
                job = read(path)
                if job['status'] in ('QUEUED','RUNNING'):
                    job.update(status='ERROR',error='Scheduler exited before finalizing the recheck.',ended_at=now())
                    write(path,job)
        jobs.append(job)
    return {'jobs': jobs, 'busy': any(j['status'] in ('QUEUED', 'RUNNING') for j in jobs),
            'preparation': counts['preparation'] if counts is not None else len(targets(bundle, 'preparation')),
            'generation': counts['generation'] if counts is not None else len(targets(bundle, 'generation'))}


def launch(bundle, phase):
    bundle = Path(bundle).resolve()
    history = bundle/'retry-history'
    history.mkdir(exist_ok=True)
    with (history/'.launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = overview(bundle)
        if state['busy']:
            raise ValueError('RECHECK_ALREADY_RUNNING')
        # Do not race an initial batch or another stage execution.
        for p in [bundle/'01-preparation/queue.json', bundle/'02-generation/queue.json',
                  * (bundle/'02-generation').glob('*-round/queue.json')]:
            if p.exists() and read(p).get('status') == 'RUNNING':
                raise ValueError('PIPELINE_ALREADY_RUNNING')
        selected = targets(bundle, phase)
        if not selected:
            raise ValueError('NO_FAILED_TARGETS')
        if phase == 'generation':
            require_generation_inputs = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['require_generation_inputs']).require_generation_inputs
            approved = require_generation_inputs(bundle)
            if any(x['case'] not in approved for x in selected):
                raise ValueError('PREPARATION_APPROVAL_REQUIRED')
        number = len(state['jobs']) + 1
        job_id = f'{number:03d}-{phase}'
        directory = history/job_id
        directory.mkdir()
        completion = importlib.import_module('finarch.dataset.viewer.reports.completion_report').view(bundle)
        job = {'round_baseline': completion, 'id': job_id, 'phase': phase, 'status': 'QUEUED', 'created_at': now(),
               'planned': len(selected), 'completed': 0, 'passed': 0, 'failed': 0,
               'not_evaluated': len(selected), 'targets': selected, 'results': []}
        write(directory/'job.json', job)
        (directory/'README.md').write_text('♪ Failure to review\n\njob.json: Fixed object and current result at the click of the button. queue.json. Simultaneous processing status. scheduler.log: existing scheduler run log. The output of the previous step is stored in the stage-history of each case. The object number is the case or case x type and does not change the entire run denominator.\n')
        project = (Path(__file__).resolve().parent / '../../../..').resolve()
        python = project/'.venv/bin/python'
        module = f'finarch.dataset.{"01-preparation" if phase == "preparation" else "02-generation"}.{"prepare" if phase == "preparation" else "generate"}_schedule'
        command = [str(python if python.exists() else sys.executable), '-B', '-m', module,
                   '--run', str(bundle), '--retry-job', job_id]
        job['command'] = command
        write(directory/'job.json', job)
        try:
            with (directory/'scheduler.log').open('wb') as stream:
                process = subprocess.Popen(command, cwd=project, env={**os.environ, 'PYTHONPATH': str(project/'src')},
                                           stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            _PROCESSES[process.pid] = process
            write(directory/'process.json', {'pid': process.pid, 'command': command})
        except Exception as error:
            job.update(status='ERROR', error=str(error), ended_at=now())
            write(directory/'job.json', job)
            raise
        return job


@scheduler_owned
def execute(bundle, job_id, phase):
    schedule = __import__('finarch.dataset.90-operations.adaptive_schedule', fromlist=['run']).run
    for_config = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['for_config']).for_config
    PreparedInputs = __import__('finarch.dataset.90-operations.staging', fromlist=['PreparedInputs']).PreparedInputs
    bundle = Path(bundle).resolve()
    if Path(job_id).name != job_id:
        raise ValueError('INVALID_RECHECK_ID')
    directory = bundle/'retry-history'/job_id
    job = read(directory/'job.json')
    if job['phase'] != phase or job['status'] != 'QUEUED':
        raise ValueError('INVALID_RECHECK_STATE')
    with (directory/'.worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        job.update(status='RUNNING', started_at=now())
        write(directory/'job.json', job)
        try:
            if phase == 'preparation':
                inputs = PreparedInputs(Path(read(bundle/'input-selection.json')['input_path']))
                runner = importlib.import_module('finarch.dataset.01-preparation.prepare_run').run
                def worker(target):
                    PREPARATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['PREPARATION']).PREPARATION
                    step = target['step']
                    if step not in PREPARATION:
                        raise ValueError('INVALID_FAILED_STEP:'+step)
                    root = bundle/target['path']
                    result = runner(inputs, target['case'], root, bundle/'config.json', start_stage=step)
                    previous = target['previous']
                    if previous.get('active_round'):
                        rounds = [dict(x) for x in previous.get('rounds', [])]
                        for entry in rounds:
                            if entry['round'] == previous['active_round']:
                                entry.update(status=result['status'], stopped_at=result.get('stopped_at'), recheck=job_id)
                        result.update(layout='preparation-generation-v2', active_round=previous['active_round'], rounds=rounds)
                        write(root.parent/'run.json', result)
                    return result
            else:
                require_generation_inputs = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['require_generation_inputs']).require_generation_inputs
                approved = require_generation_inputs(bundle, persist=True)
                runner = importlib.import_module('finarch.dataset.02-generation.generate_run')
                def worker(target):
                    index = next(i for i,t in enumerate(runner.TYPES) if t[0] == target['variant'])
                    result = runner.run(bundle, target['case'], round_name=Path(target['path']).parts[1],
                                        indices=[index], start_stage=target['step'], approved=approved)
                    return result['results'][0]
            # Keep dependent Generation variants in one case ordered, while cases run concurrently.
            groups = {}
            for target in job['targets']:
                groups.setdefault(target['case'], []).append(target)
            def case_worker(name):
                values = []
                order = {t[0]:i for i,t in enumerate(runner.TYPES)} if phase == 'generation' else {}
                for target in sorted(groups[name], key=lambda x:order.get(x.get('variant'),0)):
                    try:
                        result = worker(target)
                    except Exception as error:
                        result = {'status':'ERROR', 'reason':str(error)}
                    values.append({'case':name, 'variant':target.get('variant'), 'result':result})
                return values
            for name, values in schedule(list(groups), case_worker, settings=for_config(phase,bundle/'config.json'),
                                         monitor=lambda value:write(directory/'queue.json', value)):
                if isinstance(values, dict):
                    values = [{'case':name, 'result':values}]
                job['results'].extend(values)
                job['completed'] = len(job['results'])
                job['passed'] = sum(x['result']['status']=='PASS' for x in job['results'])
                job['failed'] = sum(x['result']['status'] in ('FAIL','ERROR') for x in job['results'])
                job['not_evaluated'] = job['planned']-job['passed']-job['failed']
                write(directory/'job.json', job)
            if phase == 'preparation':
                path = bundle/'01-preparation/summary.json'
                summary = read(path)
                summary['results'] = [read(p) for p in sorted((bundle/'01-preparation').glob('test-*/run.json'))]
                write(path, summary)
                evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
                evaluate(bundle, persist=True)
            else:
                path = bundle/'02-generation/summary.json'
                summary = read(path) if path.exists() else {}
                latest = {}
                for p in sorted((bundle/'02-generation').glob('*-round/test-*/*/run.json')):
                    index = next((i for i,t in enumerate(runner.TYPES) if t[0]==p.parent.name), None)
                    if index is not None:latest.setdefault(p.parent.parent.name,{})[str(index)]=read(p)
                summary.update(latest=latest, status='PASS' if all(v.get('status')=='PASS' for a in latest.values() for v in a.values()) else 'REQUIRES_REVIEW')
                write(path,summary)
            importlib.import_module('finarch.dataset.viewer.reports.completion_report').build(bundle, require_generation=False)
            importlib.import_module('finarch.shared.run_logging.api_usage').summarize_run(bundle)
            job.update(status='COMPLETED', ended_at=now())
        except Exception as error:
            job.update(status='ERROR', error=str(error), ended_at=now())
            raise
        finally:
            write(directory/'job.json', job)
        return job
