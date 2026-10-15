"""Run only the frozen ten-item CodeTAT-QA pilot through existing schedulers."""
import argparse
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path


def run(bundle):
    bundle = Path(bundle).resolve()
    write = importlib.import_module('finarch.dataset.90-operations.preparation_gate').write
    selection = json.loads((bundle / 'input-selection.json').read_text())
    if len(selection['cases']) != 10 or len(set(selection['cases'])) != 10:
        raise ValueError('PILOT_REQUIRES_EXACTLY_TEN_CASES')
    template = bundle / 'pilot-readme-template.md'

    def record(status, **extra):
        write(bundle / 'pilot-status.json', {
            'status': status, 'updated_at': datetime.now(timezone.utc).isoformat(),
            'scheduled_cases': selection['cases'], 'automatic_expansion': False, **extra})
        (bundle / 'README.md').write_text(template.read_text())

    record('PREPARATION_RUNNING')
    try:
        prepare = importlib.import_module('finarch.dataset.01-preparation.prepare_schedule')
        stages = importlib.import_module('finarch.dataset.90-operations.stage_range').PREPARATION
        preparation = prepare.run_selected(selection['input_path'], str(bundle / 'config.json'),
                                           selection['cases'], stages, bundle=bundle)
        record('GENERATION_RUNNING', preparation=preparation)
        gate = importlib.import_module('finarch.dataset.90-operations.preparation_gate')
        eligible = gate.require_generation_inputs(bundle, persist=True)
        if not eligible:
            record('NO_PREPARATION_PASS', preparation=preparation, generation_started=False)
            return
        generate = importlib.import_module('finarch.dataset.02-generation.generate_schedule')
        generation = generate.run(bundle, maximum_rounds=3)
        record('COMPLETED', preparation=preparation, generation=generation,
               eligible_cases=list(eligible), generation_started=True)
    except BaseException as error:
        record('ERROR', reason=type(error).__name__ + ': ' + str(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    run(parser.parse_args().run)
