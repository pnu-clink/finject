"""Run A01-A03 saved-result analysis and A04 research finding comparison."""
import argparse
from collections import defaultdict
from pathlib import Path
import shutil
from finarch.experiments import assets

a01 = __import__('finarch.experiments.02-analysis.01-results.results', fromlist=['*'])
a02 = __import__('finarch.experiments.02-analysis.02-comparison.comparison', fromlist=['*'])
pair_outcomes = __import__('finarch.experiments.02-analysis.02-comparison.pair_outcomes', fromlist=['*'])
a03 = __import__('finarch.experiments.02-analysis.03-research.research', fromlist=['*'])
a04 = __import__('finarch.experiments.02-analysis.04-quadrant.pipeline', fromlist=['*'])
outcomes = __import__('finarch.experiments.02-analysis.05-outcomes.semantic_answerability', fromlist=['*'])
backend = __import__('finarch.experiments.02-analysis.llm_backend', fromlist=['*'])
timing = __import__('finarch.experiments.02-analysis.timing', fromlist=['*'])
contracts = backend.contracts
store = a01.store
numeric = __import__('finarch.experiments.01-evaluation.04-validation.numeric_validation', fromlist=['*'])
MAX_RESEARCH_INPUT_BYTES = 500_000
MAX_COMPARISON_INPUT_BYTES = 500_000

COMPARISON_PROMPT = assets.prompt_text('comparison_common') + assets.prompt_text('comparison')
RESEARCH_PROMPT = backend.INSTRUCTIONS + assets.prompt_text('research')


def response_payload(row):
    fields = ('response_id', 'case', 'item_id', 'variant', 'model', 'prompt_condition',
              'reasoning', 'status', 'response', 'original_result', 'numeric_comparison',
              'reference', 'alternative_answer', 'matched_value_parent_ids', 'tags')
    return {k: row.get(k) for k in fields} | {'numeric_candidate': a02.choice(row),
                                            'candidate_position': a02.position(row)}


def compact(value):
    """Keep every computed count but omit repeated detail arrays for model input."""
    if isinstance(value, list):
        return [compact(v) for v in value]
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items()
                if k not in ('response_ids', 'original_cases', 'pairs', 'case_profiles', 'generated_at')}
    return value


def comparison_requests(root, rows):
    frozen = root / a01.ANALYSIS / '02_comparison/manifest.jsonl'
    if frozen.exists():
        return store.rows(frozen)
    public = a01.unique(store.rows(root / '00_input/public.jsonl'), 'item_id', 'PUBLIC')
    private = a01.unique(store.rows(root / '00_input/private.jsonl'), 'item_id', 'PRIVATE')
    rows = a02.attach_positions(rows, public, private)
    groups = defaultdict(list)
    for row in rows:
        groups[row['case']].append(row)
    requests = []
    for case, observations in sorted(groups.items()):
        ids = sorted({r['item_id'] for r in observations})
        inputs = {key: {'public': public[key], 'production_metadata': {
            k: private[key].get(k) for k in ('variant', 'value_pair', 'value_dependency',
            'patches', 'edit_provenance', 'answer_metadata', 'alternative_answer')}} for key in ids}
        payload = {'run': root.name, 'case': case, 'inputs': inputs,
                   'responses': [response_payload(r) for r in observations]}
        annotations = {store.encoded(private[key].get('original_external_knowledge')) for key in ids}
        if len(annotations) != 1:
            raise ValueError('CASE_EXTERNAL_KNOWLEDGE_INCONSISTENT:' + case)
        annotation = private[ids[0]].get('original_external_knowledge')
        if annotation is not None:
            payload['original_external_knowledge'] = annotation
            payload['external_knowledge_scope'] = private[ids[0]]['external_knowledge_scope']
        request = backend.request(root, '02_comparison', case, COMPARISON_PROMPT,
                                  contracts.INTERPRETATION_RESPONSE, payload)
        if len(store.encoded(request)) > MAX_COMPARISON_INPUT_BYTES:
            raise ValueError('A02_PARTITION_REQUIRED:' + case)
        requests.append(request)
    return requests


def research_requests(root, interpretations, comparisons):
    frozen = root / a01.ANALYSIS / '03_research/manifest.jsonl'
    if frozen.exists():
        return store.rows(frozen)
    assessment_folder = root / a01.ANALYSIS / '02_comparison'
    assessment_summary = store.read(assessment_folder / 'response-assessment-summary.json')
    assessment_rows = store.rows(assessment_folder / 'response-assessments.jsonl') if assessment_summary else []
    if assessment_summary and store.file_hash(assessment_folder / 'response-assessments.jsonl') != assessment_summary['response_assessments_sha256']:
        raise ValueError('ASSESSMENT_SUMMARY_SOURCE_CHANGED')
    assessment_index = {r['response_id']: r for r in assessment_rows}
    groups = defaultdict(list)
    for item in interpretations:
        groups[item['category']].append(item)
    aggregates = compact(comparisons)
    requests = []
    for category, items in sorted(groups.items()):
        def make_request(chunk, index, total):
            payload = {'run': root.name, 'category': category, 'partition': index,
                'partitions_in_category': total, 'aggregates': aggregates,
                'interpretations': chunk}
            if assessment_summary:
                payload['response_assessment_summary'] = assessment_summary
                refs = {ref for item in chunk for ref in item.get('response_ids', [])}
                payload['response_assessments'] = [assessment_index[ref] for ref in sorted(refs) if ref in assessment_index]
            return backend.request(root, '03_research', f'{category}-{index:03d}',
                                   RESEARCH_PROMPT, contracts.FINDINGS, payload)

        chunks, chunk = [], []
        for item in items:
            trial = chunk + [item]
            # Include prompt, schema, aggregates and all attached assessments.
            # The maximum possible partition count reserves enough digit space.
            if len(store.encoded(make_request(trial, len(items), len(items)))) > MAX_RESEARCH_INPUT_BYTES:
                if not chunk:
                    raise ValueError('A03_SINGLE_OBSERVATION_EXCEEDS_INPUT_BUDGET:' + category)
                chunks.append(chunk)
                chunk = [item]
                if len(store.encoded(make_request(chunk, len(items), len(items)))) > MAX_RESEARCH_INPUT_BYTES:
                    raise ValueError('A03_SINGLE_OBSERVATION_EXCEEDS_INPUT_BUDGET:' + category)
            else:
                chunk = trial
        if chunk:
            chunks.append(chunk)
        requests.extend(make_request(chunk, index, len(chunks))
                        for index, chunk in enumerate(chunks, 1))
    return requests


def collect_interpretations(root, requests):
    folder = root / a01.ANALYSIS / '02_comparison'
    interpretations, coverage = [], []
    for req in requests:
        result = backend.latest(folder, req)
        record = {'case': req['item_id'], 'trial_id': req['trial_id'],
                  'response_ids': [r['response_id'] for r in req['input']['responses']],
                  'status': result['status'] if result else 'NOT_RUN',
                  'coverage_note': None, 'observation_count': None,
                  'comparison_review_completeness': 'NOT_INDEPENDENTLY_VERIFIED'}
        if result and result['status'] == 'VALID':
            errors = contracts.validate_response(result['response'], req)
            if errors:
                raise ValueError('SAVED_ANALYSIS_VALIDATION_CHANGED:' + str(errors))
            record['coverage_note'] = result['response'].get('coverage_note')
            record['observation_count'] = len(result['response']['observations'])
            for index, item in enumerate(result['response']['observations'], 1):
                # Stable IDs refer back to the immutable model response without editing it.
                interpretations.append({**item, 'id': f"{req['item_id']}-O{index:02d}"})
        coverage.append(record)
    store.write_rows(folder / 'interpretations.jsonl', interpretations)
    store.write(folder / 'coverage.json', {'planned_cases': len(requests),
        'valid_cases': sum(c['status'] == 'VALID' for c in coverage), 'cases': coverage,
        'meaning': ('Pattern observations are selective. Response assessments have their own exhaustive coverage record.'
            if any('response_assessments' in req['response_schema']['properties'] for req in requests)
            else 'Selective pattern observations; no exhaustive semantic response assessments in frozen V1 requests.')})
    contracts.collect_assessments(root, requests, backend)
    pair_outcomes.build(root)
    outcomes.build(root)
    return interpretations


def finish_without_patterns(root, requests, state):
    """Close a valid V2 assessment run without fabricating A03 evidence."""
    if not all('response_assessments' in r['response_schema']['properties'] for r in requests):
        return update(root, 'A02', {**state, 'status': 'NO_INTERPRETABLE_RESPONSES'})
    folder = root / a01.ANALYSIS / '03_research'
    research_state = {'status': 'SKIPPED_NO_PATTERN_OBSERVATIONS', 'requests': 0,
        'reason': 'Response assessments are retained in A02; no interpretation IDs support A03 findings.'}
    store.write(folder / 'state.json', research_state)
    return update(root, 'A02', {**state, 'status': 'ASSESSMENTS_COLLECTED_NO_PATTERNS',
        'research': research_state, 'response_assessments': '02_comparison/response-assessments.jsonl',
        'meaning': 'Assessment collection completed; no pattern findings or A03 research claims generated.'})


def collect_findings(root, requests):
    folder = root / a01.ANALYSIS / '03_research'
    findings, discussion = [], []
    for req in requests:
        result = backend.latest(folder, req)
        if not result or result['status'] != 'VALID':
            continue
        errors = contracts.validate_response(result['response'], req)
        if errors:
            raise ValueError('SAVED_RESEARCH_VALIDATION_CHANGED:' + str(errors))
        for item in result['response']['findings']:
            findings.append({**item, 'id': f'F{len(findings)+1:03d}'})
        for item in result['response']['discussion']:
            discussion.append({**item, 'id': f'D{len(discussion)+1:03d}'})
    value = {'schema_version': 1, 'run': root.name, 'findings': findings, 'discussion': discussion}
    store.write(folder / 'findings.json', value)
    return value


def update(root, stage, state):
    current = store.read(root / 'state.json')
    current['analysis'] = {**state, 'stage': stage, 'method': a01.METHOD}
    store.write(root / 'state.json', current)
    a01.render(root, 'analysis', source=root.name,
               status=f"{stage}: {state['status']} · {state.get('valid', 0)}/{state.get('requests', 0)}")
    return current['analysis']


def ensure_pair_outcomes(root):
    """Backfill missing Q01 files after A02 collection without repeating model calls."""
    folder = root / '02_analysis/02_comparison'
    if store.read(folder / 'state.json', {}).get('status') != 'COLLECTED':
        return None
    output = root / pair_outcomes.OUTPUT
    if not all((output / name).is_file() for name in ('summary.json', 'pairs.jsonl')):
        return pair_outcomes.build(root)
    return None


def run_postprocessing(root):
    """Enter A04 alone for completed research; never invoke A02/A03 models."""
    root = Path(root).resolve()
    with store.locked(root / '.analysis.lock'):
        control = store.read(root / 'state.json').get('execution_control', {}).get('analysis', {})
        if control.get('paused'):
            return {'status': 'PAUSED_BY_USER', 'reason': control.get('reason'), 'new_model_calls': 0}
        ensure_pair_outcomes(root)
        return finish_postprocessing(root)


def finish_postprocessing(root):
    """Finish model analysis, then derive five response outcomes without new calls."""
    policy = store.read(root / '02_analysis/finalization-policy.json', {})
    if policy.get('skip_a04') is True:
        if store.read(root / '02_analysis/03_research/state.json', {}).get('status') != 'COLLECTED':
            raise ValueError('PYTHON_FINALIZATION_REQUIRES_COMPLETED_A03')
        # A04 is disabled for explicitly authorized runs; preserve its old artifacts.
        # state = a04.run(root)
        summary = outcomes.build(root)
        result = {'status': 'COLLECTED', 'stage': 'PYTHON_OUTCOMES', 'new_model_calls': 0,
                  'a04_status': 'SKIPPED_BY_USER', 'semantic_response_outcomes': {
                      'path': outcomes.OUTPUT + '/summary.json', 'schema_version': summary['schema_version'],
                      'counts': summary['scopes']['variants'], 'new_model_calls': 0}}
        current = store.read(root / 'state.json')
        current['analysis'] = {**current.get('analysis', {}), **result, 'status': 'COMPLETE',
                               'completed_at': store.now()}
        store.write(root / 'state.json', current)
        a01.render(root, 'analysis', source=root.name, status='A01·A02·A03 및 Python 응답 분류 완료 · A04 생략')
        store.event(root, 'ANALYSIS_PYTHON_FINALIZATION_COMPLETED', a04_status='SKIPPED_BY_USER', new_model_calls=0)
        timing.refresh(root, force=True)
        return result
    state = a04.run(root)
    if state.get('status') == 'COLLECTED':
        summary = outcomes.build(root)
        return {**state, 'semantic_response_outcomes': {
            'path': outcomes.OUTPUT + '/summary.json', 'schema_version': summary['schema_version'],
            'counts': summary['scopes']['variants'], 'new_model_calls': 0}}
    return state


@timing.recorded('analysis_total')
def run(root, *, aggregate_only=False):
    root = Path(root).resolve()
    with store.locked(root / '.analysis.lock'):
        control = store.read(root / 'state.json').get('execution_control', {}).get('analysis', {})
        if control.get('paused'):
            return {'status': 'PAUSED_BY_USER', 'reason': control.get('reason'), 'new_model_calls': 0}
        config = store.read(root / 'config.json')
        reuse = config.get('evaluation_reuse', {})
        if reuse and reuse.get('mode') != 'PIPELINE_ANALYSIS_VARIANT':
            raise ValueError('USE_CURRENT_SESSION_RECORDER_FOR_FROZEN_ANALYSIS_ONLY_RUN')
        startup = __import__('finarch.experiments.90-operations.execution_start', fromlist=['*'])
        startup.announce(root, 'A00', 'Verify saved Evaluation files, then execute A01-A04 Analysis.',
                         processor='PYTHON', requests=0)
        with timing.measure(root, 'integrity'):
            a01.verify_reuse(root)
        stage_state = store.read(root / 'state.json')
        statuses = {v['status'] for v in stage_state.get('models', {}).values()}
        if not statuses or statuses - {'FINISHED'}:
            return update(root, 'WAIT_EVALUATION', {'status': 'WAITING', 'evaluation_statuses': sorted(statuses)})
        base = root / a01.ANALYSIS
        if not (base / '01_results/responses.jsonl').exists():
            startup.announce(root, 'A01', 'Collect saved Evaluation responses and recorded scores.',
                             processor='PYTHON', requests=0)
            if not reuse:
                with timing.measure(root, 'numeric_comparison'):
                    numeric.build(root)
            with timing.measure(root, 'result_collection'):
                a01.build(root)
        else:
            source_hashes = store.read(base / '01_results/state.json').get('source_hashes', {})
            if not source_hashes:
                raise ValueError('ANALYSIS_SOURCE_HASHES_REQUIRED')
            with timing.measure(root, 'source_verification'):
                for path, digest in source_hashes.items():
                    if store.file_hash(a01.source_file(root, path)) != digest:
                        raise ValueError('ANALYSIS_SOURCE_CHANGED:' + path)
        if not aggregate_only and store.read(base / '03_research/state.json', {}).get('status') == 'COLLECTED':
            ensure_pair_outcomes(root)
            return finish_postprocessing(root)
        rows = store.rows(base / '01_results/responses.jsonl')
        comparison_file = base / '02_comparison/comparisons.json'
        comparisons = store.read(comparison_file)
        if aggregate_only:
            if comparison_file.exists():
                backup = comparison_file.with_name('comparisons-before-refresh-' + store.file_hash(comparison_file)[:16] + '.json')
                if not backup.exists():
                    shutil.copyfile(comparison_file, backup)
            with timing.measure(root, 'relationship_aggregation_refresh'):
                comparisons = a02.build(root, preserve_execution_state=True)
                pair_outcomes.build(root)
                outcomes.build(root)
            result = {'status': 'AGGREGATES_REFRESHED', 'responses': len(rows), 'new_model_calls': 0,
                      'analysis_execution_status': store.read(root / 'state.json').get('analysis', {}).get('status'),
                      'response_rows_sha256': comparisons['response_rows_sha256']}
            store.event(root, 'ANALYSIS_AGGREGATES_REFRESHED', **result)
            return result
        if comparisons is None:
            with timing.measure(root, 'relationship_aggregation'):
                comparisons = a02.build(root)
        if comparisons['response_rows_sha256'] != store.file_hash(base / '01_results/responses.jsonl'):
            raise ValueError('ANALYSIS_ROWS_CHANGED')
        with timing.measure(root, 'comparison_request_preparation'):
            requests = comparison_requests(root, rows)
        with timing.measure(root, 'comparison_models', planned_requests=len(requests)):
            state = backend.run(root, '02_comparison', requests)
        recovery = __import__('finarch.experiments.02-analysis.recovery', fromlist=['*'])
        with timing.measure(root, 'comparison_recovery'):
            state = recovery.recover(root, '02_comparison', requests, state, backend)
        with timing.measure(root, 'comparison_collection'):
            interpretations = collect_interpretations(root, requests)
            reviews = __import__('finarch.experiments.02-analysis.02-comparison.response_assessments', fromlist=['*'])
            state = reviews.apply_gate(state, store.read(base / '02_comparison/response-assessment-summary.json'))
            store.write(base / '02_comparison/state.json', state)
            failures = __import__('finarch.experiments.02-analysis.failure_analysis', fromlist=['*'])
            failures.build(root, requests, backend)
            update(root, 'A02', state)
        if state['status'] != 'COLLECTED':
            return state
        if not interpretations:
            return finish_without_patterns(root, requests, state)
        with timing.measure(root, 'research_request_preparation'):
            requests = research_requests(root, interpretations, comparisons)
        with timing.measure(root, 'research_models', planned_requests=len(requests)):
            state = backend.run(root, '03_research', requests)
        with timing.measure(root, 'research_recovery'):
            state = recovery.recover(root, '03_research', requests, state, backend)
        with timing.measure(root, 'research_collection'):
            collect_findings(root, requests)
            update(root, 'A03', state)
        if state['status'] != 'COLLECTED':
            return state
        with timing.measure(root, 'publication'):
            a03.finish(root, finalize=False)
        return finish_postprocessing(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--aggregate-only', action='store_true')
    args = parser.parse_args()
    print(run(args.run, aggregate_only=args.aggregate_only))
