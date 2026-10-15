"""Activate the named supervisor handoff only after all offline preflights pass."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('/home/clink-wooix/workspace/finarch/experiments')
POD='qwen38-27b-vllm-resident-core'
PYTHON='/home/clink-wooix/workspace/vllm/.venv-cu129/bin/python'


def main():
    deadline=time.monotonic()+3600
    summary=ROOT/'preflight-summary.json'
    while not summary.exists():
        if time.monotonic()>deadline:raise RuntimeError('TOKEN_PREFLIGHT_TIMEOUT_NO_ACTIVATION')
        time.sleep(15)
    if json.loads(summary.read_text()).get('status')!='PASS':raise ValueError('PREFLIGHT_NOT_PASS')
    # Verify idle inference immediately before handing over the user's reserved GPUs.
    code=('import urllib.request; t=urllib.request.urlopen("http://127.0.0.1:8000/metrics",timeout=10).read().decode(); '
          'v=[float(l.rsplit(" ",1)[1]) for l in t.splitlines() if l.startswith(("vllm:num_requests_running{","vllm:num_requests_waiting{"))]; '
          'assert v and not any(v), "INFERENCE_BUSY_NO_RESTART"')
    subprocess.run(['kubectl','exec',POD,'--',PYTHON,'-c',code],check=True,timeout=30)
    subprocess.run([sys.executable,str(ROOT/'src/finarch/experiments/a100/install_generated_hook.py')],check=True)
    subprocess.run(['kubectl','exec',POD,'--','kill','-TERM','1'],check=True,timeout=30)
    (ROOT/'activation.json').write_text(json.dumps({'status':'SUPERVISOR_RESTART_REQUESTED','at_epoch':time.time(),
        'pod':POD,'scope':'Same reserved Pod; no deletion or GPU reallocation.'},indent=2))
    print('SUPERVISOR_RESTART_REQUESTED',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        (ROOT/'activation.json').write_text(json.dumps({'status':'FAILED','error':str(error)},indent=2))
        raise
