"""Recover sealed GPU outputs, verify every byte, then run local Analysis in order."""
import argparse
import importlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile
import time

store=importlib.import_module('finarch.experiments.90-operations.storage')
analysis=importlib.import_module('finarch.experiments.02-analysis.pipeline')
collection=importlib.import_module('finarch.experiments.a100.live_collection')
protocol=importlib.import_module('finarch.experiments.a100.sync_protocol')
REMOTE='/home/clink-wooix/workspace/finarch/experiments'


def remote_json(path):
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','a100',
        'cat '+shlex.quote(path)],capture_output=True,text=True,timeout=30)
    return json.loads(result.stdout) if result.returncode==0 else None


def recover(root,archive):
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        for m in members:
            if not m.isfile() or m.name.startswith('/') or '..' in Path(m.name).parts:
                raise ValueError('UNSAFE_RECOVERY_MEMBER')
        receipt=json.load(tar.extractfile('recovery-manifest.json'))
        if receipt['run_id']!=root.name: raise ValueError('RECOVERY_RUN_MISMATCH')
        if {m.name for m in members} != set(receipt['files'])|{'recovery-manifest.json'}:
            raise ValueError('RECOVERY_FILE_SET_MISMATCH')
        with tempfile.TemporaryDirectory(dir=archive.parent) as name:
            staging=Path(name)
            tar.extractall(staging,filter='data')
            for relative,digest in receipt['files'].items():
                if protocol.sha(staging/relative)!=digest: raise ValueError('RECOVERY_HASH_MISMATCH:'+relative)
                target=protocol.safe(root,relative)
                if target.exists() and protocol.sha(target)!=digest:
                    raise ValueError('EXISTING_OUTPUT_CONFLICT:'+relative)
            for relative in receipt['files']:
                target=protocol.safe(root,relative)
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists(): (staging/relative).replace(target)
    store.write(root/'recovery-manifest.json',receipt)
    model,=store.read(root/'config.json')['evaluation']['models']
    base=root/'01_evaluation/03_execution'/model['key']
    state=store.read(base/'remote-state.json')
    requests=store.rows(root/'01_evaluation/02_request'/model['key']/'manifest.jsonl')
    expected={r['trial_id'] for r in requests}
    actual={p.parent.name for p in (base/'remote-results').glob('*/delivery.json')}
    if expected!=actual or state.get('completed')!=len(expected):
        raise ValueError('RECOVERY_REQUEST_COVERAGE_MISMATCH')
    metadata={p.name:store.read(p) for p in base.glob('*.json')}
    collection.collect(root,{'metadata':metadata,'state':state})
    store.event(root,'A100_SEALED_RECOVERY_VERIFIED',files=len(receipt['files']),requests=len(requests),new_model_calls=0)


def main(*, evaluation_only=False, start_run=None, remote_read_retries=0):
    audit=store.PROJECT/'reports/run/20261003-a100-generated-evaluation'
    timeout_retries_used = 0
    plan=store.read(audit/'evaluation-plan.json')
    entries = plan['runs']
    if start_run:
        names = [entry['run_id'] for entry in entries]
        if start_run not in names:
            raise ValueError('UNKNOWN_RECOVERY_START_RUN')
        entries = entries[names.index(start_run):]
    for entry in entries:
        root=store.PROJECT/'reports/experiments-run'/entry['run_id']
        store.write(audit/'recovery-state.json',{'status':'WAIT_REMOTE','active_run':root.name})
        while True:
            if (audit/'STOP').exists(): return
            try:
                ready=remote_json(REMOTE+'/recovery/'+root.name+'.ready.json')
                if ready: break
                activation=remote_json(REMOTE+'/activation.json')
                remote=remote_json(REMOTE+'/queue-state.json')
            except subprocess.TimeoutExpired as error:
                if timeout_retries_used >= remote_read_retries:
                    raise
                timeout_retries_used += 1
                delay = 60 * 2 ** (timeout_retries_used - 1)
                state = {'status':'WAIT_REMOTE','active_run':root.name,
                    'remote_read_error':str(error),'remote_read_retries_used':timeout_retries_used,
                    'remote_read_retry_limit':remote_read_retries,'backoff_seconds':delay}
                store.write(audit/'recovery-state.json',state)
                print(json.dumps(state), flush=True)
                time.sleep(delay)
                continue
            if activation and activation.get('status')=='FAILED':
                store.write(audit/'recovery-state.json',activation);return
            if remote and remote.get('status')=='FAILED':
                store.write(audit/'recovery-state.json',remote);return
            time.sleep(60)
        archive=audit/(root.name+'.tar.gz')
        if not archive.exists() or protocol.sha(archive)!=ready['sha256']:
            tmp=archive.with_suffix('.partial')
            subprocess.run(['scp','a100:'+ready['archive'],str(tmp)],check=True,timeout=3600)
            if protocol.sha(tmp)!=ready['sha256']: raise ValueError('ARCHIVE_HASH_MISMATCH')
            tmp.replace(archive)
        recover(root,archive)
        if evaluation_only:
            store.write(audit/'recovery-state.json',{'status':'EVALUATION_RECOVERED',
                'active_run':root.name,'analysis':'MANAGED_BY_ANALYSIS_SEQUENCE'})
            continue
        store.write(audit/'recovery-state.json',{'status':'LOCAL_ANALYSIS','active_run':root.name})
        result=analysis.run(root)
        if result['status'] not in ('COLLECTED','COMPLETE','ASSESSMENTS_COLLECTED_NO_PATTERNS'):
            store.write(audit/'recovery-state.json',{'status':'NEEDS_REVIEW','active_run':root.name,'analysis':result});return
    store.write(audit/'recovery-state.json',{'status':'RECOVERY_COMPLETE' if evaluation_only else 'COMPLETE',
        'runs':[r['run_id'] for r in entries]})


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation-only', action='store_true')
    parser.add_argument('--start-run')
    parser.add_argument('--remote-read-retries', type=int, choices=range(4), default=0)
    args = parser.parse_args()
    try:
        with store.locked(store.PROJECT/'reports/run/20261003-a100-generated-evaluation/.recovery.lock'):
            main(evaluation_only=args.evaluation_only, start_run=args.start_run,
                 remote_read_retries=args.remote_read_retries)
    except Exception as error:
        target=store.PROJECT/'reports/run/20261003-a100-generated-evaluation/recovery-state.json'
        store.write(target,{**store.read(target,{}),'status':'FAILED','error':str(error)})
        raise
