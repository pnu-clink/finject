"""Run-scoped output caps with immutable, length-only retry provenance."""
from copy import deepcopy
from pathlib import Path

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
SUPPORTED_MODEL = 'deepseek/deepseek-v4.1-flash'
TRANSPORT_MAX_OUTPUT_TOKENS = 384000


def policy_for(root, model):
    """Validate one explicit policy against this run's frozen request manifest."""
    policy = model.get('output_budget')
    if policy is None:
        return None
    root = Path(root).resolve()
    if model.get('transport') != 'orca_api' or model.get('model') != SUPPORTED_MODEL:
        raise ValueError('OUTPUT_BUDGET_ORCA_DEEPSEEK_REQUIRED')
    if (policy.get('version') != 1 or policy.get('run_id') != root.name
            or policy.get('model_key') != model['key']):
        raise ValueError('OUTPUT_BUDGET_SCOPE_MISMATCH')
    if not isinstance(policy.get('authorization'), str) or not policy['authorization'].strip():
        raise ValueError('OUTPUT_BUDGET_AUTHORIZATION_REQUIRED')
    base, maximum = policy.get('base_output_tokens'), policy.get('max_output_tokens')
    if (type(base) is not int or type(maximum) is not int
            or not 1 <= base <= maximum <= TRANSPORT_MAX_OUTPUT_TOKENS
            or policy.get('multiplier') != 2 or policy.get('retry_finish_reason') != 'length'):
        raise ValueError('OUTPUT_BUDGET_LIMIT_INVALID')
    if policy.get('frozen_requests_sha256') != store.file_hash(layout.requests(root, model['key'])):
        raise ValueError('OUTPUT_BUDGET_FROZEN_REQUESTS_CHANGED')
    return policy


def configure(root, model_key, authorization, base=8194, maximum=TRANSPORT_MAX_OUTPUT_TOKENS):
    """Record an approved runtime policy without modifying frozen definitions."""
    root = Path(root).resolve()
    with store.locked(root / '.full-pipeline.lock'), store.locked(root / '.pipeline.lock'):
        store.verify(root)
        model = next((m for m in store.configuration(root)['models'] if m['key'] == model_key), None)
        if model is None:
            raise ValueError('OUTPUT_BUDGET_MODEL_NOT_FOUND')
        policy = {'version': 1, 'run_id': root.name, 'model_key': model_key,
                  'base_output_tokens': base, 'max_output_tokens': maximum,
                  'multiplier': 2, 'retry_finish_reason': 'length',
                  'authorized_at': store.now(), 'authorization': authorization,
                  'frozen_requests_sha256': store.file_hash(layout.requests(root, model_key))}
        policy_for(root, {**model, 'output_budget': policy})
        overrides = store.read(root / 'runtime-overrides.json', {'models': {}})
        old = overrides.setdefault('models', {}).get(model_key, {}).get('output_budget')
        if old:
            policy_for(root, {**model, 'output_budget': old})
            if all(old[k] == policy[k] for k in ('base_output_tokens', 'max_output_tokens', 'multiplier')):
                return old
            raise ValueError('OUTPUT_BUDGET_ALREADY_CONFIGURED_WITH_DIFFERENT_LIMITS')
        overrides['models'].setdefault(model_key, {})['output_budget'] = policy
        store.write(root / 'runtime-overrides.json', overrides)
        state = store.read(root / 'state.json')
        state['models'][model_key]['output_budget'] = policy
        store.write(root / 'state.json', state)
        store.event(root, 'OUTPUT_BUDGET_CONFIGURED', model=model_key, policy=policy,
                    preserve_frozen_requests=True, preserve_prior_attempts=True, new_model_calls=0)
        return policy


def truncated(result):
    """Only a received, explicitly length-limited output permits a larger cap."""
    return (result is not None and result.get('status') == 'OUTPUT_TRUNCATED'
            and result.get('finish_reason') == 'length'
            and result.get('delivery_status') not in ('UNKNOWN', 'UNCONFIRMED', 'REJECTED', 'NOT_SENT'))


def next_limit(policy, frozen, attempts):
    """Resume an escalated cap from saved attempts, never from a format failure."""
    limit, reason = policy['base_output_tokens'], 'BASE_LIMIT'
    if not attempts:
        return limit, reason
    previous = store.read(attempts[-1] / 'request.json')
    result = store.read(attempts[-1] / 'result.json')
    provenance = previous.get('output_budget', {}) if previous else {}
    if provenance:
        if (provenance.get('policy_sha256') != store.digest(policy)
                or provenance.get('frozen_request_sha256') != store.digest(frozen)):
            raise ValueError('OUTPUT_BUDGET_ATTEMPT_PROVENANCE_MISMATCH')
        limit = previous['max_output_tokens']
        if type(limit) is not int or not policy['base_output_tokens'] <= limit <= policy['max_output_tokens']:
            raise ValueError('OUTPUT_BUDGET_ATTEMPT_LIMIT_INVALID')
        reason = 'PRESERVED_RETRY_LIMIT'
    if truncated(result):
        if previous is None or type(previous.get('max_output_tokens')) is not int:
            raise ValueError('OUTPUT_BUDGET_TRUNCATED_REQUEST_MISSING')
        prior_limit = previous['max_output_tokens']
        if prior_limit >= policy['max_output_tokens']:
            return None, 'MAXIMUM_REACHED'
        limit = max(limit, min(policy['max_output_tokens'], prior_limit * policy['multiplier']))
        reason = 'LENGTH_RETRY'
    return limit, reason


def retry_truncated(policy, frozen, attempts):
    if policy is None or not attempts or not truncated(store.read(attempts[-1] / 'result.json')):
        return False
    return next_limit(policy, frozen, attempts)[0] is not None


def prepare_attempt(model, frozen, policy, attempts):
    """Derive only the cap; the provider still enforces matching model/request limits."""
    if policy is None:
        return model, frozen
    limit, reason = next_limit(policy, frozen, attempts)
    if limit is None:
        raise ValueError('OUTPUT_BUDGET_MAXIMUM_REACHED')
    request, effective = deepcopy(frozen), deepcopy(model)
    request['max_output_tokens'] = limit
    request['output_budget'] = {'policy_sha256': store.digest(policy),
                              'frozen_request_sha256': store.digest(frozen),
                              'frozen_max_output_tokens': frozen['max_output_tokens'],
                              'effective_max_output_tokens': limit, 'reason': reason,
                              'previous_attempt': attempts[-1].name if attempts else None}
    effective['output_limits'][request['reasoning']] = limit
    return effective, request
