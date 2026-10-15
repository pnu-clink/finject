"""Small opt-in streaming API timing check; stores requests and raw SSE evidence."""
import json
import time
import concurrent.futures
import threading
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    output = Path('log/qwen-27b-3gpu-speed-20260916')
    output.mkdir(parents=True, exist_ok=True)
    base = 'http://127.0.0.1:8001'
    deadline = time.monotonic() + 1800
    while True:
        try:
            with urlopen(base + '/health', timeout=3) as response:
                if response.status == 200:
                    break
        except Exception:
            if time.monotonic() > deadline:
                raise TimeoutError('API readiness timeout')
            time.sleep(10)
    print('API ready; starting warm-up then concurrency 1, 2, 3', flush=True)
    def run_request(i, barrier=None):
        request = {'model': 'qwen-27b', 'messages': [{'role': 'user', 'content':
            f'Run {i}. Explain why diversified investments can reduce concentration risk in about 60 words. Return a JSON object with an explanation string.'}],
            'max_tokens': 128, 'temperature': 0, 'stream': True,
            'stream_options': {'include_usage': True}, 'chat_template_kwargs': {'enable_thinking': False},
            'response_format': {'type': 'json_schema', 'json_schema': {'name': 'explanation', 'strict': True,
                'schema': {'type': 'object', 'properties': {'explanation': {'type': 'string'}}, 'required': ['explanation'], 'additionalProperties': False}}}}
        (output / f'{i}-request.json').write_text(json.dumps(request, indent=2))
        if barrier:
            barrier.wait()
        start = time.perf_counter()
        first = None
        last = None
        text = ''
        usage = None
        raw = []
        with urlopen(Request(base + '/v1/chat/completions', data=json.dumps(request).encode(), headers={'Content-Type': 'application/json'}), timeout=600) as response:
            for line in response:
                raw.append(line.decode())
                if not line.startswith(b'data: ') or line.strip() == b'data: [DONE]':
                    continue
                event = json.loads(line[6:])
                if event.get('usage'):
                    usage = event['usage']
                for choice in event.get('choices', []):
                    chunk = choice.get('delta', {}).get('content') or ''
                    if chunk:
                        now = time.perf_counter()
                        first = first or now
                        last = now
                        text += chunk
        end = time.perf_counter()
        (output / f'{i}-response.sse').write_text(''.join(raw))
        try:
            parsed = json.loads(text)
            valid = set(parsed) == {'explanation'} and isinstance(parsed['explanation'], str)
        except (ValueError, TypeError):
            valid = False
        tokens = (usage or {}).get('completion_tokens', 0)
        result = {'request_id': i, 'ttft_seconds': first - start if first else None,
                  'total_seconds': end - start, 'output_tokens': tokens,
                  'decode_tokens_per_second': (tokens - 1) / (last - first) if first and last > first else None,
                  'usage': usage, 'schema_valid': valid}
        print(json.dumps(result), flush=True)
        return result
    warmup = run_request('warmup')
    results = {'warmup': warmup, 'batches': []}
    for count in (1, 2, 3):
        barrier = threading.Barrier(count)
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
            futures = [pool.submit(run_request, f'{count}-{i}', barrier) for i in range(count)]
            time.sleep(0.5)
            memory = subprocess.run(['ssh', 'a100', 'kubectl exec qwen-27b-3gpu-api -- nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits'],capture_output=True,text=True).stdout
            responses = [f.result() for f in futures]
        elapsed = time.perf_counter() - start
        batch = {'concurrency': count, 'wall_seconds': elapsed, 'aggregate_tokens_per_second': sum(r['output_tokens'] for r in responses)/elapsed, 'requests': responses, 'gpu_memory_sample': memory}
        results['batches'].append(batch)
        (output / 'results.json').write_text(json.dumps(results, indent=2))
        print('BATCH '+json.dumps(batch), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
