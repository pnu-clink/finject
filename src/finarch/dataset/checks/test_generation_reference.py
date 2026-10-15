"""Generation restores recorded metadata without modifying working Q/C or gold."""
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

gate = importlib.import_module('finarch.dataset.90-operations.preparation_gate')
driver = importlib.import_module('finarch.dataset.02-generation.generate_run')


class GenerationReferenceTests(unittest.TestCase):
    def case(self, root):
        case = root/'01-preparation/test-0001'
        active = case/'01-round'
        sample = {'id': 'test-0001', 'question': 'Change?', 'context': '12 to 10'}
        accepted = {**sample, 'reference_answer': '-2',
                    'reference_answer_type': 'integer', 'reference_precision': 0,
                    'answer_metadata': {'scale': 1, 'negative': False}}
        gate.write(case/'run.json', {'active_round': '01-round'})
        gate.write(active/'data.json', sample)
        gate.write(active/'02-review/accepted-input.json', accepted)
        return case, active, accepted

    def test_restore_signed_reference_without_changing_history(self):
        with tempfile.TemporaryDirectory() as folder:
            case, active, accepted = self.case(Path(folder))
            before = (active/'data.json').read_bytes()
            sample, evidence = gate.generation_sample(case)
            self.assertEqual(sample, accepted)
            self.assertEqual(sample['reference_answer'], '-2')
            self.assertEqual(evidence['source'], '01-round/02-review/accepted-input.json')
            self.assertTrue(evidence['original_data_unchanged'])
            self.assertEqual((active/'data.json').read_bytes(), before)

    def test_partial_conflicting_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            case, active, _ = self.case(Path(folder))
            sample = gate.read(active/'data.json')
            sample['reference_answer'] = '2'
            gate.write(active/'data.json', sample)
            with self.assertRaisesRegex(ValueError, 'ACCEPTED_REFERENCE_MISMATCH'):
                gate.generation_sample(case)

    def test_changed_question_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            case, active, _ = self.case(Path(folder))
            sample = gate.read(active/'data.json')
            sample['question'] = 'Different?'
            gate.write(active/'data.json', sample)
            with self.assertRaisesRegex(ValueError, 'ACCEPTED_INPUT_QC_MISMATCH'):
                gate.generation_sample(case)

    def test_batch_attempt_receives_restored_reference_and_logs_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            case, active, accepted = self.case(root)
            gate.write(active/'03-calculation/05-record-calculation-artifacts/03-program.json', {})
            gate.write(active/'04-graph/05-save-graph/01-graph.json', {})
            def validate(*args):
                args[12]['status'] = 'PASS'
            with patch.object(driver.g01_perturbation, 'run', return_value={}) as plan, \
                 patch.object(driver.g02_generate_text, 'run', return_value=({}, {}, {}, [])), \
                 patch.object(driver.g03_verification, 'run', side_effect=validate):
                result = driver._process_attempt(root, root/'02-generation/01-round',
                    'test-0001', 4, {}, {'test-0001': {'case_path': str(case.relative_to(root))}}, {})
            self.assertEqual(plan.call_args.args[1], accepted)
            self.assertEqual(result['status'], 'PASS')
            self.assertTrue((root/result['path']/'reference-metadata-handoff.json').is_file())


if __name__ == '__main__':
    unittest.main()
