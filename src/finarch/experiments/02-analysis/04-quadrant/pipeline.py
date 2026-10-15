"""Run registered post-A03 quadrant steps through the configured Analysis backend."""
from pathlib import Path
from finarch.experiments import assets

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
timing = __import__('finarch.experiments.02-analysis.timing', fromlist=['*'])
results = __import__('finarch.experiments.02-analysis.01-results.results', fromlist=['*'])
backend = __import__('finarch.experiments.02-analysis.llm_backend', fromlist=['*'])
grouping = __import__('finarch.experiments.02-analysis.04-quadrant.01-findings.grouping', fromlist=['*'])
STAGE = '04_quadrant'
SOURCE_PATHS = ('02_analysis/03_research/findings.json',
                '02_analysis/02_comparison/interpretations.jsonl',
                '02_analysis/01_results/responses.jsonl')


def prepare(root):
    """Keep the frozen F-only request on resume and reject changed source data."""
    if store.read(root / '02_analysis/03_research/state.json', {}).get('status') != 'COLLECTED':
        raise ValueError('A04_REQUIRES_COMPLETED_A03')
    source = store.read(root / SOURCE_PATHS[0])
    if source['run'] != root.name:
        raise ValueError('A04_FINDINGS_RUN_MISMATCH')
    hashes = {p: store.file_hash(root / p) for p in SOURCE_PATHS}
    folder = root / '02_analysis' / STAGE
    previous = store.read(folder / 'source-hashes.json')
    if previous is not None and previous != hashes:
        raise ValueError('A04_FROZEN_SOURCE_CHANGED')
    linked = grouping.trace(source['findings'], store.rows(root / SOURCE_PATHS[1]), store.rows(root / SOURCE_PATHS[2]))
    manifest = folder / 'manifest.jsonl'
    if manifest.exists():
        requests = store.rows(manifest)
    else:
        payload = {'run': root.name, 'scope': 'A03_FINDINGS_ONLY', 'findings': grouping.model_input(linked)}
        requests = [backend.request(root, STAGE, 'D01-findings', assets.prompt_text('quadrant_findings'),
                    assets.schema('quadrant_response'), payload)] if linked else []
        if requests and len(store.encoded(requests[0])) > 500_000:
            raise ValueError('A04_GLOBAL_GROUPING_INPUT_BUDGET_EXCEEDED')
        store.write(folder / 'source-hashes.json', hashes)
    if requests and requests[0]['input']['findings'] != grouping.model_input(linked):
        raise ValueError('A04_FINDING_INPUT_CHANGED')
    return requests, linked, hashes


def finding_step(root):
    requests, linked, hashes = prepare(root)
    folder = root / '02_analysis' / STAGE
    target = folder / '01_findings'
    cached = store.read(target / 'summary.json')
    cached_state = store.read(target / 'state.json', {})
    result = backend.latest(folder, requests[0]) if requests else None
    if (cached and cached.get('source_hashes') == hashes
            and cached_state.get('summary_sha256') == store.file_hash(target / 'summary.json')
            and result and result['status'] == 'VALID'
            and not backend.contracts.validate_response(result['response'], requests[0])
            and all(cached.get(key) == value for key, value in grouping.collect(result['response'], linked).items())):
        store.event(root, 'A04_CACHED_FINDING_GROUPS_REUSED', stage='A04', new_model_calls=0)
        state = store.read(folder / 'state.json')
        return {k: v for k, v in state.items() if k not in ('steps', 'stage', 'completed_at')} | {
            'counts': cached['counts'], 'artifact': '01_findings/summary.json', 'new_model_calls': 0, 'reused': True}
    with timing.measure(root, 'finding_grouping', stage='A04', substep='D01'):
        state = backend.run(root, STAGE, requests)
        recovery = __import__('finarch.experiments.02-analysis.recovery', fromlist=['*'])
        state = recovery.recover(root, STAGE, requests, state, backend)
        if state['status'] != 'COLLECTED':
            return state
        value = backend.latest(folder, requests[0])['response'] if requests else {'run': root.name, 'groups': []}
        if requests:
            errors = backend.contracts.validate_response(value, requests[0])
            if errors:
                raise ValueError('A04_SAVED_GROUPING_INVALID:' + str(errors))
        for path, digest in hashes.items():
            if store.file_hash(root / path) != digest:
                raise ValueError('A04_SOURCE_CHANGED:' + path)
        data = grouping.collect(value, linked)
        data.update(generated_at=store.now(), source_hashes=hashes,
                    request_ids=[r['trial_id'] for r in requests])
        store.write(target / 'summary.json', data)
        store.write(target / 'state.json', {'status': 'COLLECTED', 'step': 'D01', 'counts': data['counts'],
            'summary_sha256': store.file_hash(target / 'summary.json')})
        return state | {'counts': data['counts'], 'artifact': '01_findings/summary.json'}


# Further A04 steps append here; D01 depends only on the completed A03 findings.
STEPS = (('D01', finding_step),)


def run(root):
    root = Path(root).resolve()
    steps = []
    for code, function in STEPS:
        state = function(root)
        steps.append({'step': code, **state})
        if state['status'] != 'COLLECTED':
            current = store.read(root / 'state.json')
            current['analysis'] = {**current.get('analysis', {}), **state, 'stage': 'A04'}
            store.write(root / 'state.json', current)
            return state
    folder = root / '02_analysis' / STAGE
    completed = {**state, 'status': 'COLLECTED', 'stage': 'A04', 'steps': steps, 'completed_at': store.now()}
    store.write(folder / 'state.json', completed)
    results.render(root, '04_quadrant', findings=state['counts']['findings'], groups=state['counts']['groups'])
    current = store.read(root / 'state.json')
    current['analysis'] = {**current.get('analysis', {}), 'status': 'COMPLETE', 'stage': 'A04', 'postprocessing': completed}
    store.write(root / 'state.json', current)
    results.render(root, 'analysis', source=root.name, status='A01·A02·A03·A04 완료')
    store.event(root, 'ANALYSIS_POSTPROCESSING_COMPLETED', stage='A04', **state['counts'])
    timing.refresh(root, force=True)
    return completed
