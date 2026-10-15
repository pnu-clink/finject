"""Prompt routing at the CLI boundary; no external model/process calls."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
prompts = __import__('finarch.dataset.02-generation.02-generate-text.realization_prompts', fromlist=['*'])
cli = __import__('finarch.shared.providers.cli', fromlist=['*'])
from finarch.dataset.schemas.registry import describe
from finarch.dataset.checks.test_cli import codex_output

CASE = (Path(__file__).resolve().parent / '../../../..').resolve() / 'reports/run/first-10-pot-validated-v3/test-0002'
LABELS = ('IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY',
          'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')


class PromptChecks(unittest.TestCase):
    def test_each_type_contains_only_its_own_objective(self):
        for axis in prompts.FILES:
            with self.subTest(axis=axis):
                d = prompts.describe_prompt(axis)
                self.assertEqual(len(d['parts']), 2)
                self.assertEqual(d['instruction'].count('OBJECTIVE:'), 1)
                self.assertEqual(d['sha256'], hashlib.sha256(d['instruction'].encode()).hexdigest())
                for other in set(prompts.FILES) - {axis}:
                    self.assertNotIn('OBJECTIVE: ' + other.replace('_', '-'), d['instruction'])
                self.assertIn('exactly one patch per edit_slots entry', d['instruction'])

    def test_invalid_type_and_missing_empty_file_do_not_fallback(self):
        for axis in ('ANSWER', '', '../ea', None):
            with self.assertRaises(ValueError): prompts.describe_prompt(axis)
        with tempfile.TemporaryDirectory() as root, patch.object(prompts, 'ROOT', Path(root)):
            with self.assertRaises(cli.CLIError):cli.prepare_instruction('02-generation.02-generate-text.realization', {'axis':'EA'})
            (Path(root)/'common.md').write_text('')
            with self.assertRaises(cli.CLIError):cli.prepare_instruction('02-generation.02-generate-text.realization', {'axis':'EA'})

    def test_explicit_override_keeps_its_own_provenance(self):
        instruction, selection = cli.prepare_instruction('02-generation.02-generate-text.realization', {'axis':'EA'}, 'My explicit prompt')
        self.assertEqual(instruction, 'My explicit prompt')
        self.assertEqual(selection['scope'], 'explicit instruction override')
        self.assertNotIn('parts', selection)
        with self.assertRaises(cli.CLIError):cli.prepare_instruction('02-generation.02-generate-text.realization', {'axis':'EA'}, ' ')

    def test_all_seven_cases_use_one_prompt_and_same_response_schema(self):
        settings = dict(model='local-test', effort='low', provider='codex', execution_enabled=True,
                        policy={'tools':[], 'skills':[]}, timeout_seconds=1)
        for label in LABELS:
            with self.subTest(label=label):
                pointer = json.loads((CASE/'05-text'/label/'latest-realization.json').read_text())
                stage = CASE/pointer['stage']
                request = json.loads((stage/'01-input.json').read_text())
                patches = json.loads((stage/'03-result/patches.json').read_text())
                response = {'patches':[{k:p[k] for k in ('start','end','before','text','element_ids')} for p in patches]}
                saved = {}; sent = []
                def run(argv, stdin, work, timeout, audit):
                    sent.append(stdin)
                    self.assertEqual(json.loads((work/'01-input/response-schema.json').read_text()), describe('dtt.realize.response')['schema'])
                    return {'state':'EXITED', 'exit_code':0, 'stdout':codex_output(json.dumps(response)), 'stderr':''}
                with patch.object(cli, 'read_settings', return_value=settings), \
                     patch.object(cli, 'inspect_runtime', return_value={'executable':'local-fake', 'native_tool_enforcement':'VERIFIED'}), \
                     patch.object(cli, 'build_command', return_value=['local-fake']), \
                     patch.object(cli, 'run_process', side_effect=run):
                    result = cli.call('unused.json', '02-generation.02-generate-text.realization', request, save=lambda k,v:saved.update({k:v}))
                self.assertEqual(result.status, 'PASS')
                self.assertEqual(len(sent), 1)
                head, payload = sent[0].split('\nInput:\n', 1)
                self.assertEqual(head, prompts.describe_prompt(request['axis'])['instruction'])
                self.assertEqual(json.loads(payload), request)
                self.assertEqual(saved['01-input.json']['prompt_selection']['axis'], request['axis'])
                self.assertIn('02-raw-response.json', saved)
                self.assertEqual(saved['03-result/schema-check.json']['status'], 'PASS')

    def test_ea_prose_is_not_confused_with_fixed_cell(self):
        text = prompts.describe_prompt('EA')['instruction']
        self.assertIn('Rewrite the ENTIRE authorized sentence', text)
        self.assertIn('PROSE SLOT (exact_text is null)', text)
        self.assertIn('FIXED SLOT (exact_text is not null)', text)
        self.assertIn('The loan amount is $.', text)


if __name__ == '__main__': unittest.main()
