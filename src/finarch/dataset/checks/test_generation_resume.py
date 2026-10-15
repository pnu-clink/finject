"""Resume after a completed round without repeating completed model work."""
import tempfile
import unittest
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
g = __import__('finarch.dataset.02-generation.generate_schedule', fromlist=['*'])


class ResumeTests(unittest.TestCase):
    def test_unfinished_first_round_includes_newly_approved_case(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();g.write(root/'config.json',{});rnd=root/'02-generation/01-round'
            for directory,axis,label in g.TYPES:
                g.write(rnd/'test-0001'/directory/'run.json',
                        {'label':label,'axis':axis,'status':'PASS','path':str((rnd/'test-0001'/directory).relative_to(root))})
            def process(bundle,round_dir,name,index,*args):
                return {'label':g.TYPES[index][2],'status':'PASS','path':str((round_dir/name/g.TYPES[index][0]).relative_to(root))}
            with patch('finarch.dataset.viewer.reports.completion_report.build'),patch.object(g,'require_generation_inputs',return_value={'test-0001':{},'test-0010':{}}),patch.object(g,'measure',return_value=nullcontext()),patch.object(g._driver,'process',side_effect=process) as calls:
                result=g.run(root,3,resume=True)
            self.assertEqual(result['status'],'PASS')
            self.assertEqual(calls.call_count,7)
            self.assertTrue(all(c.args[2]=='test-0010' for c in calls.call_args_list))
            self.assertEqual(len(result['latest']['test-0001']),7)
            self.assertEqual(len(result['latest']['test-0010']),7)

    def test_round_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();g.write(root/'config.json',{});gen=root/'02-generation';rnd=gen/'01-round'
            failed=None
            for i,(directory,axis,label) in enumerate(g.TYPES):
                result={'label':label,'axis':axis,'status':'FAIL' if i==4 else 'PASS','path':str((rnd/'test-0001'/directory).relative_to(root)),'reason':'test','restart':'02-generate-text'}
                g.write(root/result['path']/'run.json',result)
                if i==4:failed={'case':'test-0001',**result}
            g.write(rnd/'final-validator.json',{'round':1,'decision':'RETRY','failure_count':1,'failures':[failed]})
            g.write(gen/'timing.json',{'status':'ERROR'})
            def process(bundle,round_dir,name,index,*args):
                return {'label':g.TYPES[index][2],'status':'PASS','path':str((round_dir/name/g.TYPES[index][0]).relative_to(root))}
            with patch('finarch.dataset.viewer.reports.completion_report.build'),patch.object(g,'require_generation_inputs',return_value={'test-0001':{}}),patch.object(g,'measure',return_value=nullcontext()),patch.object(g,'feedback') as feedback,patch.object(g._driver,'process',side_effect=process) as calls:
                result=g.run(root,3,resume=True)
            self.assertEqual(result['status'],'PASS')
            self.assertEqual([r['round'] for r in result['rounds']],[1,2])
            self.assertEqual(calls.call_count,1)
            self.assertEqual(calls.call_args.args[3],4)
            feedback.assert_called_once()

    def test_completed_feedback_reused_and_cases_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();g.write(root/'config.json',{});rnd=root/'02-generation/01-round'
            failures=[{'restart':'02-generate-text','axis':'IC_SOURCE','case':name,'label':'IC_SOURCE_A_ONLY','reason':'Wrong claim '+name} for name in ['test-0001','test-0002']]
            def respond(ctx,config,stage,role,payload):
                from finarch.dataset.schemas.feedback import FeedbackRequest
                FeedbackRequest.model_validate(payload)
                self.assertEqual(len(payload['failures']),1)
                return {'guidance':payload['failures'][0]['reason'],'changes':['Correct this claim only.']}
            with patch.object(g._driver,'invoke',side_effect=respond) as invoke:
                g.feedback(root,rnd,failures,root/'config.json')
                self.assertEqual(invoke.call_count,2)
                g.feedback(root,rnd,failures,root/'config.json')
                self.assertEqual(invoke.call_count,2)
            use_feedback = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['use_feedback']).use_feedback
            supplement = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['supplement']).supplement
            for item in failures:
                variant=next(f for f,a,l in g.TYPES if l==item['label'])
                directory=rnd/item['case']/variant/'feedback'
                with use_feedback(directory):
                    applied=supplement('02-generation.02-generate-text.realization','IC_SOURCE',{'instruction':'base','parts':[]})
                    self.assertIn(item['case'],applied['instruction'])
                    other='test-0002' if item['case']=='test-0001' else 'test-0001'
                    self.assertNotIn(other,applied['instruction'])
            self.assertFalse((root/'02-generation/feedback').exists())


class PairedFeedbackTests(unittest.TestCase):
    def test_after_feedback_reaches_shared_sentence_only_for_same_case(self):
        generation_feedback = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.case_feedback', fromlist=['generation_feedback']).generation_feedback
        RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
        use_feedback = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['use_feedback']).use_feedback
        supplement = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['supplement']).supplement
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);prior=root/'01-round/test-a/value-after'
            g.write(prior/'feedback/02-result.json',{'case':'test-a','label':g.TYPES[1][2],'guidance':'Repair the future-period mismatch.'})
            current=root/'02-round/test-a/value-before'
            ctx=RunContext(current,{},'test-a');latest={1:{'path':str(prior.relative_to(root))}}
            path=generation_feedback(ctx,root,current,'test-a',0,latest,g.TYPES)
            with use_feedback(path):
                value=supplement('02-generation.02-generate-text.realization','IC_VALUE',{'instruction':'base','parts':[]})
                self.assertIn('future-period mismatch',value['instruction'])
            with self.assertRaisesRegex(ValueError,'SCOPE_MISMATCH'):
                generation_feedback(ctx,root,current,'test-b',0,latest,g.TYPES)

if __name__=='__main__':unittest.main()
