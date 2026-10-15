"""E04: compare saved original answers, without an analysis model or re-solving."""
from collections import Counter
from pathlib import Path

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
reporting = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['*'])


def build(root):
    root = Path(root)
    public = {r['item_id']: r for r in store.rows(layout.inputs(root) / 'public.jsonl')}
    private = {r['item_id']: r for r in store.rows(layout.inputs(root) / 'private.jsonl')}
    output = []
    for model in store.configuration(root)['models']:
        for row in store.rows(layout.validation(root, model['key']) / 'results.jsonl'):
            checks = dict(row.get('checks', {}))
            if row['status'] == 'VALID':
                saved = store.read(root / row['result_path'])
                checks = reporting.screen(saved['response'], public[row['item_id']], private[row['item_id']])
            numeric = checks.get('numeric_comparison')
            tags = [] if row['status'] == 'VALID' else [row['status']]
            if numeric:
                tags.append('NUMERIC_MATCH' if numeric['matches'] else 'NUMERIC_MISMATCH')
            elif row['experiment'] == 1:
                tags.append('BASELINE_NOT_NUMERICALLY_EVALUATED')
            if checks.get('numeric_answer_present') is False:
                tags.append('NUMERIC_ANSWER_ABSENT')
            output.append({k: row[k] for k in ('trial_id', 'item_id', 'case', 'experiment', 'variant',
                           'prompt_condition', 'reasoning', 'status')} | {
                'model': model['key'], 'checks': checks, 'numeric_comparison': numeric, 'tags': tags})
    path = layout.validation(root) / 'numeric-comparisons.jsonl'
    store.write_rows(path, output)
    store.event(root, 'E04_NUMERIC_COMPARISONS_SAVED', rows=len(output),
                originals=sum(r['experiment'] == 1 for r in output),
                compared=sum(r['numeric_comparison'] is not None for r in output),
                model_calls=0, path=str(path.relative_to(root)))
    return {'rows': len(output), 'tags': dict(Counter(t for r in output for t in r['tags']))}
