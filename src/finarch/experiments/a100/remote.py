"""Sequential GPU model evaluation with durable one-attempt request journals."""
import concurrent.futures
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
from .wire import body
from jsonschema import Draft202012Validator


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temp.replace(path)


def read(path):
    return json.loads(path.read_text())


def call(root, request, runtime):
    folder = root / 'remote-results' / request['trial_id']
    if folder.exists():
        raise RuntimeError('EXISTING_ATTEMPT_REQUIRES_REVIEW:' + request['trial_id'])
    folder.mkdir(parents=True)
    payload = body(request, runtime)
    Draft202012Validator.check_schema(request['response_schema'])
    write(folder / 'provider-request.json', payload)
    write(folder / 'delivery.json', {'status': 'SENDING', 'at': time.time()})
    start = time.monotonic()
    try:
        wire = urllib.request.Request('http://127.0.0.1:18000/v1/chat/completions',
               data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(wire, timeout=1800) as response:
            raw = response.read()
        (folder / 'raw-response.json').write_bytes(raw)
        obj = json.loads(raw)
        try:
            parsed = json.loads(obj['choices'][0]['message']['content'])
            errors = [e.message for e in Draft202012Validator(request['response_schema']).iter_errors(parsed)]
        except (ValueError, TypeError) as error:
            errors = [str(error)]
        write(folder / 'format-check.json', {'status': 'INVALID_RESPONSE' if errors else 'VALID', 'errors': errors})
        write(folder / 'delivery.json', {'status': 'RECEIVED', 'elapsed_seconds': time.monotonic()-start,
              'usage': obj.get('usage'), 'finish_reason': obj['choices'][0]['finish_reason']})
        return 'RECEIVED'
    except Exception as error:
        write(folder / 'delivery.json', {'status': 'UNKNOWN_DELIVERY', 'elapsed_seconds': time.monotonic()-start,
                                         'error': str(error), 'error_type': type(error).__name__})
        raise


def evaluate(root):
    runtime = read(root / 'a100-runtime.json')
    preflight = read(root / 'token-preflight.json')
    if preflight['max_required_context'] > runtime['max_model_len']:
        raise RuntimeError('CONTEXT_CAPACITY_INSUFFICIENT')
    for relative, expected in read(root / 'transfer-manifest.json').items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError('TRANSFER_HASH_MISMATCH:' + relative)
    manifest, = root.glob('01_evaluation/02_request/*/manifest.jsonl')
    requests = [json.loads(line) for line in manifest.read_text().splitlines()]
    model = requests[0]['model']
    cache = Path('/home/clink-wooix/.cache/huggingface/hub') / ('models--' + model.replace('/', '--'))
    revision = {'Qwen/Qwen3-8B': 'b968826d9c46dd6066d109eabc6255188de91218', 'Qwen/Qwen3-14B': '40c069824f4251a91eefaf281ebe4c544efd3e18'}[model]
    model_path = cache / 'snapshots' / revision
    gpu_text = subprocess.check_output(['nvidia-smi', '--query-gpu=uuid,memory.used', '--format=csv,noheader,nounits'], text=True)
    gpu_rows = [line.split(',') for line in gpu_text.strip().splitlines()]
    if len(gpu_rows) != 4 or any(float(row[1]) > 2048 for row in gpu_rows):
        raise RuntimeError('GPU_NOT_IDLE_NO_PROCESSES_KILLED')
    write(root / 'gpu-before.json', {'devices': gpu_rows})
    argv = [sys.executable, '-m', 'vllm.entrypoints.openai.api_server', '--model', str(model_path),
            '--served-model-name', model, '--dtype', 'bfloat16', '--tensor-parallel-size', '4',
            '--max-model-len', str(runtime['max_model_len']), '--max-num-seqs', '32',
            '--max-num-batched-tokens', '8192', '--gpu-memory-utilization', str(runtime['gpu_memory_utilization']),
            '--no-enable-prefix-caching', '--enable-chunked-prefill', '--reasoning-parser', 'qwen3',
            '--generation-config', 'vllm', '--jit-monitor-mode', 'warn', '--jit-monitor-verbose',
            '--host', '127.0.0.1', '--port', '18000']
    write(root / 'server-command.json', {'argv': argv, 'revision': revision, 'started_at': time.time(),
                                        'VLLM_USE_V2_MODEL_RUNNER': os.getenv('VLLM_USE_V2_MODEL_RUNNER')})
    env = os.environ.copy()
    env.pop('OMP_NUM_THREADS', None)
    env.pop('VLLM_OMP_NUM_THREADS_SET_BY_VLLM', None)
    env['TOKENIZERS_PARALLELISM'] = 'false'
    env['VLLM_CACHE_ROOT'] = str(root / 'runtime-cache')
    owner_source = Path('/home/clink-wooix/workspace/fexperiment/gpu2-finance-timing-20260921/src/finarch/gpu2/owned_processes.py')
    spec = importlib.util.spec_from_file_location('resident_owned_processes', owner_source)
    ownership = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ownership)
    owner = ownership.OwnedProcesses()
    with (root / 'server.log').open('ab') as log:
        server = subprocess.Popen(argv, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        owner.add(server.pid)
        try:
            deadline = time.monotonic() + 1200
            while True:
                if server.poll() is not None:
                    raise RuntimeError('SERVER_EXITED:' + str(server.returncode))
                try:
                    with urllib.request.urlopen('http://127.0.0.1:18000/health', timeout=3):
                        break
                except Exception:
                    if time.monotonic() > deadline:
                        raise RuntimeError('SERVER_START_TIMEOUT')
                    time.sleep(5)
            cache_audit(root, 'initial')
            start = time.time()
            completed = 0
            write(root / 'remote-state.json', {'status': 'RUNNING', 'total': len(requests), 'completed': 0})
            remaining = iter(requests)
            with concurrent.futures.ThreadPoolExecutor(max_workers=runtime['client_concurrency']) as pool:
                pending = {pool.submit(call, root, next(remaining), runtime)
                           for _ in range(runtime['client_concurrency'])}
                while pending:
                    done, pending = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
                    for future in done:
                        future.result()
                        completed += 1
                    write(root / 'remote-state.json', {'status': 'RUNNING', 'total': len(requests),
                          'completed': completed, 'started_at': start, 'elapsed_seconds': time.time()-start})
                    for _ in done:
                        request = next(remaining, None)
                        if request is not None:
                            pending.add(pool.submit(call, root, request, runtime))
            cache_audit(root, 'final')
            trial_ids = {r['trial_id'] for r in requests}
            write(root / 'recovery-manifest.json', {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and (p.parent.name in trial_ids or p.name in ('server-command.json', 'cache-initial.json', 'cache-final.json', 'metrics-final.txt', 'metrics-initial.txt'))})
            write(root / 'remote-state.json', {'status': 'EVALUATION_RECEIVED', 'total': len(requests),
                  'completed': completed, 'started_at': start, 'elapsed_seconds': time.time()-start})
        finally:
            owner.signal(signal.SIGTERM)
            deadline = time.monotonic() + 60
            while owner.refresh() and time.monotonic() < deadline:
                time.sleep(.5)
            owner.signal(signal.SIGKILL)
            server.wait(timeout=30)
            owner.close()
            time.sleep(5)


def cache_audit(root, phase):
    with urllib.request.urlopen('http://127.0.0.1:18000/metrics', timeout=10) as response:
        text = response.read().decode()
    (root / ('metrics-' + phase + '.txt')).write_text(text)
    lines = text.splitlines()
    configs = [line for line in lines if line.startswith('vllm:cache_config_info')]
    if not configs or any('enable_prefix_caching="False"' not in line for line in configs):
        raise RuntimeError('PREFIX_CACHE_DISABLED_NOT_VERIFIED')
    hits = {}
    for name in ('vllm:prefix_cache_hits_total', 'vllm:external_prefix_cache_hits_total'):
        values = [float(line.rsplit(' ', 1)[1]) for line in lines if line.startswith(name+'{') or line.startswith(name+' ')]
        hits[name] = sum(values) if values else None
        if hits[name] is not None and hits[name] > 0:
            raise RuntimeError('CACHE_HITS_OBSERVED')
    write(root / ('cache-' + phase + '.json'), {'enabled': False, 'hits': hits,
          'resolved_config': configs, 'missing_usage': 'UNKNOWN_NOT_ZERO'})


def main():
    project = Path(__file__).resolve().parents[4]
    with (project / 'evaluation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for root in sorted((project / 'runs').glob('*'), key=lambda p: ('14b' in p.name, p.name)):
            state = root / 'remote-state.json'
            if state.exists():
                raise RuntimeError('EXISTING_RUN_REQUIRES_REVIEW:' + str(root))
            try:
                evaluate(root)
            except Exception as error:
                write(root / 'remote-failure.json', {'error': str(error), 'time': time.time()})
                raise


if __name__ == '__main__':
    main()
