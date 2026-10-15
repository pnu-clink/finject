"""Verify computation with separate deterministic and semantic evidence."""
from hashlib import sha256
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
from finarch.shared.providers.cli import call
from finarch.shared.reference import Reference, compare
from finarch.dataset.schemas.verification import VerificationResponse

ROLE = '01-preparation.05-verification.semantic'


def run(ctx, config, report):
    from pathlib import Path
    ctx.save_text('05-verification/README.md', Path(__file__).with_name('verification-readme.md').read_text())
    payload = pp01_collect_artifacts(ctx, report)
    checks = {
        'execution_answer': pp02_check_execution_and_answer(ctx, payload),
        'provenance': pp03_check_provenance_structure(ctx, payload),
        'graph': pp04_check_graph_consistency(ctx, payload),
    }
    request = pp05_build_verification_request(ctx, payload, checks)
    response = pp06_LLM_verify_semantics(ctx, config, request)
    findings = pp07_check_verification_response(ctx, response)
    pp08_record_verdict(ctx, findings, report, checks)


def pp01_collect_artifacts(ctx, report):
    paths = ['03-calculation/05-record-calculation-artifacts/01-stage-output.json', '04-graph/05-save-graph/01-graph.json']
    data, graph = [read(ctx.root / path) for path in paths]
    ctx.save('05-verification/01-collect-artifacts/02-artifact-refs.json', [
        {'path': path, 'sha256': sha256((ctx.root/path).read_bytes()).hexdigest()}
        for path in paths])
    payload = {'case': report['input_id'], 'sample': data['sample'], 'program': data['program'],
               'execution': data['execution'], 'graph': graph}
    ctx.save('05-verification/01-collect-artifacts/01-input.json', payload)
    return payload


def pp02_check_execution_and_answer(ctx, payload):
    sample, execution = payload['sample'], payload['execution']
    comparison = compare(execution['exact_value'], Reference(sample['reference_answer'],
        sample['reference_answer_type'], sample['reference_precision']))
    result = {'status': 'PASS' if comparison['matches'] else 'FAIL', 'answer': comparison}
    ctx.save('05-verification/02-check-execution-and-answer/01-result.json', result)
    return result


def pp03_check_provenance_structure(ctx, payload):
    from finarch.dataset.schemas.llm import ProgramResponse, ProgramResponseV5, check_knowledge_triggers
    program = dict(payload['program'])
    facts = program.get('facts', {})
    if isinstance(facts, dict):
        program['facts'] = [{'id': key, **value} for key, value in facts.items()]
    errors = []
    try:
        model=ProgramResponseV5 if 'external_knowledge_requirements' in program else ProgramResponse
        model.model_validate(program)
        check_knowledge_triggers(program,payload['sample']['question'],payload['sample']['context'])
    except ValueError as error:
        errors.append(str(error))
    for fact in program.get('facts', []):
        text = payload['sample']['question' if fact.get('origin') == 'QUESTION' else 'context']
        span = fact.get('span', [])
        start, end = span if isinstance(span, list) and len(span) == 2 else (None, None)
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(text)
                and text[start:end] == fact.get('text')):
            errors.append('FACT_SPAN_MISMATCH:' + fact.get('id', 'unknown'))
    for usage in program.get('source_usage', []):
        if usage.get('kind') == 'IN_CONTEXT_DATA' and not usage.get('fact_ids'):
            quote = usage.get('quote') or ''
            if not quote or not any(quote in payload['sample'][key] for key in ('question','context')):
                errors.append('SUPPLIED_CONDITION_QUOTE_MISMATCH:' + usage.get('id','unknown'))
    result = {'status': 'FAIL' if errors else 'PASS', 'errors': errors}
    ctx.save('05-verification/03-check-provenance-structure/01-result.json', result)
    return result


def pp04_check_graph_consistency(ctx, payload):
    execution, graph = payload['execution'], payload['graph']
    nodes = {node['id']: node['computed'] for node in graph['nodes']}
    variables = graph['variables']
    linked = bool(variables) and all(node in nodes and name in execution['trace'] and
        execution['trace'][name] == nodes[node] for name, node in variables.items())
    previous = read(ctx.root/'04-graph/02-build-graph/04-comparison.json')
    result = {'status': 'PASS' if linked and previous['status'] == 'PASS' else 'FAIL',
              'graph_matches': linked}
    ctx.save('05-verification/04-check-graph-consistency/01-result.json', result)
    return result


def pp05_build_verification_request(ctx, payload, checks):
    request = {**payload, 'deterministic_checks': checks}
    ctx.save('05-verification/05-build-verification-request/01-input.json', request)
    return request


def pp06_LLM_verify_semantics(ctx, config, payload):
    def verify(value, *, response_schema):
        return call(config, ROLE, value,
            save=lambda name, data: ctx.save('05-verification/06-LLM-verify-semantics/'+name, data))
    return ctx.invoke('05-verification', '06-LLM-verify-semantics', ROLE, payload, local=verify)


def pp07_check_verification_response(ctx, response):
    try:
        checked = VerificationResponse.model_validate(response).model_dump()
    except ValueError as error:
        ctx.save('05-verification/07-check-verification-response/01-result.json', {'status': 'FAIL', 'reason': str(error)})
        raise
    ctx.save('05-verification/07-check-verification-response/01-result.json', {'status': 'PASS'})
    return checked


def pp08_record_verdict(ctx, response, report, checks):
    passed = response.get('cohort') in ('INTERNAL', 'EXTERNAL') and all(value['status'] == 'PASS' for value in checks.values()) and all(
        item['judgment'] == 'PASS' for item in response['findings'])
    verdict = {**response, 'deterministic_checks': checks, 'status': 'PASS' if passed else 'FAIL'}
    ctx.save('05-verification/08-record-verdict/01-result.json', verdict)
    if not passed:
        raise ValueError('VERIFICATION_FAILED_OR_UNKNOWN')
    report.update(status='PASS', reason='VERIFICATION_PASSED')
