"""Independent output checks. Model responses cannot edit these checks."""

import ast
import importlib
import re
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from jsonschema import Draft202012Validator
from pydantic import Field
from finarch.dataset.schemas.common import StrictModel, Text
from finarch.dataset.schemas.prepared import PreparedSample

contracts = importlib.import_module('finarch.dataset.0-template.contracts')
runtime = importlib.import_module('finarch.dataset.0-template.runtime')


class CheckFailed(ValueError):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


class CandidateProvenance(StrictModel):
    dataset: Text
    name: Text
    sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class CandidateSample(PreparedSample):
    # Only the not-yet-registered provenance is replaced during stage 2.
    # All common fields and both existing validators are inherited unchanged.
    provenance: CandidateProvenance


def exact_value(value):
    """Compare original numeric tokens as well as JSON values."""
    if isinstance(value, runtime.SourceFloat):
        return ('source-float', value.token)
    if isinstance(value, dict):
        return ('object', [(key, exact_value(value[key])) for key in sorted(value)])
    if isinstance(value, list):
        return ('array', [exact_value(item) for item in value])
    return (type(value).__name__, value)


def first_difference(actual, expected, path):
    """Locate one exact mismatch without returning an entire context mapping."""
    if actual == expected:
        return None
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in sorted(actual.keys() | expected.keys()):
            pointer = path + '/' + key.replace('~', '~0').replace('/', '~1')
            if key not in actual or key not in expected:
                return {'path': pointer, 'actual': actual.get(key), 'expected': expected.get(key),
                        'actual_present': key in actual, 'expected_present': key in expected}
            difference = first_difference(actual[key], expected[key], pointer)
            if difference is not None:
                return difference
    elif isinstance(actual, list) and isinstance(expected, list):
        for index, (left, right) in enumerate(zip(actual, expected)):
            difference = first_difference(left, right, path + '/' + str(index))
            if difference is not None:
                return difference
        if len(actual) != len(expected):
            return {'path': path, 'comparison': 'array_length',
                    'actual': len(actual), 'expected': len(expected)}
    return {'path': path, 'actual': actual, 'expected': expected}


def check_implementation(stage, code, dataset, expected_class=None):
    """Bound code to pure source conversion; this is not an OS sandbox."""
    tree = ast.parse(code)
    if re.search(r'__[A-Z][A-Z_]*__', code) or '0-template' in code:
        raise CheckFailed('UNRESOLVED_TEMPLATE_OR_AUTHORING_RUNTIME_DEPENDENCY')
    body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str))]
    if stage == 3:
        expected = ast.parse(expected_class)
        for module in (tree, expected):
            for node in ast.walk(module):
                if isinstance(node, (ast.Module, ast.ClassDef)):
                    node.body = [part for part in node.body if not (
                        isinstance(part, ast.Expr) and isinstance(part.value, ast.Constant)
                        and isinstance(part.value.value, str))]
        if ast.dump(tree, include_attributes=False) != ast.dump(expected, include_attributes=False):
            raise CheckFailed('PROVENANCE_CLASS_MUST_MATCH_FIXED_CONTRACT')
        return
    signatures = {'iter_questions': ['document'], 'preprocess': ['record', 'question']} if stage == 1 else {
        dataset: ['record', 'question', 'source']}
    if (len(body) != len(signatures) or any(not isinstance(node, ast.FunctionDef) for node in body)
            or {node.name for node in body} != set(signatures)):
        raise CheckFailed('REQUIRED_FUNCTIONS: ' + ', '.join(signatures))
    for function in body:
        if ([arg.arg for arg in function.args.args] != signatures[function.name]
                or function.args.kwonlyargs or function.args.posonlyargs or function.args.vararg
                or function.args.kwarg or function.args.defaults):
            raise CheckFailed('FUNCTION_SIGNATURE_MUST_MATCH_CONTRACT: ' + function.name)
    allowed_imports = {'json', 're', 'decimal'}
    if stage == 2:
        allowed_imports.add('finarch.shared.reference')
    blocked_names = {'eval', 'exec', 'compile', 'open', 'globals', 'locals', 'vars',
                     'getattr', 'setattr', 'delattr', 'input', 'breakpoint',
                     'help', 'exit', 'quit', 'object', 'memoryview'}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.ClassDef, ast.AsyncFunctionDef)):
            raise CheckFailed('UNSUPPORTED_CODE_CONSTRUCT: ' + type(node).__name__)
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise CheckFailed('DECORATORS_NOT_ALLOWED')
        if isinstance(node, ast.Name) and (node.id in blocked_names or node.id.startswith('__')):
            raise CheckFailed('DYNAMIC_OR_EXTERNAL_OPERATION_NOT_ALLOWED: ' + node.id)
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise CheckFailed('PRIVATE_ATTRIBUTE_ACCESS_NOT_ALLOWED')
        if isinstance(node, ast.Import) and any(alias.name not in allowed_imports for alias in node.names):
            raise CheckFailed('IMPORT_NOT_ALLOWED')
        if isinstance(node, ast.ImportFrom):
            if node.level or node.module not in allowed_imports or any(
                    alias.name == '*' or alias.name.startswith('_') for alias in node.names):
                raise CheckFailed('IMPORT_NOT_ALLOWED')
            if node.module == 'finarch.shared.reference' and any(alias.name not in {
                    'SourceFloat', 'Reference', 'load_raw', 'extract_reference'} for alias in node.names):
                raise CheckFailed('REFERENCE_IMPORT_NOT_ALLOWED')
    if stage == 2:
        template = (Path(__file__).parent / 'template2_adapter.py').read_text()
        template = template.replace('__DATASET__', dataset).replace('__DATASET_LITERAL__', repr(dataset))
        expected = ast.parse(template)
        for module in (tree, expected):
            for node in ast.walk(module):
                if isinstance(node, (ast.Module, ast.FunctionDef)):
                    node.body = [part for part in node.body if not (
                        isinstance(part, ast.Expr) and isinstance(part.value, ast.Constant)
                        and isinstance(part.value.value, str))]
        if ast.dump(tree, include_attributes=False) != ast.dump(expected, include_attributes=False):
            raise CheckFailed('ADAPTER_MUST_USE_SHARED_TEMPLATE: preprocessing belongs in the source file',
                              {'expected_implementation': template})


def check_source(paths, specification, reader):
    Draft202012Validator(contracts.PREPROCESS_SOURCE).validate(specification)
    first, second = reader(paths), reader(paths)
    if exact_value(first) != exact_value(second):
        raise CheckFailed('NONDETERMINISTIC_SOURCE_READER')
    expected = runtime.preprocessed_records(paths, specification)
    if set(first) != {'records', 'sources', 'exclusions'}:
        raise CheckFailed('READER_BUNDLE_FIELDS_MISMATCH')
    if exact_value(first['records']) != exact_value(expected['records']):
        difference = first_difference(first['records'], expected['records'], '/records')
        raise CheckFailed('READER_COVERAGE_ORDER_OR_ORIGINAL_RECORD_MISMATCH',
                          {'differences': [difference] if difference else []})
    if first['sources'] != expected['sources']:
        raise CheckFailed('READER_SOURCE_METADATA_MISMATCH')
    locations = lambda rows: [(row['source'], row['record_pointer'], row['question_pointer'],
                                row['reason']) for row in rows]
    if locations(first['exclusions']) != locations(expected['exclusions']):
        raise CheckFailed('READER_EXCLUSION_COVERAGE_MISMATCH')
    documents = {doc['name']: doc for doc in runtime.load_documents(paths)}
    seen = set()
    for row in first['records']:
        key = (row['source'], row['record_pointer'], row['question_pointer'])
        if key in seen:
            raise CheckFailed('DUPLICATE_READER_LOCATION')
        seen.add(key)
        doc = documents[row['source']]
        original = doc['document'][0] if doc['wrapped'] else doc['document']
        original_record = runtime.at(original, row['record_pointer'])
        if exact_value(original_record) != exact_value(row['record']):
            raise CheckFailed('READER_CHANGED_ORIGINAL_RECORD')
        if exact_value(runtime.at(original_record, row['question_pointer'])) != exact_value(row['question']):
            raise CheckFailed('READER_QUESTION_LOCATION_MISMATCH')
    return first


def check_sample(sample, row, specification, dataset):
    CandidateSample.model_validate({'id': 'check-0001', **sample}, strict=True)
    if set(sample) != set(PreparedSample.model_fields) - {'id'}:
        raise CheckFailed('ADAPTER_FIELDS_MISMATCH')
    if sample['raw_id'] != row['raw_id']:
        raise CheckFailed('RAW_ID_CHANGED')
    if sample['provenance'] != {'dataset': dataset, **row['source_metadata']}:
        raise CheckFailed('SOURCE_METADATA_CHANGED')
    question_path = runtime.field_pointer(specification['question'], row['question_pointer'])
    answer_path = runtime.field_pointer(specification['answer'], row['question_pointer'])
    if question_path == answer_path:
        raise CheckFailed('QUESTION_AND_ANSWER_MUST_USE_DIFFERENT_FIELDS')
    forbidden = {'exe_ans', 'python_solution', 'program', 'gold_inds'}
    if set(runtime.tokens(answer_path)) & forbidden:
        raise CheckFailed('DISPLAYED_ANSWER_REQUIRED_NOT_EXECUTION_OR_SOLUTION')
    if sample['question'] != runtime.at(row['record'], question_path):
        raise CheckFailed('QUESTION_CHANGED')
    original_answer = runtime.at(row['record'], answer_path)
    token = runtime.answer_token(original_answer, specification['answer_format'])
    expected = Decimal(token)
    actual = Decimal(sample['reference_answer'])
    if actual != expected or actual.is_signed() != expected.is_signed():
        raise CheckFailed('DISPLAYED_ANSWER_VALUE_CHANGED')
    if sample['reference_precision'] != max(0, -expected.as_tuple().exponent):
        raise CheckFailed('DISPLAYED_ANSWER_PRECISION_CHANGED')
    expected_type = 'float' if any(marker in token.lower() for marker in ('.', 'e')) else 'integer'
    if sample['reference_answer_type'] != expected_type:
        raise CheckFailed('RAW_NUMERIC_TYPE_CHANGED')
    if sample['answer_metadata']['scale'] is not None:
        raise CheckFailed('ADAPTER_MUST_NOT_INFER_SCALE')
    locations = sample['source_content']['paragraphs'] + [
        cell for table in sample['source_content']['tables'] for cell in table['cells']]
    declared = []
    expected_context = []
    for part in specification['context']:
        for pointer, original in runtime.select(row['record'], runtime.field_pointer(part, row['question_pointer'])):
            if part['kind'] == 'text':
                declared.append(pointer)
                expected_context.append(runtime.literal_text(original))
            else:
                declared.extend(f'{pointer}/{r}/{c}' for r, cells in enumerate(original) for c in range(len(cells)))
                expected_context.append('\n'.join(' | '.join(runtime.literal_text(v) for v in cells) for cells in original))
    if sample['context'] != '\n\n'.join(expected_context):
        raise CheckFailed('CONTEXT_ORDER_OR_CONTENT_CHANGED')
    actual_pointers = [item['source_pointer'] for item in sample['context_mapping']['segments']]
    if actual_pointers != declared or len(set(declared)) != len(declared):
        raise CheckFailed('MISSING_OR_DUPLICATED_CONTEXT_FRAGMENT')
    for item in locations:
        pointer = item['source_pointer']
        if pointer in (question_path, answer_path) or set(runtime.tokens(pointer)) & forbidden:
            raise CheckFailed('ANSWER_OR_SOLUTION_LEAKED_INTO_CONTEXT')
        source = runtime.at(row['record'], pointer)
        if item['text'] != runtime.literal_text(source):
            raise CheckFailed('CONTEXT_FRAGMENT_CHANGED: ' + pointer)
    expected_locations = runtime.assemble_context(row['record'], row['question_pointer'], specification['context'])
    differences = []
    for key in ('source_content', 'context_mapping'):
        # Report one mismatch per component so repeated IDs do not hide a
        # different problem in table cells, segments or fixed metadata.
        for field, expected in expected_locations[key].items():
            difference = first_difference(sample[key][field], expected, f'/{key}/{field}')
            if difference is not None:
                differences.append(difference)
    if differences:
        key = differences[0]['path'].split('/')[1]
        raise CheckFailed('CONTEXT_LOCATIONS_OR_NUMBER_SPANS_CHANGED: ' + key,
                          {'differences': differences})
    return sample


def check_adapter(bundle, specification, dataset, adapter):
    Draft202012Validator(contracts.ADAPTER).validate(specification)
    samples = []
    for row in bundle['records']:
        try:
            arguments = (row['adapter_record'], row['adapter_question'], row['source_metadata'])
            first = adapter(*arguments)
            second = adapter(*arguments)
            if runtime.json_bytes(first) != runtime.json_bytes(second):
                raise CheckFailed('NONDETERMINISTIC_ADAPTER')
            check_sample(first, row, specification, dataset)
            samples.append(first)
        except Exception as error:
            details = dict(getattr(error, 'details', {}))
            details.update({'source': row['source'],
                'record_pointer': row['record_pointer'], 'question_pointer': row['question_pointer'],
                'record': row['record']})
            raise CheckFailed(str(error), details) from error
    return samples


def check_provenance(specification, dataset):
    Draft202012Validator(contracts.PROVENANCE).validate(specification)
    if specification != {'dataset': dataset, 'required_fields': ['dataset', 'name', 'sha256']}:
        raise CheckFailed('PROVENANCE_CONTRACT_MUST_REMAIN_FIXED')


def check_source_metadata(bundle, samples, dataset):
    """Check actual file hashes in Python; never ask an LLM to count hex digits."""
    if not bundle['sources'] or len(samples) != len(bundle['records']):
        raise CheckFailed('SOURCE_METADATA_INPUTS_INCOMPLETE')
    sources = {source['name']: source for source in bundle['sources']}
    if len(sources) != len(bundle['sources']):
        raise CheckFailed('DUPLICATE_SOURCE_NAME')
    for source in sources.values():
        value = source.get('sha256')
        if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None:
            raise CheckFailed('SOURCE_SHA256_FORMAT_INVALID')
        actual = runtime.digest(Path(source['path']).read_bytes())
        if actual != value:
            raise CheckFailed('RAW_FILE_CHANGED_DURING_AUTHORING: ' + source['name'])
    for row, sample in zip(bundle['records'], samples):
        source = sources[row['source']]
        expected = {'dataset': dataset, 'name': source['name'], 'sha256': source['sha256']}
        if sample['raw_id'] != row['raw_id'] or sample['provenance'] != expected:
            raise CheckFailed('SOURCE_METADATA_CHANGED')
    return {'status': 'PASS', 'validator': 'Python hashlib.sha256 and exact file comparison',
            'source_count': len(sources), 'record_count': len(samples),
            'required_fields': ['dataset', 'name', 'sha256'],
            'sha256_hex_length': 64, 'all_hashes_match_original_files': True}


def main():
    """Execute candidate conversion checks in a timed child, without API keys."""
    import json
    import sys
    request = json.loads(Path(sys.argv[1]).read_text())
    native = importlib.import_module('finarch.dataset.00-input.adapters')
    namespace = {'__name__': 'candidate_check', '__file__': request['target_path'],
                 'assemble': native.assemble, 'extract_reference': native.extract_reference, 'Decimal': Decimal}
    try:
        code = Path(request['code_path']).read_text()
        exec(compile(code, request['target_path'], 'exec'), namespace)
        if request['stage'] == 1:
            bundle = check_source(request['paths'], request['specification'], namespace['read_records'])
            result = {'status': 'PASS', 'records': len(bundle['records'])}
        else:
            if request['specification'] != request['source_specification']['fields']:
                raise CheckFailed('ADAPTER_DECLARATION_MUST_MATCH_CHECKED_PREPROCESSING')
            bundle = runtime.preprocessed_records(request['paths'], request['source_specification'])
            rows = check_adapter(bundle, request['specification'], request['dataset'], namespace[request['dataset']])
            result = {'status': 'PASS', 'records': len(rows)}
        print(json.dumps(result))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'message': str(error),
                          'details': getattr(error, 'details', {})}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
