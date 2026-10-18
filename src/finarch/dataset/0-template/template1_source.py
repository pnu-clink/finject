"""Deterministic source reader and native input runner for __DATASET__."""

import argparse
import csv
import hashlib
import importlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from finarch.shared.reference import SourceFloat, load_raw

DATASET = __DATASET_LITERAL__
SCHEMA_ID = '01-preparation.01-source.prepared-input'
# This records the checked selection; the implementation below reads the source.
SOURCE_SELECTION = __SOURCE_SPEC__
RUN_README = __RUN_README__


__SOURCE_IMPLEMENTATION__


def displayed_number(value, *, prefix='', suffix='', grouping_separator='', parentheses_negative=False):
    """Preprocess literal answer punctuation; never rescale or infer meaning."""
    if isinstance(value, SourceFloat):
        return value.token
    if type(value) is int:
        return str(value)
    if not isinstance(value, str):
        raise ValueError('NUMERIC_DISPLAY_ANSWER_REQUIRED')
    token = value.strip()
    negative = parentheses_negative and token.startswith('(') and token.endswith(')')
    if negative:
        token = token[1:-1].strip()
    if prefix and token.startswith(prefix):
        token = token[len(prefix):].strip()
    if suffix and token.endswith(suffix):
        token = token[:-len(suffix)].strip()
    if grouping_separator and ',' in token:
        if not re.fullmatch(r'-?\d{1,3}(?:,\d{3})+(?:\.\d+)?', token):
            raise ValueError('INVALID_GROUPED_ANSWER: ' + repr(value))
        token = token.replace(',', '')
    if negative:
        if token.startswith('-'):
            raise ValueError('DOUBLE_NEGATIVE_ANSWER')
        token = '-' + token
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', token):
        raise ValueError('UNSUPPORTED_DISPLAY_ANSWER: ' + repr(value))
    return token


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def digest(value):
    return hashlib.sha256(value).hexdigest()


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


def read_records(paths):
    """Return unchanged original records, source locations and actual file hashes."""
    documents = load_documents(paths)
    records, exclusions = [], []
    for doc in documents:
        for selected in iter_questions(doc['document']):
            if set(selected) != {'record_pointer', 'question_pointer', 'record', 'question', 'included'}:
                raise ValueError('SOURCE_SELECTION_FIELDS_MISMATCH')
            if type(selected['included']) is not bool:
                raise ValueError('SOURCE_SELECTION_INCLUDED_MUST_BE_BOOL')
            record, question = selected['record'], selected['question']
            if not isinstance(record, dict) or not isinstance(question, dict):
                raise ValueError('SOURCE_RECORD_AND_QUESTION_MUST_BE_OBJECTS')
            original_pointer = selected['record_pointer']
            question_pointer = selected['question_pointer']
            if doc['wrapped']:
                if not (original_pointer == '/0' or original_pointer.startswith('/0/')):
                    raise ValueError('WRAPPED_ROOT_LOCATION_INVALID')
                original_pointer = original_pointer[2:]
            origin = {'source': doc['name'], 'record_pointer': original_pointer,
                      'question_pointer': question_pointer}
            if not selected['included']:
                exclusions.append({**origin, 'reason': 'EXPLICIT_SOURCE_CATEGORY_FILTER'})
                continue
            location = json.dumps(origin, sort_keys=True, ensure_ascii=False)
            raw_id = 'raw-' + digest((doc['sha256'] + location).encode())[:24]
            adapter_record, adapter_question = preprocess(record, question)
            if set(adapter_record) != {'context_parts'} or set(adapter_question) != {'question', 'answer'}:
                raise ValueError('PREPROCESS_FIELDS_MISMATCH')
            adapter_question = {'uid': raw_id, **adapter_question}
            index = int(original_pointer[1:]) if re.fullmatch(r'/\d+', original_pointer) else None
            records.append({**origin, 'raw_id': raw_id, 'record': record, 'question': question,
                            'adapter_record': adapter_record, 'adapter_question': adapter_question,
                            'record_index': index,
                            'source_metadata': {'name': doc['name'], 'sha256': doc['sha256']}})
    if not records:
        raise ValueError('NO_SELECTED_QUESTIONS')
    if len({row['raw_id'] for row in records}) != len(records):
        raise ValueError('DUPLICATE_SOURCE_LOCATION')
    sources = [{key: doc[key] for key in ('name', 'path', 'sha256')} for doc in documents]
    return {'records': records, 'sources': sources, 'exclusions': exclusions}


def input_run_directory(output):
    helper = importlib.import_module('finarch.dataset.shared.adapter')
    return helper.input_run_directory(output)


def new_output(dataset):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    return ROOT / 'data' / 'prepared' / f'{dataset}-{stamp}-{uuid4().hex[:6]}'


def prepare(paths, output=None):
    """Write the native bundle; existing code performs schema/loader validation."""
    dataset = DATASET
    output = Path(output).expanduser().resolve() if output else new_output(dataset)
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS: ' + str(output))
    run_dir = input_run_directory(output)
    if (run_dir / 'preparation-result.json').exists():
        raise ValueError('RUN_EVIDENCE_ALREADY_EXISTS: ' + str(run_dir))
    bundle = read_records(paths)
    adapter = getattr(importlib.import_module('finarch.dataset.00-input.adapters'), dataset)
    samples, intermediate, providers = [], [], {}
    for index, row in enumerate(bundle['records']):
        sample = {'id': f'test-{index + 1:04d}', **adapter(
            row['adapter_record'], row['adapter_question'], row['source_metadata'])}
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
        'exclusions': bundle['exclusions'], 'source_reader': SOURCE_SELECTION,
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
    readme = RUN_README
    (run_dir / 'README.md').write_text(readme.format(
        dataset=dataset, count=len(samples), excluded=len(bundle['exclusions']),
        input_path=output / 'input.json', intermediate_path=output / 'intermediate.json'), encoding='utf-8')
    return {'status': 'PASS', 'input': str(output / 'input.json'), 'records': len(samples),
            'excluded': len(bundle['exclusions']), 'run_directory': str(run_dir),
            'conversion_model_calls': 0, 'preparation_started': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', help='Raw files with the same source layout')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.paths, args.output), indent=2))
