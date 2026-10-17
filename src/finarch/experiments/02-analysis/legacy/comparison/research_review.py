"""A03: explicit research interpretation using the selected analysis backend."""
import argparse
from collections import defaultdict
from pathlib import Path

review = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_review', fromlist=['*'])
store, layout = review.store, review.run_layout


def prepare(root):
    root = Path(root).resolve()
    review.pipeline.verify(root)
    folder = root / '02_analysis/03_research'
    manifest = folder / 'manifest.jsonl'
    if manifest.exists():
        for relative, expected in store.rows(manifest)[0]['source_hashes'].items():
            if store.file_hash(root / relative) != expected:
                raise ValueError('RESEARCH_SOURCE_CHANGED:' + relative)
        return folder
    summary_path = root / '02_analysis/02_comparison/summary.json'
    rows_path = summary_path.parent / 'rows.jsonl'
    summary, rows = store.read(summary_path), store.rows(rows_path)
    if not summary or not rows:
        raise ValueError('A02_RESULTS_REQUIRED_BEFORE_RESEARCH')
    review.checked_results(root / review.ROOT / '02-LLM-response')
    selected = {row['item_id'] for row in rows if row['variant'] == 'ORIGINAL'}
    groups = defaultdict(list)
    for row in rows:
        outcome = (row.get('review') or {}).get('outcome', 'NOT_REVIEWED')
        if outcome == 'UNRESOLVED' or row.get('input_classification') == 'ANSWERABLE':
            selected.add(row['item_id'])
        groups[('variant', row['variant'])].append(row)
        groups[('outcome', outcome)].append(row)
    for group in groups.values():
        selected.add(sorted(group, key=lambda r: (r.get('appropriate') is True, r['item_id'], r['trial_id']))[0]['item_id'])
    public = {r['item_id']: r for r in store.rows(layout.inputs(root) / 'public.jsonl')}
    assessments = {r['item_id']: r for r in review.effective_results(root / review.ROOT / '01-LLM-input')}
    evidence = []
    source_paths = [summary_path, rows_path, layout.inputs(root) / 'public.jsonl']
    for stage in ('01-LLM-input', '02-LLM-response'):
        source_paths.append(root / review.ROOT / stage / 'results.jsonl')
        retry = root / review.ROOT / stage / 'retry-001/results.jsonl'
        if retry.exists():
            source_paths.append(retry)
    sources = {str(p.relative_to(root)): store.file_hash(p) for p in source_paths}
    for row in rows:
        if row['item_id'] not in selected:
            continue
        path = root / row['result_path'] if row.get('result_path') else None
        saved = store.read(path, {}) if path else {}
        evidence.append({**row, 'solver_response': saved.get('response')})
        if path and path.exists():
            sources[row['result_path']] = store.file_hash(path)
    items = [{**public[key], 'provisional_assessment': assessments[key].get('response'),
              'assessment_status': assessments[key]['status']} for key in sorted(selected)]
    data = {'scope': 'FILE_FLOW_PILOT_NOT_CONFIRMATORY',
            'statistics': {k: v for k, v in summary.items() if k not in ('review_stages', 'analysis_config')},
            'evidence_selection': 'ALL_ORIGINALS_ANSWERABLE_INPUTS_UNRESOLVED_REVIEWS_PLUS_ONE_ITEM_PER_VARIANT_AND_OUTCOME_ALL_CONDITIONS_NOT_RANDOM',
            'items': items, 'evidence': evidence,
            'solver_prompts': {path.name: path.read_text() for path in
                               [layout.definition(root) / 'common.md',
                                *(layout.prompt_file(layout.definition(root), condition) for condition in layout.PROMPT_FILES)]}}
    model = review.model_for(root)
    request = {'item_id': root.name, 'stage': 'research', 'model': model['model'],
               'reasoning_effort': model['reasoning_effort'],
               'prompt': (store.PROJECT / 'experiment/archtecture/analysis/research-review.md').read_text(),
               'response_schema': review.contract.RESEARCH_SCHEMA, 'input': data, 'source_hashes': sources}
    if model['transport'] == 'openai_batch':
        request['max_output_tokens'] = model.get('max_output_tokens', 65536)
    request['trial_id'] = store.digest(request)[:32]
    store.write_rows(manifest, [request])
    store.event(root, 'RESEARCH_REVIEW_PREPARED', model=model['model'], reasoning=model['reasoning_effort'],
                evidence_items=len(items), evidence_responses=len(evidence), solver_calls=0)
    return folder


def run(root):
    root = Path(root).resolve()
    folder = prepare(root)
    state = review.run_stage(root, folder)
    if state['status'] == 'COLLECTED':
        results = review.checked_results(folder)
        store.event(root, 'RESEARCH_REVIEW_COLLECTED', statuses=state['statuses'],
                    user_decision='PENDING', automatic_improvements=False)
        if results[0]['status'] == 'VALID' and not (folder / 'findings.md').exists():
            render(root)
        return results[0]
    return state


def render(root, notes_ko=None):
    """Generate the saved report; Korean display notes never replace raw judgments."""
    root = Path(root).resolve()
    folder = root / '02_analysis/03_research'
    result = review.checked_results(folder)[0]
    if result['status'] != 'VALID':
        raise ValueError('VALID_RESEARCH_REVIEW_REQUIRED')
    evidence = result['response']
    if notes_ko is None:
        notes = 'Below is the English preface to the analysis model and the Korean review description is pending.\n\n' + evidence['overall_assessment']
        for finding in evidence['findings']:
            notes += '\n\n- **' + finding['title'] + '**: ' + finding['observation'] + '\n  - Alternative: ' + finding['alternative_explanation'] + '\n  - Limitation: ' + finding['limitation']
    else:
        notes = notes_ko
    summary = store.read(root / '02_analysis/02_comparison/summary.json')
    overall = summary['overall']
    evaluation = store.read(layout.validation(root) / 'summary.json')
    model = review.model_for(root)
    conditions = [(prompt, reasoning) for prompt in layout.PROMPT_FILES for reasoning in ('off', 'on')]
    matrix = 'The model is the model of the model, the model is the one that is the model, and the model is a model of the Model, the model, which is the model.\n|---|---|---:|---:|---:|---:|'
    variants = review.pipeline.dataset.LABELS
    for solver in sorted({r.get('model') or 'Aggregated across existing models' for r in summary['matrix']}):
        for variant in ['ORIGINAL', *variants]:
            cells = []
            for prompt, reasoning in conditions:
                cell = next((r for r in summary['matrix'] if (r.get('model') or '\uae30\uc874 \ubaa8\ub378 \ud569\uc0b0', r['variant'], layout.prompt_condition(r['prompt']), r['reasoning']) == (solver, variant, prompt, reasoning)), None)
                cells.append(f"{cell['appropriate']}/{cell['assessed']} ({cell['unassessed']})" if cell else 'Not recorded')
            matrix += '\n|' + solver + '|' + variant + '|' + '|'.join(cells) + '|'
    config = store.configuration(root)
    limits = {r['max_output_tokens'] for m in config['models'] for r in store.rows(layout.requests(root, m['key']))}
    fields = dict(run=root.name, originals=evaluation['originals'], variants=evaluation['variants'],
                  planned=overall['planned'], valid=overall['format_valid'], numeric_matches=overall['numeric_matches'],
                  numeric_compared=overall['numeric_compared'], assessed=overall['assessed'], unassessed=overall['unassessed'],
                  analysis_model=model['model'], effort=model['reasoning_effort'], backend=model['backend'],
                  solver_models=', '.join(m['model'] + ' · ' + m['transport'] for m in config['models']),
                  analysis_billing='The additional API for Codex analysis is 0So subscriber usage is a star.' if model['backend'] == 'codex' else
                      'API analysis cost-benefit analysis is determined in the cost estimate and raw response of each analysis step state.json.',
                  matrix=matrix, notes=notes, run_output_limit=', '.join(map(str, sorted(limits))),
                  cost=sum(m.get('paid_batch_usage_cost_estimate_usd', 0) for m in evaluation['models']))
    template = store.PROJECT / 'src/finarch/experiments/templates/research-findings-template.md'
    text = template.read_text().format(**fields)
    store.write_text(folder / 'findings.md', text)
    if notes_ko is not None:
        store.event(root, 'STUDY_CRITICAL_REVIEW', report_ko=text, analysis_model=model['model'],
                    source=str((folder / 'results.jsonl').relative_to(root)), user_decision='PENDING',
                    review_status='REQUIRES_ADJUDICATION' if any(r['priority'] == 'HIGH' for r in evidence['recommendations']) else 'PROVISIONAL',
                    automatic_improvements=False)
    return text


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    result = run(Path(args.run))
    print(result['status'])
