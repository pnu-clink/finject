"""Six saved EA observations; only the independent inverse-review calls are new."""
import argparse
from datetime import datetime, timezone
from importlib import import_module
import hashlib
import json
from pathlib import Path

from finarch.paths import PROJECT
from finarch.shared.providers.cli import read_settings
from finarch.dataset.schemas.ea_inverse_review import ROLE
from finarch.dataset.schemas.validation import validate

ops = import_module('finarch.dataset.90-operations.staging')
gate = import_module('finarch.dataset.90-operations.preparation_gate')
inverse = import_module('finarch.dataset.02-generation.03-validation.ea_inverse_review')
g05 = import_module('finarch.dataset.02-generation.05-human-review.stage')
TEMPLATE = Path(__file__).parents[2]/'documentation/templates/ea-inverse-review-pilot.md'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())


def sources():
    fixtures = read(Path(__file__).with_name('fixtures')/'ea-recovery-v1.json')
    records = []
    for item in fixtures:
        path = PROJECT/item['source_path']
        state = read(path)
        if sha(path) != item['source_sha256'] or state['observation'] != item['observation']:
            raise ValueError('EA_PILOT_FIXTURE_CHANGED')
        records.append({'path': str(path.relative_to(PROJECT)), 'sha256': sha(path)})
    root = PROJECT/'reports/run/20260917-002'
    for filename, case in [('06-ea-earlier-input.json', 'test-0005'),
                           ('07-ea-later-input.json', 'test-0005'),
                           ('07-ea-later-input.json', 'test-0006')]:
        row = next(item for item in read(root/'results'/filename) if item['id'] == case)
        path = root/row['result']/'run.json'; state = read(path)
        qc = {key: row[key] for key in ('question', 'context')}
        if state['observation'] != qc: raise ValueError('EA_PILOT_EXPORT_MISMATCH')
        records.append({'path': str(path.relative_to(PROJECT)), 'sha256': sha(path)})
    return records


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for source in sources():
        path = PROJECT/source['path']; state = read(path)
        variant, case, source_round = path.parent.name, path.parent.parent.name, path.parent.parent.parent.name
        bundle = path.parents[4]
        prep = gate.active_case_path(bundle/'01-preparation'/case)
        target = output/'01-preparation'/case
        if not target.exists():
            target.mkdir(parents=True)
            # Preserve source inputs and status, explicitly marked as reused evidence.
            for relative in ('data.json', 'run.json', '01-source/01-receive-input/01-input.json'):
                original = prep/relative
                if original.is_file(): gate.write(target/relative, read(original))
            gate.write(target/'source-copy.json', {'path': str(prep.relative_to(PROJECT)), 'new_preparation_calls': 0})
        relative = f'02-generation/01-round/{case}/{variant}'
        folder = output/relative
        ctx = ops.RunContext(folder, {}, case)
        qc = state['observation']
        with ctx.trace.activate(), ctx.trace.span('copy_saved_ea', kind='python', stage='source-copy'):
            ctx.save('run.json', {**state, 'path': relative, 'round': '01-round',
                     'source_reuse': {**source, 'source_round': source_round,
                      'scope': 'Saved generation status/text, not a new generation or semantic audit.'}})
            ctx.save('02-generate-text/04-observation.json', qc)
        rows.append({'source_path': source['path'], 'source_sha256': source['sha256'],
                     'case': case, 'variant': variant, 'path': relative,
                     'existing_status': state['status']})
    gate.write(output/'pilot-selection.json', rows)
    gate.write(output/'input-selection.json', {'cases': sorted({row['case'] for row in rows}),
               'scope': 'Saved source inputs for the annotation-only pilot; no new preparation.'})
    gate.write(output/'summary.json', {'status': 'PREPARED', 'scope': 'EA inverse annotation only', 'variants': 6, 'model_calls': 0})
    gate.write(output/'config.json', {'workflow': 'ea_inverse_review_pilot', 'source_reuse': True})
    (output/'README.md').write_text(TEMPLATE.read_text().format(status='PREPARED', completed=0, inverse_true=0, inverse_false=0, errors=0))


def execute(output, config):
    rows = read(output/'pilot-selection.json')
    settings = read_settings(config, ROLE, profile_id='luna-low-api')
    for row in rows:
        if sha(PROJECT/row['source_path']) != row['source_sha256']:
            raise ValueError('EA_PILOT_SOURCE_CHANGED')
        folder = output/row['path']
        if (folder/inverse.BASE/'latest.ref.json').exists():
            raise ValueError('EA_PILOT_ALREADY_CALLED_NO_AUTOMATIC_RETRY')
    results = []
    for row in rows:
        folder = output/row['path']
        ctx = ops.RunContext.resume(folder, {}, row['case'])
        state = read(folder/'run.json'); qc = state['observation']
        ref = inverse.review(ctx, config, qc, private_ref={'source_path': row['source_path'], 'source_sha256': row['source_sha256']}, profile_id='luna-low-api')
        state['inverse_review_ref'] = ref
        gate.write(folder/'run.json', state)
        g05.run(output, state)
        record = inverse.verify_reference(folder, ref, qc)
        annotation = record['inverse_review']
        results.append({'case': row['case'], 'variant': row['variant'], 'status': record['status'],
                        'inverse_possible': annotation['inverse_possible'] if annotation else None,
                        'missing_quantity': annotation['missing_quantity'] if annotation else None,
                        'formula': annotation['formula'] if annotation else None,
                        'existing_status': row['existing_status'], 'status_after': state['status'],
                        'inverse_review_ref': {**ref, 'path': row['path']+'/'+ref['path']}})
        gate.write(output/'pilot-results.json', results)
        gate.write(output/'summary.json', {'status': 'RUNNING', 'scope': 'EA inverse annotation only', 'processed': len(results), 'variants': 6})
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    true = sum(r['inverse_possible'] is True for r in results)
    false = sum(r['inverse_possible'] is False for r in results)
    summary = {'status': 'COMPLETED', 'scope': 'Six inverse calls on saved EA text; no generation/quality revalidation.',
               'variants': 6, 'processed': len(results), 'annotation_completed': true+false,
               'inverse_true': true, 'inverse_false': false, 'annotation_errors': 6-true-false,
               'quality_status_preserved': all(r['existing_status'] == r['status_after'] for r in results),
               'model': settings['model'], 'effort': settings['effort'], 'automatic_retries': 0,
               'timestamp': datetime.now(timezone.utc).isoformat()}
    gate.write(output/'summary.json', summary)
    (output/'README.md').write_text(TEMPLATE.read_text().format(status=summary['status'], completed=true+false, inverse_true=true, inverse_false=false, errors=6-true-false))
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def verify_saved(output):
    """Check saved linkage and public-input separation; never replay calls or formulas."""
    public_input = import_module('finarch.experiments.00-input.dataset').public_input
    checks = []
    for row in read(output/'pilot-selection.json'):
        folder = output/row['path']; state = read(folder/'run.json')
        record = inverse.verify_reference(folder, state['inverse_review_ref'], state['observation'])
        stage = Path(record['request_ref']).parents[1]
        qc = read(folder/record['request_ref'])
        handler = read(folder/stage/'02-call/01-input/handler-input.json')
        schema_check = read(folder/stage/'02-call/03-result/schema-check.json')
        display = read(folder/record['evidence_display_check_ref'])
        validate(ROLE+'.request', handler)
        validate(ROLE+'.response', {'inverse_review': record['inverse_review']})
        annotation = record['inverse_review']
        check = {'case': row['case'], 'variant': row['variant'],
                 'source_hash_unchanged': sha(PROJECT/row['source_path']) == row['source_sha256'],
                 'quality_status_preserved': state['status'] == row['existing_status'],
                 'only_remaining_qc_sent': handler == qc == state['observation'],
                 'response_schema_pass': schema_check['status'] == 'PASS',
                 'g05_reference_matches': read(folder/'05-human-review/01-result.json')['inverse_review_ref'] == state['inverse_review_ref'],
                 'display_check_matches': display == inverse.evidence_display_check(qc, annotation['evidence']),
                 'public_input_is_clean': public_input({**qc, 'inverse_review_ref': state['inverse_review_ref'],
                                                       'inverse_review': annotation}, 0) == {**qc, 'answer_format': {'decimal_places': 0}},
                 'display_status': display['status'],
                 'quote_statuses': [item['status'] for item in display['checks']]}
        if not all(value for value in check.values() if type(value) is bool):
            raise ValueError('EA_PILOT_SAVED_CHECK_FAILED')
        checks.append(check)
    ui_path = output/'viewer-verification.json'
    result = {'status': 'PASS', 'scope': 'Saved schema/linkage/coordinates; no semantic rejudgment or formula execution.',
              'model_calls': 0, 'checks': checks,
              'viewer': read(ui_path) if ui_path.exists() else {'status': 'NOT_VERIFIED'},
              'local_tests_log': 'logs/local-tests.log', 'viewer_tests_log': 'logs/viewer-tests.log',
              'documentation_log': 'logs/documentation-validation.log',
              'broader_suite_limit': 'Older tests still contain absent legacy fixture paths, old provider defaults and unregistered legacy dtt.answer contracts; this is not a full-project suite pass.'}
    gate.write(output/'verification.json', result)
    summary = read(output/'summary.json')
    (output/'README.md').write_text(TEMPLATE.read_text().format(
        status=summary['status'], completed=summary['annotation_completed'],
        inverse_true=summary['inverse_true'], inverse_false=summary['inverse_false'],
        errors=summary['annotation_errors']))
    print(json.dumps({'status': result['status'], 'verified_observations': len(checks),
                      'viewer': result['viewer']['status'], 'model_calls': 0}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--config', type=Path, default=PROJECT/'config/llm.json')
    args = parser.parse_args()
    if args.execute and args.verify_only: parser.error('Choose execute or verify-only.')
    if args.verify_only: verify_saved(args.output.resolve())
    elif args.execute: execute(args.output.resolve(), args.config.resolve())
    else: prepare(args.output.resolve())


if __name__ == '__main__': main()
