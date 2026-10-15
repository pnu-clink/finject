"""Capture, diagnose and publish single-case retry feedback."""
import json
from pathlib import Path
from finarch.shared.providers.cli import call
publish = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['publish']).publish

ROLE = 'shared.01-06.02-04.exception-handler'
TARGETS = {
    '02-review': '01-preparation.02-review-and-correct.revision',
    '03-calculation': '01-preparation.03-calculation.pot',
    '05-verification': '01-preparation.05-verification.semantic',
}


def run(ctx, config, result, error, *, round_number=1):
    request = pp01_capture_exception(ctx, result, error, round_number)
    request = pp02_build_feedback_request(ctx, request)
    infrastructure = any(code in request['reason'] for code in
        ('FileExistsError', 'PermissionError', 'No space left on device', 'Read-only file system'))
    if infrastructure:
        response = {'retryable': False, 'target_step': request['failed_step'] if request['failed_step'] in TARGETS else '02-review',
                    'diagnosis': 'Artifact storage failure; a prompt cannot repair the filesystem or writer contract.',
                    'guidance': 'Preserve the failed attempt and request infrastructure repair before another model call.'}
        ctx.save('06-exception-handler/03-LLM-diagnose-and-feedback/not-called.json',
                 {'status': 'NOT_EVALUATED', 'reason': 'INFRASTRUCTURE_REQUIRES_CODE_OR_ENVIRONMENT_REPAIR'})
    else:
        response = pp03_LLM_diagnose_and_feedback(ctx, config, request)
    return pp04_route_retry(ctx, request, response)


def pp01_capture_exception(ctx, result, error, round_number):
    evidence = {}
    step = result.get('stopped_at', '01-source')
    for path in sorted((ctx.root / step).rglob('*.json')):
        # Keep the model-facing evidence to actual input, output and diagnostics.
        if path.name in {'01-input.json', 'response.json', 'raw-response.json', 'schema-check.json',
                         '04-execution-result.json', '05-response-check.json', '01-comparison.json', '03-result.json', '04-verdict.json', '02-deterministic.json', '01-artifacts.json', '02-execution-and-answer.json', '03-provenance-structure.json', '04-graph-consistency.json', '08-verdict.json', '01-result.json'}:
            try: evidence[str(path.relative_to(ctx.root))] = json.loads(path.read_text())
            except (ValueError, OSError): pass
    from hashlib import sha256
    evidence['artifact_refs'] = [{'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()}
                                 for path in sorted((ctx.root/step).rglob('*.json'))]
    evidence['failed_substep'] = getattr(error, 'step', result.get('failed_substep', str(error)))
    request = {'case': result['input_id'], 'phase': 'preparation',
               'source_round': f'{round_number:02d}-round', 'failed_step': step,
               'error_type': type(error).__name__, 'reason': str(error),
               'evidence': evidence, 'allowed_steps': list(TARGETS)}
    ctx.save('06-exception-handler/01-capture-exception/01-error.json', request)
    return request


def pp03_LLM_diagnose_and_feedback(ctx, config, request):
    prefix = '06-exception-handler'
    def diagnose(payload, *, response_schema):
        return call(config, ROLE, payload, save=lambda name, value: ctx.save(prefix + '/03-LLM-diagnose-and-feedback/' + name, value))
    return ctx.invoke(prefix, '03-LLM-diagnose-and-feedback', ROLE, request, local=diagnose)


def pp04_route_retry(ctx, request, response):
    target = response['target_step']
    if target not in TARGETS:
        raise ValueError('INVALID_FEEDBACK_TARGET_STEP')
    number = int(request['source_round'].split('-')[0])
    target_round = f'{number + 1:02d}-round'
    prefix = '06-exception-handler'
    ctx.save(prefix + '/04-route-retry/01-diagnosis.json', response)
    ref = publish(ctx.root / prefix / 'feedback' / target_round / 'feedback.json',
                  case=request['case'], variant='ANSWER', source_round=request['source_round'],
                  target_round=target_round, target_role=TARGETS[target], target_step=target,
                  axis='ANSWER', guidance=response['guidance'], source=ctx.root / prefix / '01-capture-exception/01-error.json')
    result = {**response, 'feedback_ref': ref, 'target_round': target_round}
    ctx.save(prefix + '/04-route-retry/02-result.json', result)
    return result


def pp02_build_feedback_request(ctx, request):
    ctx.save('06-exception-handler/02-build-feedback-request/01-input.json', request)
    return request

# Historical callers retain the same contract.
pp01_collect_error = pp01_capture_exception
pp02_llm_diagnose = pp03_LLM_diagnose_and_feedback
pp03_record_feedback = pp04_route_retry
