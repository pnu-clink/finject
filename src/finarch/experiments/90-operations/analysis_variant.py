"""Prepare a tagged Analysis run from byte-identical completed Evaluation files."""
from pathlib import Path
import re

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
settings = __import__('finarch.experiments.90-operations.settings', fromlist=['*'])
results = __import__('finarch.experiments.02-analysis.01-results.results', fromlist=['*'])


def prepare(source, target, path, tag, authorization):
    source, target, path = Path(source).resolve(), Path(target).resolve(), Path(path).resolve()
    if not authorization or not authorization.strip():
        raise ValueError('ANALYSIS_VARIANT_AUTHORIZATION_REQUIRED')
    if not isinstance(tag, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', tag):
        raise ValueError('ANALYSIS_TAG_INVALID')
    if not target.name.endswith('-' + tag):
        raise ValueError('ANALYSIS_TAG_MUST_MATCH_RUN_SUFFIX')
    _, selected = settings.load_file(path)
    chosen = selected['backends'][selected['backend']]
    print(f'[{store.now()}] TASK_START ' + store.encoded({
        'run': target.name, 'analysis_tag': tag, 'stage': 'A00', 'processor': 'PYTHON',
        'task': 'Prepare a fresh Analysis run from byte-identical completed Evaluation files.',
        'model': chosen['model'], 'reasoning_effort': chosen['reasoning_effort'],
        'concurrency': selected['schedule']['concurrency'], 'new_model_calls': 0}).decode(), flush=True)
    with store.locked(source / '.full-pipeline.lock'), store.locked(source / '.analysis.lock'):
        state = store.read(source / 'state.json')
        models = state.get('models', {})
        if not models or any(m.get('status') != 'FINISHED' for m in models.values()):
            raise ValueError('ANALYSIS_VARIANT_REQUIRES_FINISHED_EVALUATION')
        if not (source / '01_evaluation/04_validation/numeric-comparisons.jsonl').is_file():
            raise ValueError('ANALYSIS_VARIANT_REQUIRES_RECORDED_NUMERIC_COMPARISONS')
        results.prepare(source, target, analysis=selected, tag=tag)
        store.write(target / '02_analysis/config.json', {'analysis': selected,
            'analysis_sha256': store.digest(selected), 'source_path': str(path),
            'source_sha256': store.file_hash(path), 'frozen_at': store.now()})
        store.command(target)
        store.event(target, 'ANALYSIS_VARIANT_PREPARED', analysis_tag=tag,
                    source_run=source.name, authorization=authorization, new_model_calls=0,
                    previous_analysis_reused=False, execution_scope='ANALYSIS_ONLY')
        return {'run': str(target), 'analysis_tag': tag, 'evaluation_source': source.name,
                'new_model_calls': 0, 'previous_analysis_reused': False}
