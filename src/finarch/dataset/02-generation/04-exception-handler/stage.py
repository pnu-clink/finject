"""Diagnose a failed variant and bind its next-round feedback."""
from finarch.shared.providers.cli import call
publish = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['publish']).publish

ROLE='shared.01-06.02-04.exception-handler'
TARGETS={'02-generate-text':'02-generation.02-generate-text.realization',
         '03-validation':'shared.01-02.02-03.review-and-validation'}


def run(ctx, config, item, case):
    request=gg01_collect_error(item,case)
    ctx.save('04-exception-handler/01-error.json',request)
    if item.get('reason') in ('EA_RECOVERABLE_TARGET', 'EA_RECOVERY_UNKNOWN', 'EA_RECOVERY_NOT_EVALUATED') or item.get('reason', '').startswith('IC_SOURCE_EXACT_MISMATCH:'):
        result = {'retryable': False, 'reason': item['reason'], 'handler': 'GENERATION_PYTHON_GATES_V2',
                  'disposition': item.get('disposition', 'REQUIRES_PLAN_REVIEW'), 'target_reselection': 'NOT_IMPLEMENTED'}
        ctx.save('04-exception-handler/03-retry.json', result)
        return result
    response=gg02_llm_diagnose(ctx,config,request)
    return gg03_record_feedback(ctx,request,response,item)


def gg01_collect_error(item,case):
    return {'case':case,'phase':'generation','source_round':item['round'],
            'failed_step':item.get('restart','01-perturbation'),
            'error_type':'VARIANT_FAILURE','reason':item.get('reason') or 'Verification failed',
            'evidence':{'plan':item.get('plan'),'request':item.get('generation_request'),
                        'response':item.get('generation_response'),'audit':item.get('audit'),
                        **({'recovery_screen':item['recovery_screen']} if item.get('recovery_screen') else {}),
                        **({'source_exact':item['source_exact']} if item.get('source_exact') else {})},
            'allowed_steps':list(TARGETS)}


def gg02_llm_diagnose(ctx,config,request):
    def diagnose(value,*,response_schema):
        return call(config,ROLE,value,save=lambda name,data:ctx.save('04-exception-handler/02-llm/'+name,data))
    return ctx.invoke('04-exception-handler','02-diagnose',ROLE,request,local=diagnose)


def gg03_record_feedback(ctx,request,response,item):
    target=response['target_step']
    if target not in TARGETS:raise ValueError('INVALID_FEEDBACK_TARGET_STEP')
    target_round=f"{int(item['round'].split('-')[0])+1:02d}-round"
    ref=publish(ctx.root/'04-exception-handler/feedback'/target_round/'feedback.json',
        case=request['case'],variant=item['label'],source_round=item['round'],target_round=target_round,
        target_role=TARGETS[target],target_step=target,axis=item['axis'],guidance=response['guidance'],
        source=ctx.root/'04-exception-handler/01-error.json')
    result={**response,'feedback_ref':ref,'target_round':target_round}
    ctx.save('04-exception-handler/03-retry.json',result)
    return result
