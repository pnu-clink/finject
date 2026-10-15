"""Load scheduling numbers from the project's hyperparameter file."""
import json
from pathlib import Path
ROOT=(Path(__file__).resolve().parent / '../../../..').resolve()
DEFAULT=ROOT/'config/hyperparameter.json'

def read(path=None):
    return json.loads(Path(path or DEFAULT).read_text())

def api_concurrency(path=None):
    value=read(path)['shared']['api']['concurrency']
    if type(value) is not int or value<1:raise ValueError('INVALID_API_CONCURRENCY')
    return value

def for_config(stage, config):
    """API batches use one fixed limit; CLI batches retain CPU-based scheduling."""
    from finarch.shared.providers.profiles import selected_profile
    config_path=Path(config).resolve()
    runtime=json.loads(config_path.read_text())
    parameters = config_path.parent / runtime.get('hyperparameter_path', 'hyperparameter.json')
    parameters = parameters if parameters.exists() else None
    result=load(stage, parameters)
    phase='generation' if stage=='feedback' else stage
    roles=(('01-preparation.02-review-and-correct.revision','01-preparation.03-calculation.pot',
            '01-preparation.05-verification.semantic','shared.01-06.02-04.exception-handler')
           if phase=='preparation' else
           ('02-generation.02-generate-text.realization','shared.01-02.02-03.review-and-validation',
            '02-generation.feedback.case-feedback','02-generation.03-validation.ea-recoverability-review'))
    profiles=(config_path.parent/runtime.get('profiles_path','codex-profiles.toml')).resolve()
    api=runtime.get('use_model_selection') and all(
        selected_profile(profiles,role,phase=phase).get('transport')=='api' for role in roles)
    if api:
        result.update(mode='fixed',transport='api',concurrency=api_concurrency(parameters),
                      initial_concurrency=api_concurrency(parameters),max_concurrency=api_concurrency(parameters))
    else:result.update(mode='adaptive',transport='cli-or-mixed')
    return result

def load_run(stage, path=None):
    result=read(path)[stage]['run']
    if stage=='generation' and 'perturbation_policy' in result:
        validate = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['validate']).validate
        validate(result['perturbation_policy'])
    return result

def load(stage, path=None):
    config=read(path)
    schedule=config['generation' if stage=='feedback' else stage]['schedule']
    if stage=='feedback':schedule={**schedule,**schedule['feedback']}
    result={**schedule,'initial_concurrency':schedule['concurrency']}
    for key in ('initial_concurrency','increase_by'):
        if type(result[key]) is not int or result[key]<1:raise ValueError('INVALID_SCHEDULE_'+key.upper())
    for key in ('monitor_interval_seconds','cpu_threshold_percent'):
        if type(result[key]) not in (int,float) or result[key]<=0:raise ValueError('INVALID_SCHEDULE_'+key.upper())
    if result['cpu_threshold_percent']>100:raise ValueError('INVALID_CPU_THRESHOLD')
    result['hyperparameter_path']=str(Path(path or DEFAULT).resolve())
    return result
