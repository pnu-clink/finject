"""POT validation failure excludes a case from downstream dataset production."""
import hashlib
import json
from pathlib import Path
traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
StepStopped = __import__('finarch.dataset.90-operations.staging', fromlist=['StepStopped']).StepStopped


@traced('python')
def record_gate(ctx, comparison, program):
    # [PG01] docs/02-architecture.md#PG01 The failure of the correct answer is preserved, but excluded from subsequent production.
    passed = comparison.get('matches') is True
    decision = {
        'status': 'PASS' if passed else 'FAIL',
        'disposition': 'ELIGIBLE' if passed else 'EXCLUDED',
        'reason': 'GOLD_MATCH' if passed else 'GOLD_MISMATCH',
        'stage': '09', 'next_stage': '10', 'allow_next_stage': passed,
        'automatic_retry': False,
        'message': 'Reference answer comparison passed; eligible for the next stage.' if passed else
                   'Validation failed; this case is excluded from subsequent stages.',
        'computed': comparison.get('computed'), 'gold': comparison.get('gold'),
        'code_sha256': hashlib.sha256(program['code'].encode()).hexdigest(),
        'program_sha256': hashlib.sha256(json.dumps(program,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        'semantic_correctness': 'NOT_CERTIFIED',
    }
    ctx.save('02-calculation/04-compare-answer/02-disposition.json', decision)
    ctx.trace.update(disposition=decision['disposition'], allow_next_stage=passed)
    return decision


@traced('python')
def require_eligible(decision, program):
    # [PG02] docs/02-architecture.md#PG02 FAIL. External. Close. Modified code blocks before the next step calls.
    if (decision.get('status') != 'PASS' or decision.get('disposition') != 'ELIGIBLE'
            or decision.get('allow_next_stage') is not True
            or decision.get('code_sha256') != hashlib.sha256(program['code'].encode()).hexdigest()
            or decision.get('program_sha256') != hashlib.sha256(json.dumps(program,sort_keys=True,ensure_ascii=False).encode()).hexdigest()):
        raise StepStopped('02-calculation', 'PG02-next-stage', StepResult('FAIL', 'POT_NOT_ELIGIBLE'))


def load_eligible(case_dir):
    """Read a saved POT handoff; refuse excluded or edited artifacts."""
    root = Path(case_dir)
    decision = json.loads((root/'02-calculation/04-compare-answer/02-disposition.json').read_text())
    program = json.loads((root/'02-calculation/02-prepare-code/03-program.json').read_text())
    require_eligible(decision, program)
    comparison = json.loads((root/'02-calculation/04-compare-answer/01-comparison.json').read_text())
    if comparison.get('matches') is not True:
        raise StepStopped('02-calculation', 'PG02-next-stage', StepResult('FAIL', 'POT_NOT_ELIGIBLE'))
    return {'program': program, 'comparison': comparison, 'validation': decision}
