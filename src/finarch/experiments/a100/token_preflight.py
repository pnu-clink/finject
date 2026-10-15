"""Count complete wire messages without GPU inference or truncation."""
import argparse
import json
from pathlib import Path
from transformers import AutoTokenizer
from .wire import body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--tokenizer', required=True)
    args = parser.parse_args()
    runtime = json.loads((args.run / 'a100-runtime.json').read_text())
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True)
    manifests = list(args.run.glob('01_evaluation/02_request/*/manifest.jsonl'))
    if len(manifests) != 1:
        raise ValueError('ONE_MODEL_REQUIRED')
    counts = []
    for line in manifests[0].read_text().splitlines():
        request = json.loads(line)
        payload = body(request, runtime)
        ids = tokenizer.apply_chat_template(payload['messages'], tokenize=True, add_generation_prompt=True,
                                             **payload['chat_template_kwargs'])
        ids = ids['input_ids'] if hasattr(ids, 'keys') else ids
        if not ids or not isinstance(ids[0], int):
            raise ValueError('INVALID_TOKENIZER_OUTPUT')
        counts.append({'trial_id': request['trial_id'], 'input_tokens': len(ids),
                       'required_context': len(ids) + payload['max_tokens']})
    maximum = max(x['required_context'] for x in counts)
    summary = {'requests': len(counts), 'max_input_tokens': max(x['input_tokens'] for x in counts),
               'max_required_context': maximum, 'configured_context': runtime['max_model_len'],
               'over_limit': sum(x['required_context'] > runtime['max_model_len'] for x in counts),
               'status': 'PASS' if maximum <= runtime['max_model_len'] else 'CONTEXT_ADJUSTMENT_REQUIRED',
               'truncation': False}
    (args.run / 'token-counts.json').write_text(json.dumps(counts))
    (args.run / 'token-preflight.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
