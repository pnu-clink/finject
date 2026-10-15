import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
decide = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['decide']).decide
expand_dependencies = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['expand_dependencies']).expand_dependencies
finish_rounds = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['finish_rounds']).finish_rounds
save = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['save']).save
inherit_case = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['inherit_case']).inherit_case
use_feedback = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['use_feedback']).use_feedback
from finarch.shared.providers.cli import prepare_instruction
RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs
from finarch.dataset.schemas.registry import describe

class FeedbackLoopTests(unittest.TestCase):
    def test_fixed_audit_instructions_are_not_rewritten_by_feedback(self):
        build_feedback = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['build_feedback']).build_feedback
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'config.json'
            save(config,{'feedback_target_roles':['02-generation.02-generate-text.realization']})
            error={'case':'test-0001','label':'ANSWER','axis':'ANSWER','target_role':'shared.01-02.02-03.review-and-validation','reason':'Audit failed'}
            with patch.object(__import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['*']), 'call') as llm:
                build_feedback(root,root/'01-round',[error],config)
            llm.assert_not_called()
            self.assertFalse((root/'feedback/dtt.audit').exists())

    def test_parallel_context_and_code_supplement(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(2)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('one','two'):
                save(root/name/'pot.author/answer.json',{'axis':'ANSWER','target_role':'01-preparation.03-calculation.pot','version':1,'guidance':name})
            def job(name):
                with use_feedback(root/name):
                    barrier.wait()
                    _,definition=prepare_instruction('01-preparation.03-calculation.pot',{})
                    return definition['parts'][-1]['text']
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(job,('one','two'))),['one','two'])

    def test_stop_and_limit(self):
        self.assertEqual(decide([],1)['decision'],'PASS')
        self.assertEqual(decide([{}],1)['decision'],'RETRY')
        self.assertEqual(decide([{}],3)['decision'],'LIMIT_REACHED')

    def test_dependency_invalidation(self):
        variants=[{'label':'IC_SOURCE_A_ONLY','axis':'IC_SOURCE'},{'label':'IC_SOURCE_B_ONLY','axis':'IC_SOURCE'}]
        self.assertEqual(expand_dependencies(['EA_01'],variants),{'EA_01'})
        self.assertEqual(expand_dependencies(['IC_VALUE_01_AFTER'],variants),{'IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER','IC_SOURCE_A_ONLY','IC_SOURCE_B_ONLY'})

    def test_cumulative_prompt_separate_from_baseline(self):
        base,_=prepare_instruction('02-generation.02-generate-text.realization',{'axis':'IC_SOURCE'})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            save(path/'dtt.realize/ic_source.json',{'axis':'IC_SOURCE','target_role':'02-generation.02-generate-text.realization','version':2,'guidance':'Preserve valid sentence boundaries.'})
            with use_feedback(path):
                text,parts=prepare_instruction('02-generation.02-generate-text.realization',{'axis':'IC_SOURCE'})
                self.assertTrue(text.startswith(base))
                self.assertEqual(parts['parts'][-1]['version'],2)
                self.assertEqual(len(parts['parts']),3)
                untouched,_=prepare_instruction('02-generation.02-generate-text.realization',{'axis':'EA'})
                self.assertNotIn('Preserve valid sentence boundaries.',untouched)
            self.assertEqual(prepare_instruction('02-generation.02-generate-text.realization',{'axis':'IC_SOURCE'})[0],base)

    def test_three_rounds_two_feedback_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first=root/'01-round';first.mkdir()
            progress={'cases':{'test-0001':{'status':'CHECKED'}}}
            save(first/'production-progress.json',progress)
            def retry(previous,current,*args):save(current/'production-progress.json',progress)
            errors=[{'case':'test-0001','label':'EA_01','reason':'readability','restart':'01-generate-text'}]
            with patch.object(__import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['*']), 'failures',return_value=errors),patch.object(__import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['*']), 'build_feedback') as feedback,patch.object(__import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['*']), 'retry_round',side_effect=retry) as rerun,patch.object(__import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['*']), 'build',return_value={'ready':0}):
                result=finish_rounds(root,first,root/'config.json')
            self.assertEqual(result['status'],'LIMIT_REACHED')
            self.assertEqual(feedback.call_count,2)
            self.assertEqual(rerun.call_count,2)
            self.assertEqual(len(result['rounds']),3)

    def test_pass_stops_without_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first=root/'01-round';first.mkdir()
            save(first/'production-progress.json',{'cases':{'test-0001':{'status':'CHECKED'}}})
            with patch.object(__import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['*']), 'failures',return_value=[]),patch.object(__import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['*']), 'build_feedback') as feedback,patch.object(__import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['*']), 'build',return_value={'ready':1}):
                result=finish_rounds(root,first,root/'config.json')
            self.assertEqual(result['status'],'PASS');feedback.assert_not_called()
            self.assertFalse((root/'02-round').exists())

    def test_round_logs_and_no_cross_run_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=root/'reports/run/run-a/02-round/test-0001';case.mkdir(parents=True)
            logs=RunLogs.for_case(case);logs.write('detail.log','example',problem_id='test-0001',stage='05-text',value={'ok':True})
            base=root/'log/run/run-a'
            self.assertTrue((base/'02-round/test-0001/05-text/detail.log').is_file())
            self.assertEqual(len((base/'default.log').read_text().splitlines()),1)
            self.assertTrue((base/'02-round/default.log').is_file())
            with self.assertRaises(ValueError):inherit_case(case,root/'reports/run/run-b/03-round/test-0001')

    def test_feedback_has_both_contracts(self):
        for kind in ('request','response'):
            self.assertTrue(describe('dtt.feedback.'+kind)['schema'])

    def test_feedback_merges_previous_and_preserves_creation_record(self):
        build_feedback = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['build_feedback']).build_feedback
        StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);round_dir=root/'01-round';round_dir.mkdir()
            file=root/'feedback/dtt.realize/ic_source.json'
            save(file,{'guidance':'Existing guidance.','version':1})
            error={'case':'test-0001','label':'IC_SOURCE_A_ONLY','axis':'IC_SOURCE','target_role':'02-generation.02-generate-text.realization','reason':'Sentence boundary','request':{},'response':{}}
            response=StepResult('PASS','checked',{'guidance':'Merged complete guidance.','changes':['Clarified sentence boundaries.']})
            with patch.object(__import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['*']), 'call',return_value=response) as llm:
                build_feedback(root,round_dir,[error],root/'config.json')
            payload=llm.call_args.args[2]
            self.assertEqual(payload['previous_guidance'],'Existing guidance.')
            self.assertEqual(json.loads(file.read_text())['version'],2)
            self.assertEqual(json.loads(file.read_text())['guidance'],'Merged complete guidance.')
            self.assertTrue(list(round_dir.rglob('README.md')))

    def test_round_view_excludes_feedback_journals(self):
        from finarch.dataset.viewer.server import batch_data
        with tempfile.TemporaryDirectory() as tmp:
            runs=Path(tmp);bundle=runs/'run-a';first=bundle/'01-round';second=bundle/'02-round'
            for directory in [first/'test-0001',second/'test-0001',second/'05-text/04-LLM-build-feedback/ic_source']:
                directory.mkdir(parents=True);(directory/'events.jsonl').write_text('{"phase":"START"}\n')
            data=batch_data(runs,'run-a')
            self.assertEqual(data['batch']['round'],'02-round')
            self.assertEqual(len(data['runs']),1)
            self.assertEqual(batch_data(runs,'run-a','01-round')['batch']['round'],'01-round')
            with self.assertRaises(ValueError):batch_data(runs,'run-a','../outside')
