"""Run the frozen generated-data Qwen queue on four reserved GPUs."""
import argparse
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request

from . import worker, sync_protocol as protocol
store = importlib.import_module('finarch.experiments.90-operations.storage')


def publish(path, value):
    store.write(path, value)
    # The GPU Pod runs as root; the SSH recovery owner must read atomic records.
    if os.geteuid() == 0:
        os.chown(path, 1289, 1289)


def token_check(root, snapshot):
    from transformers import AutoTokenizer
    from .wire import body
    tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True)
    runtime = store.read(root/'01_evaluation/01_preparation/a100-runtime.json')
    model, = store.read(root/'config.json')['evaluation']['models']
    rows = store.rows(root/'01_evaluation/02_request'/model['key']/'manifest.jsonl')
    maximum = 0
    over = []
    with (root/'01_evaluation/01_preparation/token-counts.jsonl').open('w') as handle:
        for index, req in enumerate(rows, 1):
            payload = body(req, runtime)
            ids = tokenizer.apply_chat_template(payload['messages'], tokenize=True,
                add_generation_prompt=True, **payload['chat_template_kwargs'])
            if hasattr(ids, 'keys'): ids = ids['input_ids']
            if not ids or type(ids[0]) is not int: raise ValueError('INVALID_TOKENIZER_OUTPUT')
            required = len(ids) + req['max_output_tokens']
            maximum = max(maximum, required)
            if required > runtime['max_model_len']: over.append(req['trial_id'])
            handle.write(json.dumps({'trial_id':req['trial_id'],'input_tokens':len(ids),'required_context':required})+'\n')
            if index % 1000 == 0: print(root.name, 'TOKEN_PREFLIGHT',index,len(rows),flush=True)
    summary={'status':'PASS' if not over else 'CONTEXT_ADJUSTMENT_REQUIRED','requests':len(rows),
        'max_required_context':maximum,'max_model_len':runtime['max_model_len'],
        'over_limit':over,'truncation':False,'tokenizer_snapshot':str(snapshot)}
    publish(root/'01_evaluation/01_preparation/token-preflight.json',summary)
    if over: raise ValueError('CONTEXT_ADJUSTMENT_REQUIRED:'+root.name)
    return summary


def snapshot_for(entry):
    return Path('/home/clink-wooix/.cache/huggingface/hub')/('models--'+entry['model'].replace('/','--'))/'snapshots'/entry['revision']


def seal(root):
    base = root.parent.parent.parent/'recovery'
    base.mkdir(exist_ok=True)
    files=protocol.inventory(root,['01_evaluation/03_execution','01_evaluation/01_preparation/token-counts.jsonl',
        '01_evaluation/01_preparation/token-preflight.json','server-command.json'])
    receipt={'run_id':root.name,'files':files,'status':'SEALED','new_model_calls':0}
    path=base/(root.name+'.tar.gz')
    publish(root/'recovery-manifest.json',receipt)
    with tarfile.open(path.with_suffix('.tmp'),'w:gz') as tar:
        for name in files: tar.add(root/name,arcname=name,recursive=False)
        tar.add(root/'recovery-manifest.json',arcname='recovery-manifest.json',recursive=False)
    path.with_suffix('.tmp').replace(path)
    publish(base/(root.name+'.ready.json'),{'archive':str(path),'sha256':protocol.sha(path),
        'run_id':root.name,'files':len(files)})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args()
    project=store.PROJECT
    plan=store.read(project/'evaluation-plan.json')
    status_path=project/'queue-state.json'
    if args.preflight_only:
        checks=[]
        for entry in plan['runs']:
            root=project/'reports/experiments-run'/entry['run_id']
            checks.append(token_check(root,snapshot_for(entry)))
        publish(project/'preflight-summary.json',{'status':'PASS','runs':len(checks),'new_model_calls':0})
        return
    if store.read(project/'preflight-summary.json',{}).get('status')!='PASS':
        raise ValueError('ALL_TOKEN_PREFLIGHTS_REQUIRED')
    completed=[]
    for entry in plan['runs']:
        root=project/'reports/experiments-run'/entry['run_id']
        runtime=store.read(root/'01_evaluation/01_preparation/a100-runtime.json')
        snapshot=snapshot_for(entry)
        publish(status_path,{'status':'STARTING_SERVER','active_run':root.name,'completed':completed})
        command=[sys.executable,'-m','vllm.entrypoints.openai.api_server','--model',str(snapshot),
            '--served-model-name',entry['model'],'--dtype','bfloat16','--tensor-parallel-size','4',
            '--max-model-len',str(runtime['max_model_len']),'--max-num-seqs',str(runtime['max_num_seqs']),
            '--max-num-batched-tokens',str(runtime['max_num_batched_tokens']),
            '--gpu-memory-utilization',str(runtime['gpu_memory_utilization']),
            '--no-enable-prefix-caching','--enable-chunked-prefill','--reasoning-parser','qwen3',
            '--generation-config','vllm','--host','127.0.0.1','--port','18000']
        env=os.environ.copy();env['TOKENIZERS_PARALLELISM']='false'
        env['VLLM_USE_V2_MODEL_RUNNER']='0'
        publish(root/'server-command.json',{'argv':command,'model_revision':entry['revision'],
                    'prefix_caching':False,'VLLM_USE_V2_MODEL_RUNNER':'0'})
        with (root/'server.log').open('ab') as log:
            server=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            try:
                endpoint='http://127.0.0.1:18000'
                deadline=time.monotonic()+1200
                while True:
                    if server.poll() is not None: raise RuntimeError('VLLM_SERVER_EXITED:'+str(server.returncode))
                    try:
                        with urllib.request.urlopen(endpoint+'/health',timeout=3) as response:
                            if response.status==200: break
                    except Exception: pass
                    if time.monotonic()>deadline: raise RuntimeError('VLLM_START_TIMEOUT')
                    time.sleep(5)
                publish(status_path,{'status':'EVALUATING','active_run':root.name,'completed':completed})
                result=worker.run(root,[endpoint],str(snapshot),plan['authorization'])
                if result['status']!='EVALUATION_RECEIVED': raise RuntimeError('EVALUATION_NOT_COMPLETE:'+str(result))
                seal(root)
                completed.append(root.name)
                publish(status_path,{'status':'RUN_COMPLETE','active_run':root.name,'completed':completed})
            finally:
                if server.poll() is None:
                    os.killpg(server.pid,signal.SIGTERM)
                    try: server.wait(timeout=120)
                    except subprocess.TimeoutExpired:
                        os.killpg(server.pid,signal.SIGKILL);server.wait()
                time.sleep(5)
    publish(status_path,{'status':'COMPLETE','completed':completed})


if __name__=='__main__':
    try: main()
    except Exception as error:
        publish(store.PROJECT/'queue-state.json',{'status':'FAILED','error':str(error)})
        raise
