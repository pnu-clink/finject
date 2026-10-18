#!/usr/bin/env python3
"""Generate and check a native dataset adapter from one or more raw files."""

import argparse
import ast
import difflib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from jsonschema.exceptions import ValidationError as ResponseValidationError

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
runtime = importlib.import_module('finarch.dataset.0-template.runtime')
contracts = importlib.import_module('finarch.dataset.0-template.contracts')
checks = importlib.import_module('finarch.dataset.0-template.checks')


def slug(value):
    name = re.sub(r'[^a-z0-9_]+', '_', value.lower()).strip('_')
    if not name or len(name) > 64:
        raise ValueError('DATASET_NAME_MUST_CONTAIN_1_TO_64_ASCII_CHARACTERS')
    if not name[0].isalpha():
        name = 'dataset_' + name
    if '__' in name:
        raise ValueError('DOUBLE_UNDERSCORE_IN_DATASET_NAME')
    return name


def class_name(dataset):
    return ''.join(part.capitalize() for part in dataset.split('_')) + 'Provenance'


def named_template(stage, dataset):
    template = HERE / {1: 'template1_source.py', 2: 'template2_adapter.py', 3: 'template3_schema.py'}[stage]
    values = {'__DATASET__': dataset, '__DATASET_LITERAL__': repr(dataset),
              '__CLASS__': class_name(dataset), '__ADAPTER__': dataset}
    return re.sub(r'__(?:DATASET|DATASET_LITERAL|CLASS|ADAPTER)__',
                  lambda match: values[match.group()], template.read_text())


def render(stage, dataset, specification, implementation):
    checks.check_implementation(stage, implementation, dataset,
                                expected_class=named_template(3, dataset) if stage == 3 else None)
    if stage == 1:
        values = {'__SOURCE_IMPLEMENTATION__': implementation.rstrip(),
                  '__SOURCE_SPEC__': repr(specification),
                  '__RUN_README__': repr((HERE / 'run-readme-template.md').read_text())}
        text = re.sub(r'__(?:SOURCE_IMPLEMENTATION|SOURCE_SPEC|RUN_README)__',
                      lambda match: values[match.group()], named_template(1, dataset))
    else:
        text = implementation.rstrip() + '\n'
    ast.parse(text)
    return text


def load_implementation(code, path):
    # Used for trusted local fixtures. Authoring candidates execute in a child.
    native = importlib.import_module('finarch.dataset.00-input.adapters')
    namespace = {'__name__': 'generated_adapter_check', '__file__': str(path),
                 'assemble': native.assemble, 'extract_reference': native.extract_reference,
                 'Decimal': native.Decimal}
    exec(compile(code, str(path), 'exec'), namespace)
    return namespace


def patched_schema(original, declaration, name):
    tree = ast.parse(original)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    if name in classes:
        raise ValueError('PROVENANCE_CLASS_ALREADY_EXISTS: ' + name)
    sample = classes['PreparedSample']
    field = next(node for node in sample.body if isinstance(node, ast.AnnAssign)
                 and isinstance(node.target, ast.Name) and node.target.id == 'provenance')
    annotation = field.annotation
    if not isinstance(annotation, ast.Subscript) or not isinstance(annotation.slice, ast.Tuple):
        raise ValueError('UNRECOGNIZED_PROVENANCE_REGISTRATION')
    union = annotation.slice.elts[0]
    lines = original.splitlines(keepends=True)

    def offset(line, column):
        # AST columns are UTF-8 byte offsets, not Python character offsets.
        return sum(len(part) for part in lines[:line - 1]) + len(lines[line - 1].encode()[:column].decode())

    insertion = offset(sample.lineno, 0)
    union_end = offset(union.end_lineno, union.end_col_offset)
    updated = original[:union_end] + ' | ' + name + original[union_end:]
    updated = updated[:insertion] + declaration + '\n\n' + updated[insertion:]
    ast.parse(updated)
    return updated


def target_files(repository, dataset):
    base = repository / 'src/finarch/dataset'
    return [base / '00-input' / (dataset + '.py'), base / '00-input/adapters.py', base / 'schemas/prepared.py']


def snapshot_targets(repository, dataset):
    paths = target_files(repository, dataset)
    if paths[0].exists():
        raise ValueError('SOURCE_RUNNER_ALREADY_EXISTS: use ' + str(paths[0]) + ' to convert more files without an LLM')
    original = {path: path.read_bytes() if path.exists() else None for path in paths}
    adapter_tree = ast.parse(original[paths[1]].decode())
    names = {node.name for node in adapter_tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    if dataset in names:
        raise ValueError('ADAPTER_NAME_ALREADY_EXISTS: ' + dataset)
    schema_tree = ast.parse(original[paths[2]].decode())
    if class_name(dataset) in {node.name for node in schema_tree.body if isinstance(node, ast.ClassDef)}:
        raise ValueError('PROVENANCE_CLASS_ALREADY_EXISTS')
    return original


def originals_for_build(repository, dataset, replace_from=None):
    """Replace a prior generated result only when every recorded hash matches."""
    if replace_from is None:
        original = snapshot_targets(repository, dataset)
        return original, original
    directory = Path(replace_from).expanduser().resolve()
    if directory.name != 'adapter-generation':
        directory = directory / 'adapter-generation'
    if json.loads((directory / 'result.json').read_text()).get('status') != 'PASS':
        raise ValueError('REPLACEMENT_REQUIRES_PREVIOUS_SUCCESSFUL_RUN')
    entries = json.loads((directory / 'changes.json').read_text())
    paths = target_files(repository, dataset)
    expected = {str(path.relative_to(repository)) for path in paths}
    if len(entries) != 3 or {entry['path'] for entry in entries} != expected:
        raise ValueError('REPLACEMENT_TARGETS_DO_NOT_MATCH_DATASET')
    original, baseline = {}, {}
    for entry in entries:
        path = repository / entry['path']
        current = path.read_bytes()
        if runtime.digest(current) != entry['after_sha256']:
            raise ValueError('GENERATED_FILE_CHANGED_SINCE_PREVIOUS_RUN: ' + str(path))
        original[path] = current
        before = entry.get('baseline_sha256', entry['before_sha256'])
        if before is None:
            if path != paths[0]:
                raise ValueError('INVALID_REPLACEMENT_BASELINE')
            baseline[path] = None
        else:
            folder = 'baseline' if 'baseline_sha256' in entry else 'originals'
            saved = (directory / folder / entry['path']).read_bytes()
            if runtime.digest(saved) != before:
                raise ValueError('REPLACEMENT_BACKUP_HASH_MISMATCH')
            baseline[path] = saved
    return original, baseline


def native_adapter_examples(text):
    lines = text.splitlines(keepends=True)
    return ''.join(''.join(lines[node.lineno - 1:node.end_lineno]) + '\n\n'
                   for node in ast.parse(text).body
                   if isinstance(node, ast.FunctionDef) and node.name in ('finance', 'tatqa'))


def preview(value, depth=0):
    """Bounded source excerpts for authoring; never use these excerpts as data."""
    if depth > 7:
        return {'excerpt_omitted': True, 'type': type(value).__name__}
    if isinstance(value, dict):
        items = list(value.items())
        result = {str(k): preview(v, depth + 1) for k, v in items[:40]}
        if len(items) > 40:
            result['__excerpt_omitted_keys__'] = len(items) - 40
        return result
    if isinstance(value, list):
        if len(value) <= 12:
            return [preview(v, depth + 1) for v in value]
        return {'array_length': len(value), 'first_items': [preview(v, depth + 1) for v in value[:6]],
                'last_item': preview(value[-1], depth + 1), 'excerpt_truncated': True}
    if isinstance(value, str) and len(value) > 6000:
        return {'string_excerpt': value[:6000], 'length': len(value), 'excerpt_truncated': True}
    if isinstance(value, runtime.SourceFloat):
        return {'numeric_token': value.token}
    return value


def overview(paths):
    result = []
    for doc in runtime.load_documents(paths):
        items = doc['document']
        indexes = sorted(set((0, len(items) // 2, len(items) - 1))) if items else []
        result.append({'name': doc['name'], 'format': doc['format'], 'normalized_length': len(items),
                       'original_root_wrapped': doc['wrapped'],
                       'examples': [{'index': index, 'record': preview(items[index])} for index in indexes]})
    return result


def registration_payload(dataset, template, bundle, samples, previous=None, error=None):
    # Only the registration contract and Python's checked result go to the LLM.
    # File hashes, source contents and adapter samples are not model judgments.
    checked = checks.check_source_metadata(bundle, samples, dataset)
    return {'dataset': dataset, 'class_name': class_name(dataset), 'input_contract': 3,
            'contract_version': contracts.CONTRACT_VERSION, 'contract': (HERE / 'CONTRACT.md').read_text(),
            'template': template,
            'python_validation': checked, 'previous_response': previous, 'validation_error': error}


def resume_responses(path):
    """Read successful code responses; reject the obsolete mapping-only format."""
    if path is None:
        return {}
    directory = Path(path).expanduser().resolve()
    if directory.name != 'adapter-generation':
        directory = directory / 'adapter-generation'
    if not directory.is_dir():
        raise ValueError('RESUME_GENERATION_DIRECTORY_NOT_FOUND: ' + str(directory))
    reused = {}
    for stage in (1, 2):
        for attempt in sorted((directory / f'stage-{stage}').glob('attempt-*'), reverse=True):
            check_path, response_path = attempt / 'check.json', attempt / 'response.json'
            if not check_path.is_file() or not response_path.is_file():
                continue
            if json.loads(check_path.read_text()).get('status') != 'PASS':
                continue
            response = json.loads(response_path.read_text())
            if 'implementation' not in response:
                raise ValueError('RESUME_REQUIRES_PYTHON_CODE_RESPONSES: old mapping-only runs cannot be resumed; start a new authoring run')
            if stage == 1 and 'fields' not in response.get('specification', {}):
                raise ValueError('RESUME_REQUIRES_PREPROCESSING_CONTRACT: start a new authoring run')
            contracts.validate_response(stage, response)
            reused[stage] = {'response': response, 'path': str(response_path),
                             'sha256': runtime.digest(response_path.read_bytes())}
            break
    if not reused:
        raise ValueError('NO_PASSED_READER_OR_ADAPTER_RESPONSES_TO_RESUME')
    return reused


class ApiAuthor:
    def __init__(self, args, repository):
        config_path = Path(args.config).resolve() if args.config else repository / 'config/llm.json'
        config = json.loads(config_path.read_text())
        if config.get('execution_enabled') is not True:
            raise ValueError('MODEL_EXECUTION_DISABLED_IN_CONFIG')
        profiles_path = config_path.parent / config.get('profiles_path', 'codex-profiles.toml')
        profiles = tomllib.loads(profiles_path.read_text())
        profile_id = args.profile or 'sol61-low-api'
        profile = dict(profiles['profiles'][profile_id])
        if profile.get('provider') != 'openai' or profile.get('transport') != 'api':
            raise ValueError('OPENAI_API_PROFILE_REQUIRED')
        if args.model:
            profile['model'] = args.model
        profile['max_output_tokens'] = min(profile.get('max_output_tokens', 16384), args.max_output_tokens)
        # This is a dedicated adapter-authoring purpose, not a POT/semantic call.
        profile.pop('total_token_budget', None)
        profile['purpose'] = 'adapter_authoring'
        self.settings = {'execution_enabled': True, 'policy': {'tools': [], 'skills': []},
                         'profile': profile, 'model': profile['model'], 'effort': profile['effort'],
                         'timeout_seconds': config.get('cli_limits', {}).get('timeout_seconds', 300)}
        self.transport = importlib.import_module('finarch.shared.providers.api')
        # Fail before creating a run if the key is absent. Never print or persist it.
        self.transport.api_key()
        self.description = {'provider': 'openai', 'profile': profile_id, 'model': profile['model'],
                            'effort': profile['effort'], 'expected_calls': 3,
                            'maximum_calls': 3 * args.attempts,
                            'max_output_tokens_per_call': profile['max_output_tokens'],
                            'cost': None, 'cost_note': 'Paid API calls; cost depends on tokens and model pricing. Actual usage is saved.'}

    def __call__(self, stage, payload, directory):
        schema = contracts.response_schema(stage)
        from jsonschema import Draft202012Validator
        if not schema.get('properties'):
            raise ValueError('NONEMPTY_RESPONSE_SCHEMA_REQUIRED')
        Draft202012Validator.check_schema(schema)
        prompt = (HERE / f'prompt{stage}.md').read_text()
        text = self.transport.complete_api(
            settings=self.settings, role=f'adapter-authoring.stage-{stage}', payload=payload,
            response_schema=schema, instruction=prompt,
            prompt_selection={'file': f'prompt{stage}.md', 'stage': stage},
            save=lambda name, value: runtime.write_json(directory / name, value))
        response = json.loads(text)
        # The same schema used in the request validates the actual response.
        Draft202012Validator(schema).validate(response)
        return response


def child_environment(source):
    keep = ('PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT', 'WINDIR', 'TMPDIR', 'TEMP', 'TMP')
    result = {key: os.environ[key] for key in keep if key in os.environ}
    result.update(PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1')
    return result


def run_child(command, repository, timeout=180):
    result = subprocess.run(command, cwd=repository, env=child_environment(repository / 'src'),
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # Candidate checks emit structured JSON. Preserve the original reason
        # and field differences before applying any bounded source preview.
        try:
            failure = json.loads(result.stderr)
        except json.JSONDecodeError:
            failure = None
        if (isinstance(failure, dict) and failure.get('status') == 'FAIL'
                and isinstance(failure.get('message'), str)
                and isinstance(failure.get('details', {}), dict)):
            raise checks.CheckFailed(failure['message'], failure.get('details', {}))
        raise checks.CheckFailed('GENERATED_RUN_FAILED', {'stdout': result.stdout[-6000:],
                                                          'stderr': result.stderr[-10000:]})
    return result.stdout


def check_candidate(stage, repository, dataset, paths, specification, code, source_specification):
    with tempfile.TemporaryDirectory(prefix='finject-candidate-check-') as folder:
        temporary = Path(folder)
        (temporary / 'code.txt').write_text(code)
        request = {'stage': stage, 'dataset': dataset, 'paths': list(map(str, paths)),
                   'specification': specification, 'source_specification': source_specification,
                   'target_path': str(target_files(repository, dataset)[0 if stage == 1 else 1]),
                   'code_path': str(temporary / 'code.txt')}
        runtime.write_json(temporary / 'request.json', request)
        return json.loads(run_child([sys.executable, '-B', str(HERE / 'checks.py'),
                                     str(temporary / 'request.json')], repository))


def integration_check(repository, dataset, paths, generated, directory):
    """Run the patched native code in a temporary checkout without credentials."""
    with tempfile.TemporaryDirectory(prefix='finject-adapter-') as temp:
        stage = Path(temp)
        shutil.copytree(repository / 'src', stage / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(repository / 'config', stage / 'config')
        if (repository / 'data/sample').exists():
            shutil.copytree(repository / 'data/sample', stage / 'data/sample')
        for target, data in generated.items():
            dest = stage / target.relative_to(repository)
            dest.write_bytes(data)
        regression = run_child([sys.executable, '-B', str(stage / 'src/finarch/dataset/0-template/regression.py')], stage)
        # Installed implementations must work after authoring tools are removed.
        shutil.rmtree(stage / 'src/finarch/dataset/0-template')
        output = stage / 'data/prepared/check'
        runner = stage / 'src/finarch/dataset/00-input' / (dataset + '.py')
        stdout = run_child([sys.executable, '-B', str(runner), *map(str, paths), '--output', str(output)], stage)
        plan_code = (
            'import importlib,json,sys; '
            "sys.path.insert(0,'src'); "
            "plan=importlib.import_module('finarch.dataset.01-preparation.prepare_schedule').plan; "
            f"estimate=plan({str(output / 'input.json')!r},'config/llm.json')[3]; "
            "print(json.dumps({'case_count':estimate['case_count'],'generation_started':False}))")
        planned = run_child([sys.executable, '-B', '-c', plan_code], stage)
        # Existing Finance/TAT-QA samples must still validate under the new union.
        result = {'status': 'PASS', 'runner': json.loads(stdout), 'plan': json.loads(planned),
                  'existing_sources': json.loads(regression), 'model_calls': 0,
                  'authoring_directory_present': False}
        # Keep only useful small evidence, not a second full source checkout.
        runtime.write_json(directory / 'integration.json', result)
        runtime.write_json(directory / 'input-preview.json', json.loads((output / 'input.json').read_text())[:3])
        return result


def build_changes(repository, dataset, originals, codes):
    paths = target_files(repository, dataset)
    schema = patched_schema(originals[paths[2]].decode(), codes[3], class_name(dataset))
    adapters = originals[paths[1]].decode().rstrip() + '\n\n\n' + codes[2]
    return {paths[0]: codes[1].encode(), paths[1]: adapters.encode(), paths[2]: schema.encode()}


def install(repository, dataset, originals, generated, paths, output, generation_dir, baseline=None):
    baseline = originals if baseline is None else baseline
    for path, original in originals.items():
        current = path.read_bytes() if path.exists() else None
        if current != original:
            raise ValueError('TARGET_CHANGED_DURING_GENERATION: ' + str(path))
    changes, diff = [], []
    for path, updated in generated.items():
        relative = str(path.relative_to(repository))
        before = originals[path]
        if before is not None:
            backup = generation_dir / 'originals' / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(before)
        initial = baseline[path]
        if initial is not None:
            baseline_backup = generation_dir / 'baseline' / relative
            baseline_backup.parent.mkdir(parents=True, exist_ok=True)
            baseline_backup.write_bytes(initial)
        diff.extend(difflib.unified_diff((before or b'').decode().splitlines(True),
                                        updated.decode().splitlines(True),
                                        fromfile='before/' + relative, tofile='after/' + relative))
        changes.append({'path': relative, 'action': 'unchanged' if before == updated else ('add' if before is None else 'modify'),
                        'before_sha256': runtime.digest(before) if before is not None else None,
                        'after_sha256': runtime.digest(updated),
                        'baseline_sha256': runtime.digest(initial) if initial is not None else None})
    (generation_dir / 'changes.patch').write_text(''.join(diff))
    runtime.write_json(generation_dir / 'changes.json', changes)
    installed = []
    try:
        for path, updated in generated.items():
            # Recheck immediately before replacing each target.
            if (path.read_bytes() if path.exists() else None) != originals[path]:
                raise ValueError('CONCURRENT_TARGET_EDIT: ' + str(path))
            if originals[path] == updated:
                continue
            temporary = path.with_name(path.name + '.adapter-tmp')
            with temporary.open('xb') as stream:
                stream.write(updated)
            temporary.replace(path)
            installed.append(path)
        runner = target_files(repository, dataset)[0]
        stdout = run_child([sys.executable, '-B', str(runner), *map(str, paths), '--output', str(output)], repository)
        result = json.loads(stdout)
        result['changed_files'] = changes
        return result
    except BaseException:
        for path in reversed(installed):
            if path.read_bytes() != generated[path]:
                continue  # Never overwrite a concurrent user's edit during rollback.
            if originals[path] is None:
                path.unlink()
            else:
                path.write_bytes(originals[path])
        # Keep failed output for diagnosis. A concurrently created output must
        # never be moved or deleted on the assumption that this invocation owns it.
        raise


def build(args, *, author=None, repository=ROOT):
    repository = Path(repository).resolve()
    paths = [Path(path).expanduser().resolve() for path in args.paths]
    dataset = slug(args.name or paths[0].stem)
    inventory = overview(paths)  # Check local files before any API request.
    if args.inspect:
        print(json.dumps({'dataset': dataset, 'sources': inventory, 'model_calls': 0}, indent=2))
        return {'status': 'INSPECTED', 'model_calls': 0}
    originals, baseline = originals_for_build(repository, dataset, args.replace_from)
    output = Path(args.output).expanduser().resolve() if args.output else (
        repository / 'data/prepared' / runtime.new_output(dataset).name)
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS: ' + str(output))
    run_dir = runtime.input_run_directory(output)
    generation_dir = run_dir.parent / 'adapter-generation'
    if generation_dir.exists() or (run_dir / 'preparation-result.json').exists():
        raise ValueError('RUN_ALREADY_EXISTS: ' + str(generation_dir))
    reused = resume_responses(args.resume)
    if author is None:
        author = ApiAuthor(args, repository)
    description = dict(getattr(author, 'description', {'provider': 'offline fixture', 'model_calls': 0}))
    description['contract_version'] = contracts.CONTRACT_VERSION
    description['reused_stages'] = sorted(reused)
    if description.get('provider') == 'openai':
        description['expected_calls'] = 3 - len(reused)
        description['maximum_calls'] = 3 * args.attempts - len(reused)
    print(json.dumps(description, indent=2), flush=True)
    generation_dir.mkdir(parents=True, exist_ok=False)
    runtime.write_json(generation_dir / 'execution.json', description)
    specifications, codes, bundle, samples = {}, {}, None, None
    changed = False
    try:
        for stage in (1, 2, 3):
            last_error = None
            previous = None
            for attempt in range(1, args.attempts + 1):
                directory = generation_dir / f'stage-{stage}' / f'attempt-{attempt}'
                directory.mkdir(parents=True)
                payload = {'dataset': dataset, 'input_contract': stage,
                           'contract_version': contracts.CONTRACT_VERSION,
                           'contract': (HERE / 'CONTRACT.md').read_text(),
                           'template': named_template(stage, dataset),
                           'sources': inventory if stage == 1 else None,
                           'reader_specification': specifications.get(1),
                           'adapter_specification': specifications.get(2),
                           'reader_implementation': codes.get(1) if stage == 2 else None,
                           'real_records': [preview(row['record']) for row in (bundle or {}).get('records', [])[:3]],
                           'question_pointers': [row['question_pointer'] for row in (bundle or {}).get('records', [])[:3]],
                           'native_sample_schema': checks.CandidateSample.model_json_schema() if stage == 2 else None,
                           'native_adapter_examples': native_adapter_examples(baseline[target_files(repository, dataset)[1]].decode()) if stage == 2 else None,
                           'number_pattern': runtime.NUMBER.pattern if stage == 2 else None,
                           'previous_response': previous, 'validation_error': last_error}
                if stage == 3:
                    payload = registration_payload(dataset, payload['template'], bundle, samples,
                                                   previous=previous, error=last_error)
                    runtime.write_json(directory / 'source-metadata-check.json', payload['python_validation'])
                try:
                    if stage in reused and attempt == 1:
                        saved = reused[stage]
                        response = saved['response']
                        runtime.write_json(directory / 'reused-response.json', {
                            'source': saved['path'], 'sha256': saved['sha256'],
                            'model_call_skipped': True, 'current_input_checks_required': True})
                    else:
                        response = author(stage, payload, directory)
                    previous = response
                    runtime.write_json(directory / 'response.json', response)
                    spec = contracts.validate_response(stage, response)
                    code = render(stage, dataset, spec, response['implementation'])
                    # Code is kept as text in run evidence; executable files belong under src.
                    (directory / 'implementation.txt').write_text(code)
                    if stage == 1:
                        check_candidate(stage, repository, dataset, paths, spec, code, None)
                        # Independent expected records are used only as authoring/check input.
                        bundle = runtime.preprocessed_records(paths, spec)
                    elif stage == 2:
                        if spec != specifications[1]['fields']:
                            raise checks.CheckFailed('ADAPTER_DECLARATION_MUST_MATCH_CHECKED_PREPROCESSING')
                        check_candidate(stage, repository, dataset, paths, spec, code, specifications[1])
                        samples = [runtime.adapter_record(row['record'], row['source_metadata'],
                            question_pointer=row['question_pointer'], raw_id=row['raw_id'],
                            dataset=dataset, specification=spec) for row in bundle['records']]
                    else:
                        checks.check_provenance(spec, dataset)
                        codes[stage] = code
                        generated = build_changes(repository, dataset, baseline, codes)
                        integration_check(repository, dataset, paths, generated, directory)
                    specifications[stage], codes[stage] = spec, code
                    runtime.write_json(directory / 'check.json', {'status': 'PASS', 'stage': stage})
                    print(f'Stage {stage}/3 PASS (attempt {attempt})', flush=True)
                    break
                except contracts.NeedsInformation:
                    raise
                except (ValueError, KeyError, TypeError, AssertionError, SyntaxError, ResponseValidationError,
                        subprocess.TimeoutExpired) as error:
                    last_error = {'message': str(error), 'details': preview(getattr(error, 'details', {}))}
                    runtime.write_json(directory / 'check.json', {'status': 'FAIL', **last_error})
                    print(f'Stage {stage}/3 FAIL (attempt {attempt}): {str(error)[:300]}', flush=True)
                    if attempt == args.attempts:
                        raise
        generated = build_changes(repository, dataset, baseline, codes)
        for source in bundle['sources']:
            if runtime.digest(Path(source['path']).read_bytes()) != source['sha256']:
                raise ValueError('RAW_FILE_CHANGED_DURING_AUTHORING: ' + source['name'])
        # Registering a provenance variant changes the existing schema hash.
        # Never rewrite old datasets/manifests silently to hide this incompatibility.
        old_manifests = []
        for base in (repository / 'data/prepared', repository / 'reports/run'):
            if base.exists():
                old_manifests.extend(str(path.relative_to(repository)) for path in base.rglob('selection-manifest.json'))
        schema_path = target_files(repository, dataset)[2]
        if old_manifests and generated[schema_path] != originals[schema_path]:
            print('Schema registration changes the schema hash. Existing prepared bundles may need rebuilding; originals are preserved.', flush=True)
            runtime.write_json(generation_dir / 'existing-manifests.json', old_manifests)
        result = install(repository, dataset, originals, generated, paths, output, generation_dir, baseline=baseline)
        changed = True
        result['authoring'] = description
        result['generation_directory'] = str(generation_dir)
        runtime.write_json(generation_dir / 'result.json', result)
        print(json.dumps(result, indent=2), flush=True)
        return result
    except BaseException as error:
        runtime.write_json(generation_dir / 'result.json', {
            'status': 'FAIL', 'error_type': type(error).__name__, 'reason': str(error),
            'code_installed': changed})
        raise


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('paths', nargs='+', help='Raw JSON, JSONL or CSV files sharing one layout')
    result.add_argument('--name', help='Dataset/adapter name; default: first input filename')
    result.add_argument('--output', type=Path, help='New data directory; defaults to data/prepared/<unique-run>')
    result.add_argument('--config', type=Path, help='Existing LLM configuration; default: config/llm.json')
    result.add_argument('--profile', help='OpenAI API profile; default: sol61-low-api (gpt-6.1-sol, low effort)')
    result.add_argument('--model', help='Optional model override for adapter authoring only')
    result.add_argument('--resume', type=Path, help='Previous run or adapter-generation directory; recheck and reuse successful stages 1/2')
    result.add_argument('--replace-from', type=Path, help='Replace only the three unchanged files installed by this previous successful run')
    result.add_argument('--attempts', type=int, choices=range(1, 4), default=3, help='Attempts per stage, including the first (1-3)')
    result.add_argument('--max-output-tokens', type=int, default=16384)
    result.add_argument('--inspect', action='store_true', help='Inspect input without an API call or file changes')
    return result


def main():
    args = parser().parse_args()
    if not 1024 <= args.max_output_tokens <= 65536:
        raise SystemExit('--max-output-tokens must be between 1024 and 65536')
    try:
        build(args)
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
