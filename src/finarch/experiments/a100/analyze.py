"""Use the configured Codex analysis with explicit private original-label scope."""
import argparse
from collections import Counter
from copy import deepcopy
import importlib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    root = args.run.resolve()
    pipeline = importlib.import_module('finarch.experiments.02-analysis.pipeline')
    store = pipeline.store
    store.verify(root)
    if store.read(root / 'state.json')['status'] != 'FINISHED':
        raise ValueError('EVALUATION_MUST_BE_FINISHED')
    private = store.rows(root / '00_input/private.jsonl')
    labels = {r['case']: r['original_external_knowledge'] for r in private if r['variant'] == 'ORIGINAL'}
    source_request = pipeline.backend.request

    def enriched_request(run, stage, item_id, prompt, schema, payload):
        payload = deepcopy(payload)
        if stage == '02_comparison':
            payload['original_external_knowledge'] = labels[item_id]
        else:
            payload['original_external_knowledge_counts'] = dict(Counter(
                str(value) for value in labels.values()))
            payload['original_external_knowledge_by_case'] = labels
        prompt += ('\nThe original_external_knowledge fields are private production annotations. '
                   'They describe verified external dependencies in the original dataset construction, '
                   'not observed model behavior and not independently verified labels of edited variants. '
                   'used=false does not prove absence of external knowledge. Relate observations to '
                   'EXTERNAL_RULE or EXTERNAL_DATA only when supplied evidence supports it; do not infer causation.\n')
        return source_request(run, stage, item_id, prompt, schema, payload)

    pipeline.backend.request = enriched_request
    result = pipeline.run(str(root))
    store.event(root, 'A100_CODEX_ANALYSIS_RETURNED', result=result)
    print(result)
    state = store.read(root / 'state.json')
    if state.get('analysis', {}).get('status') != 'COMPLETE':
        raise RuntimeError('ANALYSIS_INCOMPLETE_REQUIRES_REVIEW')
    state['full_pipeline'] = {'status': 'COMPLETE', 'completed_at': store.now()}
    store.write(root / 'state.json', state)


if __name__ == '__main__':
    main()
