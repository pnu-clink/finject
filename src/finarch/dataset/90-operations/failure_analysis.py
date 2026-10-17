"""Confirmed, immutable failure-analysis jobs dispatched by existing schedulers."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
targets = __import__('finarch.dataset.90-operations.failed_recheck', fromlist=['targets']).targets
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
active_case_path = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['active_case_path']).active_case_path
hyperparameters = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['read']).read
scheduler_owned = __import__('finarch.dataset.90-operations.schedule_lock', fromlist=['scheduler_owned']).scheduler_owned
from finarch.dataset.schemas.failure_interpretation import ROLE, TRANSLATION_ROLE

PROJECT = (Path(__file__).resolve().parent / '../../../..').resolve()
_PROCESSES = {}

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def _inside(bundle, relative):
    path = (bundle/relative).resolve()
    if not path.is_relative_to(bundle):
        raise ValueError('ANALYSIS_PATH_OUTSIDE_RUN')
    return path

def evidence(bundle, target, phase):
    """Project saved results, never credentials or whole transport request envelopes."""
    bundle = Path(bundle).resolve()
    root = _inside(bundle, target['path'])
    roots = [root]
    if phase == 'generation':
        roots.append(active_case_path(bundle/'01-preparation'/target['case']))
    paths = set()
    for source in roots:
        for path in source.rglob('*'):
            relative = path.relative_to(source)
            if not path.is_file() or any(part in {'stage-history','failure-analysis','07-human-review','05-human-review','08-records'} for part in relative.parts):
                continue
            name = path.name
            # One canonical stage result plus explicit raw/code/feedback evidence.
            included = (name in {'run.json','data.json','accepted-input.json','accepted-audit.json','feedback-ref.json','feedback.json'}
                        or (len(relative.parts) <= 3 and path.suffix == '.json' and 'input' not in name.lower())
                        or ('01-source' in relative.parts and name == '01-input.json')
                        or name in {'schema-check.json','failure.json','handler-check.json'}
                        or ('03-preserve-response-and-code' in relative.parts and path.suffix == '.py'))
            if included:
                paths.add(path)
    marker = bundle/'01-preparation'/target['case']/'run.json' if phase == 'preparation' else root/'run.json'
    paths.add(marker)
    # Pull the exact referenced previous-round guidance, not only the next-round
    # feedback authored by the current exception handler.
    for path in list(paths):
        if path.name == 'feedback-ref.json':
            for ref in read(path).get('references', []):
                referenced = _inside(bundle,ref['path'])
                if referenced.is_file():
                    paths.add(referenced)
    artifacts = []
    for path in sorted(paths):
        path = _inside(bundle, str(path.relative_to(bundle)))
        raw = path.read_bytes()
        artifacts.append({'id':f'E{len(artifacts)+1:03d}', 'path':str(path.relative_to(bundle)),
                          'sha256':hashlib.sha256(raw).hexdigest(), 'content':raw.decode('utf-8')})
    stages = ['01-source','02-review','03-calculation','04-graph','05-verification'] if phase == 'preparation' else ['01-perturbation','02-generate-text','03-validation']
    request = {'run':bundle.name,'phase':phase,'case':target['case'],'variant':target.get('variant'),
               'round':next((x for x in root.parts if x.endswith('-round')),''),
               'failed_step':target['step'],'current_rejection':target['previous'].get('reason',''),
               'artifacts':artifacts,'missing_stages':[s for s in stages if not (root/s).exists()]}
    from finarch.dataset.schemas.registry import CONTRACTS
    CONTRACTS[ROLE+'.request'].model.model_validate(request)
    return request

def settings(phase):
    from finarch.dataset.schemas.registry import describe
    from finarch.shared.providers.profiles import read_profile, DEFAULT
    from finarch.shared.providers.cli import read_settings, prepare_instruction
    config_path = PROJECT/'config/llm.json'
    profile_name = hyperparameters()[phase]['run']['models']['failure_interpretation']
    profile = read_profile(DEFAULT, profile_name)
    if (profile['transport'],profile['model'],profile['effort']) != ('api','gpt-6-luna','max'):
        raise ValueError('LUNA_MAX_API_PROFILE_REQUIRED')
    api_concurrency = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['api_concurrency']).api_concurrency
    schedule = {**hyperparameters()[phase]['schedule']['failure_interpretation'],
                'concurrency':api_concurrency()}
    if type(schedule['concurrency']) is not int or schedule['concurrency'] < 1 or schedule['monitor_interval_seconds'] <= 0 or schedule['max_calls_per_target'] != 2:
        raise ValueError('INVALID_FAILURE_ANALYSIS_SETTINGS')
    for role in (ROLE, TRANSLATION_ROLE):
        read_settings(config_path, role, profile_id=profile_name, profiles_path=DEFAULT)
    return {'profile':profile,'schedule':schedule,'config':json.loads(config_path.read_text()),
            'profiles':Path(DEFAULT).read_text(),
            'pricing':importlib.import_module('finarch.shared.run_logging.api_usage').pricing_snapshot(),
            'prompt_hashes':{r:digest(prepare_instruction(r,{})[0]) for r in (ROLE, TRANSLATION_ROLE)},
            'schemas':{r+'.'+d:describe(r+'.'+d)['sha256'] for r in (ROLE,TRANSLATION_ROLE) for d in ('request','response')}}

def _snapshot(bundle, phase):
    selected = targets(bundle, phase)
    return {'targets':selected, 'requests':[evidence(bundle,t,phase) for t in selected], 'settings':settings(phase)}

def _preview(snapshot, phase):
    usage = importlib.import_module('finarch.shared.run_logging.api_usage')
    p = snapshot['settings']['profile']
    n = len(snapshot['targets'])
    costs = usage.estimate_api_cost(p['model'], {'input_tokens':p['total_token_budget']-p['max_output_tokens'],
        'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}, 'output_tokens':p['max_output_tokens']},
        snapshot=snapshot['settings']['pricing'])
    per_call = costs['estimated_cost']
    rate = snapshot['settings']['pricing']['models'].get(p['model'], {})
    return {'preview_id':digest(snapshot),'phase':phase,'planned':n,'model':p['model'],'effort':p['effort'],
            'calls':2*n,'analysis_calls':n,'translation_calls':n,
            'estimated_cost_usd':None if per_call is None else 2*n*per_call,
            'cost_breakdown':{'input_token_budget':p['total_token_budget']-p['max_output_tokens'],
                'output_token_budget':p['max_output_tokens'],'total_token_budget':p['total_token_budget'],
                'input_per_million':rate.get('input_per_million'),'output_per_million':rate.get('output_per_million'),
                'per_call_usd':per_call,'analysis_usd':None if per_call is None else n*per_call,
                'translation_usd':None if per_call is None else n*per_call},
            'estimate_note':'Input + output 500K It\'s the cached-use limit for each call, the maximum for the budget that applies the same limit to the translation, and not the actual input-based estimate. 1Circular and screen translation 1It\'s rotating and there\'s no automatic re-schedule.'}

def preview(bundle, phase):
    """Read-only: no model calls and no files created before confirmation."""
    return _preview(_snapshot(Path(bundle).resolve(), phase), phase)

def stale(bundle, artifacts):
    for item in artifacts:
        path = _inside(Path(bundle).resolve(), item['path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            return True
    return False

def overview(bundle, *, counts=None):
    bundle = Path(bundle).resolve()
    jobs = []
    for path in sorted((bundle/'failure-analysis').glob('*/job.json')):
        job = read(path)
        if job['status'] in ('QUEUED','RUNNING') and (path.parent/'process.json').exists():
            pid = read(path.parent/'process.json')['pid']
            process = _PROCESSES.get(pid)
            try:
                os.kill(pid,0)
                alive = process is None or process.poll() is None
            except ProcessLookupError:
                alive = False
            if not alive:
                job = read(path)
                if job['status'] in ('QUEUED','RUNNING'):
                    job.update(status='ERROR',error='Analysis scheduler exited before finalizing.')
        for result in job.get('results',[]):
            result['stale'] = stale(bundle,result.get('artifacts',[]))
        jobs.append(job)
    return {'jobs':jobs,'busy':any(j['status'] in ('QUEUED','RUNNING') for j in jobs),
            'preparation':counts['preparation'] if counts is not None else len(targets(bundle,'preparation')),
            'generation':counts['generation'] if counts is not None else len(targets(bundle,'generation'))}

def launch(bundle, phase, preview_id):
    bundle = Path(bundle).resolve()
    directory = bundle/'failure-analysis'
    directory.mkdir(exist_ok=True)
    with (directory/'.launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = overview(bundle)
        if state['busy']:
            raise ValueError('FAILURE_ANALYSIS_ALREADY_RUNNING')
        snapshot = _snapshot(bundle,phase)
        detail = _preview(snapshot,phase)
        if detail['preview_id'] != preview_id:
            raise ValueError('ANALYSIS_PREVIEW_CHANGED_RECONFIRM_REQUIRED')
        if not detail['planned']:
            raise ValueError('NO_FAILED_TARGETS')
        # A duplicate click cannot bill twice for the same immutable analysis.
        for old in state['jobs']:
            if old.get('preview_id') == preview_id and old['status'] == 'COMPLETED':
                return old
        number = max([int(j['id'].split('-')[0]) for j in state['jobs']]+[0])+1
        job_id = f'{number:03d}-{phase}'
        dest = directory/job_id
        dest.mkdir()
        write(dest/'snapshot.json',snapshot)
        write(dest/'config.json',snapshot['settings']['config'])
        (dest/'profiles.toml').write_text(snapshot['settings']['profiles'])
        job = {**detail,'id':job_id,'phase':phase,'status':'QUEUED','created_at':now(),'completed':0,'results':[]}
        project_python = PROJECT/'.venv/bin/python'
        module = f'finarch.dataset.{"01-preparation" if phase == "preparation" else "02-generation"}.{"prepare" if phase == "preparation" else "generate"}_schedule'
        command = [str(project_python if project_python.exists() else sys.executable),'-B','-m',module,'--run',str(bundle),'--analysis-job',job_id]
        job['command'] = command
        write(dest/'job.json',job)
        (dest/'README.md').write_text((Path(__file__).with_name('failure-analysis-readme.md')).read_text())
        try:
            with (dest/'scheduler.log').open('wb') as stream:
                process = subprocess.Popen(command,cwd=PROJECT,env={**os.environ,'PYTHONPATH':str(PROJECT/'src')},stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            _PROCESSES[process.pid] = process
            write(dest/'process.json',{'pid':process.pid,'command':command})
        except Exception as error:
            job.update(status='ERROR',error=str(error),ended_at=now())
            write(dest/'job.json',job)
            raise
        return job

@scheduler_owned
def execute(bundle, job_id, phase, *, worker_override=None):
    """Scheduler mode: bounded independent analysis; no automatic pipeline loops."""
    bundle = Path(bundle).resolve()
    if Path(job_id).name != job_id:
        raise ValueError('INVALID_ANALYSIS_JOB_ID')
    dest = _inside(bundle,'failure-analysis/'+job_id)
    with (dest/'.worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        job, snapshot = read(dest/'job.json'), read(dest/'snapshot.json')
        if job['phase'] != phase or job['status'] != 'QUEUED':
            raise ValueError('INVALID_ANALYSIS_STATE')
        job.update(status='RUNNING',started_at=now())
        write(dest/'job.json',job)
        schedule = snapshot['settings']['schedule']
        try:
            runner = getattr(importlib.import_module(f'finarch.dataset.{"01-preparation" if phase == "preparation" else "02-generation"}.{"07-human-review" if phase == "preparation" else "05-human-review"}.stage'),
                             'pp02_LLM_interpret_failure' if phase == 'preparation' else 'gg02_LLM_interpret_failure')
            def worker(index):
                target, request = snapshot['targets'][index], snapshot['requests'][index]
                item_dir = dest/'items'/target['case']/(target.get('variant') or 'ANSWER')
                item_dir.mkdir(parents=True)
                write(item_dir/'request.json',request)
                result = {'case':target['case'],'variant':target.get('variant'),'round':request['round'],
                          'path':str(item_dir.relative_to(bundle)),
                          'artifacts':[{k:a[k] for k in ('id','path','sha256')} for a in request['artifacts']]}
                try:
                    if digest(settings(phase)) != digest(snapshot['settings']):
                        raise ValueError('ANALYSIS_CONFIGURATION_CHANGED')
                    value = (worker_override or runner)(request,item_dir,dest/'config.json',dest/'profiles.toml')
                    result.update(value)
                except Exception as error:
                    result.update(status='ERROR',error=str(error),analysis=None,display_ko=None)
                write(item_dir/'result.json',result)
                review_step = '07-human-review' if phase == 'preparation' else '05-human-review'
                # A history reference, not a verdict, decision or retry feedback.
                ref = _inside(bundle,target['path'])/review_step/'failure-analysis'/f'{job_id}.ref.json'
                write(ref,{'analysis_id':job_id,'path':str((item_dir/'result.json').relative_to(bundle)),
                           'snapshot_sha256':digest(request),'display_only':True})
                return result
            with ThreadPoolExecutor(max_workers=schedule['concurrency']) as pool:
                futures = {pool.submit(worker,i):i for i in range(job['planned'])}
                while futures:
                    done,_ = wait(futures,timeout=schedule['monitor_interval_seconds'],return_when=FIRST_COMPLETED)
                    for future in done:
                        index = futures.pop(future)
                        try:
                            job['results'].append(future.result())
                        except Exception as error:
                            target = snapshot['targets'][index]
                            job['results'].append({'case':target['case'],'variant':target.get('variant'),'status':'ERROR','error':str(error)})
                    job['completed'] = len(job['results'])
                    write(dest/'job.json',job)
                    write(dest/'queue.json',{'status':'RUNNING','planned':job['planned'],'completed':job['completed'],
                                           'active':sum(f.running() for f in futures),'pending':sum(not f.running() for f in futures)})
            job['status'] = 'COMPLETED' if all(r['status']=='COMPLETED' for r in job['results']) else 'PARTIAL'
            usage = importlib.import_module('finarch.shared.run_logging.api_usage').summarize_run(dest)
            job['usage'] = usage['total']
        except Exception as error:
            job.update(status='ERROR',error=str(error))
        finally:
            job['ended_at'] = now()
            write(dest/'job.json',job)
            write(dest/'queue.json',{'status':job['status'],'planned':job['planned'],'completed':job['completed'],'active':0,'pending':0})
        return job
