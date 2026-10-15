"""Offline scheduling: growth before completion and parameter-driven limits."""
import threading
import unittest
import tempfile
import json
from pathlib import Path
run = __import__('finarch.dataset.90-operations.adaptive_schedule', fromlist=['run']).run
adjusted_limit = __import__('finarch.dataset.90-operations.adaptive_schedule', fromlist=['adjusted_limit']).adjusted_limit
load = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['load']).load

class AdaptiveScheduleTests(unittest.TestCase):
    def test_growth_does_not_wait_for_completion(self):
        release=threading.Event();states=[]
        settings={'initial_concurrency':1,'monitor_interval_seconds':0.02,'cpu_threshold_percent':50,'increase_by':10}
        def worker(item):
            if not release.wait(2):raise RuntimeError('monitor did not grow')
            return {'status':'PASS'}
        def monitor(value):
            states.append(value)
            if value['active']==11:release.set()
        result=list(run(range(11),worker,settings=settings,monitor=monitor,cpu_reader=lambda:10))
        self.assertEqual(len(result),11)
        self.assertTrue(any(s['active']==11 and s['completed']==0 for s in states))
        self.assertEqual(states[-1]['status'],'COMPLETED')
    def test_threshold_and_total(self):
        self.assertEqual(adjusted_limit(2,40,49,threshold=50,increase_by=10),12)
        self.assertEqual(adjusted_limit(2,40,50,threshold=50,increase_by=10),2)
        self.assertEqual(adjusted_limit(2,5,0,threshold=50,increase_by=10),5)
    def test_parameters_are_loaded(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'h.json';p.write_text(json.dumps({'preparation':{'schedule':{'concurrency':7,'monitor_interval_seconds':9,'cpu_threshold_percent':42,'increase_by':4},'run':{}}}))
            settings=load('preparation',p)
            self.assertEqual(settings['initial_concurrency'],7)
            self.assertEqual(settings['increase_by'],4)
            self.assertEqual(settings['monitor_interval_seconds'],9)
    def test_worker_failure_does_not_drop_other_cases(self):
        def worker(n):
            if n==1:raise ValueError('failure')
            return {'status':'PASS'}
        states=[]
        values=list(run(range(3),worker,settings=load('preparation'),monitor=states.append,cpu_reader=lambda:60))
        self.assertEqual(len(values),3)
        self.assertEqual(states[-1]['failed'],1)
    def test_phase_model_selection(self):
        from unittest.mock import patch
        from finarch.shared.providers.profiles import selected_profile, DEFAULT
        with patch.object(__import__('finarch.dataset.90-operations.schedule_settings', fromlist=['*']), 'load_run',return_value={'models':{'generation_profile':'luna-low','validation_profile':'luna-medium'}}):
            profile=selected_profile(DEFAULT,'01-preparation.03-calculation.pot',phase='preparation')
            self.assertEqual(profile['id'],'luna-low')
    def test_run_modules_do_not_manage_batches(self):
        import importlib
        for phase,prefix in [('preparation','prepare'),('generation','generate')]:
            module=importlib.import_module(f'finarch.dataset.{"01-preparation" if phase == "preparation" else "02-generation"}.{prefix}_run')
            self.assertIn('name',__import__('inspect').signature(module.run).parameters)
            self.assertNotIn('schedule_cases',vars(module))
