"""Ordered stage subjobs; artifact paths retain their existing contract."""
from copy import deepcopy
import json


from hashlib import sha256
def digest(value):
    return sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def run(ctx, sample, program, graph, index, latest, build, policy=None, perturbation_policy=None):
    validate = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['validate']).validate
    binding = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['binding']).binding
    NoCoefficient = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['NoCoefficient']).NoCoefficient
    perturbation_policy=validate(perturbation_policy)
    prior = gg01_select_prior_plan(index, latest)
    if prior and index<5:
        saved=prior['plan'].get('coefficient_selection')
        if bool(saved)!=bool(perturbation_policy):raise ValueError('PERTURBATION_POLICY_PLAN_MISMATCH')
        if saved:
            expected=binding(sample,program,perturbation_policy,'VALUE' if index<4 else 'RELATION')
            if any(saved.get(k)!=v for k,v in expected.items()):raise ValueError('PERTURBATION_POLICY_PLAN_MISMATCH')
    if prior is not None and index < 5:
        return gg02_reuse_plan(ctx, prior)
    with ctx.trace.span('generation.graph', kind='python', stage='01-perturbation'):
        if perturbation_policy and index<5:
            inherited=None
            if index in (1,2,3):
                parent=latest.get(1 if index==3 else 0,{})
                inherited=parent.get('plan',{}).get('coefficient_selection')
                if not inherited:raise ValueError('PAIRED_COEFFICIENT_PARENT_REQUIRED')
            try:
                plan=build(sample,program,graph,index,perturbation_policy=perturbation_policy,inherited_selection=inherited)
                ctx.save('01-perturbation/04-coefficient-selection.json',plan['coefficient_selection'])
            except NoCoefficient as error:
                ctx.save('01-perturbation/04-coefficient-selection.json',error.report)
                raise
        else:
            plan = gg03_build_change_plan(sample, program, graph, index, build, policy)
        gg04_record_plan(ctx, sample, program, graph, plan)
    return plan


def gg01_select_prior_plan(index, latest):
    prior = latest.get(index)
    if index == 4 and prior and prior.get('plan'):
        scope = __import__('finarch.dataset.02-generation.01-perturbation.relation_scope', fromlist=['VERSION'])
        if prior['plan'].get('relation_policy_version') != scope.VERSION:
            return None
        planner = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['RELATION_PLACEMENT_VERSION'])
        if prior['plan'].get('relation_placement_version') != planner.RELATION_PLACEMENT_VERSION:
            return None
    if prior and prior.get('plan') and prior.get('restart') != '01-perturbation':
        return prior
    return None


def gg02_reuse_plan(ctx, prior):
    plan = deepcopy(prior['plan'])
    ctx.save('01-perturbation/01-inherited-plan.json', {'source': prior['path'], 'new_execution': False, 'plan_sha256': digest(plan), 'plan': plan})
    return plan


def gg03_build_change_plan(sample, program, graph, index, build, policy=None):
    if policy and policy.get('enabled') is True:
        return build(sample, program, graph, index, policy=policy)
    return build(sample, program, graph, index)


def gg04_record_plan(ctx, sample, program, graph, plan):
    ctx.save('01-perturbation/01-input.json', {'sample': sample, 'program': program, 'graph': graph})
    ctx.save('01-perturbation/02-graph.json', plan['graph'])
    ctx.save('01-perturbation/03-result.json', {'status': 'PASS', 'execution': plan['execution'], 'plan': plan})
