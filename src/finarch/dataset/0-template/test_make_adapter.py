"""Offline tests of code generation and native I/O, including shipped FinQA data."""

import ast
import copy
import importlib
import inspect
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
make = importlib.import_module('finarch.dataset.0-template.make_adapter')
runtime = importlib.import_module('finarch.dataset.0-template.runtime')
checks = importlib.import_module('finarch.dataset.0-template.checks')

SOURCE = {'records_path': '/*', 'questions_path': '/qa', 'include': []}
ADAPTER = {
    'question': {'root': 'question', 'path': '/question'},
    'answer': {'root': 'question', 'path': '/answer'},
    'context': [{'root': 'record', 'path': '/pre_text/*', 'kind': 'text'},
                {'root': 'record', 'path': '/table', 'kind': 'table'},
                {'root': 'record', 'path': '/post_text/*', 'kind': 'text'}],
    'answer_format': {'prefix': '', 'suffix': '%', 'grouping_separator': ',',
                      'parentheses_negative': False},
}


def iter_questions(document):
    for index, record in enumerate(document):
        yield {'record_pointer': f'/{index}', 'question_pointer': '/qa',
               'record': record, 'question': record['qa'], 'included': True}


def preprocess(record, question):
    parts = [{'kind': 'text', 'source_pointer': f'/pre_text/{i}', 'value': text}
             for i, text in enumerate(record['pre_text'])]
    parts.append({'kind': 'table', 'source_pointer': '/table', 'value': record['table']})
    parts.extend({'kind': 'text', 'source_pointer': f'/post_text/{i}', 'value': text}
                 for i, text in enumerate(record['post_text']))
    return {'context_parts': parts}, {
        'question': question['question'],
        'answer': displayed_number(question['answer'], suffix='%', grouping_separator=','),
    }


SOURCE['fields'] = copy.deepcopy(ADAPTER)


def code_response(stage, dataset):
    spec = {1: copy.deepcopy(SOURCE), 2: copy.deepcopy(ADAPTER),
            3: {'dataset': dataset, 'required_fields': ['dataset', 'name', 'sha256']}}[stage]
    implementation = {1: inspect.getsource(iter_questions) + '\n\n' + inspect.getsource(preprocess),
                      2: make.named_template(2, dataset),
                      3: make.named_template(3, dataset)}[stage]
    return {'status': 'ready', 'reason': 'Handwritten offline code fixture, not a model response.',
            'specification': spec, 'implementation': implementation}


def example(answer='14%'):
    return {'id': 'example', 'pre_text': ['Sales rose from 100 to 114.'],
            'table': [['Year', 'Sales'], ['2020', '100'], ['2021', '114']],
            'post_text': ['Use the percentage change.'],
            'qa': {'question': 'What is the percentage increase?', 'answer': answer,
                   'exe_ans': 0.14, 'program': 'subtract(114, 100)'}}


def wrong_adapter_code(code):
    """A candidate must not move punctuation preprocessing into the adapter."""
    return code.replace("token = question['answer']", "token = question['answer'].rstrip('%')")


class OfflineAuthor:
    description = {'provider': 'handwritten offline code fixture', 'model_calls': 0}

    def __init__(self, repair=False, reject_hash_once=False, repair_locations=False):
        self.calls = []
        self.repair, self.reject_hash_once = repair, reject_hash_once
        self.repair_locations = repair_locations

    def __call__(self, stage, payload, directory):
        self.calls.append((stage, payload))
        result = code_response(stage, payload['dataset'])
        count = sum(s == stage for s, _ in self.calls)
        if self.repair and stage == 1 and count == 1:
            result['unexpected'] = True
        if self.repair and stage == 2 and count == 1:
            result['implementation'] = result['implementation'].replace("question['question']", "question['missing_question']")
        if self.repair_locations and stage == 2 and count == 1:
            result['implementation'] = wrong_adapter_code(result['implementation'])
        if self.reject_hash_once and stage == 3 and count == 1:
            return {'status': 'needs_information', 'reason': 'The supplied sha256 value has 62 characters.',
                    'specification': None, 'implementation': None}
        return result


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='finject-adapter-test-')
        self.base = Path(self.temporary.name)
        self.raw = self.base / 'raw.json'
        self.raw.write_text(json.dumps([example(), example('9.9%'), example('1.00')]))

    def tearDown(self):
        self.temporary.cleanup()

    def code(self, stage, name='finqa_test'):
        response = code_response(stage, name)
        return make.render(stage, name, response['specification'], response['implementation'])

    def reader(self):
        return make.load_implementation(self.code(1), HERE / 'reader-check.py')['read_records']

    def adapter(self):
        return make.load_implementation(self.code(2), HERE / 'adapter-check.py')['finqa_test']

    def test_array_and_separate_objects_have_same_question_context_and_answer(self):
        paths = []
        for i, record in enumerate(json.loads(self.raw.read_text())):
            path = self.base / f'raw-{i}.json'
            path.write_text(json.dumps(record))
            paths.append(path)
        outputs = []
        for selected in ([self.raw], paths):
            bundle = checks.check_source(selected, SOURCE, self.reader())
            outputs.append(checks.check_adapter(bundle, ADAPTER, 'finqa_test', self.adapter()))
        project = lambda rows: [{k: row[k] for k in ('question', 'context', 'reference_answer', 'reference_precision')} for row in rows]
        self.assertEqual(project(outputs[0]), project(outputs[1]))
        self.assertEqual([s['reference_answer'] for s in outputs[0]], ['14', '9.9', '1.00'])
        self.assertEqual([s['reference_precision'] for s in outputs[0]], [0, 1, 2])
        self.assertEqual(set(outputs[0][0]), set(checks.PreparedSample.model_fields) - {'id'})

    def test_raw_numeric_tokens_signed_zero_and_unicode_spans(self):
        row = example('0')
        row['pre_text'][0] = 'Revenue in caf\u00e9 \u0394 rose by 10.00.'
        self.raw.write_text(json.dumps([row]).replace('"answer": "0"', '"answer": -0.00'))
        bundle = checks.check_source([self.raw], SOURCE, self.reader())
        rows = checks.check_adapter(bundle, ADAPTER, 'finqa_test', self.adapter())
        self.assertEqual(rows[0]['reference_answer'], '-0.00')
        self.assertEqual(rows[0]['reference_precision'], 2)
        self.assertTrue(rows[0]['answer_metadata']['negative'])
        self.assertEqual(bundle['records'][0]['question']['answer'].token, '-0.00')

    def test_code_must_be_real_conversion_with_explicit_native_return(self):
        wrapper = "def finqa_test(record, source, *, question_pointer='', raw_id=None):\n    runtime = __import__('finarch.dataset.0-template.runtime')\n    return runtime.adapter_record(record, source)\n"
        with self.assertRaises(checks.CheckFailed):
            make.render(2, 'finqa_test', ADAPTER, wrapper)
        with self.assertRaises(checks.CheckFailed):
            checks.check_implementation(1, 'import os\ndef iter_questions(document):\n    return []\n', 'finqa_test')
        with self.assertRaises(checks.CheckFailed):
            checks.check_implementation(2, "def finqa_test(record, source, *, question_pointer='', raw_id=None):\n    return record\n", 'finqa_test')
        self.assertNotIn('0-template', self.code(1))
        self.assertNotIn('0-template', self.code(2))
        self.assertNotIn('runtime.', self.code(2))

    def test_dropped_records_or_changed_numeric_tokens_are_rejected(self):
        real = self.reader()
        def dropped(paths):
            bundle = real(paths)
            bundle['records'].pop()
            return bundle
        with self.assertRaisesRegex(checks.CheckFailed, 'READER_COVERAGE'):
            checks.check_source([self.raw], SOURCE, dropped)
        self.raw.write_text(json.dumps([example('0')]).replace('"answer": "0"', '"answer": 1.00'))
        def rounded(paths):
            bundle = real(paths)
            bundle['records'][0]['record']['qa']['answer'] = runtime.SourceFloat('1.0')
            return bundle
        with self.assertRaisesRegex(checks.CheckFailed, 'READER_COVERAGE'):
            checks.check_source([self.raw], SOURCE, rounded)

    def test_wrong_answer_field_and_changed_question_rejected(self):
        bundle = self.reader()([self.raw])
        wrong = copy.deepcopy(ADAPTER)
        wrong['answer']['path'] = '/exe_ans'
        with self.assertRaisesRegex(checks.CheckFailed, 'DISPLAYED_ANSWER_REQUIRED'):
            checks.check_adapter(bundle, wrong, 'finqa_test', self.adapter())
        actual = self.adapter()
        def changed(record, question, source):
            sample = actual(record, question, source)
            sample['question'] = 'A different question with the correct JSON type.'
            return sample
        with self.assertRaisesRegex(checks.CheckFailed, 'QUESTION_CHANGED'):
            checks.check_adapter(bundle, ADAPTER, 'finqa_test', changed)

    def test_missing_answers_are_not_silently_dropped(self):
        self.raw.write_text(json.dumps([example(), example('N/A')]))
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_DISPLAY_ANSWER'):
            checks.check_source([self.raw], SOURCE, self.reader())

    def test_mapping_differences_and_structured_child_errors_remain_available(self):
        bundle = self.reader()([ROOT / 'data/sample/finqa-3.json'])
        adapter = self.adapter()
        def damaged(record, question, source):
            sample = adapter(record, question, source)
            sample['source_content']['paragraphs'][0]['id'] = 'wrong-id'
            sample['context_mapping']['number_status'] = 'wrong-status'
            return sample
        with self.assertRaises(checks.CheckFailed) as caught:
            checks.check_adapter(bundle, ADAPTER, 'finqa_test', damaged)
        details = caught.exception.details
        self.assertGreater(len(json.dumps(details)), 6000)
        differences = details['differences']
        self.assertEqual(differences[0], {'path': '/source_content/paragraphs/0/id',
                                        'actual': 'wrong-id', 'expected': 'paragraph-0'})
        stderr = json.dumps({'status': 'FAIL', 'message': str(caught.exception), 'details': details})
        result = make.subprocess.CompletedProcess(['candidate'], 1, '', stderr)
        with patch.object(make.subprocess, 'run', return_value=result):
            with self.assertRaises(checks.CheckFailed) as child:
                make.run_child(['candidate'], ROOT)
        self.assertEqual(make.preview(child.exception.details)['differences'], differences)

    def test_preprocessing_cannot_be_implemented_inside_adapter(self):
        code = wrong_adapter_code(self.code(2))
        with self.assertRaisesRegex(checks.CheckFailed, 'ADAPTER_MUST_USE_SHARED_TEMPLATE'):
            make.render(2, 'finqa_test', ADAPTER, code)
        signature = ast.parse(self.code(2)).body[0].args
        self.assertEqual([arg.arg for arg in signature.args], ['record', 'question', 'source'])
        self.assertFalse(signature.kwonlyargs)

    def test_stage_one_rejects_execution_answer_before_adapter_generation(self):
        response = code_response(1, 'finqa_test')
        implementation = response['implementation'].replace("question['answer']", "question['exe_ans']")
        code = make.render(1, 'finqa_test', SOURCE, implementation)
        reader = make.load_implementation(code, HERE / 'reader-check.py')['read_records']
        with self.assertRaisesRegex(checks.CheckFailed, 'READER_COVERAGE') as caught:
            checks.check_source([self.raw], SOURCE, reader)
        difference = caught.exception.details['differences'][0]
        self.assertEqual(difference['path'], '/records/0/adapter_question/answer')
        self.assertEqual(difference['actual'], '0.14')
        self.assertEqual(difference['expected'], '14')

    def test_unstructured_child_failure_keeps_process_diagnostics(self):
        result = make.subprocess.CompletedProcess(['candidate'], 1, 'partial stdout', 'unstructured stderr')
        with patch.object(make.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(checks.CheckFailed, '^GENERATED_RUN_FAILED$') as caught:
                make.run_child(['candidate'], ROOT)
        self.assertEqual(caught.exception.details, {'stdout': 'partial stdout', 'stderr': 'unstructured stderr'})

    def test_duplicate_keys_and_jsonl(self):
        self.raw.write_text('[{"question":"a","question":"b"}]')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_JSON_KEY'):
            self.reader()([self.raw])
        raw = self.base / 'raw.jsonl'
        raw.write_text(json.dumps(example()) + '\n' + json.dumps(example('9.9%')) + '\n')
        self.assertEqual(len(checks.check_source([raw], SOURCE, self.reader())['records']), 2)

    def test_nested_question_selection_and_exclusions_use_real_code(self):
        self.raw.write_text(json.dumps([{'context': 'Reported value 1.00.', 'questions': [
            {'kind': 'number', 'text': 'How much?', 'answer': '1.00'},
            {'kind': 'span', 'text': 'Which?', 'answer': 'name'}]}]))
        code = '''def iter_questions(document):
    for i, record in enumerate(document):
        for j, question in enumerate(record['questions']):
            yield {'record_pointer': f'/{i}', 'question_pointer': f'/questions/{j}',
                   'record': record, 'question': question, 'included': question['kind'] == 'number'}

def preprocess(record, question):
    return {'context_parts': [{'kind': 'text', 'source_pointer': '/context', 'value': record['context']}]}, {
        'question': question['text'], 'answer': displayed_number(question['answer'])}
'''
        spec = {'records_path': '/*', 'questions_path': '/questions/*',
                'include': [{'path': '/kind', 'equals': 'number'}],
                'fields': {**copy.deepcopy(ADAPTER),
                           'question': {'root': 'question', 'path': '/text'},
                           'context': [{'root': 'record', 'path': '/context', 'kind': 'text'}]}}
        rendered = make.render(1, 'nested', spec, code)
        reader = make.load_implementation(rendered, HERE / 'reader-check.py')['read_records']
        bundle = checks.check_source([self.raw], spec, reader)
        self.assertEqual(len(bundle['records']), 1)
        self.assertEqual(len(bundle['exclusions']), 1)

    def test_csv_reader_preserves_strings(self):
        raw = self.base / 'raw.csv'
        raw.write_text('question,context,answer\nHow much?,The value is 1.00.,1.00\n')
        code = '''def iter_questions(document):
    for i, record in enumerate(document):
        yield {'record_pointer': f'/{i}', 'question_pointer': '',
               'record': record, 'question': record, 'included': True}

def preprocess(record, question):
    return {'context_parts': [{'kind': 'text', 'source_pointer': '/context', 'value': record['context']}]}, {
        'question': question['question'], 'answer': displayed_number(question['answer'])}
'''
        spec = {'records_path': '/*', 'questions_path': '', 'include': [],
                'fields': {**copy.deepcopy(ADAPTER),
                           'context': [{'root': 'record', 'path': '/context', 'kind': 'text'}]}}
        reader = make.load_implementation(make.render(1, 'flat', spec, code), HERE / 'reader-check.py')['read_records']
        bundle = checks.check_source([raw], spec, reader)
        self.assertEqual(bundle['records'][0]['record']['answer'], '1.00')

    def test_schema_transport_and_python_hash_checks(self):
        author = make.ApiAuthor.__new__(make.ApiAuthor)
        author.settings = {'test': True}
        captured = {}
        class Transport:
            @staticmethod
            def complete_api(**kwargs):
                captured.update(kwargs)
                return json.dumps(code_response(1, 'finqa_test'))
        author.transport = Transport()
        result = author(1, {'dataset': 'finqa_test'}, self.base)
        self.assertEqual(captured['response_schema'], make.contracts.response_schema(1))
        self.assertIn('implementation', captured['response_schema']['required'])
        self.assertTrue(result['implementation'].startswith('def iter_questions'))
        bundle = self.reader()([self.raw])
        rows = checks.check_adapter(bundle, ADAPTER, 'finqa_test', self.adapter())
        payload = make.registration_payload('finqa_test', make.named_template(3, 'finqa_test'), bundle, rows)
        self.assertTrue(payload['python_validation']['all_hashes_match_original_files'])
        self.assertNotIn(bundle['sources'][0]['sha256'], json.dumps(payload))
        bundle['sources'][0]['sha256'] = bundle['sources'][0]['sha256'][:-2]
        with self.assertRaisesRegex(checks.CheckFailed, 'SOURCE_SHA256_FORMAT_INVALID'):
            make.registration_payload('finqa_test', '', bundle, rows)

    def test_schema_change_is_only_class_and_union_addition(self):
        original = (ROOT / 'src/finarch/dataset/schemas/prepared.py').read_text()
        declaration = self.code(3)
        updated = make.patched_schema(original, declaration, 'FinqaTestProvenance')
        self.assertEqual(updated.replace(declaration + '\n\n', '').replace(' | FinqaTestProvenance', ''), original)
        with self.assertRaisesRegex(checks.CheckFailed, 'PROVENANCE_CLASS'):
            make.render(3, 'finqa_test', {}, declaration.replace('{64}', '{62}'))

    def copy_repository(self):
        repository = self.base / 'repository'
        shutil.copytree(ROOT / 'src', repository / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(ROOT / 'config', repository / 'config')
        shutil.copytree(ROOT / 'data/sample', repository / 'data/sample')
        return repository

    def build(self, repository, name, output, author=None, extras=(), raw=None):
        args = make.parser().parse_args([str(raw or self.raw), '--name', name,
                                        '--output', str(repository / 'data/prepared' / output), *extras])
        with redirect_stdout(io.StringIO()):
            return make.build(args, author=author or OfflineAuthor(), repository=repository)

    def test_complete_code_generation_repairs_and_runs_without_authoring_directory(self):
        repository = self.copy_repository()
        author = OfflineAuthor(repair=True)
        raw = self.raw.read_bytes()
        result = self.build(repository, 'finqa_test', 'test', author)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual([s for s, _ in author.calls], [1, 1, 2, 2, 3])
        self.assertEqual(self.raw.read_bytes(), raw)
        output = Path(result['input']).parent
        self.assertEqual(sorted(p.name for p in output.iterdir()), ['input.json', 'intermediate.json'])
        self.assertEqual(len(result['changed_files']), 3)
        saved = json.loads((Path(result['generation_directory']) / 'stage-3/attempt-1/integration.json').read_text())
        self.assertEqual(saved['plan']['case_count'], 3)
        self.assertEqual(saved['existing_sources']['status'], 'PASS')
        self.assertFalse(saved['authoring_directory_present'])
        self.assertEqual(saved['model_calls'], 0)
        self.assertIn('contract', author.calls[0][1])
        self.assertIn('native_adapter_examples', author.calls[2][1])

    def test_standard_adapter_feedback_reaches_next_authoring_attempt(self):
        repository = self.copy_repository()
        author = OfflineAuthor(repair_locations=True)
        result = self.build(repository, 'finqa_feedback', 'feedback', author,
                            raw=ROOT / 'data/sample/finqa-3.json')
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual([s for s, _ in author.calls], [1, 2, 2, 3])
        first, retry = [payload for stage, payload in author.calls if stage == 2]
        self.assertIn("**assemble(record, 'parts')", first['template'])
        self.assertIn('extract_reference(load_raw(token))', first['template'])
        feedback = retry['validation_error']
        self.assertTrue(feedback['message'].startswith('ADAPTER_MUST_USE_SHARED_TEMPLATE'))
        self.assertIn('expected_implementation', feedback['details'])
        saved = Path(result['generation_directory']) / 'stage-2/attempt-1/check.json'
        self.assertEqual(json.loads(saved.read_text()), {'status': 'FAIL', **feedback})
        final = json.loads(Path(result['input']).read_text())
        self.assertEqual([row['reference_answer'] for row in final], ['94', '14', '9.9'])
        self.assertEqual([row['reference_precision'] for row in final], [0, 0, 1])

    def test_resume_requires_code_and_rechecks_cached_responses(self):
        repository = self.copy_repository()
        previous = repository / 'reports/run/previous/adapter-generation'
        for stage in (1, 2):
            directory = previous / f'stage-{stage}/attempt-1'
            runtime.write_json(directory / 'check.json', {'status': 'PASS', 'stage': stage})
            runtime.write_json(directory / 'response.json', code_response(stage, 'finqa_test'))
        frozen = {path: path.read_bytes() for path in previous.rglob('*') if path.is_file()}
        author = OfflineAuthor(reject_hash_once=True)
        result = self.build(repository, 'finqa_test', 'resumed', author, ['--resume', str(previous)])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual([s for s, _ in author.calls], [3, 3])
        for path, content in frozen.items():
            self.assertEqual(path.read_bytes(), content)
        response_path = previous / 'stage-1/attempt-1/response.json'
        response = json.loads(response_path.read_text())
        response.pop('implementation')
        runtime.write_json(response_path, response)
        with self.assertRaisesRegex(ValueError, 'RESUME_REQUIRES_PYTHON_CODE'):
            make.resume_responses(previous)

    def test_raw_only_reader_cannot_resume_into_preprocessed_contract(self):
        previous = self.base / 'adapter-generation'
        directory = previous / 'stage-1/attempt-1'
        response = code_response(1, 'finqa_test')
        response['specification'].pop('fields')
        response['implementation'] = inspect.getsource(iter_questions)
        runtime.write_json(directory / 'check.json', {'status': 'PASS'})
        runtime.write_json(directory / 'response.json', response)
        with self.assertRaisesRegex(ValueError, 'RESUME_REQUIRES_PREPROCESSING_CONTRACT'):
            make.resume_responses(previous)

    def test_missing_information_and_install_failure_preserve_code(self):
        repository = self.copy_repository()
        originals = make.snapshot_targets(repository, 'ambiguous')
        def author(stage, payload, directory):
            return {'status': 'needs_information', 'reason': 'Two conflicting displayed answers.',
                    'specification': None, 'implementation': None}
        with self.assertRaises(make.contracts.NeedsInformation):
            self.build(repository, 'ambiguous', 'ambiguous', author)
        for path, data in originals.items():
            self.assertEqual(path.read_bytes() if path.exists() else None, data)
        codes = {stage: self.code(stage, 'rollback') for stage in (1, 2, 3)}
        originals = make.snapshot_targets(repository, 'rollback')
        generated = make.build_changes(repository, 'rollback', originals, codes)
        directory = repository / 'reports/run/rollback/adapter-generation'
        directory.mkdir(parents=True)
        with patch.object(make, 'run_child', side_effect=ValueError('forced failure')):
            with self.assertRaisesRegex(ValueError, 'forced failure'):
                make.install(repository, 'rollback', originals, generated, [self.raw], repository / 'data/prepared/rollback', directory)
        for path, data in originals.items():
            self.assertEqual(path.read_bytes() if path.exists() else None, data)

    def test_explicit_replacement_checks_prior_hashes_and_retains_native_functions(self):
        repository = self.copy_repository()
        first = self.build(repository, 'replace_test', 'first')
        before = (repository / 'src/finarch/dataset/00-input/adapters.py').read_text()
        second = self.build(repository, 'replace_test', 'second', extras=['--replace-from', first['generation_directory']])
        self.assertEqual(second['status'], 'PASS')
        _, baseline = make.originals_for_build(repository, 'replace_test', second['generation_directory'])
        self.assertIsNone(baseline[make.target_files(repository, 'replace_test')[0]])
        self.assertNotIn('def replace_test(', baseline[make.target_files(repository, 'replace_test')[1]].decode())
        self.assertEqual(make.native_adapter_examples(before), make.native_adapter_examples(
            (repository / 'src/finarch/dataset/00-input/adapters.py').read_text()))
        path = repository / 'src/finarch/dataset/00-input/replace_test.py'
        path.write_text(path.read_text() + '\n# A user edit.\n')
        with self.assertRaisesRegex(ValueError, 'GENERATED_FILE_CHANGED'):
            make.originals_for_build(repository, 'replace_test', second['generation_directory'])

    def test_real_finqa_three_records_to_native_input(self):
        raw = Path(os.environ.get('FINJECT_TEST_RAW_FILE', ROOT / 'data/sample/finqa-3.json')).resolve()
        original = raw.read_bytes()
        repository = self.copy_repository()
        result = self.build(repository, 'finqa_downloaded', 'real-finqa', raw=raw)
        final = json.loads(Path(result['input']).read_text())
        self.assertEqual(len(final), 3)
        self.assertEqual([row['reference_answer'] for row in final], ['94', '14', '9.9'])
        self.assertEqual([row['reference_precision'] for row in final], [0, 0, 1])
        self.assertEqual(set(final[0]), set(checks.PreparedSample.model_fields))
        self.assertEqual(raw.read_bytes(), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
