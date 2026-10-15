"""Run offline QI01 checks and publish immutable, shared-viewer-readable evidence."""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import unittest

from finarch.dataset.checks.test_ea_recovery import FIXTURES, screen

TESTS = [
    'finarch.dataset.checks.test_ea_recovery',
    'finarch.dataset.checks.test_ea_plan',
    'finarch.dataset.checks.test_generation_recovery_state',
    'finarch.dataset.checks.test_generation_placement',
    'finarch.dataset.checks.test_ordered_stage_modules.OrderedStages.test_inherited_plan_is_copied_without_rebuilding',
    'finarch.dataset.checks.test_ordered_stage_modules.OrderedStages.test_legacy_imports_share_the_real_implementation',
    'finarch.dataset.checks.test_ordered_stage_modules.OrderedStages.test_paired_sentence_uses_no_llm_and_keeps_artifact',
]


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()

    def save(path, data):
        path = output / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(TESTS))
    (output / 'tests.txt').write_text(stream.getvalue())
    for item in FIXTURES:
        evidence = screen(item)
        prefix = item['id'] + '/'
        save(prefix + 'observation.json', item['observation'])
        save(prefix + 'source.json', {k: item[k] for k in ('source_path', 'source_sha256', 'target_descriptor')})
        save(prefix + '03-validation/05-recovery-screen.json', evidence)
        save(prefix + 'run.json', {'status': 'PASS' if evidence['status'] == 'RECOVERABLE' else 'FAIL',
             'scope': 'Offline counterexample detection test, not generation acceptance', 'model_calls': 0,
             'full_EA_verdict': 'NOT_EVALUATED', 'recovery_status': evidence['status']})
    summary = {'run_id': output.name, 'status': 'PASS' if result.wasSuccessful() else 'FAIL',
               'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'test_selectors': TESTS, 'model_calls': 0, 'started_at': started,
               'ended_at': datetime.now(timezone.utc).isoformat(),
               'scope': 'QI01 offline bounded recovery checks; no production generation',
               'out_of_scope_prior_failures': [
                   {'test': 'test_graph_mismatch_does_not_publish_accepted_graph', 'reason': "KeyError: question"},
                   {'test': 'test_pot_request_preserves_metadata_but_excludes_gold',
                    'reason': "answer_metadata expected negative=False, actual only scale=None"}]}
    save('summary.json', summary)
    (output / 'README.md').write_text(Path(__file__).with_name('qi01-readme-template.md').read_text().format(**summary))
    (output / 'events.jsonl').write_text(json.dumps({'phase': 'END', **summary}) + '\n')
    from finarch.dataset.viewer.server import batch_data, list_batches
    payload = batch_data(output.parent, output.name)
    visible = {Path(item['path']).name: item['artifacts']['03-validation/05-recovery-screen.json']['status']
               for item in payload['runs']}
    viewer_ok = len(visible) == 3 and all(value == 'RECOVERABLE' for value in visible.values())
    listed = output.name in str(list_batches(output.parent))
    save('viewer-check.json', {'status': 'PASS' if viewer_ok and listed else 'FAIL', 'visible': visible,
                              'listed': listed, 'scope': 'Shared viewer data reader, not browser or user confirmation'})
    print(json.dumps({**summary, 'viewer_ok': viewer_ok and listed, 'output': str(output)}, ensure_ascii=False))
    return 0 if result.wasSuccessful() and viewer_ok and listed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    raise SystemExit(run(parser.parse_args().output))
