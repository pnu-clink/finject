"""Execute source audit before calculation and stop at human review."""
from pathlib import Path
import json

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
from finarch.dataset.shared.review.dtt_audit import audit_one, observation_hash
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.dataset.shared.calculation.python_graph import compile_graph
name_constants = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['name_constants']).name_constants
from finarch.shared.providers.cli import call
from finarch.dataset.schemas.llm import executable_program
from finarch.shared.reference import Reference, compare


original_request = __import__('finarch.dataset.01-preparation.02-review.stage', fromlist=['original_request']).original_request


def run_case(inputs, name, output, config):
    ctx = RunContext(Path(output), {}, case_id=name)
    report = {'input_id': name, 'status': 'RUNNING', 'human_decision': 'PENDING',
              'allow_next_stage': False, 'layout': 'preparation-generation-v1'}
    ctx.save_text('README.md', Path(__file__).with_name('preparation-readme.md').read_text())
    with ctx.trace.activate():
        try:
            settings = json.loads(Path(config).read_text())
            maximum = settings.get('preparation_revision_attempts', 0)
            if type(maximum) is not int or not 0 <= maximum <= 3:
                raise ValueError('INVALID_PREPARATION_REVISION_LIMIT')
            source, sample = __import__('finarch.dataset.01-preparation.01-source.stage', fromlist=['run']).run(ctx, inputs, name)
            sample, audit = __import__('finarch.dataset.01-preparation.02-review.stage', fromlist=['run']).run(ctx, config, sample, maximum)
            if audit['status'] != 'PASS':
                report.update(status='FAIL', reason='ORIGINAL_AUDIT_NOT_PASSED',
                              stopped_at='02-review-and-correct', audit=audit)
            else:
                ctx.save('02-review-and-correct/accepted-input.json', sample)
                ctx.save('02-review-and-correct/accepted-audit.json', audit)
                publish = __import__('finarch.dataset.01-preparation.01-source.working_data', fromlist=['publish']).publish
                publish(ctx, source['sample'], sample, audit)
                calculate(ctx, config, json.loads((ctx.root/'data.json').read_text()), report)
                __import__('finarch.dataset.01-preparation.05-verification.stage', fromlist=['run']).run(ctx, config, report)
        except Exception as error:
            report.update(status='FAIL', reason=str(error))
        __import__('finarch.dataset.01-preparation.07-human-review.stage', fromlist=['collect']).collect(ctx, report)
        ctx.save('run.json', report)
    return report


calculate = __import__('finarch.dataset.01-preparation.03-calculation.stage', fromlist=['calculate']).calculate


def prepare_batch(bundle, inputs, names, config):
    bundle = Path(bundle)
    write(bundle / 'input-selection.json', {'cases': names, 'input_path': str(inputs.path)})
    preparation_results = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['preparation_results']).preparation_results
    for _ in preparation_results(bundle, inputs, names, config, run_case):
        pass
    return evaluate(bundle)
