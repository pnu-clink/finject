"""Install a single named evaluation handoff in the existing GPU-2 supervisor."""
import ast
import hashlib
import json
from pathlib import Path

root = Path('/home/clink-wooix/workspace/fexperiment/finarch-a100-20260928')
worker = Path('/home/clink-wooix/workspace/vllm/gpu-residency/worker.py')
original = (root / 'provenance/worker.original.py').read_text()
if worker.read_text() != original:
    raise ValueError('WORKER_CHANGED_SINCE_SNAPSHOT')
needle = '    def start_experiment(self,request):\n'
addition = '''    def start_experiment(self,request):
        if request.get('runner') == 'finarch_a100_20260928':
            if self.slot != 'core' or self.args.gpus != 4 or request.get('id') != 'finarch-a100-20260928':
                raise ValueError('A100_EVALUATION_HANDOFF_MISMATCH')
            project = Path('/home/clink-wooix/workspace/fexperiment/finarch-a100-20260928')
            if not (project/'src/finarch/experiments/a100/remote.py').is_file():
                raise ValueError('A100_EVALUATION_RUNNER_MISSING')
            write(self.consumed_path(request), {'at':stamp(), 'state':'STARTED',
                  'runner':request['runner'], 'pod_uid':os.environ.get('POD_UID'),
                  'automatic_retry':False})
            code = "import sys; sys.path.insert(0, " + repr(str(project/'src')) + "); from finarch.experiments.a100.remote import main; main()"
            self.spawn([sys.executable, '-u', '-B', '-c', code], role='experiment')
            self.mode='EXPERIMENT'; self.publish(experiment_request=request['id'])
            return
'''
if original.count(needle) != 1:
    raise ValueError('WORKER_INSERTION_POINT_MISMATCH')
updated = original.replace(needle, addition)
ast.parse(updated)
worker.write_text(updated)
(root / 'provenance/worker-handoff.json').write_text(json.dumps({
    'old_sha256': hashlib.sha256(original.encode()).hexdigest(),
    'new_sha256': hashlib.sha256(updated.encode()).hexdigest(),
    'scope': 'One named GPU-2 core request; no GPU-3 changes; no automatic retry'}, indent=2))
