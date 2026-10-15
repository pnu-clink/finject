"""Package frozen experiment inputs for a separately owned GPU benchmark."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
import shutil
from string import Template


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(part)
    return result.hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def jsonl(path, values):
    with Path(path).open('w') as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root):
    """GH04: Verify a transferred package using only the Python standard library."""
    root = Path(root).resolve()
    manifest = read(root / 'manifest.json')
    for name, expected in manifest.items():
        path = (root / name).resolve()
        require(root in path.parents, 'MANIFEST_PATH_OUTSIDE_PACKAGE')
        require(sha(path) == expected, 'TRANSFER_HASH_MISMATCH:' + name)
    public, private = rows(root / '01-input/public.jsonl'), rows(root / '01-input/private.jsonl')
    inputs = rows(root / '01-input/model-inputs.jsonl')
    trials = rows(root / '01-input/trial-matrix.jsonl')
    require(len(public) == len(private) == len(inputs) == 8640, 'COHORT_SIZE_MISMATCH')
    require(len({x['item_id'] for x in public}) == 8640, 'DUPLICATE_ITEM_ID')
    require(len(trials) == len({x['trial_key'] for x in trials}) == 32400, 'DUPLICATE_OR_MISSING_TRIAL')
    by_id = {x['item_id']: x for x in private}
    require(set(by_id) == {x['item_id'] for x in public}, 'PUBLIC_PRIVATE_ID_MISMATCH')
    for item, model_input in zip(public, inputs):
        allowed = {'item_id', 'question', 'context'}
        require(set(item) in (allowed, allowed | {'answer_format'}), 'PRIVATE_PUBLIC_FIELD')
        require(set(model_input) == {'item_id', 'input'}, 'PRIVATE_MODEL_INPUT_ENVELOPE')
        require(model_input['item_id'] == item['item_id'], 'MODEL_INPUT_ID_MISMATCH')
        payload = model_input['input']
        require(set(payload) == {'question', 'context', 'answer_format'}, 'PRIVATE_MODEL_INPUT_FIELD')
        require(set(payload['answer_format']) == {'decimal_places'}, 'PRIVATE_ANSWER_FORMAT_FIELD')
        require(all(payload[k] == item[k] for k in ('question', 'context')), 'QC_CHANGED')
        # Preserve read-only verification of legacy packages; new inputs are complete.
        precision = (item['answer_format']['decimal_places'] if 'answer_format' in item
                     else by_id[item['item_id']]['reference']['reference_precision'])
        require(type(precision) is int and 0 <= precision <= 100, 'INVALID_PRECISION')
        require(payload['answer_format']['decimal_places'] == precision, 'PRECISION_CHANGED')
    expected_types = {'ORIGINAL', 'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY',
                      'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02'}
    cases = {}
    for item in private:
        cases.setdefault(item['case'], []).append(item['variant'])
    require(len(cases) == 1080 and all(len(v) == 8 and set(v) == expected_types for v in cases.values()),
            'INCOMPLETE_SEVEN_VARIANTS')
    require(Counter(t['experiment'] for t in trials) == {1: 2160, 2: 30240}, 'TRIAL_DENOMINATOR_MISMATCH')
    expected = {(x['item_id'], p, r) for x in private
                for p in (('P0',) if x['experiment'] == 1 else ('P0', 'P1')) for r in ('off', 'on')}
    require({(t['item_id'], t['prompt_condition'], t['reasoning']) for t in trials} == expected,
            'TRIAL_CONDITION_MISMATCH')
    require(read(root / '00-definition/response.schema.json')['title'] == 'FinancialAnswerMagnitudeV4',
            'WRONG_RESPONSE_CONTRACT')
    return {'status': 'PASS', 'verified_files': len(manifest), 'originals': 1080, 'variants': 7560,
            'dual_mode_requests_per_model': 32400, 'single_mode_requests_per_model': 16200}


def build(project, config_path):
    """GH01-GH03: Check provenance, freeze public inputs, and emit a transfer manifest."""
    answer_format = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['*'])
    request_order = __import__('finarch.experiments.01-evaluation.02-request.request_order', fromlist=['*'])
    allocate = __import__('finarch.experiments.90-operations.storage', fromlist=['allocate']).allocate

    project = Path(project).resolve()
    config = read(config_path)
    source, luna = (project / config[k] for k in ('dataset_source_run', 'definition_source_run'))
    for root in (source, luna):
        for name, expected in read(root / 'manifest.json').items():
            if name.startswith(('01-input/', '00-definition/')) or name.endswith('/01-requests/manifest.jsonl') or name == 'config.json':
                require(sha(root / name) == expected, 'SOURCE_FROZEN_HASH_MISMATCH:' + name)
    public, private = rows(source / '01-input/public.jsonl'), rows(source / '01-input/private.jsonl')
    luna_public, luna_private = rows(luna / '01-input/public.jsonl'), rows(luna / '01-input/private.jsonl')
    require(public[:800] == luna_public and private[:800] == luna_private, 'LUNA_100_INPUT_CHANGED')
    selection = request_order.selection_from_manifests(source, public=public, require_same_items=True)
    require(selection['originals'] == 1080 and selection['variants'] == 7560, 'WRONG_COHORT')
    schema = read(luna / '00-definition/response.schema.json')
    model_inputs = [{'item_id': item['item_id'], 'input': answer_format.model_input(item, schema)}
                    for item in public]
    root = allocate(project / 'reports/experiments-run')
    created = datetime.now().astimezone().isoformat(timespec='seconds')
    write(root / 'state.json', {'status': 'PREPARING_TRANSFER', 'models': {}})
    write(root / 'config.json', config)
    shutil.copytree(luna / '00-definition', root / '00-definition')
    (root / '01-input').mkdir()
    for name in ('public.jsonl', 'private.jsonl'):
        shutil.copyfile(source / '01-input' / name, root / '01-input' / name)
    schema = read(root / '00-definition/response.schema.json')
    for item in model_inputs:
        answer_format.validate_input({'input': item['input'], 'response_schema': schema})
    jsonl(root / '01-input/model-inputs.jsonl', model_inputs)
    tasks = []
    for item in selection['items']:
        for prompt in ('P0',) if item['experiment'] == 1 else ('P0', 'P1'):
            for reasoning in ('off', 'on'):
                tasks.append({**{k: item[k] for k in ('item_id', 'case', 'experiment', 'variant')},
                              'prompt_condition': prompt, 'reasoning': reasoning,
                              'trial_key': f"{item['case']}/{item['variant']}/{prompt}/{reasoning}"})
    random.Random(config['seed']).shuffle(tasks)
    tasks.sort(key=lambda x: x['experiment'])
    jsonl(root / '01-input/trial-matrix.jsonl', tasks)
    prompt_text = (root / '00-definition/common.md').read_text()
    layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
    prompts = {p: prompt_text + '\n' + layout.prompt_file(root / '00-definition', p).read_text()
               for p in ('P0', 'P1')}
    model_map = {x['item_id']: x['input'] for x in model_inputs}
    luna_requests = rows(luna / 'luna-api/01-requests/manifest.jsonl')
    for request in luna_requests:
        require(request['input'] == model_map[request['item_id']], 'LUNA_REQUEST_INPUT_CHANGED')
        require(request['prompt'] == prompts[request['prompt_condition']], 'LUNA_PROMPT_CHANGED')
        require(request['response_schema'] == schema, 'LUNA_SCHEMA_CHANGED')
        require(request['max_output_tokens'] == config['max_output_tokens'], 'OUTPUT_BUDGET_CHANGED')
    proof = {'created_at': created, 'luna_reference_run': luna.name, 'full_cohort_source_run': source.name,
             'luna_requests_compared': len(luna_requests), 'luna_common_inputs_identical': True,
             'luna_prompt_schema_identical': True, 'prior_responses_copied': 0,
             'new_model_calls': 0, 'frozen_input_hashes': {n: sha(source / n) for n in
                ('01-input/public.jsonl', '01-input/private.jsonl', *selection['manifest_files'])},
             'definition_hashes': {p.name: sha(p) for p in (root / '00-definition').iterdir()}}
    write(root / 'provenance/luna-comparison.json', proof)
    for name in ('current-vs-frozen.json', 'current-selection.json'):
        origin = project / 'log/20260921-gpu2-handoff' / name
        require(origin.exists(), 'CURRENT_PROVENANCE_MISSING:' + name)
        shutil.copyfile(origin, root / 'provenance' / name)
    for name, path in (('cohort-manifest.json', source / 'manifest.json'),
                       ('luna-manifest.json', luna / 'manifest.json')):
        shutil.copyfile(path, root / 'provenance' / name)
    source_files = [
        '01-evaluation/04-validation/answer_format.py',
        '01-evaluation/02-request/request_order.py',
        '01-evaluation/03-execution/call_layout.py',
        '01-evaluation/04-validation/reporting.py',
        '01-evaluation/04-validation/numeric_analysis.py', '02-analysis/legacy/content-analysis/analysis.py',
        '90-operations/storage.py', '00-input/dataset.py', '01-evaluation/pipeline.py',
    ]
    write(root / 'support/legacy-source-snapshot.json', {
        'src/finarch/experiments/' + name: {
            'sha256': sha(project / 'src/finarch/experiments' / name),
            'text': (project / 'src/finarch/experiments' / name).read_text(),
        } for name in source_files})
    shutil.copyfile(Path(__file__), root / 'support/exporter-source.txt')
    shutil.copyfile(project / 'archive/20260923-documentation-reorganization/docs/experiments-gpu2-handoff.md', root / 'PLAN.md')
    template = Template(Path(__file__).with_name('gpu2-handoff-readme-template.md').read_text())
    (root / 'README.md').write_text(template.substitute(run_id=root.name, created_at=created,
                                                      originals=1080, variants=7560))
    write(root / 'verification.json', {**proof, 'status': 'PASS', 'originals': 1080, 'variants': 7560})
    write(root / 'plan.json', {'created_at': created, 'models': [], 'execution_owner': config['remote_thread_id'],
                             'dual_mode_requests_per_model': 32400, 'single_mode_requests_per_model': 16200,
                             'total_requests': None, 'total_requests_status': 'AWAIT_REMOTE_MODEL_CAPABILITIES'})
    write(root / 'manifest.json', {str(p.relative_to(root)): sha(p) for p in root.rglob('*')
                                 if p.is_file() and p.name not in ('state.json', 'events.jsonl')})
    result = verify(root)
    write(root / 'state.json', {'status': 'TRANSFER_READY', 'models': {}, 'new_model_calls': 0})
    jsonl(root / 'events.jsonl', [
        {'time': created, 'event': 'INPUT_SELECTION', 'source_run': source.name,
         **{key: value for key, value in selection.items() if key != 'items'}},
        {'time': created, 'event': 'HANDOFF_PACKAGE_VERIFIED', **result}])
    return {'run': str(root), **result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--root', default='.')
    parser.add_argument('--config', default='config/experiments-gpu2.json')
    args = parser.parse_args()
    result = verify(args.root) if args.command == 'verify' else build(args.root, args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
