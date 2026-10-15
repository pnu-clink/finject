import tempfile
import unittest
from pathlib import Path
save = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['save']).save
from finarch.dataset.viewer.reports.comparison_report import outcomes, build, guidance_application, audit_condition_check
audit_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['audit_root']).audit_root


class ComparisonReportTests(unittest.TestCase):
    def test_audit_condition_detects_added_instruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline=Path(tmp)/'baseline';comparison=Path(tmp)/'comparison'
            request={'role':'shared.01-02.02-03.review-and-validation','model':'same-model','effort':'none','response_schema':{'type':'object'},
                     'prompt_selection':{'instruction':'Original criteria','parts':[{'file':'common.md'},{'file':'ea.md'}]}}
            relative='01-round/test-0001/03-LLM-call/01-request.json'
            save(baseline/relative,request);save(comparison/relative,request)
            self.assertTrue(audit_condition_check(baseline,comparison)['all_equal'])
            request['prompt_selection']['instruction']+=' Added instruction'
            save(comparison/relative,request)
            self.assertEqual(len(audit_condition_check(baseline,comparison)['mismatched']),1)

    def test_unfinalized_label_is_not_reported_as_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            save(root/'01-round/test-0001/04-perturbation/05-list-candidates/03-result.json',[{'label':'IC_VALUE_01'}])
            result=outcomes(root,'01-round')
            self.assertEqual(result[('test-0001','IC_VALUE_01')]['status'],'NOT_EVALUATED')

    def test_guidance_verification_requires_actual_text_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            save(root/'feedback/pot.author/answer.json',{'target_role':'01-preparation.03-calculation.pot','axis':'ANSWER','guidance':'Expected guidance'})
            save(root/'01-round/test-0001/03-LLM-call/01-request.json',{'role':'01-preparation.03-calculation.pot','fresh_session':True,'prompt_selection':{'parts':[{'file':'pot-prompt.md','text':'Different guidance','sha256':'incorrect'}]}})
            result=guidance_application(root)
            self.assertEqual(result['fresh_session_requests'],1)
            self.assertEqual(len(result['missing_or_mismatched']),1)
            self.assertEqual(result['supplement_applied'],{})

    def case(self, bundle, round_name, status):
        case = bundle / round_name / 'test-0001'
        save(case/'04-perturbation/05-list-candidates/03-result.json', [])
        save(case/audit_root('ANSWER')/round_name/'03-result.json',
             {'status': status, 'reason': 'Recorded reason'})
        return case

    def test_retry_keeps_observed_success_and_missing_round_stays_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.case(root,'01-round','PASS')
            (root/'02-round').mkdir()
            self.assertEqual(outcomes(root,'02-round')[('test-0001','ANSWER')]['status'],'PASS')
            self.assertEqual(outcomes(root,'03-round'),{})

    def test_new_failure_and_missing_candidate_are_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=Path(tmp)/'baseline';second=Path(tmp)/'comparison'
            self.case(first,'01-round','PASS')
            self.case(second,'01-round','FAIL')
            for root in (first,second):
                save(root/'input-selection.json',{'sha256':'same','cases':['test-0001']})
            report=build(first,second)
            self.assertTrue(report['same_input'])
            self.assertEqual(report['transitions'],{'PASS → FAIL':1})
            self.assertEqual(report['rows'][0]['results'][1]['status'],'NOT_GENERATED')
            self.assertIsNone(report['evaluation_prompt_changed'])

    def test_upstream_exclusion_retains_actual_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory=root/'01-round'
            save(directory/'graph-next-stage.json',{'blocked':[{'input_id':'test-0001'}]})
            save(directory/'test-0001/run.json',{'reason':'Unsupported graph operation'})
            result=outcomes(root,'01-round')[('test-0001','PIPELINE')]
            self.assertEqual(result['status'],'EXCLUDED')
            self.assertEqual(result['reason'],'Unsupported graph operation')

    def test_single_round_comparison_has_only_two_actual_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=Path(tmp)/'baseline';second=Path(tmp)/'comparison'
            self.case(first,'01-round','FAIL')
            self.case(second,'01-round','PASS')
            report=build(first,second,baseline_rounds=(1,))
            self.assertEqual(len(report['columns']),2)
            self.assertEqual([v['status'] for v in report['rows'][0]['results']],['FAIL','PASS'])
            self.assertEqual(report['transitions'],{'FAIL → PASS':1})
            self.assertEqual(report['transitions_by_baseline_round'],{'01-round':{'FAIL → PASS':1}})


if __name__=='__main__':
    unittest.main()
