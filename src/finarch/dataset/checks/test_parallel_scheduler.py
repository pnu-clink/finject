"""Offline concurrency limits, dependency barriers, and stable output checks."""
import tempfile
import threading
import unittest
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
g = __import__('finarch.dataset.02-generation.generate_schedule', fromlist=['*'])
preparation_results = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['preparation_results']).preparation_results
limit = __import__('finarch.dataset.02-generation.operations.parallel_scheduler', fromlist=['limit']).limit

class ParallelTests(unittest.TestCase):
    def test_preparation_ten_overlap_and_stable_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();names=[str(i) for i in range(20)]
            barrier=threading.Barrier(10,timeout=5);lock=threading.Lock();active=peak=0
            def worker(inputs,name,path,config):
                nonlocal active,peak
                with lock:active+=1;peak=max(peak,active)
                barrier.wait()
                with lock:active-=1
                return {'input_id':name,'status':'PASS'}
            list(preparation_results(root,None,names,{},worker))
            self.assertEqual(peak,10)
            self.assertEqual([r['input_id'] for r in g.read(root/'01-preparation/summary.json')['results']],names)
            self.assertEqual(g.read(root/'01-preparation/queue.json')['status'],'COMPLETED')

    def test_generation_two_cases_and_source_barrier(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();g.write(root/'config.json',{})
            names=['a','b','c','d'];first={n:threading.Barrier(5,timeout=5) for n in names}
            source={n:threading.Barrier(2,timeout=5) for n in names}
            two=threading.Barrier(2,timeout=5);lock=threading.Lock();active=set();peak=0;done={n:set() for n in names}
            def process(bundle,round_dir,name,index,config,approved,latest,value_ready=None):
                nonlocal peak
                with lock:
                    if name not in active:active.add(name);peak=max(peak,len(active))
                    self.assertLessEqual(len(active),2)
                if index not in (2,3):
                    first[name].wait()
                    if index==0:two.wait()
                else:
                    with lock:self.assertTrue({0,1,4,5,6} <= done[name])
                    source[name].wait()
                with lock:
                    done[name].add(index)
                    if len(done[name])==7:active.remove(name)
                return {'label':g.TYPES[index][2],'status':'PASS','path':str((round_dir/name/g.TYPES[index][0]).relative_to(root))}
            with patch.object(g,'require_generation_inputs',return_value={n:{} for n in names}),patch.object(g,'measure',return_value=nullcontext()),patch.object(g,'process',side_effect=process),patch('finarch.dataset.viewer.reports.completion_report.build'):
                result=g.run(root,1)
            self.assertEqual(peak,2);self.assertEqual(result['status'],'PASS')
            self.assertTrue(all(len(items)==7 for items in done.values()))

    def test_value_failure_releases_paired_waiter(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();g.write(root/'config.json',{})
            released=threading.Event()
            def process(bundle,round_dir,name,index,config,approved,latest,value_ready=None):
                if index==0:raise RuntimeError('author failed before initialization')
                if index==1:
                    self.assertEqual(value_ready.result(timeout=3),{});released.set()
                return {'label':g.TYPES[index][2],'status':'PASS','path':str((round_dir/name/g.TYPES[index][0]).relative_to(root))}
            with patch.object(g,'require_generation_inputs',return_value={'a':{}}),patch.object(g,'measure',return_value=nullcontext()),patch.object(g,'process',side_effect=process),self.assertRaisesRegex(RuntimeError,'author failed'):
                g.run(root,1)
            self.assertTrue(released.is_set())
            self.assertEqual(g.read(root/'02-generation/01-round/queue.json')['status'],'ERROR')

    def test_same_value_sentence_shared_before_first_audit_finishes(self):
        from concurrent.futures import Future, ThreadPoolExecutor
        from unittest.mock import MagicMock
        ready=Future();audits=threading.Barrier(2,timeout=3)
        sample={'context':'original','question':'question'}
        slot={'start':0,'end':0,'before':'','element_ids':[]}
        plan={'request':{'context':'original','edit_slots':[slot]},'anchor':[0,1],'intent':{},'graph':{},'execution':{}}
        ctx=MagicMock();ctx.trace.activate.side_effect=lambda:nullcontext();ctx.trace.span.side_effect=lambda *a,**k:nullcontext()
        def audit(*args):
            audits.wait()
            return {'status':'PASS'}
        def check(request,response):
            return {'context':response['patches'][0]['text'],'question':'question'},response['patches']
        with patch.object(g,'RunContext',return_value=ctx),patch.object(g,'read',return_value=sample),patch.object(g,'build',return_value=plan),patch.object(g,'invoke',return_value={'patches':[dict(slot,text='Shared new claim.')]}),patch.object(g,'check_response',side_effect=check),patch.object(g,'audit_one',side_effect=audit),patch.object(g,'observation_hash',return_value='hash'):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(g.process,Path('/tmp/check'),Path('/tmp/check/02-generation/01-round'),'a',i,{}, {'a':{'case_path':'a'}},{},ready) for i in (0,1)]
                values=[f.result(timeout=5) for f in futures]
        self.assertTrue(all(v['status']=='PASS' for v in values))
        self.assertEqual(values[0]['patches'][0]['text'].strip(),values[1]['patches'][0]['text'].strip())

    def test_limits_reject_invalid(self):
        for stage,value in [('preparation',11),('generation',3),('generation',True),('preparation',0)]:
            with self.assertRaises(ValueError):limit({'parallelism':{stage:value}},stage)

if __name__=='__main__':unittest.main()
