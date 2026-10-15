"""Ordered stage subjobs; artifact paths retain their existing contract."""
from copy import deepcopy
from pathlib import Path
from finarch.dataset.shared.review.dtt_audit import observation_hash
_plan = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['TYPES', 'source_request'])
TYPES, source_request = _plan.TYPES, _plan.source_request
use_feedback = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['use_feedback']).use_feedback


def run(ctx, config, bundle, root, name, index, axis, sample, plan, latest, result, value_ready, invoke, digest, check_response):
    request = gg01_build_generation_request(ctx, index, axis, plan, latest, result)
    response = gg02_llm_generate_text(ctx, config, bundle, root, name, index, sample, plan, latest, value_ready, invoke, request)
    observation, patches = gg03_check_and_record_response(ctx, request, response, result, check_response, digest)
    return gg04_publish_value_dependency(index, value_ready, result, request, response, observation, patches)

def gg01_build_generation_request(ctx, index, axis, plan, latest, result):
    request=source_request(plan,latest.get(1 if index==3 else 0,{})) if axis=='IC_SOURCE' else deepcopy(plan['request'])
    if axis=='IC_SOURCE':ctx.save('02-generate-text/00-value-dependency.json',{'source':latest[1 if index==3 else 0]['path'],'observation_sha256':observation_hash(latest[1 if index==3 else 0]['observation'])})
    result['generation_request']=deepcopy(request)
    ctx.save('02-generate-text/01-input.json',request)
    return request


def gg02_llm_generate_text(ctx, config, bundle, root, name, index, sample, plan, latest, value_ready, invoke, request):
    if index==1:
        base=value_ready.result() if value_ready is not None else latest.get(0,{})
        if not base.get('patches'):raise ValueError('VALUE_BEFORE_GENERATION_REQUIRED')
        text=base['patches'][0]['text'].strip();slot=request['edit_slots'][0]
        separator='\n' if '|' in sample['context'][slice(*plan['anchor'])] else ' '
        response={'patches':[{k:slot[k] for k in ('start','end','before','element_ids')}|{'text':separator+text}]}
        ctx.save('02-generate-text/02-place-paired-sentence.json',{'source':base['path'],'new_model_calls':0,'response':response})
    else:
        generation_feedback = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.case_feedback', fromlist=['generation_feedback']).generation_feedback
        feedback_dir=generation_feedback(ctx,bundle,root,name,index,latest,TYPES)
        from contextlib import nullcontext
        context = use_feedback(feedback_dir,case=name,target_round=Path(root).parents[1].name) if any(feedback_dir.glob('*/*.json')) else nullcontext()
        with context:
            response=invoke(ctx,config,'02-generate-text','02-generation.02-generate-text.realization',request)
    return response


def gg03_check_and_record_response(ctx, request, response, result, check_response, digest):
    result['generation_response']=deepcopy(response)
    observation,patches=check_response(request,response)
    ctx.save('02-generate-text/03-edit-check.json',{'status':'PASS','request_sha256':digest(request),'response_sha256':digest(response)})
    ctx.save('02-generate-text/04-observation.json',observation)
    ctx.save('02-generate-text/05-patches.json',patches)
    result.update(observation=observation,patches=patches)
    return observation, patches


def gg04_publish_value_dependency(index, value_ready, result, request, response, observation, patches):
    if index==0 and value_ready is not None and not value_ready.done():
        value_ready.set_result(deepcopy(result))
    return request, response, observation, patches
