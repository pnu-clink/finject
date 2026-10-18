"""Authoring-time reference checks. New installed code does not import this file.

The reference conversion supplies independent expected values for candidate
checks; it is not the generated adapter's implementation.
"""

import csv
import hashlib
import importlib
import io
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from finarch.shared.reference import SourceFloat, Reference, extract_reference, load_raw

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SCHEMA_ID = '01-preparation.01-source.prepared-input'
NUMBER = re.compile(r'(?<!\w)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?!\w)')
JSON_NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def escape(value):
    return str(value).replace('~', '~0').replace('/', '~1').replace('*', '~2')


def tokens(pointer):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')):
        raise ValueError('INVALID_JSON_POINTER: ' + repr(pointer))
    return [] if pointer == '' else pointer[1:].split('/')


def select(value, pointer):
    """Resolve an extended JSON Pointer without eval, code or filesystem access."""
    found = [('', value)]
    for component in tokens(pointer):
        following = []
        for parent, node in found:
            if component == '*':
                if isinstance(node, list):
                    children = enumerate(node)
                elif isinstance(node, dict):
                    children = node.items()
                else:
                    raise ValueError('WILDCARD_REQUIRES_CONTAINER: ' + parent)
                following.extend((parent + '/' + escape(key), child) for key, child in children)
            else:
                if re.search(r'~(?![012])', component):
                    raise ValueError('INVALID_POINTER_ESCAPE: ' + component)
                key = component.replace('~2', '*').replace('~1', '/').replace('~0', '~')
                if isinstance(node, dict) and key in node:
                    child = node[key]
                elif isinstance(node, list) and key.isdigit() and str(int(key)) == key and int(key) < len(node):
                    child = node[int(key)]
                else:
                    raise ValueError('SOURCE_PATH_MISSING: ' + parent + '/' + component)
                following.append((parent + '/' + escape(key), child))
        found = following
    return found


def at(value, pointer):
    if '*' in tokens(pointer):
        raise ValueError('SCALAR_POINTER_CANNOT_USE_WILDCARD')
    matches = select(value, pointer)
    if len(matches) != 1:
        raise ValueError('EXACTLY_ONE_SOURCE_VALUE_REQUIRED: ' + pointer)
    return matches[0][1]


def load_documents(paths):
    documents = []
    resolved = [Path(path).expanduser().resolve() for path in paths]
    if not resolved or len(set(resolved)) != len(resolved):
        raise ValueError('UNIQUE_INPUT_FILES_REQUIRED')
    for position, path in enumerate(resolved):
        content = path.read_bytes()
        suffix = path.suffix.lower()
        if suffix == '.json':
            raw = load_checked_json(content)
        elif suffix in ('.jsonl', '.ndjson'):
            lines = content.decode('utf-8-sig').splitlines()
            if any(not line.strip() for line in lines):
                raise ValueError('EMPTY_JSONL_LINE: ' + str(path))
            raw = [load_checked_json(line) for line in lines]
        elif suffix == '.csv':
            reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError('UNIQUE_CSV_HEADERS_REQUIRED')
            raw = list(reader)
            if any(None in row or None in row.values() for row in raw):
                raise ValueError('RAGGED_CSV_ROW')
        else:
            raise ValueError('SUPPORTED_INPUTS_ARE_JSON_JSONL_CSV: ' + str(path))
        if not isinstance(raw, (dict, list)):
            raise ValueError('SOURCE_ROOT_MUST_BE_OBJECT_OR_ARRAY')
        name = f'{position + 1:03d}-{path.name}'
        documents.append({'name': name, 'path': str(path), 'sha256': digest(content),
                          'wrapped': isinstance(raw, dict),
                          'document': [raw] if isinstance(raw, dict) else raw,
                          'format': suffix.lstrip('.')})
    return documents


def load_checked_json(content):
    # Check duplicate keys/non-finite tokens without losing the lexical numbers.
    importlib.import_module('finarch.dataset.schemas.validation').parse_json(content)
    return load_raw(content)


def read_records(paths, specification):
    """Stage 1: preserve original objects; record every literal-filter exclusion."""
    contracts = importlib.import_module('finarch.dataset.0-template.contracts')
    from jsonschema import Draft202012Validator
    Draft202012Validator(contracts.SOURCE).validate(specification)
    documents = load_documents(paths)
    records, exclusions = [], []
    for doc in documents:
        for record_pointer, record in select(doc['document'], specification['records_path']):
            if not isinstance(record, dict):
                raise ValueError('RECORD_MUST_BE_OBJECT: ' + record_pointer)
            original_pointer = record_pointer
            if doc['wrapped']:
                if not (record_pointer == '/0' or record_pointer.startswith('/0/')):
                    raise ValueError('WRAPPED_ROOT_LOCATION_INVALID')
                original_pointer = record_pointer[2:]
            questions = select(record, specification['questions_path'])
            if not questions:
                raise ValueError('NO_QUESTIONS_IN_RECORD: ' + original_pointer)
            for question_pointer, question in questions:
                if not isinstance(question, dict):
                    raise ValueError('QUESTION_RECORD_MUST_BE_OBJECT: ' + question_pointer)
                origin = {'source': doc['name'], 'record_pointer': original_pointer,
                          'question_pointer': question_pointer}
                mismatches = [rule for rule in specification['include']
                              if at(question, rule['path']) != rule['equals']]
                if mismatches:
                    exclusions.append({**origin, 'reason': 'EXPLICIT_SOURCE_CATEGORY_FILTER',
                                       'filters': mismatches})
                    continue
                location = json.dumps(origin, sort_keys=True, ensure_ascii=False)
                raw_id = 'raw-' + digest((doc['sha256'] + location).encode())[:24]
                index = int(original_pointer[1:]) if re.fullmatch(r'/\d+', original_pointer) else None
                records.append({**origin, 'raw_id': raw_id, 'record': record,
                                'question': question, 'record_index': index,
                                'source_metadata': {'name': doc['name'], 'sha256': doc['sha256']}})
    if not records:
        raise ValueError('NO_SELECTED_QUESTIONS')
    identifiers = [row['raw_id'] for row in records]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('DUPLICATE_SOURCE_LOCATION')
    sources = [{k: doc[k] for k in ('name', 'path', 'sha256')} for doc in documents]
    return {'records': records, 'sources': sources, 'exclusions': exclusions}


def literal_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, SourceFloat):
        return value.token
    if type(value) is int:
        return str(value)
    if value is None or type(value) is bool:
        return json.dumps(value)
    raise ValueError('CONTEXT_FRAGMENT_MUST_BE_SCALAR')


def field_pointer(selection, question_pointer):
    return (question_pointer if selection['root'] == 'question' else '') + selection['path']


def answer_token(value, formatting):
    """Remove declared literal punctuation only; never rescale or solve."""
    if isinstance(value, SourceFloat):
        return value.token
    if type(value) is int:
        return str(value)
    if not isinstance(value, str):
        raise ValueError('NUMERIC_DISPLAY_ANSWER_REQUIRED')
    token = value.strip()
    negative = formatting['parentheses_negative'] and token.startswith('(') and token.endswith(')')
    if negative:
        token = token[1:-1].strip()
    prefix, suffix = formatting['prefix'], formatting['suffix']
    if prefix and token.startswith(prefix):
        token = token[len(prefix):].strip()
    if suffix and token.endswith(suffix):
        token = token[:-len(suffix)].strip()
    if formatting['grouping_separator'] and ',' in token:
        if not re.fullmatch(r'-?\d{1,3}(?:,\d{3})+(?:\.\d+)?', token):
            raise ValueError('INVALID_GROUPED_ANSWER: ' + repr(value))
        token = token.replace(',', '')
    if negative:
        if token.startswith('-'):
            raise ValueError('DOUBLE_NEGATIVE_ANSWER')
        token = '-' + token
    if not JSON_NUMBER.fullmatch(token):
        raise ValueError('UNSUPPORTED_DISPLAY_ANSWER: ' + repr(value))
    return token


def context_parts(record, question_pointer, specification):
    """Declare original pieces; common content.py owns all assembly and spans."""
    return [{'kind': part['kind'], 'source_pointer': pointer, 'value': value}
            for part in specification
            for pointer, value in select(record, field_pointer(part, question_pointer))]


def preprocessed_records(paths, specification):
    """Independent expected preprocessor output, never an installed dependency."""
    contracts = importlib.import_module('finarch.dataset.0-template.contracts')
    from jsonschema import Draft202012Validator
    Draft202012Validator(contracts.PREPROCESS_SOURCE).validate(specification)
    bundle = read_records(paths, {key: specification[key] for key in contracts.SOURCE['properties']})
    fields = specification['fields']
    content = importlib.import_module('finarch.dataset.00-input.content')
    for row in bundle['records']:
        record, pointer = row['record'], row['question_pointer']
        question = at(record, field_pointer(fields['question'], pointer))
        if not isinstance(question, str) or not question.strip():
            raise ValueError('NONEMPTY_QUESTION_TEXT_REQUIRED')
        row['adapter_record'] = {'context_parts': context_parts(record, pointer, fields['context'])}
        row['adapter_question'] = {
            'uid': row['raw_id'], 'question': question,
            'answer': answer_token(at(record, field_pointer(fields['answer'], pointer)), fields['answer_format'])}
        # Invalid tables and context fail in stage 1, before the adapter is frozen.
        content.assemble(row['adapter_record'], 'parts')
    return bundle


def assemble_context(record, question_pointer, context_specification):
    content = importlib.import_module('finarch.dataset.00-input.content')
    return content.assemble({'context_parts': context_parts(record, question_pointer, context_specification)}, 'parts')


def adapter_record(record, source, *, question_pointer, raw_id, dataset, specification):
    """Stage 2: return the native adapter dictionary, without the runner's id."""
    question = at(record, field_pointer(specification['question'], question_pointer))
    if not isinstance(question, str) or not question.strip():
        raise ValueError('NONEMPTY_QUESTION_TEXT_REQUIRED')
    answer = at(record, field_pointer(specification['answer'], question_pointer))
    token = answer_token(answer, specification['answer_format'])
    reference = Reference('-0', 'integer', 0) if token == '-0' else extract_reference(load_raw(token))
    if not raw_id:
        raise ValueError('RUNNER_RAW_ID_REQUIRED')
    return {'raw_id': raw_id, 'question': question,
            **assemble_context(record, question_pointer, specification['context']),
            **reference.fields(),
            'answer_metadata': {'scale': None, 'negative': Decimal(reference.reference_answer).is_signed()},
            'provenance': {'dataset': dataset, 'name': source['name'], 'sha256': source['sha256']}}


def input_run_directory(output):
    helper = importlib.import_module('finarch.dataset.shared.adapter')
    return helper.input_run_directory(output)


def new_output(dataset):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    return ROOT / 'data' / 'prepared' / f'{dataset}-{stamp}-{uuid4().hex[:6]}'


def prepare_dataset(dataset, paths, source_specification, *, output=None):
    """Write the native bundle; existing code performs schema/loader validation."""
    output = Path(output).expanduser().resolve() if output else new_output(dataset)
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS: ' + str(output))
    run_dir = input_run_directory(output)
    if (run_dir / 'preparation-result.json').exists():
        raise ValueError('RUN_EVIDENCE_ALREADY_EXISTS: ' + str(run_dir))
    bundle = read_records(paths, source_specification)
    adapter = getattr(importlib.import_module('finarch.dataset.00-input.adapters'), dataset)
    samples, intermediate, providers = [], [], {}
    for index, row in enumerate(bundle['records']):
        sample = {'id': f'test-{index + 1:04d}', **adapter(
            row['record'], row['source_metadata'], question_pointer=row['question_pointer'], raw_id=row['raw_id'])}
        samples.append(sample)
        intermediate.append({key: sample[key] for key in (
            'question', 'context', 'reference_answer', 'reference_precision')})
        providers[row['raw_id']] = {
            'source': row['source'], 'record_index': row['record_index'], 'record': row['record'],
            'question_id': row['question_pointer'], 'record_pointer': row['record_pointer']}
    validation = importlib.import_module('finarch.dataset.schemas.validation')
    registry = importlib.import_module('finarch.dataset.schemas.registry')
    validation.validate(SCHEMA_ID, samples)
    for source in bundle['sources']:
        if digest(Path(source['path']).read_bytes()) != source['sha256']:
            raise ValueError('RAW_FILE_CHANGED_DURING_CONVERSION')
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'intermediate.json', intermediate)
    write_json(output / 'input.json', samples)
    write_json(run_dir / 'provider-records.json', providers)
    definition = registry.describe(SCHEMA_ID)
    manifest = {
        'format': 'fin-arch-preparation-v1', 'families': len(samples), 'model_calls': 0,
        'sources': bundle['sources'], 'ids': [{'id': s['id'], 'raw_id': s['raw_id']} for s in samples],
        'input_schema': {k: v for k, v in definition.items() if k != 'schema'},
        'input_file_sha256': digest((output / 'input.json').read_bytes()),
        'provider_file_sha256': digest((run_dir / 'provider-records.json').read_bytes()),
        'selection_policy': 'Preserve source order; only declared literal category filters; no deduplication.',
        'exclusions': bundle['exclusions'], 'source_reader': source_specification,
    }
    write_json(run_dir / 'selection-manifest.json', manifest)
    write_json(run_dir / 'selection-log.json', bundle['exclusions'])
    write_json(run_dir / 'input-schema.json', definition)
    write_json(run_dir / 'preparation-result.json', {
        'status': 'PASS', 'families': len(samples), 'model_calls': 0,
        'manifest_sha256': digest((run_dir / 'selection-manifest.json').read_bytes())})
    try:
        loaded = importlib.import_module('finarch.dataset.90-operations.staging').PreparedInputs(output / 'input.json')
        for sample in samples:
            loaded.case(sample['id'])
    except Exception as error:
        write_json(run_dir / 'preparation-result.json', {'status': 'FAIL', 'reason': str(error), 'model_calls': 0})
        raise
    readme = (HERE / 'run-readme-template.md').read_text()
    (run_dir / 'README.md').write_text(readme.format(
        dataset=dataset, count=len(samples), excluded=len(bundle['exclusions']),
        input_path=output / 'input.json', intermediate_path=output / 'intermediate.json'), encoding='utf-8')
    return {'status': 'PASS', 'input': str(output / 'input.json'), 'records': len(samples),
            'excluded': len(bundle['exclusions']), 'run_directory': str(run_dir),
            'conversion_model_calls': 0, 'preparation_started': False}
