"""Offline fixed concurrency, isolated artifacts and synchronized aggregate logs."""
import importlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
run = __import__('finarch.dataset.90-operations.adaptive_schedule', fromlist=['run']).run
for_config = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['for_config']).for_config
from finarch.shared.providers.api_limits import request_slot

ROOT=(Path(__file__).resolve().parent / '../../../..').resolve()
RunLogs=importlib.import_module('finarch.shared.run_logging.run_logs').RunLogs

class FixedApiTests(unittest.TestCase):
    def test_api_uses_fixed_200_and_cli_remains_adaptive(self):
        settings=for_config('preparation',ROOT/'config/llm.json')
        self.assertEqual((settings['mode'],settings['initial_concurrency']),('fixed',200))
        with patch('finarch.shared.providers.profiles.selected_profile',return_value={'transport':'cli'}):
            self.assertEqual(for_config('preparation',ROOT/'config/llm.json')['mode'],'adaptive')

    def test_200_workers_keep_distinct_artifacts_and_one_log_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ready=threading.Barrier(200,timeout=15)
            states=[];threads=set();seen=set();lock=threading.Lock();active=peak=0
            settings={'mode':'fixed','initial_concurrency':200,'monitor_interval_seconds':0.01,
                      'cpu_threshold_percent':50,'increase_by':10}
            logs=RunLogs(root/'logs','check')
            def worker(n):
                nonlocal active,peak
                with lock:active+=1;peak=max(peak,active)
                if n<200:ready.wait()
                case=root/f'test-{n:04d}';case.mkdir()
                with (case/'response-schema.json').open('x') as f:json.dump({'case':n},f)
                logs.write('detail.log','collision-check',value={'case':n})
                with lock:active-=1
                return {'status':'PASS','case':n}
            def monitor(value):
                threads.add(threading.get_ident());states.append(value)
            for n,result in run(range(250),worker,settings=settings,monitor=monitor,
                                cpu_reader=lambda: self.fail('API mode must not read CPU')):
                seen.add(n);self.assertEqual(result['status'],'PASS',result)
            self.assertEqual(len(seen),250);self.assertEqual(peak,200)
            self.assertEqual(threads,{threading.get_ident()})
            self.assertTrue(all(s['limit']==200 and s['active']<=200 for s in states))
            rows=[json.loads(line) for line in (root/'logs/run/check/default.log').read_text().splitlines()]
            self.assertEqual([r['sequence'] for r in rows],list(range(1,251)))
            self.assertEqual(len({r['collision-check']['case'] for r in rows}),250)
            self.assertEqual(len(list(root.glob('test-*/response-schema.json'))),250)

    def test_nested_api_requests_share_cap_and_exceptions_release_slot(self):
        lock=threading.Lock();active=peak=0
        def task(n):
            nonlocal active,peak
            try:
                with request_slot():
                    with lock:active+=1;peak=max(peak,active)
                    try:
                        time.sleep(0.01)
                        if n==0:raise RuntimeError('simulated failure')
                    finally:
                        with lock:active-=1
            except RuntimeError:pass
        with patch('finarch.shared.providers.api_limits.api_concurrency',return_value=4):
            with ThreadPoolExecutor(max_workers=20) as pool:list(pool.map(task,range(40)))
        self.assertEqual(peak,4);self.assertEqual(active,0)

if __name__=='__main__':unittest.main()
