"""Resolve the shared schedule/run structure into frozen experiment settings."""
from copy import deepcopy
from pathlib import Path
import tomllib

from finarch.shared.providers.profiles import DEFAULT, read_profile

layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
DEFAULT_CONFIG = store.PROJECT / 'config/hyperparameter.json'


def read_source(value):
    """Read central JSON and shared profiles, or an explicitly selected legacy TOML."""
    if isinstance(value, dict):
        return deepcopy(value), DEFAULT
    path = Path(value).resolve()
    if path.suffix == '.toml':
        source = tomllib.loads(path.read_text())
        if not source.get('profiles'):
            raise ValueError('EXPERIMENT_TOML_PROFILES_REQUIRED')
        return source, path
    return store.read(path), DEFAULT


def load_file(path=DEFAULT_CONFIG):
    value, profiles = read_source(path)
    return load(value, profile_path=profiles)


def profile(name, backend, path):
    selected = read_profile(path, name)
    expected = ('api', 'openai') if backend == 'api' else ('cli', 'codex')
    if (selected.get('transport', 'cli'), selected['provider']) != expected:
        raise ValueError('EXPERIMENT_PROFILE_BACKEND_MISMATCH:' + name)
    return selected


def load(value, profile_path=DEFAULT):
    """Keep old frozen runs readable; resolve profiles only for new preparation."""
    evaluation, analysis = deepcopy(layout.split_config(value))
    if 'run' in evaluation:
        run, schedule = evaluation['run'], evaluation['schedule']
        if run.get('transport', 'batch') != 'batch' or run.get('cache') != 'off':
            raise ValueError('EVALUATION_REQUIRES_BATCH_AND_CACHE_OFF')
        models = []
        modes = None
        for key, names in run['models'].items():
            if not names or set(names) - {'off', 'on'}:
                raise ValueError('EVALUATION_REASONING_MODES_INVALID')
            selected = {mode: profile(name, 'api', profile_path) for mode, name in names.items()}
            if modes is not None and set(selected) != set(modes):
                raise ValueError('EVALUATION_REASONING_MODES_MUST_MATCH')
            modes = list(selected)
            if len({p['model'] for p in selected.values()}) != 1:
                raise ValueError('EVALUATION_OFF_ON_MODEL_MISMATCH')
            if 'off' in selected and selected['off']['effort'] != 'none':
                raise ValueError('EVALUATION_OFF_REQUIRES_NONE')
            if 'on' in selected and selected['on']['effort'] == 'none':
                raise ValueError('EVALUATION_ON_REQUIRES_REASONING')
            models.append({'key': key, 'model': next(iter(selected.values()))['model'],
                           'transport': 'openai_batch', 'key_variable': 'OPENAI_API_KEY',
                           'key_file': str(store.PROJECT / '.env'),
                           'reasoning_efforts': {m: p['effort'] for m, p in selected.items()},
                           'output_limits': {m: p['max_output_tokens'] for m, p in selected.items()},
                           'profiles': selected})
        if not models:
            raise ValueError('EVALUATION_MODELS_REQUIRED')
        evaluation = {'dataset': {**schedule['dataset'], 'require_generated': True},
                      'schedule': {k: v for k, v in schedule.items() if k != 'dataset'},
                      'models': models, 'reasoning_modes': modes, 'seed': run['seed'],
                      'output_root': 'reports/experiments-run',
                      'definition_source_run': run.get('definition_source_run'),
                      'run_label': run.get('run_label')}
    if 'run' in analysis:
        run = analysis['run']
        backend = run.get('backend')
        if backend not in ('api', 'codex'):
            raise ValueError('ANALYSIS_BACKEND_MUST_BE_API_OR_CODEX')
        backends = {}
        for name, profile_id in run['models'].items():
            if name not in ('api', 'codex'):
                raise ValueError('ANALYSIS_BACKEND_MUST_BE_API_OR_CODEX')
            selected = profile(profile_id, name, profile_path)
            model = {'model': selected['model'], 'reasoning_effort': selected['effort'], 'profile': selected}
            if name == 'api':
                model.update(max_output_tokens=selected['max_output_tokens'], key_variable='OPENAI_API_KEY',
                             key_file=str(store.PROJECT / '.env'), transport='openai_batch')
            else:
                model['transport'] = 'codex_cli'
            backends[name] = model
        if backend not in backends:
            raise ValueError('CONFIGURED_ANALYSIS_BACKEND_REQUIRED')
        for key in ('concurrency', 'timeout_seconds'):
            value = analysis['schedule'].get(key, 4 if key == 'concurrency' else 600)
            if type(value) is not int or value < 1:
                raise ValueError('ANALYSIS_POSITIVE_SCHEDULE_REQUIRED:' + key)
        scheduler = __import__('finarch.experiments.02-analysis.scheduler', fromlist=['*'])
        scheduler.validate(analysis['schedule'])
        retries = run['technical_retry_limit']
        if type(retries) is not int or retries < 0:
            raise ValueError('ANALYSIS_NONNEGATIVE_RETRY_LIMIT_REQUIRED')
        analysis = {'enabled': True, 'backend': backend, 'schedule': analysis['schedule'],
                    'backends': backends, 'technical_retry_limit': run['technical_retry_limit'],
                    'automatic_experiment_improvements': False}
    for model in evaluation.get('models', []):
        if model.get('transport') == 'orca_api':
            orca = __import__('finarch.experiments.01-evaluation.03-execution.orca_api', fromlist=['*'])
            orca.validate_model(model)
            if evaluation.get('reasoning_modes') != ['off', 'on']:
                raise ValueError('ORCA_EVALUATION_REQUIRES_BOTH_REASONING_MODES')
        if model.get('model') == 'claude-haiku-5-5':
            modes = evaluation.get('reasoning_modes', [])
            if not modes or len(set(modes)) != len(modes) or set(modes) - {'off', 'on'}:
                raise ValueError('HAIKU_55_REASONING_MODES_INVALID')
            if 'thinking_budget' in model or 'thinking_budget' in evaluation:
                raise ValueError('HAIKU_55_REQUIRES_EFFORT_NOT_THINKING_BUDGET')
            efforts = model.get('reasoning_efforts', {})
            for mode in modes:
                effort = efforts.get(mode)
                if effort not in ('low', 'medium', 'high', 'xhigh', 'max'):
                    raise ValueError('HAIKU_55_SUPPORTED_EFFORT_REQUIRED')
                if mode == 'off' and effort in ('xhigh', 'max'):
                    raise ValueError('HAIKU_55_REASONING_OFF_UNSUPPORTED_AT_XHIGH_OR_MAX')
                limit = model.get('output_limits', {}).get(mode, evaluation.get('max_output_tokens'))
                if type(limit) is not int or not 1 <= limit <= 128000:
                    raise ValueError('HAIKU_55_OUTPUT_LIMIT_INVALID')
        if model.get('model') in ('gemini-3.8-flash', 'gemini-3.5-flash-lite'):
            if evaluation.get('reasoning_modes') != ['on']:
                raise ValueError('GEMINI_LEVEL_MODEL_HAS_NO_REASONING_OFF')
            if model.get('transport') != 'gemini_batch':
                raise ValueError('GEMINI_LEVEL_MODEL_REQUIRES_NATIVE_BATCH')
            levels = ('minimal', 'low', 'medium', 'high') if model['model'] == 'gemini-3.5-flash-lite' else ('low', 'medium', 'high')
            if model.get('thinking_levels', {}).get('on') not in levels:
                raise ValueError('GEMINI_LEVEL_MODEL_REQUIRES_SUPPORTED_THINKING_LEVEL')
    return evaluation, analysis
