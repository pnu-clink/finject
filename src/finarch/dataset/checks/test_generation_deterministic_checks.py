"""Bounded recovery must not use hidden answers or unrelated numeric matches."""
import unittest
from importlib import import_module
from unittest.mock import Mock
inv=import_module('finarch.dataset.02-generation.01-perturbation.ea_inversion')
stage=import_module('finarch.dataset.02-generation.03-validation.stage')

class DeterministicChecks(unittest.TestCase):
    def fixture(self):
        source={'question':'Find x','context':'x 4 y 6 total 10'}
        observation={**source,'context':'x  y 6 total 10'}
        patches=[{'start':2,'end':3,'before':'4','text':''}]
        graph={'nodes':[{'id':'x','kind':'fact','fact_id':'x'}, {'id':'y','kind':'fact','fact_id':'y'}, {'id':'op','kind':'operation','operator':'+','inputs':['x','y']}, {'id':'t','kind':'variable','variable':'total','inputs':['op']}], 'variables':{'total':'t'}}
        inputs={'facts':{'y':{'span':[6,7],'text':'6'}},'bindings':[{'variable':'total','field':'context','span':[14,16],'text':'10'}]}
        return observation,source,patches,graph,'x',inputs
    def test_recover_and_substitute(self):
        result=inv.screen(*self.fixture())
        self.assertEqual(result['status'],'RECOVERABLE')
        self.assertEqual(result['witnesses'][0]['recovered_value'],'4')
    def test_no_binding_cannot_use_cached_answer(self):
        args=list(self.fixture());args[-1]['bindings']=[];args[3]['nodes'][-1]['computed']='10'
        self.assertEqual(inv.screen(*args)['status'],'NOT_EVALUATED')
    def test_deleted_binding_rejected(self):
        args=list(self.fixture());args[-1]['bindings'][0].update(span=[2,3],text='4')
        self.assertEqual(inv.screen(*args)['status'],'NOT_EVALUATED')
    def test_gate_preserves_audit_when_unavailable(self):
        obs,source,patches,graph,target,inputs=self.fixture();inputs['bindings']=[]
        result={'status':'PASS'}
        stage.gg04_screen_recovery(Mock(),{},dict(request=source,graph=graph,target=target,recovery_inputs=inputs),obs,'EA',result,patches)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['recovery_screen']['status'],'NOT_EVALUATED')
    def test_gate_blocks_recoverable(self):
        obs,source,patches,graph,target,inputs=self.fixture();result={'status':'PASS'}
        stage.gg04_screen_recovery(Mock(),{},dict(request=source,graph=graph,target=target,recovery_inputs=inputs),obs,'EA',result,patches)
        self.assertEqual(result['reason'],'EA_RECOVERABLE_TARGET')

if __name__=='__main__':unittest.main()

class SourceExactChecks(unittest.TestCase):
    def test_saved_source_pairs_and_unplanned_edit(self):
        import json
        from pathlib import Path
        from copy import deepcopy
        check=import_module('finarch.dataset.02-generation.03-validation.source_validation').validate
        root=(Path(__file__).resolve().parent / '../../../..').resolve()
        records=json.loads((root/'reports/run/20260916-quality-v1/quality_scope.json').read_text())['records']
        count=0
        for row in records:
            if '/03-ic-source-type-1' not in row['id'] and '/04-ic-source-type-2' not in row['id']:continue
            path=root/row['references']['generation']['path'];saved=json.loads(path.read_text())
            dependency=json.loads((path.parent/'02-generate-text/00-value-dependency.json').read_text())
            basepath=root/'reports/run/20260916-001'/dependency['source']
            base=json.loads((basepath/'run.json').read_text())
            index=2 if '/03-' in row['id'] else 3
            args=[saved['plan'],saved['generation_request'],saved['generation_response'],saved['observation'],saved['patches'],base,dependency,index]
            self.assertEqual(check(*args)['status'],'PASS',row['id'])
            bad=deepcopy(args);bad[3]['context']+=' unauthorized change'
            self.assertEqual(check(*bad)['status'],'FAIL')
            count+=1
        self.assertGreater(count,0)
