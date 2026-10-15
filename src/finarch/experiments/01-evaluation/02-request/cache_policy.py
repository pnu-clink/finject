"""Fail closed before inference unless cache reads and writes can be disabled."""
from copy import deepcopy

POLICY = {
    'mode': 'forbidden',
    'scope': ['provider_prompt_cache_reads', 'provider_prompt_cache_writes', 'cross_run_response_reuse'],
    'require_verified_transport_control': True,
    'require_explicit_zero_cache_usage': True,
    'on_violation': 'STOP_NEW_CALLS_PRESERVE_RAW_RESPONSE',
    'missing_usage': 'UNKNOWN_NOT_ZERO',
}
STOP_STATUSES = {'CACHE_POLICY_BLOCKED', 'CACHE_POLICY_VIOLATION', 'CACHE_USAGE_UNVERIFIED'}


class CachePolicyError(ValueError):
    def __init__(self, check):
        self.check = check
        super().__init__(check['reason'])


def snapshot():
    return deepcopy(POLICY)


def implicit_cache_exception(model):
    """Return only the run-scoped authorization loaded by storage.configuration."""
    record = model.get('_cache_exception', {})
    scopes = {'gemini_batch': 'GEMINI_IMPLICIT_PROMPT_CACHE',
              'orca_api': 'ORCA_DEEPSEEK_IMPLICIT_PROMPT_CACHE'}
    if model.get('transport') == 'orca_api' and model.get('model') != 'deepseek/deepseek-v4.1-flash':
        return None
    if (model.get('transport') in scopes and
            record.get('scope') == scopes[model['transport']] and
            record.get('model_key') == model.get('key') and
            record.get('model') == model.get('model') and
            record.get('authorization') and record.get('authorized_at') and
            record.get('run_id') and record.get('explicit_cache_allowed') is False and
            record.get('cross_run_response_reuse_allowed') is False):
        return deepcopy(record)
    return None


def authorize_gemini(root, model_key, authorization):
    return authorize_implicit(root, model_key, authorization, 'gemini_batch')


def authorize_orca(root, model_key, authorization):
    return authorize_implicit(root, model_key, authorization, 'orca_api')


def authorize_implicit(root, model_key, authorization, transport):
    """Record permission before any submission, preserving the frozen policy."""
    store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
    root = store.Path(root).resolve()
    if not authorization or not authorization.strip():
        raise ValueError('EXPLICIT_USER_AUTHORIZATION_REQUIRED')
    with store.locked(root / '.full-pipeline.lock'), store.locked(root / '.pipeline.lock'):
        store.verify(root)
        model = next((m for m in store.configuration(root)['models'] if m['key'] == model_key), None)
        if not model or model.get('transport') != transport:
            raise ValueError('EXCEPTION_TRANSPORT_MISMATCH')
        if transport == 'orca_api' and model.get('model') != 'deepseek/deepseek-v4.1-flash':
            raise ValueError('EXCEPTION_REQUIRES_ORCA_DEEPSEEK_V41_FLASH')
        path = root / 'cache-exceptions.json'
        ledger = store.read(path, {'run_id': root.name, 'models': {}})
        if ledger['run_id'] != root.name:
            raise ValueError('CACHE_EXCEPTION_RUN_MISMATCH')
        if model_key in ledger['models']:
            return ledger['models'][model_key]
        layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
        execution = layout.execution(root, model_key)
        if any(execution.glob('**/job.json')) or any(execution.glob('**/started.json')):
            raise ValueError('CACHE_EXCEPTION_MUST_PRECEDE_SUBMISSION')
        state = store.read(root / 'state.json')
        if state['status'] not in ('PREPARED', 'CACHE_POLICY_BLOCKED'):
            raise ValueError('CACHE_EXCEPTION_REQUIRES_UNSENT_RUN')
        record = {'run_id': root.name, 'model_key': model_key, 'model': model['model'],
                  'scope': 'GEMINI_IMPLICIT_PROMPT_CACHE' if transport == 'gemini_batch' else 'ORCA_DEEPSEEK_IMPLICIT_PROMPT_CACHE', 'authorized_at': store.now(),
                  'authorization': authorization.strip(), 'explicit_cache_allowed': False,
                  'cross_run_response_reuse_allowed': False,
                  'missing_usage': 'UNKNOWN_NOT_ZERO'}
        ledger['models'][model_key] = record
        store.write(path, ledger)
        previous = deepcopy(state)
        store.write(root / 'state-before-cache-exception.json', previous)
        state['status'] = 'PREPARED'
        state['models'][model_key].update(status='PENDING', cache_exception=record)
        state['models'][model_key].pop('reason', None)
        store.write(root / 'state.json', state)
        store.event(root, 'GEMINI_IMPLICIT_CACHE_AUTHORIZED' if transport == 'gemini_batch' else 'ORCA_IMPLICIT_CACHE_AUTHORIZED', model=model_key,
                    reason='USER_ALLOWED_IMPLICIT_CACHE_FOR_THIS_RUN', authorization=record,
                    new_model_calls=0)
        return record


def control(model):
    """Only implemented and documented transport controls may authorize dispatch."""
    transport = model.get('transport')
    check = {'policy': snapshot(), 'transport': transport, 'status': 'CACHE_POLICY_BLOCKED',
             'delivery_status': 'NOT_SENT', 'verified_control': None}
    if transport == 'claude_code':
        check.update(status='READY', verified_control={'environment': {'DISABLE_PROMPT_CACHING': '1'}},
                     reason='Documented Claude Code cache-disable environment variable is enforced.',
                     source='https://code.claude.com/docs/en/env-vars')
    elif transport in ('anthropic_api', 'anthropic_batch'):
        check.update(status='READY', verified_control={'cache_control': 'absent', 'tools': 'absent'},
                     reason='Messages API request has no cache_control breakpoint or tool use; returned cache counters are checked.',
                     source='https://platform.claude.com/docs/en/build-with-claude/prompt-caching')
    elif transport == 'codex_cli':
        check.update(reason='CODEX_CLI_NO_VERIFIED_PROMPT_CACHE_DISABLE_CONTROL',
                     detail='Installed CLI 0.155.0 exposes no verified way to send explicit-only caching without breakpoints. Ephemeral sessions do not disable provider prompt caching.',
                     source='https://developers.openai.com/codex/config-reference')
    elif transport in ('gemini_free_api', 'gemini_paid_api', 'gemini_batch'):
        check.update(reason='GEMINI_DEVELOPER_API_IMPLICIT_CACHE_DISABLE_NOT_VERIFIED',
                     detail='Gemini 2.5 implicit caching is enabled by default. Omitting cachedContent disables only explicit caching; the Developer API has no documented implicit-cache off control. Google Cloud Vertex AI has a separate project-level disableCache setting, which is not this transport.',
                     source='https://ai.google.dev/gemini-api/docs/caching')
        exception = implicit_cache_exception(model)
        if exception:
            check.update(status='READY', reason='USER_ALLOWED_IMPLICIT_CACHE_FOR_THIS_RUN',
                         effective_policy='IMPLICIT_CACHE_ALLOWED_BY_USER', exception=exception,
                         detail='Implicit prompt caching is allowed for this run. Explicit cachedContent and cross-run response reuse remain forbidden. Cache counters are preserved; missing counters remain unknown.')
    elif transport in ('openai_responses', 'openai_batch') and model.get('model') in ('gpt-5.6-luna', 'gpt-6-luna', 'gpt-6-sol'):
        check.update(status='READY',
                     verified_control={'prompt_cache_options': {'mode': 'explicit'}, 'breakpoints': []},
                     reason='Explicit-only mode with no breakpoints disables cache reads and writes.',
                     source='https://developers.openai.com/api/docs/guides/prompt-caching')
    elif transport == 'orca_api':
        check.update(reason='ORCA_DEEPSEEK_CACHE_OFF_NOT_VERIFIED',
                     source='https://api-docs.deepseek.com/guides/kv_cache/')
        exception = implicit_cache_exception(model)
        if exception:
            check.update(status='READY', reason='USER_ALLOWED_IMPLICIT_CACHE_FOR_THIS_RUN',
                         effective_policy='IMPLICIT_CACHE_ALLOWED_BY_USER', exception=exception,
                         detail='Provider automatic prompt caching is allowed for this run; explicit cache and cross-run response reuse remain forbidden. Missing cache-write usage remains unknown.')
    else:
        check['reason'] = 'TRANSPORT_NO_VERIFIED_PROMPT_CACHE_DISABLE_CONTROL'
    return check


def require_control(model):
    check = control(model)
    if check['status'] != 'READY':
        raise CachePolicyError(check)
    return check


def usage_check(transport, usage):
    """A missing counter is unknown, even when no explicit cache was requested."""
    usage = usage if isinstance(usage, dict) else {}
    if transport == 'codex_cli':
        read, written = usage.get('cached_input_tokens'), usage.get('cache_write_input_tokens')
    elif transport in ('gemini_free_api', 'gemini_paid_api', 'gemini_batch'):
        read, written = usage.get('cachedContentTokenCount'), None
    elif transport in ('claude_code', 'anthropic_api', 'anthropic_batch'):
        read, written = usage.get('cache_read_input_tokens'), usage.get('cache_creation_input_tokens')
    elif transport == 'orca_api':
        details = usage.get('prompt_tokens_details') or {}
        read, written = details.get('cached_tokens'), details.get('cache_write_tokens')
    else:
        details = usage.get('input_tokens_details') or {}
        read, written = details.get('cached_tokens'), details.get('cache_write_tokens')
    counts = (read, written)
    valid = [type(value) is int and value >= 0 for value in counts]
    if any(ok and value > 0 for ok, value in zip(valid, counts)):
        status = 'CACHE_POLICY_VIOLATION'
    elif not all(valid):
        status = 'CACHE_USAGE_UNVERIFIED'
    else:
        status = 'VERIFIED_ZERO'
    return {'status': status, 'cache_read_tokens': read, 'cache_write_tokens': written,
            'missing_or_invalid_counter': not all(valid)}


def enforce_result(model, result):
    """Keep every response and token counter, but prevent cache failures being scored."""
    check = usage_check(model['transport'], result.get('usage'))
    exception = implicit_cache_exception(model)
    if exception:
        check['strict_policy_status'] = check['status']
        check['status'] = ('CACHE_USED_ALLOWED_BY_USER' if check['status'] == 'CACHE_POLICY_VIOLATION'
                           else 'CACHE_USAGE_UNKNOWN_ALLOWED_BY_USER' if check['missing_or_invalid_counter']
                           else 'VERIFIED_ZERO')
        check['exception'] = exception
    result['cache_check'] = check
    if check['status'] in STOP_STATUSES:
        result['status_before_cache_check'] = result['status']
        result['status'] = check['status']
        result['error'] = check['status']
    return result
