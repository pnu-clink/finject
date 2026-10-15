"""Fixed-target opt-in coefficients: local execution, pairing, and resume boundaries."""
from copy import deepcopy
from importlib import import_module
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
validate = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['validate']).validate
bind = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['bind']).bind
NoCoefficient = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['NoCoefficient']).NoCoefficient
domain = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['domain']).domain
load_run = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['load_run']).load_run
from finarch.dataset.shared.calculation.python_graph import compile_graph
p=import_module('finarch.dataset.02-generation.01-perturbation.generation_plan')
g01=import_module('finarch.dataset.02-generation.01-perturbation.stage')
driver=import_module('finarch.dataset.02-generation.generate_run')
PROJECT=(Path(__file__).resolve().parent / '../../../..').resolve()
POLICY={'name':'bounded-coefficients-v1','seed':1}

def fixture(value='100',unit='USD',expression='x',precision=0):
    context='Amount is '+value+'.';start=context.index(value)
    program={'code':'x=fact("x")\nanswer='+expression,'context':context,'facts':{'x':{'value':value,'text':value,'span':[start,start+len(value)],'unit':unit}}}
    graph,answer,_=compile_graph(program)
    sample={'id':'test-0001','context':context,'question':'What is the amount? Answer to the nearest integer.' if precision==0 else 'What is the amount? Answer to one decimal place.',
            'reference_answer':'0' if precision==0 else '0.0','reference_answer_type':'integer' if precision==0 else 'float','reference_precision':precision}
    return sample,program,graph

def real():
    root=PROJECT/'reports/run/20260916-001/01-preparation/test-0001/01-round'
    return tuple(json.loads((root/name).read_text()) for name in ('data.json','03-calculation/05-record-calculation-artifacts/03-program.json','04-graph/05-save-graph/01-graph.json'))

def relation_fixture(value='100', reference='60'):
    sample,program,_=fixture(value)
    context='Amount is '+value+'. Reference amount is '+reference+'.'
    start=context.rindex(reference)
    program.update(context=context,code='x=fact("x")\ny=fact("y")\nanswer=x+y')
    program['facts']['y']={'value':reference,'text':reference,'span':[start,start+len(reference)],'unit':'USD'}
    sample['context']=context
    graph,_,_=compile_graph(program)
    return sample,program,graph

class CoefficientChecks(unittest.TestCase):
    def test_legacy_entire_real_plans_equal_saved_and_explicit_legacy(self):
        args=real()
        for index in (0,1):
            saved=json.loads((PROJECT/'reports/run/20260916-001/02-generation/01-round/test-0001'/p.TYPES[index][0]/'run.json').read_text())['plan']
            self.assertEqual(p.build(*args,index),saved)
            self.assertEqual(p.build(*args,index,perturbation_policy={'name':'legacy-v1'}),saved)
        relation=p.build(*args,4)
        self.assertEqual(relation['relation_policy_version'],'source-scoped-relation-v2')
        self.assertEqual(relation,p.build(*args,4,perturbation_policy={'name':'legacy-v1'}))

    def test_seed_reproducible_order_independent_and_both_factors(self):
        args=fixture();answers={}
        for seed in range(8):
            plan=p.build(*args,0,perturbation_policy={**POLICY,'seed':seed});answers[seed]=plan['coefficient_selection']
        self.assertEqual({r['selected_factor'] for r in answers.values()},{'0.9','1.1'})
        for seed in reversed(range(8)):
            self.assertEqual(p.build(*args,0,perturbation_policy={**POLICY,'seed':seed})['coefficient_selection'],answers[seed])

    def test_relation_factor_code_intent_and_slot_agree(self):
        factors=set()
        for seed in range(6):
            plan=p.build(*relation_fixture(),4,perturbation_policy={**POLICY,'seed':seed});factor=plan['coefficient_selection']['selected_factor'];factors.add(factor)
            self.assertEqual(plan['intent']['relation']['factor'],factor)
            self.assertIn(' * '+factor,plan['program']['code'])
            self.assertEqual(set(plan['request']['edit_slots'][0]['allowed_numbers']),{factor,'60'})
        self.assertEqual(factors,{'0.5','2'})

    def test_four_plans_inherit_before_selection_and_fixed_target(self):
        args=real();latest={};ctx=MagicMock()
        for index in range(4):
            plan=g01.run(ctx,*args,index,latest,p.build,perturbation_policy=POLICY)
            latest[index]={'path':'fixture/'+str(index),'plan':plan}
        plans=[r['plan'] for r in latest.values()]
        self.assertEqual(len({r['coefficient_selection']['selected_factor'] for r in plans}),1)
        self.assertEqual(len({tuple(r['intent']['value_pair']) for r in plans}),1)
        self.assertEqual(len({r['target'] for r in plans}),1)
        self.assertTrue(all('inherited_selection_sha256' in r['coefficient_selection'] for r in plans[1:]))
        with self.assertRaisesRegex(ValueError,'PAIRED_COEFFICIENT_PARENT_REQUIRED'):g01.run(ctx,*args,1,{},p.build,perturbation_policy=POLICY)

    def test_zero_has_two_rejections_no_plus_one_fallback(self):
        with self.assertRaises(NoCoefficient) as caught:p.build(*fixture('0'),0,perturbation_policy=POLICY)
        r=caught.exception.report;self.assertEqual(len(r['attempts']),2);self.assertIsNone(r['selected_factor'])
        self.assertEqual({a['reason'] for a in r['attempts']},{'UNCHANGED_TARGET_VALUE'})
        self.assertEqual(p.build(*fixture('0'),0)['alternative'],'1')

    def test_domain_count_percent_and_unknown(self):
        for value,unit in [('3','shares'),('100','widgets')]:
            with self.assertRaises(NoCoefficient) as caught:p.build(*fixture(value,unit),0,perturbation_policy=POLICY)
            self.assertEqual(len(caught.exception.report['attempts']),2)
        for seed in range(8):
            r=p.build(*fixture('100','percent'),0,perturbation_policy={**POLICY,'seed':seed})['coefficient_selection']
            self.assertEqual(r['selected_factor'],'0.9')
            self.assertLessEqual(len(r['attempts']),2)
        with self.assertRaisesRegex(ValueError,'INTEGER_COUNT'):domain({'unit':'count','value':'10'},__import__('decimal').Decimal('-1'))

    def test_exact_cancellation_and_display_rounding_rejected(self):
        for args in (fixture(expression='x-x'),fixture('100',expression='x / 1000')):
            with self.assertRaises(NoCoefficient) as caught:p.build(*args,0,perturbation_policy=POLICY)
            self.assertEqual(len(caught.exception.report['attempts']),2)
            self.assertTrue(all('UNCHANGED' in a['reason'] for a in caught.exception.report['attempts']))

    def test_relation_zero_does_not_fall_back(self):
        with self.assertRaises(NoCoefficient) as caught:p.build(*relation_fixture('0','0'),4,perturbation_policy=POLICY)
        self.assertEqual({r['reason'] for r in caught.exception.report['attempts']},{'ZERO_COEFFICIENT_INPUT'})

    def test_scheduler_rejects_policy_change_before_preparation_writes(self):
        schedule=import_module('finarch.dataset.02-generation.generate_schedule')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);hp=root/'hyper.json';hp.write_text(json.dumps({'generation':{'run':{'perturbation_policy':POLICY}}}))
            driver.write(root/'config.json',{'hyperparameter_path':str(hp)})
            bind({'hyperparameter_path':str(hp)},root)
            hp.write_text(json.dumps({'generation':{'run':{'perturbation_policy':{**POLICY,'seed':22}}}}))
            with patch.object(schedule,'require_generation_inputs',side_effect=AssertionError('preparation write')):
                with self.assertRaisesRegex(ValueError,'SNAPSHOT_MISMATCH'):schedule.run(root,1,resume=True)

    def test_ambiguous_or_changed_precision_unevaluated(self):
        for question in ('What amount?','Answer to two decimal places.'):
            args=list(fixture());args[0]['question']=question
            with self.assertRaises(NoCoefficient) as caught:p.build(*args,0,perturbation_policy=POLICY)
            self.assertTrue(all('PRECISION' in a['reason'] for a in caught.exception.report['attempts']))

    def test_graph_execution_check_remains_mandatory(self):
        with patch.object(p,'checked_branch',side_effect=ValueError('BRANCH_GRAPH_EXECUTION_MISMATCH')) as checked:
            with self.assertRaises(NoCoefficient) as caught:p.build(*fixture(),0,perturbation_policy=POLICY)
        self.assertEqual(checked.call_count,2);self.assertTrue(all(a['reason']=='BRANCH_GRAPH_EXECUTION_MISMATCH' for a in caught.exception.report['attempts']))

    def test_resume_reuses_same_plan_rejects_seed_and_input_changes(self):
        args=fixture();ctx=MagicMock();plan=g01.run(ctx,*args,0,{},p.build,perturbation_policy=POLICY)
        prior={0:{'path':'old','plan':plan}}
        with patch.object(p,'build',side_effect=AssertionError('rebuild')):
            self.assertEqual(g01.run(ctx,*args,0,prior,p.build,perturbation_policy=POLICY),plan)
        with self.assertRaisesRegex(ValueError,'POLICY_PLAN_MISMATCH'):g01.run(ctx,*args,0,prior,p.build,perturbation_policy={**POLICY,'seed':9})
        changed=deepcopy(args);changed[0]['context']+=' change'
        with self.assertRaisesRegex(ValueError,'POLICY_PLAN_MISMATCH'):g01.run(ctx,*changed,0,prior,p.build,perturbation_policy=POLICY)

    def test_v2_loader_snapshot_guard_and_legacy_no_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);hp=root/'hyper.json';hp.write_text(json.dumps({'generation':{'run':{'perturbation_policy':POLICY}}}));settings={'hyperparameter_path':str(hp)}
            self.assertEqual(load_run('generation',hp)['perturbation_policy'],POLICY)
            self.assertEqual(bind(settings,root)['perturbation_policy'],POLICY)
            self.assertEqual(bind(settings,root,resume=True)['perturbation_policy'],POLICY)
            hp.write_text(json.dumps({'generation':{'run':{}}}))
            with self.assertRaisesRegex(ValueError,'SNAPSHOT_MISMATCH'):bind(settings,root,resume=True)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(__import__('finarch.dataset.90-operations.schedule_settings', fromlist=['*']), 'load_run',return_value={}):self.assertEqual(bind({},Path(tmp)),{})
            self.assertFalse((Path(tmp)/'02-generation').exists())

    def test_existing_legacy_run_cannot_opt_in_and_bad_policy_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'02-generation/01-round').mkdir(parents=True)
            with patch.object(__import__('finarch.dataset.90-operations.schedule_settings', fromlist=['*']), 'load_run',return_value={'perturbation_policy':POLICY}):
                with self.assertRaisesRegex(ValueError,'NEW_GENERATION_RUN'):bind({},root)
        for bad in ({'name':'bounded-coefficients-v1','seed':True},{'name':'other','seed':1},{**POLICY,'enabled':True}):
            with self.assertRaises(ValueError):validate(bad)

    def test_local_rejection_never_invokes_llm_handler(self):
        args=fixture('0')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'prep';config=root/'config.json'
            driver.write(config,{'perturbation_policy':POLICY})
            for name,value in zip(('data.json','03-calculation/02-prepare-code/03-program.json','04-graph/04-save-graph/01-graph.json'),args):driver.write(source/name,value)
            with patch.object(driver,'invoke',side_effect=AssertionError('API')) as api,patch.object(driver.g04_exception_handler,'run',side_effect=AssertionError('handler')) as handler:
                result=driver.process(root,root/'02-generation/01-round','test-0001',0,config,{'test-0001':{'case_path':'prep'}},{})
            self.assertEqual(result['disposition'],'COEFFICIENT_POLICY_BLOCKED');self.assertFalse(result['retryable'])
            api.assert_not_called();handler.assert_not_called()
            sidecar=root/result['path']/'01-perturbation/04-coefficient-selection.json'
            self.assertEqual(len(json.loads(sidecar.read_text())['attempts']),2)

    def test_saved_examples_hashes_and_read_only_viewer(self):
        import hashlib
        from finarch.dataset.viewer.server import batch_data
        root=PROJECT/'reports/run/20260916-coefficients-v1'
        manifest=json.loads((root/'manifest.json').read_text())
        for ref in manifest['inputs']:self.assertEqual(hashlib.sha256((PROJECT/ref['path']).read_bytes()).hexdigest(),ref['sha256'])
        with patch.object(p,'build',side_effect=AssertionError('recompute')),patch.object(Path,'write_text',side_effect=AssertionError('write')):
            report=batch_data(PROJECT/'reports/run',root.name)['batch']['coefficient_policy']
            self.assertEqual(len(report['records']),8);self.assertEqual(report['model_calls'],0)
            for family,expected in [('VALUE',{'0.9','1.1'}),('RELATION',{'0.5','2'})]:
                self.assertEqual({r['selection']['selected_factor'] for r in report['records'] if r['family']==family},expected)

    def test_actual_stage_route_loads_v2_policy_and_records_without_api(self):
        args=real()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);hp=root/'hyper.json';hp.write_text(json.dumps({'generation':{'run':{'perturbation_policy':POLICY}}}))
            driver.write(root/'config.json',{'hyperparameter_path':str(hp)})
            source=root/'01-preparation/test-0001'
            for name,value in zip(('data.json','03-calculation/02-prepare-code/03-program.json','04-graph/04-save-graph/01-graph.json'),args):driver.write(source/name,value)
            with patch.object(driver,'invoke',side_effect=AssertionError('API')),patch.object(driver.g04_exception_handler,'run',side_effect=AssertionError('handler')):
                result=driver.run(root,'test-0001',indices=[0],only_stage='01-perturbation',approved={'test-0001':{'case_path':'01-preparation/test-0001'}})
            saved=json.loads((root/'02-generation/01-round/test-0001/01-ic-value-before/run.json').read_text())
            self.assertEqual(saved['plan']['coefficient_selection']['policy'],POLICY)
            self.assertEqual(saved['status'],'PAUSED')
            before=(root/'02-generation/01-round/test-0001/runtime-config.json').read_bytes()
            hp.write_text(json.dumps({'generation':{'run':{'perturbation_policy':{**POLICY,'seed':99}}}}))
            with self.assertRaisesRegex(ValueError,'SNAPSHOT_MISMATCH'):driver.run(root,'test-0001',indices=[0],only_stage='01-perturbation',approved={'test-0001':{'case_path':'01-preparation/test-0001'}})
            self.assertEqual((root/'02-generation/01-round/test-0001/runtime-config.json').read_bytes(),before)

if __name__=='__main__':unittest.main()
