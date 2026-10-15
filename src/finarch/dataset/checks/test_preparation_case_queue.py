"""Interrupted IDs restart without old feedback; completed cases remain intact."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from contextlib import nullcontext
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read

CaseQueue=importlib.import_module('finarch.dataset.01-preparation.prepare_queue').CaseQueue

class CaseQueueTests(unittest.TestCase):
    def setup_queue(self,root):
        input_path=root/'input.json';input_path.write_text('[]')
        names=['test-0001','test-0002','test-0003']
        write(root/'input-selection.json',{'cases':names})
        return SimpleNamespace(path=input_path),names,['01-source','02-review']

    def test_interrupted_ids_restart_and_completed_case_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inputs,names,selected=self.setup_queue(root)
            queue=CaseQueue(root,inputs,names,selected)
            write(root/'01-preparation'/names[0]/'run.json',{'status':'PASS','input_id':names[0]})
            queue.complete(names[0]);queue.observe([names[1]])
            old=root/'01-preparation'/names[1]/'01-round/feedback.json'
            write(old,{'guidance':'old feedback'})
            queue.close(interrupted=True)
            restarted=CaseQueue(root,inputs,names,selected,resume=True)
            self.assertEqual(restarted.targets,names[1:])
            self.assertFalse((root/'01-preparation'/names[1]).exists())
            self.assertTrue((root/'restart-history/002-preparation'/names[1]/'01-round/feedback.json').is_file())
            self.assertEqual(read(root/'01-preparation'/names[0]/'run.json')['status'],'PASS')
            self.assertEqual(restarted.state['pending_ids'],names[1:])

    def test_explicit_completed_id_can_restart_and_input_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inputs,names,selected=self.setup_queue(root)
            queue=CaseQueue(root,inputs,names,selected)
            queue.complete(names[0]);queue.close(interrupted=True)
            restarted=CaseQueue(root,inputs,[names[0]],selected,resume=True,explicit=True)
            self.assertEqual(restarted.targets,[names[0]])
            self.assertNotIn(names[0],restarted.state['completed_ids'])
            inputs.path.write_text('[1]')
            with self.assertRaisesRegex(ValueError,'RESUME_INPUT_CHANGED'):
                CaseQueue(root,inputs,names,selected,resume=True)

    def test_duplicate_ids_rejected_before_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inputs,names,selected=self.setup_queue(root)
            with self.assertRaisesRegex(ValueError,'INVALID_QUEUE_CASE_IDS'):
                CaseQueue(root,inputs,[names[0],names[0]],selected)
            self.assertFalse((root/'01-preparation/schedule-state.json').exists())

    def test_existing_outputs_require_explicit_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inputs,names,selected=self.setup_queue(root)
            marker=root/'01-preparation'/names[0]/'run.json';write(marker,{'status':'PASS'})
            with self.assertRaisesRegex(ValueError,'EXISTING_CASE_REQUIRES_RESUME'):
                CaseQueue(root,inputs,names,selected)
            self.assertEqual(read(marker),{'status':'PASS'})

    def test_scheduler_registers_only_unfinished_ids_and_aggregates_in_parent(self):
        import threading
        schedule=importlib.import_module('finarch.dataset.01-preparation.prepare_schedule')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inputs,names,selected=self.setup_queue(root)
            write(root/'input-selection.json',{'cases':names,'input_path':str(inputs.path)})
            write(root/'config.json',{})
            queue=CaseQueue(root,inputs,names,selected)
            write(root/'01-preparation'/names[0]/'run.json',{'status':'PASS','input_id':names[0]})
            write(root/'01-preparation'/names[1]/'01-round/old-feedback.json',{'old':True})
            queue.complete(names[0]);queue.observe([names[1]]);queue.close(interrupted=True)
            seen=[];writers=[];parent=threading.get_ident()
            def plan(path,config,cases):
                return inputs,{'run_phase':'preparation'},Path('profiles.toml'),{'cases':cases,'case_count':len(cases)}
            def worker(inputs,name,path,config,steps,settings):
                self.assertEqual(read(config)['run_phase'],'preparation')
                self.assertEqual(read(config)['profiles_path'],'profiles.toml')
                self.assertEqual(steps[0],'01-source');self.assertFalse(path.exists())
                seen.append(name);result={'status':'PASS','input_id':name}
                write(path/'run.json',result)
                return result
            original_save=CaseQueue.save
            def save(obj):writers.append(threading.get_ident());original_save(obj)
            settings={'mode':'fixed','initial_concurrency':2,'monitor_interval_seconds':0.01,
                      'increase_by':1,'cpu_threshold_percent':50,'max_rounds':3}
            with patch.object(schedule,'plan',side_effect=plan),patch.object(schedule,'run_case_rounds',side_effect=worker),\
                 patch.object(schedule,'measure',return_value=nullcontext()),\
                 patch.object(__import__('finarch.dataset.90-operations.schedule_settings', fromlist=['*']), 'for_config',return_value=settings),\
                 patch.object(__import__('finarch.dataset.90-operations.preparation_gate', fromlist=['*']), 'evaluate'),patch.object(CaseQueue,'save',save):
                result=schedule.run_selected(None,None,None,selected,bundle=root,resume=True)
                again=schedule.run_selected(None,None,None,selected,bundle=root,resume=True)
            self.assertEqual(set(seen),set(names[1:]));self.assertEqual(result['processed'],3)
            self.assertEqual(result['status'],'COMPLETED');self.assertEqual(set(writers),{parent})
            self.assertEqual(again['status'],'NO_UNFINISHED_CASES')
            self.assertEqual(read(root/'01-preparation/schedule-state.json')['pending_ids'],[])

if __name__=='__main__':unittest.main()
