"""Ordered stage subjobs; artifact paths retain their existing contract."""
import json
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.shared.providers.cli import call
from finarch.dataset.schemas.llm import executable_program
from finarch.shared.reference import Reference, compare
name_constants = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['name_constants']).name_constants


def run(ctx, config, sample, report, *, include_graph=False):
    stage = '03-calculation'
    request = pp01_build_pot_request(sample)
    ctx.save(stage+'/01-build-pot-request/01-input.json', request)
    program = pp02_llm_generate_code(ctx, config, sample, request, stage)
    program = pp03_prepare_code(ctx, program, stage)
    result = pp04_execute_python(ctx, sample, program, stage)
    sample, program, result, comparison = pp05_compare_answer(ctx, config, sample, program, result, report, stage)
    pp06_record_calculation_artifacts(ctx, sample, program, result, comparison, report, stage)
    if include_graph:
        __import__('finarch.dataset.01-preparation.04-graph.stage', fromlist=['run']).run(ctx, sample, program, result, report)

def pp01_build_pot_request(sample):
    from finarch.dataset.shared.calculation.numeric_index import numeric_index
    request = {'context': sample['context'], 'question': sample['question'],
               'reference_answer_type': sample['reference_answer_type'],
               'reference_precision': sample['reference_precision'],
               'answer_metadata': {'scale': sample['answer_metadata']['scale']},
               'provider_record': {'raw_id': sample['raw_id'], 'numeric_index': numeric_index(sample['context'])}}
    return request


def pp02_llm_generate_code(ctx, config, sample, request, stage):
    def author(payload, *, response_schema):
        diagnostics = __import__('finarch.dataset.01-preparation.03-calculation.diagnostics', fromlist=['preserve_and_execute'])
        def diagnose(value):
            diagnostics.preserve_and_execute(value, sample['context'],
                lambda name, data: ctx.save(diagnostics.DIRECTORY + '/' + name, data),
                lambda name, text: ctx.save_text(diagnostics.DIRECTORY + '/' + name, text), question=sample['question'])
        return call(config, '01-preparation.03-calculation.pot', payload,
                    before_validate=diagnose,
                    save=lambda name, value: ctx.save(stage + '/02-LLM-generate-code/' + name, value))
    program = executable_program(ctx.invoke(stage, '02-LLM-generate-code', '01-preparation.03-calculation.pot', request, local=author))
    from finarch.dataset.schemas.llm import check_knowledge_triggers
    check_knowledge_triggers(program, sample['question'], sample['context'])
    return program


def pp03_prepare_code(ctx, program, stage):
    program, layout = name_constants(program)
    ctx.save(stage + '/03-preserve-response-and-code/07-transformation.json', layout)
    ctx.save(stage+'/03-preserve-response-and-code/08-program.json',program)
    ctx.save_text(stage+'/03-preserve-response-and-code/09-program.py',program['code'])
    from finarch.dataset.shared.calculation.external_evidence import publish
    publish(ctx,program)
    return program


def pp04_execute_python(ctx, sample, program, stage):
    result = ctx.invoke(stage, '04-execute-python', 'pot.execute',
                        {**program, 'context': sample['context'], 'question': sample['question']},
                        local=lambda payload: execute(payload, save=lambda name, value: ctx.save(stage + '/04-execute-python/' + name, value)))
    return result


def pp05_compare_answer(ctx, config, sample, program, result, report, stage):
    comparison = compare(result['exact_value'], Reference(sample['reference_answer'],
                         sample['reference_answer_type'], sample['reference_precision']))
    return sample, program, result, comparison


def pp06_record_calculation_artifacts(ctx, sample, program, result, comparison, report, stage):
    ctx.save(stage + '/05-record-calculation-artifacts/03-program.json', program)
    ctx.save(stage + '/05-record-calculation-artifacts/02-comparison.json', comparison)
    ctx.save(stage + '/05-record-calculation-artifacts/01-stage-output.json', {'sample':sample,'program':program,'execution':result})
    report.update(status='PASS',reason='CALCULATION_COMPLETED')


def calculate(ctx, config, sample, report, *, include_graph=True):
    """Preserve the legacy combined calculation/graph entry point."""
    return run(ctx, config, sample, report, include_graph=include_graph)
