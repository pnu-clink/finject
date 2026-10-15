"""I00: select delivered cases and validate public/private identity before freezing."""
from pathlib import Path

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
dataset = __import__('finarch.experiments.00-input.dataset', fromlist=['*'])
request_order = __import__('finarch.experiments.01-evaluation.02-request.request_order', fromlist=['*'])
PROJECT, rows, file_hash, verify = store.PROJECT, store.rows, store.file_hash, store.verify


def prepare(config):
    if config['dataset'].get('require_generated') and not config['dataset'].get('generated_path'):
        raise ValueError('GENERATED_DATASET_REQUIRED')
    if config['dataset'].get('generated_path') and config['dataset'].get('reuse_input_run'):
        raise ValueError('GENERATED_INPUT_CANNOT_REUSE_OLD_EXPERIMENT_INPUT')
    if config['dataset'].get('require_collected_results') and config['dataset'].get('reuse_input_run'):
        raise ValueError('CONSOLIDATED_RESULTS_CANNOT_REUSE_OLD_EXPERIMENT_INPUT')
    if config['dataset'].get('reuse_input_run'):
        previous = (PROJECT / config['dataset']['reuse_input_run']).resolve()
        verify(previous)
        public, private = rows(run_layout.inputs(previous) / 'public.jsonl'), rows(run_layout.inputs(previous) / 'private.jsonl')
        selection = request_order.selection_from_manifests(previous, public=public, require_same_items=True)
        if selection['originals'] != config['dataset']['count'] or selection['variants'] != 7 * selection['originals']:
            raise ValueError('REUSED_COHORT_COUNT_MISMATCH')
        selection.update(reused_from_experiment=previous.name,
                         reused_input_sha256={p: file_hash(previous / p) for p in (str((run_layout.inputs(previous) / n).relative_to(previous)) for n in ('public.jsonl', 'private.jsonl'))},
                         reused_request_sha256={p: file_hash(previous / p) for p in selection['manifest_files']})
    else:
        public, private, selection = dataset.select(config['dataset'])
    items = selection.get('items')
    if not isinstance(items, list) or not items:
        raise ValueError('SELECTED_ITEMS_REQUIRED_FROM_DATASET_OR_MANIFEST')
    public_ids = [item['item_id'] for item in public]
    if (len(set(public_ids)) != len(public_ids) or
            sorted(item['item_id'] for item in items) != sorted(public_ids)):
        raise ValueError('PUBLIC_SELECTION_ID_MISMATCH')
    if config['dataset'].get('originals_only'):
        if config['dataset'].get('reuse_input_run'):
            raise ValueError('ORIGINALS_ONLY_CANNOT_REUSE_FULL_COHORT')
        original_ids = {item['item_id'] for item in items if item['experiment'] == 1}
        public = [item for item in public if item['item_id'] in original_ids]
        private = [item for item in private if item['item_id'] in original_ids]
        items = [item for item in items if item['experiment'] == 1]
        selection['items'] = items
        selection['eligible_variants_checked'] = selection['variants']
        selection['variants'] = 0
        selection['variant_counts'] = {}
        selection['request_scope'] = 'ORIGINAL_ONLY'
    return public, private, selection
