"""Register exactly one approved queue with the existing four-GPU supervisor."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path('/home/clink-wooix/workspace/finarch/experiments')
WORKER=Path('/home/clink-wooix/workspace/vllm/gpu-residency/worker.py')
IDENT='finarch-generated-qwen-20261003'


def main():
    if json.loads((ROOT/'preflight-summary.json').read_text()).get('status')!='PASS':
        raise ValueError('ALL_PREFLIGHTS_REQUIRED')
    original=WORKER.read_text()
    if IDENT in original: raise ValueError('HOOK_ALREADY_INSTALLED')
    needle='    def start_experiment(self,request):\n'
    if original.count(needle)!=1: raise ValueError('UNKNOWN_WORKER_VERSION')
    addition='''    def start_experiment(self,request):
        if request.get('runner') == 'finarch_generated_20261003':
            if self.slot != 'core' or self.args.gpus != 4 or request.get('id') != 'finarch-generated-qwen-20261003':
                raise ValueError('GENERATED_EVALUATION_HANDOFF_MISMATCH')
            project = Path('/home/clink-wooix/workspace/finarch/experiments')
            if read(project/'preflight-summary.json').get('status') != 'PASS':
                raise ValueError('GENERATED_PREFLIGHT_REQUIRED')
            write(self.consumed_path(request), {'at':stamp(), 'state':'STARTED',
                'runner':request['runner'], 'pod_uid':os.environ.get('POD_UID'), 'automatic_retry':False})
            code = ('import sys, runpy; sys.path.insert(0, ' + repr(str(project/'src'))
                + '); runpy.run_module(\"finarch.experiments.a100.generated_runner\", run_name=\"__main__\")')
            self.spawn([sys.executable, '-u', '-B', '-c', code], role='experiment')
            self.mode='EXPERIMENT'; self.publish(experiment_request=request['id'])
            return
'''
    changed=original.replace(needle,addition)
    ast.parse(changed)
    provenance=ROOT/'provenance';provenance.mkdir(exist_ok=True)
    (provenance/'worker.before.py').write_text(original)
    request=WORKER.parent/'experiment-request.json'
    (provenance/'experiment-request.before.json').write_bytes(request.read_bytes())
    temporary=WORKER.with_suffix('.generated.tmp');temporary.write_text(changed);temporary.replace(WORKER)
    value={'id':IDENT,'enabled':True,'runner':'finarch_generated_20261003','gpu_count':4,
        'run_order':['Qwen/Qwen3-8B','Qwen/Qwen3-14B','Qwen/Qwen3.8-27B'],
        'authorization':'User requested generated TAT-QA and FinanceReasoning evaluation, sealed recovery, and local Analysis.'}
    temporary=request.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2));temporary.replace(request)
    (provenance/'supervisor-hook.json').write_text(json.dumps({'before_sha256':hashlib.sha256(original.encode()).hexdigest(),
        'after_sha256':hashlib.sha256(changed.encode()).hexdigest(),'request':value},indent=2))
    print('HOOK_INSTALLED_REQUIRES_SUPERVISOR_RESTART')


if __name__=='__main__':main()
