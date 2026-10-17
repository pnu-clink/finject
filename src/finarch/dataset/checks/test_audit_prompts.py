"""R17P routing and unchanged response boundary using only a fake CLI process."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
prompts = __import__('finarch.dataset.shared.review.audit_prompts', fromlist=['*'])
cli = __import__('finarch.shared.providers.cli', fromlist=['*'])
from finarch.dataset.schemas.registry import describe
from finarch.dataset.schemas.llm import AUDIT_CRITERIA
from finarch.dataset.shared.review.dtt_audit import evaluate
from finarch.dataset.checks.test_cli import codex_output

ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()
CASE = ROOT/'reports/run/first-10-pot-validated-v3/test-0002'
LABELS = ('ANSWER', 'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY',
          'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')


def request_for(label):
    pointer = json.loads((CASE/'05-text'/label/'latest-audit.json').read_text())
    return json.loads((CASE/pointer['stage']/'01-input.json').read_text())


class AuditPromptChecks(unittest.TestCase):
    def test_five_types_keep_only_the_selected_objective(self):
        for axis in prompts.FILES:
            with self.subTest(axis=axis):
                d = prompts.describe_prompt(axis)
                self.assertEqual(len(d['parts']), 2)
                self.assertEqual(d['instruction'].count('AUDIT TYPE:'), 1)
                self.assertEqual(d['sha256'], hashlib.sha256(d['instruction'].encode()).hexdigest())
                self.assertIn('RETURN EXACTLY THREE FINDINGS', d['instruction'])
                for other in set(prompts.FILES) - {axis}:
                    self.assertNotIn('AUDIT TYPE: '+other.replace('_','-'), d['instruction'])

    def test_missing_unknown_or_empty_instructions_stop_without_process(self):
        for axis in ('', None, '../ea', 'unrecognized'):
            with self.assertRaises(cli.CLIError):cli.prepare_instruction('shared.01-02.02-03.review-and-validation', {'axis':axis})
        for contents in (None, ''):
            with tempfile.TemporaryDirectory() as root, patch.object(prompts, 'ROOT', Path(root)), \
                 patch.object(cli, 'run_process') as run, patch.object(cli, 'inspect_runtime') as inspect:
                if contents is not None:(Path(root)/'common.md').write_text(contents)
                saved={}
                result=cli.call('unused.json','shared.01-02.02-03.review-and-validation',request_for('EA_01'),save=lambda k,v:saved.update({k:v}))
                self.assertEqual(result.status,'FAIL')
                self.assertEqual(saved['03-result/failure.json']['reason'],'AUDIT_PROMPT_UNAVAILABLE')
                run.assert_not_called();inspect.assert_not_called()

    def test_all_eight_inputs_use_one_prompt_and_preserve_three_findings(self):
        settings = dict(model='gpt-5.6-luna', effort='none', provider='codex', execution_enabled=True,
                        policy={'tools':[], 'skills':[]}, timeout_seconds=1)
        for label in LABELS:
            with self.subTest(label=label):
                request=request_for(label)
                response={'findings':[{'criterion':c,'judgment':'PASS','reason':''} for c in AUDIT_CRITERIA]}
                # Synthetic judgments check aggregation, not these real texts' quality.
                if label=='EA_01':response['findings'][2].update(judgment='FAIL',reason='\ub85c\uceec \uc751\ub2f5 \ud615\uc2dd \uac80\uc0ac \uc608\uc2dc')
                if label=='EA_02':response['findings'][2].update(judgment='UNKNOWN',reason='\ub85c\uceec \ubcf4\ub958 \uc608\uc2dc')
                saved={};sent=[]
                def run(argv, stdin, work, timeout, audit):
                    sent.append(stdin)
                    self.assertEqual(json.loads((work/'01-input/response-schema.json').read_text()),describe('dtt.audit.response')['schema'])
                    return {'state':'EXITED','exit_code':0,'stdout':codex_output(json.dumps(response)), 'stderr':''}
                with patch.object(cli,'read_settings',return_value=settings), \
                     patch.object(cli,'inspect_runtime',return_value={'executable':'local-fake','native_tool_enforcement':'VERIFIED'}), \
                     patch.object(cli,'build_command',return_value=['local-fake']),patch.object(cli,'run_process',side_effect=run):
                    result=cli.call('unused.json','shared.01-02.02-03.review-and-validation',request,save=lambda k,v:saved.update({k:v}))
                self.assertEqual(result.status,'PASS')
                self.assertEqual(len(sent),1)
                head,payload=sent[0].split('\nInput:\n',1)
                self.assertEqual(head,prompts.describe_prompt(request['axis'])['instruction'])
                self.assertEqual(json.loads(payload),request)
                self.assertEqual(saved['01-input.json']['prompt_selection']['axis'],request['axis'])
                self.assertEqual(saved['01-input.json']['effort'],'none')
                self.assertIn('02-raw-response.json',saved)
                self.assertEqual(saved['03-result/schema-check.json']['status'],'PASS')
                report=evaluate(request,result.data)
                self.assertEqual(report['status'],{'EA_01':'FAIL','EA_02':'NOT_EVALUATED'}.get(label,'PASS'))
                self.assertEqual(report['stage18'],'NOT_RUN')

    def test_default_none_and_explicit_override_are_preserved(self):
        settings=cli.read_settings(ROOT/'config/llm.json','shared.01-02.02-03.review-and-validation')
        self.assertEqual((settings['model'],settings['effort']),('gpt-5.6-luna','none'))
        instruction,definition=cli.prepare_instruction('shared.01-02.02-03.review-and-validation',request_for('EA_01'),'Explicit audit prompt')
        self.assertEqual(instruction,'Explicit audit prompt')
        self.assertEqual(definition['scope'],'explicit instruction override')


if __name__=='__main__':unittest.main()
