"""Project argv profiles, distinct from Codex's native --profile layering."""
import hashlib
import re
import tomllib
from pathlib import Path

ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()
from finarch.dataset.schemas.ea_inverse_review import ROLE as INVERSE_ROLE
DEFAULT = ROOT / 'config/codex-profiles.toml'
# Other options can affect isolation, output parsing, or implicit config loading.
CONFIG_KEYS = {'model_reasoning_effort', 'model_reasoning_summary', 'model_verbosity',
               'model_context_window', 'model_auto_compact_token_limit', 'service_tier'}


def read_profile(path, profile_id):
    raw = Path(path).read_bytes()
    definitions = tomllib.loads(raw.decode('utf-8')).get('profiles', {})
    if profile_id not in definitions:
        raise ValueError(f'UNKNOWN_CODEX_PROFILE: {profile_id}; available: {", ".join(definitions)}')
    item = definitions[profile_id]
    transport = item.get('transport', 'cli')
    if transport not in ('cli', 'api'):
        raise ValueError('PROFILE_UNKNOWN_TRANSPORT')
    if transport == 'api':
        model, effort = item.get('model'), item.get('effort')
        if item.get('provider') != 'openai' or 'argv' in item:
            raise ValueError('API_PROFILE_REQUIRES_OPENAI_WITHOUT_ARGV')
        if not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.:/-]*', model):
            raise ValueError('PROFILE_INVALID_MODEL')
        if effort not in ('none', 'low', 'medium', 'high', 'xhigh', 'max'):
            raise ValueError('PROFILE_EXPLICIT_MODEL_AND_EFFORT_REQUIRED')
        limit = item.get('max_output_tokens')
        if type(limit) is not int or not 0 < limit <= 128000:
            raise ValueError('API_MAX_OUTPUT_TOKENS_REQUIRED')
        budget = item.get('total_token_budget')
        if budget is not None and (type(budget) is not int or budget <= 0):
            raise ValueError('API_INVALID_TOTAL_TOKEN_BUDGET')
        return {'id': profile_id, 'path': str(Path(path).resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
                'transport': 'api', 'provider': 'openai', 'model': model, 'effort': effort,
                'max_output_tokens': limit, 'total_token_budget': budget,
                'argv': [], 'config_overrides': {}}
    provider = item.get('provider', 'codex')
    if provider not in ('codex', 'agy'):
        raise ValueError('PROFILE_UNKNOWN_PROVIDER')
    argv = item.get('argv')
    if not isinstance(argv, list) or not argv or any(not isinstance(s, str) or not s or '\x00' in s for s in argv):
        raise ValueError('PROFILE_ARGV_MUST_BE_NONEMPTY_STRING_ARRAY')
    model, overrides, seen = None, {}, set()
    agy_effort = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if provider == 'agy':
            if arg not in ('--model', '--effort') or i + 1 >= len(argv):
                raise ValueError('PROFILE_PROTECTED_OR_UNSUPPORTED_AGY_OPTION:' + arg)
            key = arg
            value = argv[i+1]
            if arg == '--model':
                model = value
                if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.:/-]*', model):
                    raise ValueError('PROFILE_INVALID_MODEL')
            else:
                agy_effort = value
            i += 2
        elif arg == '--skip-git-repo-check':
            key = arg
            i += 1
        elif arg in ('-m', '--model', '-c', '--config'):
            if i + 1 >= len(argv):
                raise ValueError(f'PROFILE_MISSING_OPTION_VALUE: {arg}')
            value = argv[i+1]
            i += 2
            if arg in ('-m', '--model'):
                key = 'model'
                model = value
                if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.:/-]*', model):
                    raise ValueError('PROFILE_INVALID_MODEL')
            else:
                name, sep, literal = value.partition('=')
                name = name.strip()
                if not sep or name not in CONFIG_KEYS:
                    raise ValueError(f'PROFILE_PROTECTED_OR_UNSUPPORTED_CONFIG: {name}')
                key = name
                try:
                    parsed = tomllib.loads('value=' + literal)['value']
                except tomllib.TOMLDecodeError:
                    if not re.fullmatch(r'[A-Za-z0-9_-]+', literal):
                        raise ValueError(f'PROFILE_INVALID_CONFIG_VALUE: {name}') from None
                    parsed = literal
                if not isinstance(parsed, (str, int)) or isinstance(parsed, bool):
                    raise ValueError(f'PROFILE_INVALID_CONFIG_VALUE: {name}')
                overrides[name] = parsed
        else:
            raise ValueError(f'PROFILE_PROTECTED_OR_UNSUPPORTED_OPTION: {arg}')
        if key in seen:
            raise ValueError(f'PROFILE_DUPLICATE_OPTION: {key}')
        seen.add(key)
    effort = agy_effort if provider == 'agy' else overrides.get('model_reasoning_effort')
    if provider == 'agy' and effort not in ('low', 'medium', 'high'):
        raise ValueError('PROFILE_INVALID_AGY_EFFORT')
    if not model or effort not in ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'):
        raise ValueError('PROFILE_EXPLICIT_MODEL_AND_EFFORT_REQUIRED')
    return {'id': profile_id, 'path': str(Path(path).resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
            'argv': argv, 'model': model, 'effort': effort, 'config_overrides': overrides, 'provider': provider}


GENERATION_ROLES = frozenset({'01-preparation.03-calculation.pot', '02-generation.02-generate-text.realization', '02-generation.feedback.case-feedback', 'dag.source', '01-preparation.02-review-and-correct.revision'})
VALIDATION_ROLES = frozenset({INVERSE_ROLE,"shared.01-07.02-05.failure-interpretation","shared.01-07.02-05.display-translation","01-preparation.05-verification.semantic","shared.01-06.02-04.exception-handler",'shared.01-02.02-03.review-and-validation', 'dtt.answer', 'dag.review_inverse', '01-preparation.03-calculation.review-answer-evidence'})


def purpose_for_role(role, *, phase=None):
    """Resolve the call's purpose without changing its schema/role identifier."""
    from finarch.shared.providers.roles import resolve_role
    role = resolve_role(role)
    if role == INVERSE_ROLE:
        return 'ea_inverse_review'
    if role.startswith('shared.01-07.02-05.'):
        return 'failure_interpretation' if role.endswith('failure-interpretation') else 'failure_display_translation'
    if role == '01-preparation.03-calculation.pot':
        return 'pot_generation'
    if role in ('shared.01-06.02-04.exception-handler', '02-generation.feedback.case-feedback'):
        return 'exception_feedback'
    if role == '02-generation.02-generate-text.realization':
        return 'text_generation'
    if role == '01-preparation.02-review-and-correct.revision' or (
            role == 'shared.01-02.02-03.review-and-validation' and phase == 'preparation'):
        return 'source_review'
    if role in VALIDATION_ROLES:
        return 'verification'
    return None


def selected_profile(path, role, *, phase=None):
    from finarch.shared.providers.roles import resolve_role
    role = resolve_role(role)
    selection = tomllib.loads(Path(path).read_text()).get('selection', {})
    group = 'generation' if role in GENERATION_ROLES else 'validation' if role in VALIDATION_ROLES else None
    if group is None:
        raise ValueError('MODEL_ROLE_GROUP_UNDEFINED:' + role)
    if phase is not None:
        load_run = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['load_run']).load_run
        run_parameters = Path(path).resolve().parent / 'hyperparameter.json'
        models = load_run(phase, run_parameters if run_parameters.exists() else None)['models']
        selection = {key.removesuffix('_profile'): value for key, value in models.items()}
    purpose = purpose_for_role(role, phase=phase)
    # Saved configurations without a dedicated inverse entry keep their review selection.
    fallback = selection.get('verification', selection.get(group)) if role == INVERSE_ROLE else selection.get(group)
    name = selection.get(purpose, fallback)
    if not isinstance(name, str) or not name:
        raise ValueError('MODEL_SELECTION_REQUIRED:' + group)
    return {**read_profile(path, name), 'purpose': purpose or group}
