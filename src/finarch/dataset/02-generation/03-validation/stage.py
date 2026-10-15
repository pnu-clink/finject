"""Ordered stage subjobs; artifact paths retain their existing contract."""
from finarch.dataset.shared.review.dtt_audit import observation_hash


def run(ctx, config, sample, plan, request, response, observation, patches, axis, label, index, latest, result, digest, audit_one, inverse_one=None):
    request_for_review = gg01_build_verification_request(plan, request, response, observation, axis)
    audit = gg02_llm_verify(ctx, config, request_for_review, plan, observation, label, digest, audit_one)
    gg03_record_verdict(ctx, sample, observation, patches, latest, index, axis, result, audit)
    gg04_screen_recovery(ctx, config, plan, observation, axis, result, patches)
    gg05_validate_source(ctx, plan, request, response, observation, patches, axis, index, latest, result)
    gg06_record_inverse_review(ctx, config, observation, axis, result, digest(plan), inverse_one)

def gg01_build_verification_request(plan, request, response, observation, axis):
    intent={**plan['intent'],'authorized_edit_slots':request['edit_slots'], 'verification_requirements': ['Check perturbation locality and preservation of non-target entities, periods and units.', 'Judge solvability against the intended conflict or missing-evidence state; do not require a numeric answer for every perturbation.', 'Report unsupported assumptions or competing unintended answers as failures or unknown, not automatic passes.']}
    if axis == 'EA':
        intent['verification_requirements'].append('Inverse recoverability is recorded separately as an annotation; never reject an EA item merely because a missing value can be recovered.')
    if axis == 'IC_RELATION':
        intent['verification_requirements'].extend([
            'Identify the left target by quantity and period only; its observed amount must not be repeated in the added sentence.',
            'Check each operand against its own approved period; planned cross-period comparisons are permitted.',
            'For a source-grounded total-component relation, require the total on the left and reject nonnegative components exceeding their containing total.'])
    audit_request={'original_context':request['context'],'context':observation['context'],'question':observation['question'],'axis':axis,'intent':intent,'edits':response['patches'],'recovery_review':'SEPARATE_LLM_ANNOTATION' if axis == 'EA' else 'DEFERRED_BY_USER'}
    return audit_request


def gg02_llm_verify(ctx, config, audit_request, plan, observation, label, digest, audit_one):
    audit=audit_one(ctx,config,audit_request,{'stage16_ref':'02-generate-text','plan_sha256':digest(plan),'observation_sha256':observation_hash(observation)},'03-validation',label)
    return audit


def gg03_record_verdict(ctx, sample, observation, patches, latest, index, axis, result, audit):
    result.update(status=audit['status'],reason=audit.get('reason',''),audit=audit)
    ctx.save('03-validation/04-comparison.json',{'reference':{k:sample[k] for k in ('context','question')},'working':observation,'patches':patches,'value_dependency':latest.get(1 if index==3 else 0,{}).get('patches') if axis=='IC_SOURCE' else None})


def gg04_screen_recovery(ctx, config, plan, observation, axis, result, patches=None):
    """Retain the existing bounded Python result as a diagnostic, never a gate."""
    if axis != 'EA':
        return
    from importlib import import_module
    inversion = import_module('finarch.dataset.02-generation.01-perturbation.ea_inversion')
    screen = inversion.screen(observation, plan.get('request', {}), patches or [],
                              plan.get('graph', {}), plan.get('target'), plan.get('recovery_inputs', {}))
    screen.pop('perturbation_validity', None)
    screen['affects_quality_status'] = False
    path = '03-validation/05-recovery-screen.json'
    ctx.save(path, screen)
    result['recovery_screen'] = {'path': path, **screen}


def gg06_record_inverse_review(ctx, config, observation, axis, result, plan_hash, inverse_one=None):
    if axis != 'EA':
        return
    from importlib import import_module
    review = inverse_one or import_module('finarch.dataset.02-generation.03-validation.ea_inverse_review').review
    result['inverse_review_ref'] = review(ctx, config, observation, private_ref={'plan_sha256': plan_hash})


def gg05_validate_source(ctx, plan, request, response, observation, patches, axis, index, latest, result):
    if axis != 'IC_SOURCE':
        return
    import json
    from importlib import import_module
    dependency_path = ctx.root / '02-generate-text/00-value-dependency.json'
    try:
        dependency = json.loads(dependency_path.read_text())
    except (OSError, ValueError):
        dependency = {}
    check = import_module('finarch.dataset.02-generation.03-validation.source_validation').validate(
        plan, request, response, observation, patches, latest.get(1 if index == 3 else 0, {}), dependency, index)
    path = '03-validation/06-source-exact.json'
    ctx.save(path, check)
    result['source_exact'] = {'path': path, **check}
    if check['status'] != 'PASS':
        result.update(status='FAIL', reason=check['reason'], retryable=False,
                      disposition='REQUIRES_DEPENDENCY_REVIEW')
