"""Offline adapter integration using real source records and explicit edge cases."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from finarch.dataset.shared.adapter import make_record, RawSource, input_run_directory
from finarch.shared.reference import load_raw

custom = importlib.import_module('finarch.dataset.00-input.custom')
PreparedInputs = importlib.import_module('finarch.dataset.90-operations.staging').PreparedInputs
build = importlib.import_module('finarch.dataset.00-input.build')
ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = ROOT / 'src/finarch/dataset/0-template/adapter_template.py'
FINANCE = ROOT / 'data/sample/finance-easy.json'
TATQA = ROOT / 'data/sample/tatqa-dev.json'


class CustomInputChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='finject-adapter-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def convert(self, name='output', *, adapter=TEMPLATE, inputs=None):
        output = self.root / name
        result = custom.prepare(adapter, inputs or [FINANCE], output, name='reviewer-example')
        return output, result

    def adapter(self, text):
        path = self.root / 'custom_adapter.py'
        path.write_text(text)
        return path

    def read(self, path):
        return json.loads(path.read_text())

    def test_real_sample_round_trip_and_pot_projection(self):
        before = FINANCE.read_bytes()
        output, result = self.convert()
        self.assertEqual((result['status'], result['families'], result['model_calls']), ('PASS', 1, 0))
        raw = load_raw(before)[0]
        middle = self.read(output / 'intermediate.json')[0]
        self.assertEqual(set(middle), {'question', 'context', 'reference_answer', 'reference_precision'})
        self.assertEqual((middle['question'], middle['context'], middle['reference_answer']),
                         (raw['question'], raw['context'], str(raw['ground_truth'])))
        case = PreparedInputs(output / 'input.json').case('test-0001')
        self.assertEqual(case['provider_record']['record'], raw)
        sample = case['sample']
        self.assertIsNone(sample['answer_metadata']['scale'])
        self.assertEqual(sample['provenance']['dataset'], 'custom')
        self.assertNotIn('level', sample['provenance'])
        request = importlib.import_module('finarch.dataset.01-preparation.03-calculation.stage').pp01_build_pot_request(sample)
        self.assertNotIn('reference_answer', request)
        self.assertEqual(request['question'], raw['question'])
        self.assertTrue(request['provider_record']['numeric_index'])
        self.assertEqual(FINANCE.read_bytes(), before)

    def test_repeated_conversion_is_byte_identical(self):
        first, _ = self.convert('first')
        second, _ = self.convert('second')
        for filename in ('intermediate.json', 'input.json'):
            self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())
        self.assertEqual((input_run_directory(first) / 'provider-records.json').read_bytes(),
                         (input_run_directory(second) / 'provider-records.json').read_bytes())

    def test_data_only_contains_two_files_and_evidence_is_in_run(self):
        output, result = self.convert('data/prepared/reviewer-example')
        run = (self.root / 'reports/run/reviewer-example/00-input').resolve()
        self.assertEqual(Path(result['run']), run)
        self.assertEqual({p.name for p in output.iterdir()}, {'intermediate.json', 'input.json'})
        self.assertEqual({p.name for p in run.iterdir()}, {'provider-records.json',
            'selection-manifest.json', 'preparation-result.json', 'preparation-start.json',
            'selection-log.json', 'README.md'})
        self.assertEqual(len(PreparedInputs(output / 'input.json').samples), 1)
        for name in ('selection-manifest.json', 'provider-records.json', 'preparation-result.json'):
            path = run / name
            before = path.read_bytes()
            path.write_bytes(before + b'\n')
            if name == 'preparation-result.json':
                path.write_text(json.dumps({**json.loads(before), 'status': 'FAIL'}))
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                PreparedInputs(output / 'input.json')
            path.write_bytes(before)

    def test_existing_run_is_untouched(self):
        output = self.root / 'data/prepared/existing'
        run = input_run_directory(output)
        run.mkdir(parents=True)
        marker = run / 'marker.txt'
        marker.write_text('Existing run must not be overwritten.')
        with self.assertRaises(FileExistsError):
            self.convert('data/prepared/existing')
        self.assertFalse(output.exists())
        self.assertEqual(marker.read_text(), 'Existing run must not be overwritten.')

    def test_custom_schema_rejects_injected_scale(self):
        output, _ = self.convert()
        samples = self.read(output / 'input.json')
        samples[0]['answer_metadata']['scale'] = 'billion'
        with self.assertRaises(ValueError):
            custom.validate(custom.SCHEMA, samples)

    def test_answer_tokens_and_question_instructions_are_separate(self):
        for token, precision in [('10.00', 2), ('0.125', 3), ('10', 0),
                                 ('-0.00', 2), ('1e2', 0)]:
            with self.subTest(token=token):
                item = make_record(question='Report a percentage to two decimal places.',
                                   context='Source text.', reference_answer=load_raw(token), origins=[])
                self.assertEqual((item.data.reference_precision, item.data.reference_answer),
                                 (precision, token))
                self.assertNotIn('reference_answer_type', item.data.model_dump())
        self.assertEqual(make_record(question='Q', context='C', reference_answer='10.00',
                                     origins=[]).data.reference_answer, '10.00')
        for value in (True, 10.0, '1,234', '12%', [], None, 'NaN'):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                make_record(question='Q', context='C', reference_answer=value, origins=[])

    def test_builder_recovers_numeric_type_from_preserved_token(self):
        for index, (token, answer_type) in enumerate([('100', 'integer'), ('1e2', 'float')]):
            with self.subTest(token=token):
                text = TEMPLATE.read_text().replace("reference_answer=raw['ground_truth']",
                                                    f'reference_answer={token!r}')
                output, _ = self.convert(f'token-{index}', adapter=self.adapter(text))
                middle = self.read(output / 'intermediate.json')[0]
                sample = PreparedInputs(output / 'input.json').case('test-0001')['sample']
                self.assertEqual(middle['reference_answer'], token)
                self.assertEqual(middle['reference_precision'], 0)
                self.assertNotIn('reference_answer_type', middle)
                self.assertEqual(sample['reference_answer'], '100')
                self.assertEqual(sample['reference_answer_type'], answer_type)

    def test_join_two_files_keeps_both_origins(self):
        raw = self.read(FINANCE)[0]
        questions, documents = self.root / 'questions.json', self.root / 'documents.json'
        questions.write_text(json.dumps([{'key': raw['question_id'], 'question': raw['question'], 'gold': raw['ground_truth']}]))
        documents.write_text(json.dumps({raw['question_id']: {'main': raw['context']}}))
        adapter = self.adapter('''from finarch.dataset.shared.adapter import make_record
def adapt(sources):
    questions, documents = sources
    docs = documents.json()
    for index, q in enumerate(questions.json()):
        d = docs[q['key']]
        yield make_record(question=q['question'], context=d['main'], reference_answer=q['gold'], origins=[
            questions.origin(q, locator=f'/{index}', index=index),
            documents.origin(d, locator='/' + q['key'])])
''')
        output, _ = self.convert(adapter=adapter, inputs=[questions, documents])
        case = PreparedInputs(output / 'input.json').case('test-0001')
        self.assertEqual(case['sample']['context'], raw['context'])
        self.assertEqual(len(case['provider_record']['origins']), 2)
        self.assertEqual(len(case['sample']['provenance']['sources']), 2)
        documents.write_text(documents.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_SOURCE_HASH'):
            PreparedInputs(output / 'input.json')

    def test_tatqa_shared_context_keeps_distinct_questions_and_exclusions(self):
        adapter = self.adapter('''from importlib import import_module
from finarch.dataset.shared.adapter import make_record, exclude
assemble = import_module('finarch.dataset.00-input.content').assemble
def adapt(sources):
    for source in sources:
        for index, doc in enumerate(source.json()):
            for qi, q in enumerate(doc['questions']):
                origins = [source.origin(doc, locator=f'/{index}', index=index),
                           source.origin(q, locator=f'/{index}/questions/{qi}')]
                if q['answer_type'] != 'arithmetic':
                    yield exclude('Only arithmetic questions are supported.', origins=origins)
                    continue
                yield make_record(question=q['question'], context=assemble(doc, 'tatqa')['context'],
                                  reference_answer=q['answer'], origins=origins)
''')
        output, result = self.convert(adapter=adapter, inputs=[TATQA])
        questions = [q for doc in self.read(TATQA) for q in doc['questions']]
        expected = sum(q['answer_type'] == 'arithmetic' for q in questions)
        self.assertEqual(result['families'], expected)
        self.assertEqual(result['excluded'], len(questions) - expected)
        samples = self.read(output / 'input.json')
        self.assertEqual(len({s['context'] for s in samples}), 1)
        self.assertTrue(all(s['answer_metadata']['scale'] is None for s in samples))
        PreparedInputs(output / 'input.json')

    def test_duplicate_source_question_fails_visibly(self):
        text = TEMPLATE.read_text().replace('for index, raw in enumerate(records):',
                                           'for index, raw in [(0, records[0]), (0, records[0])]:')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_SOURCE_QUESTION'):
            self.convert(adapter=self.adapter(text))
        self.assertEqual(self.read(input_run_directory(self.root / 'output') / 'preparation-result.json')['status'], 'FAIL')

    def test_adapter_error_and_empty_output_cannot_start_pipeline(self):
        for name, text in [('error', 'def adapt(sources):\n    raise ValueError("bad mapping")\n'),
                           ('empty', 'def adapt(sources):\n    return []\n')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.convert(name, adapter=self.adapter(text))
            self.assertEqual(self.read(input_run_directory(self.root / name) / 'preparation-result.json')['status'], 'FAIL')
            with self.assertRaisesRegex(ValueError, 'PREPARATION_NOT_COMPLETE'):
                PreparedInputs(self.root / name / 'input.json')

    def test_missing_origin_is_rejected(self):
        adapter = self.adapter(TEMPLATE.read_text().replace('origins=[origin]', 'origins=[]'))
        with self.assertRaisesRegex(ValueError, 'VALID_SOURCE_ORIGINS_REQUIRED'):
            self.convert(adapter=adapter)

    def test_intermediate_tampering_is_rejected(self):
        output, _ = self.convert()
        path = output / 'intermediate.json'
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'INTERMEDIATE_HASH_MISMATCH'):
            PreparedInputs(output / 'input.json')

    def test_existing_output_is_untouched(self):
        output, _ = self.convert()
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        with self.assertRaises(FileExistsError):
            self.convert()
        self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_legacy_sample_still_loads(self):
        for name in ('legacy', 'legacy-data/data', 'legacy-prepared/data/prepared'):
            with self.subTest(path=name):
                output = self.root / name
                build.prepare(ROOT / 'data/sample/source-catalog.json', output, 1, 'reviewer-sample-v1')
                self.assertEqual(len(PreparedInputs(output / 'input.json').samples), 2)

    def test_legacy_collocated_custom_bundle_still_loads(self):
        output, _ = self.convert()
        run = input_run_directory(output)
        for path in run.iterdir():
            path.rename(output / path.name)
        run.rmdir()
        self.assertEqual(len(PreparedInputs(output / 'input.json').samples), 1)

    def test_cli_and_existing_scheduler_plan(self):
        output = self.root / 'cli'
        command = [sys.executable, '-B', '-m', 'finarch.cli', 'prepare-custom',
                   '--adapter', str(TEMPLATE), '--input', str(FINANCE),
                   '--name', 'reviewer-example', '--output', str(output)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['families'], 1)
        result = subprocess.run([sys.executable, '-B', '-m',
            'finarch.dataset.01-preparation.prepare_schedule', '--input', str(output / 'input.json'),
            '--config', 'config/llm.json', '--plan-only'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
