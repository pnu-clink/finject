"""No live CLI calls: profile argv, mocked transport and viewer contracts."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
cli = __import__('finarch.shared.providers.cli', fromlist=['*'])
from finarch.shared.providers.profiles import read_profile, selected_profile, DEFAULT
from finarch.shared.providers.profile_cli import main
from finarch.dataset.checks.test_cli import codex_output
from finarch.dataset.viewer.build import collect

class Profiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root/'llm.json'
        self.config.write_text(json.dumps({'provider':'codex','execution_enabled':True,
            'roles':{'dtt.answer':{'model':'original','effort':'low'}},
            'capabilities':{'dtt.answer':{'tools':[],'skills':[]}},'cli_limits':{'timeout_seconds':1}}))
        self.input = self.root/'input.json'; self.input.write_text('{"context":"C","question":"Q"}')
    def test_defaults_and_none_argv(self):
        self.assertEqual(cli.read_settings(self.config,'dtt.answer')['model'],'original')
        settings=cli.read_settings(self.config,'dtt.answer',profile_id='luna-none')
        argv=cli.build_command(settings,'codex',self.root,self.input,self.input,self.input)
        self.assertIn('model_reasoning_effort="none"',argv)
        self.assertEqual(sum(x.startswith('model_reasoning_effort=') for x in argv),1)
    def test_migrated_purpose_models_keep_efforts_and_limits(self):
        for phase, roles in {
            'preparation': ('01-preparation.02-review-and-correct.revision',
                            '01-preparation.03-calculation.pot', '01-preparation.05-verification.semantic',
                            'shared.01-06.02-04.exception-handler'),
            'generation': ('02-generation.02-generate-text.realization',
                           'shared.01-02.02-03.review-and-validation',
                           '02-generation.feedback.case-feedback',
                           '02-generation.03-validation.ea-recoverability-review'),
        }.items():
            for role in roles:
                with self.subTest(phase=phase, role=role):
                    profile = selected_profile(DEFAULT, role, phase=phase)
                    pot = profile['purpose'] == 'pot_generation'
                    inverse = profile['purpose'] == 'ea_inverse_review'
                    self.assertEqual(profile['model'], 'gpt-6.1-sol' if pot or inverse else 'gpt-6-luna')
                    self.assertEqual(profile['effort'], 'medium' if pot else 'high' if inverse else 'max')
                    self.assertEqual(profile['max_output_tokens'], 128000 if pot else 32768)
                    self.assertEqual(profile['total_token_budget'], 500000)
        for role in ('shared.01-07.02-05.failure-interpretation', 'shared.01-07.02-05.display-translation'):
            profile = selected_profile(DEFAULT, role)
            self.assertEqual((profile['model'], profile['effort']), ('gpt-6-luna', 'max'))
        for name, effort in (('luna-none', 'none'), ('luna-low', 'low'), ('luna-medium', 'medium'), ('luna-max-cli', 'max')):
            profile = read_profile(DEFAULT, name)
            self.assertEqual((profile['model'], profile['effort']), ('gpt-6-luna', effort))
    def test_conflicting_or_unsafe_options(self):
        for argv in [['--sandbox','danger-full-access'],['-p','secret'],['-c','features.shell_tool=true'],
                     ['-c','"model_reasoning_effort"="none"'],['-m','x','--model','y'],['-c','model_provider=other'],['exec'],['-c']]:
            p=self.root/'profiles.toml';p.write_text('[profiles.bad]\nargv='+json.dumps(argv))
            with self.assertRaises(ValueError):read_profile(p,'bad')
    def test_unknown_profile(self):
        with self.assertRaisesRegex(ValueError,'UNKNOWN_CODEX_PROFILE'):read_profile(DEFAULT,'missing')
    def test_dry_run_no_subprocess_and_viewer_artifacts(self):
        out=self.root/'out'
        with patch.object(cli,'inspect_runtime') as inspect, patch.object(cli,'run_process') as run:
            self.assertEqual(main(['luna-none','--config',str(self.config),'--input',str(self.input),'--dry-run','--output',str(out)]),0)
        inspect.assert_not_called();run.assert_not_called()
        artifacts=collect(out)['artifacts']
        self.assertIn('profile-plan.json',artifacts);self.assertIn('events.jsonl',artifacts)
        self.assertNotIn('02-raw-response/cli-execution.json',artifacts)
    def test_mock_process_raw_response_and_validation(self):
        for response, expected in [('{"text":"OK"}',0),('{"text":42}',1)]:
            out=self.root/str(expected)
            result={'state':'EXITED','exit_code':0,'stdout':codex_output(response),'stderr':'','elapsed_seconds':.1}
            with patch.object(cli,'inspect_runtime',return_value={'executable':'codex','native_tool_enforcement':'VERIFIED'}), patch.object(cli,'run_process',return_value=result) as run:
                self.assertEqual(main(['luna-none','--config',str(self.config),'--input',str(self.input),'--output',str(out)]),expected)
            self.assertIn('model_reasoning_effort="none"',run.call_args.args[0])
            self.assertEqual(json.loads((out/'05-text/profile-call/02-raw-response.json').read_text())['text'],response)
            self.assertEqual(json.loads((out/'05-text/profile-call/01-input.json').read_text())['profile']['id'],'luna-none')
    def test_invalid_input_stops_before_process(self):
        self.input.write_text('{}')
        with patch.object(cli,'run_process') as run:
            self.assertEqual(main(['luna-low','--config',str(self.config),'--input',str(self.input),'--output',str(self.root/'fail')]),1)
        run.assert_not_called()
    def test_stdin_prompt_override_and_failed_preflight(self):
        instruction=self.root/'prompt.txt';instruction.write_text('Custom instruction')
        out=self.root/'blocked'
        with patch('sys.stdin') as stdin, patch.object(cli,'inspect_runtime',return_value={'native_tool_enforcement':'UNVERIFIED'}), patch.object(cli,'run_process') as run:
            stdin.read.return_value=self.input.read_text()
            self.assertEqual(main(['luna-none','--config',str(self.config),'--prompt-file',str(instruction),'--output',str(out)]),1)
        run.assert_not_called()
        self.assertEqual(json.loads((out/'05-text/profile-call/01-input/cli-profile.json').read_text())['id'],'luna-none')
        self.assertEqual(json.loads((out/'profile-plan.json').read_text())['instruction_override'],'Custom instruction')
    def test_snapshot_changes_rejected(self):
        profile=self.root/'p.toml';profile.write_text(DEFAULT.read_text())
        settings=cli.read_settings(self.config,'dtt.answer',profile_id='luna-none',profiles_path=profile)
        profile.write_text(profile.read_text()+'\n# modified\n')
        with self.assertRaisesRegex(cli.CLIError,'PROFILE_CHANGED_AFTER_LOAD'):
            cli.build_command(settings,'codex',self.root,self.input,self.input,self.input)
    def test_role_profile_config(self):
        value=json.loads(self.config.read_text()); value['roles']['dtt.answer']['profile_id']='luna-none'
        self.config.write_text(json.dumps(value))
        self.assertEqual(cli.read_settings(self.config,'dtt.answer')['effort'],'none')

if __name__=='__main__':unittest.main()
