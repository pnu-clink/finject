"""Record local relation checks for the common viewer; never call a model."""
from datetime import datetime, timezone
import hashlib
from importlib import import_module
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUN = ROOT / 'reports/run/20261001-ic-relation-scope-check'
planner = import_module('finarch.dataset.02-generation.01-perturbation.generation_plan')
realize = import_module('finarch.dataset.02-generation.02-generate-text.dtt_realize')
from finarch.dataset.schemas.validation import validate


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks = json.loads((RUN / '04-local-checks.json').read_text())
    if checks['status'] != 'PASS':
        raise ValueError('LOCAL_TESTS_NOT_PASSED')
    examples = {
        'test-0025': ' The 2015 balance of unrecognized tax benefits was twice the 2014 balance of $1,171 million.',
        'test-0254': " IMFT's total assets in 2018 were twice its property, plant, and equipment in 2019."}
    records = []
    for case, example in examples.items():
        base = ROOT / f'reports/run/20260917-002/02-generation/01-round/{case}/05-ic-relation'
        source = base / '01-perturbation/01-input.json'
        preserved = {str(path.relative_to(ROOT)): digest(path) for path in
                     (source, base / 'run.json', ROOT / 'reports/run/20260917-002/results/05-ic-relation.json')}
        inputs = json.loads(source.read_text())
        before = json.loads((base / 'run.json').read_text())['plan']
        after = planner.build(inputs['sample'], inputs['program'], inputs['graph'], 4)
        request = after['request']
        validate('02-generation.02-generate-text.realization.request', request)
        slot = request['edit_slots'][0]
        manual = {'patches': [{k: slot[k] for k in ('start', 'end', 'before', 'element_ids')} | {'text': example}]}
        observation, patches = realize.check_response(request, manual)
        for name, expected in preserved.items():
            if digest(ROOT / name) != expected:
                raise ValueError('HISTORICAL_ARTIFACT_CHANGED:' + name)
        records.append({'case': case, 'source': str(source.relative_to(ROOT)), 'preserved_sha256': preserved,
                        'before_plan': before, 'after_plan': after,
                        'example_origin': 'MANUALLY_WRITTEN_LOCAL_PATCH_FIXTURE_NOT_MODEL_OUTPUT',
                        'example': manual, 'example_observation': observation, 'patches': patches,
                        'mechanical_status': 'PASS', 'model_generation_status': 'NOT_RUN',
                        'semantic_review_status': 'NOT_RUN'})
    write(RUN / '05-sample-checks.json', {'scope': 'LOCAL_MECHANICAL_CHECK_ONLY', 'model_calls': 0, 'records': records})
    before = json.loads((RUN / '01-before-prompts.json').read_text())
    changes = []
    for name, old in before.items():
        path = ROOT / name
        changes.append({'path': name, 'before_characters': old['characters'],
                        'after_characters': len(path.read_text()), 'before_sha256': old['sha256'],
                        'after_sha256': digest(path), 'after_text': path.read_text()})
    write(RUN / '06-prompt-changes.json', changes)
    url = 'http://127.0.0.1:8893/?run=' + RUN.name
    template = ROOT / 'src/finarch/documentation/templates/checks/relation-scope-readme.md'
    (RUN / 'README.md').write_text(template.read_text().format(tests_run=checks['tests_run'], viewer_url=url))
    files = ['README.md', '01-before-prompts.json', '04-local-checks.json', '05-sample-checks.json', '06-prompt-changes.json']
    docs = [{'path': str((RUN / name).relative_to(ROOT)), 'title': name,
             'sha256': digest(RUN / name), 'group': 'local-verification'} for name in files]
    for name in before:
        docs.append({'path': name, 'title': Path(name).name, 'sha256': digest(ROOT / name), 'group': 'active-prompts'})
    for step in ('01-perturbation', '02-generate-text', '03-validation'):
        name = f'docs/01-dataset/02-generation/{step}/README.md'
        docs.append({'path': name, 'title': step, 'sha256': digest(ROOT / name), 'group': 'architecture'})
    write(RUN / 'documentation.json', {'kind': 'PIPELINE_DOCUMENTATION', 'title': 'IC-RELATION \uc801\uc6a9 · \ub85c\uceec \ud655\uc778',
          'documents': docs, 'model_calls': 0, 'entry_document': docs[0]['path'],
          'reference_files': [str((RUN / name).relative_to(ROOT)) for name in ('02-tests.log', '03-focused-tests.log', 'events.jsonl')]})
    write(RUN / 'migration.json', [])
    write(RUN / 'summary.json', {'kind': 'LOCAL_RELATION_SCOPE_CHECK', 'status': 'LOCAL_CHECKED',
          'tests_run': checks['tests_run'], 'model_calls': 0, 'semantic_review_status': 'NOT_RUN'})
    with (RUN / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(), 'action': 'relation_scope_local_check',
                                'tests_run': checks['tests_run'], 'model_calls': 0, 'cases': list(examples)}) + '\n')
    print(json.dumps({'run': RUN.name, 'cases': len(records), 'model_calls': 0, 'tests_run': checks['tests_run']}))


if __name__ == '__main__':
    main()
