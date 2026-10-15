"""RQ1 pairs: recorded original numeric correctness and validated variant reviews."""
from collections import Counter, defaultdict
from pathlib import Path

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])

OUTPUT = '02_analysis/02_comparison/pair-outcomes'
VARIANTS = ('IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY',
            'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')


def indexed(rows, fields):
    """Reject duplicate IDs instead of silently dropping planned responses."""
    result = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        if key in result:
            raise ValueError('RQ1_DUPLICATE_RECORD:' + str(key))
        result[key] = row
    return result


def original_numeric(row, check):
    """Expose the saved numeric screen, not a new semantic or unit judgment."""
    if not row or row['status'] != 'VALID':
        return 'UNASSESSED'
    comparison = (check or {}).get('numeric_comparison')
    if isinstance(comparison, dict) and type(comparison.get('matches')) is bool:
        return 'MATCH' if comparison['matches'] else 'MISMATCH'
    if (check or {}).get('checks', {}).get('numeric_answer_present') is False:
        return 'MISMATCH'
    return 'UNASSESSED'


def quadrant(original, variant):
    """Two booleans determine placement; an unknown axis stays outside the matrix."""
    if type(original) is not bool or type(variant) is not bool:
        return None
    return 1 if original and variant else 4 if original else 2 if variant else 3


def aggregate(pairs):
    states = Counter(p['placement_status'] for p in pairs)
    counts = Counter(p['quadrant'] for p in pairs if p['quadrant'] is not None)
    total = len(pairs)
    placed = sum(counts.values())
    return {'planned_pairs': total, 'original_cases': len({p['original_item_id'] for p in pairs}),
            'quadrants': {str(i): {'count': counts[i],
                'ratio_of_planned': counts[i] / total if total else None} for i in range(1, 5)},
            'placed_pairs': placed, 'unplaced_pairs': total - placed,
            'placement_counts': dict(states),
            'variant_answer_shapes': dict(Counter(p['variant_answer_shape'] for p in pairs)),
            'classifications': dict(Counter(p['classification_display'] for p in pairs))}


def build(root):
    """Read frozen manifests and evaluation files, then save zero-call RQ1 data."""
    root = Path(root).resolve()
    with store.locked(root / '.pair-outcomes.lock'):
        store.verify(root)
        config = store.configuration(root)
        private = indexed(store.rows(layout.inputs(root) / 'private.jsonl'), ('item_id',))
        public = indexed(store.rows(layout.inputs(root) / 'public.jsonl'), ('item_id',))
        numeric_path = layout.validation(root) / 'numeric-comparisons.jsonl'
        numeric = indexed(store.rows(numeric_path), ('model', 'trial_id'))
        source_paths = [root / 'manifest.json', layout.inputs(root) / 'private.jsonl',
                        layout.inputs(root) / 'public.jsonl', numeric_path]
        backend = __import__('finarch.experiments.02-analysis.llm_backend', fromlist=['*'])
        reviews = __import__('finarch.experiments.02-analysis.02-comparison.response_assessments', fromlist=['*'])
        review_folder = root / '02_analysis/02_comparison'
        review_manifest = review_folder / 'manifest.jsonl'
        if review_manifest.exists():
            reviews.collect(root, store.rows(review_manifest), backend)
        review_path = review_folder / 'response-assessments.jsonl'
        assessments = indexed(store.rows(review_path), ('response_id',))
        if review_path.exists():
            source_paths.append(review_path)
        pairs = []
        for model in config['models']:
            requests_path = layout.requests(root, model['key'])
            results_path = layout.validation(root, model['key']) / 'results.jsonl'
            source_paths.extend((requests_path, results_path))
            requests = store.rows(requests_path)
            indexed(requests, ('trial_id',))
            expected = indexed(requests, ('item_id', 'prompt_condition', 'reasoning'))
            results = indexed(store.rows(results_path), ('trial_id',))
            planned_ids = {r['trial_id'] for r in requests}
            if any(k[0] not in planned_ids for k in results):
                raise ValueError('RQ1_RESULT_NOT_IN_MANIFEST')
            for request in requests:
                if request['experiment'] == 1:
                    continue
                meta = private[(request['item_id'],)]
                original_id = meta['original_item_id']
                original = expected.get((original_id, request['prompt_condition'], request['reasoning']))
                baseline = results.get((original['trial_id'],)) if original else None
                variant = results.get((request['trial_id'],))
                for definition, result in ((original, baseline), (request, variant)):
                    if definition and result and any(result.get(k) != definition[k] for k in
                        ('item_id', 'case', 'variant', 'prompt_condition', 'reasoning')):
                        raise ValueError('RQ1_REQUEST_RESULT_LINK_MISMATCH')
                check = numeric.get((model['key'], original['trial_id'])) if original else None
                original_result = original_numeric(baseline, check)
                status = variant['status'] if variant else 'NOT_COLLECTED'
                response = (variant or {}).get('response') or {}
                shape = ('NULL' if response.get('answer') is None else 'NUMERIC') if status == 'VALID' else 'UNAVAILABLE'
                classification = response.get('classification')
                review = assessments.get((model['key'] + ':' + request['trial_id'],))
                if review and any(review.get(k) != request[k] for k in
                                  ('case', 'item_id', 'variant', 'prompt_condition', 'reasoning')):
                    raise ValueError('RQ1_ASSESSMENT_LINK_MISMATCH')
                appropriate = review.get('adaptation_success') if review and review.get('review_status') == 'COMPLETED' and status == 'VALID' else None
                correct = True if original_result == 'MATCH' else False if original_result == 'MISMATCH' else None
                placement = quadrant(correct, appropriate)
                reason = ('PLACED' if placement else 'ORIGINAL_NUMERIC_UNASSESSED' if correct is None
                          else 'VARIANT_UNAVAILABLE' if status != 'VALID' else 'SEMANTIC_NOT_REVIEWED')
                answerability = meta.get('semantic_answerability', 'NOT_ESTABLISHED')

                source_type = private[(original_id,)].get('generated_metadata', {}).get('provenance', {}).get('dataset', 'NOT_RECORDED')
                pairs.append({'pair_id': store.digest({'model': model['key'], 'trial_id': request['trial_id'], 'original': original_id}),
                    'model': model['key'], 'case': request['case'], 'source_type': source_type,
                    'variant': request['variant'], 'prompt_condition': request['prompt_condition'], 'reasoning': request['reasoning'],
                    'original_item_id': original_id, 'variant_item_id': request['item_id'],
                    'original_trial_id': original['trial_id'] if original else None, 'variant_trial_id': request['trial_id'],
                    'original_numeric_result': original_result, 'original_correctness': correct,
                    'answerability': answerability,
                    'original_status': baseline['status'] if baseline else 'NOT_COLLECTED',
                    'original_unit_assessment': (check or {}).get('checks', {}).get('unit_assessment', 'NOT_ASSESSED'),
                    'variant_status': status, 'variant_answer_shape': shape, 'classification': classification,
                    'classification_display': 'NOT_REQUESTED' if request['prompt_condition'] == 'unguided' and status == 'VALID'
                        else classification or 'UNAVAILABLE',
                    'variant_appropriateness': appropriate, 'quadrant': placement, 'placement_status': reason,
                    'assessment_id': (review or {}).get('assessment_id'),
                    'assessment_review_status': (review or {}).get('review_status'),
                    'original_result_path': (baseline or {}).get('result_path'),
                    'variant_result_path': (variant or {}).get('result_path'),
                    'original_context_sha256': store.digest(public[(original_id,)]),
                    'variant_context_sha256': store.digest(public[(request['item_id'],)])})
        if len({p['pair_id'] for p in pairs}) != len(pairs):
            raise ValueError('RQ1_DUPLICATE_PAIR')
        hashes = {str(p.relative_to(root)): store.file_hash(p) for p in source_paths}
        by_condition, by_type = defaultdict(list), defaultdict(list)
        for pair in pairs:
            by_condition[tuple(pair[k] for k in ('model', 'source_type', 'prompt_condition', 'reasoning'))].append(pair)
            by_type[tuple(pair[k] for k in ('model', 'source_type', 'prompt_condition', 'reasoning', 'variant', 'answerability'))].append(pair)
        def grouped(groups, keys):
            return [{**dict(zip(keys, key)), **aggregate(values)} for key, values in sorted(groups.items())]
        summary = {'schema_version': 'RQ1PairOutcomeV2', 'run_id': root.name, 'created_at': store.now(),
            'status': 'COMPLETE' if all(p['quadrant'] is not None for p in pairs) else 'PARTIAL', 'new_model_calls': 0,
            'rubric': 'docs/02-experiments/02_analysis/02_comparison/01-rq1-pair-outcomes.md',
            'source_hashes': hashes, 'original_axis_scope': 'RECORDED_SIGNED_NUMERIC_MATCH_UNITS_NOT_SEPARATELY_SCORED',
            'quadrant_axes': {'x': 'original_correctness', 'y': 'variant_appropriateness'},
            'quadrant_order': {'1': [True, True], '2': [False, True], '3': [False, False], '4': [True, False]},
            'overall': aggregate(pairs), 'conditions': grouped(by_condition, ('model', 'source_type', 'prompt_condition', 'reasoning')),
            'types': grouped(by_type, ('model', 'source_type', 'prompt_condition', 'reasoning', 'variant', 'answerability'))}
        # Verify a stable read before writing any aggregate.
        for name, expected_hash in hashes.items():
            if store.file_hash(root / name) != expected_hash:
                raise ValueError('RQ1_SOURCE_CHANGED_DURING_AGGREGATION:' + name)
        output = root / OUTPUT
        store.write_rows(output / 'pairs.jsonl', pairs)
        store.write(output / 'summary.json', summary)
        template = store.PROJECT / 'src/finarch/experiments/templates/ordered-pair-outcomes-readme-template.md'
        store.write_text(output / 'README.md', template.read_text().replace('{run_id}', root.name))
        store.event(root, 'RQ1_PAIR_OUTCOMES_SAVED', status=summary['status'], planned_pairs=len(pairs),
                    placed_pairs=summary['overall']['placed_pairs'], unplaced_pairs=summary['overall']['unplaced_pairs'], new_model_calls=0, path=OUTPUT)
        return {'run_id': root.name, 'status': summary['status'], **summary['overall'], 'new_model_calls': 0}
