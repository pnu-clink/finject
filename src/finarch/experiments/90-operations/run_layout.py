"""Explicit Input/Evaluation/Analysis paths; legacy runs remain readable in place."""
import json
from pathlib import Path

PROMPT_FILES = {'unguided': 'prompt-unguided.md', 'guided': 'prompt-guided.md'}
LEGACY_PROMPT_FILES = {'unguided': 'p0-standard.md', 'guided': 'p1-abstention-aware.md'}
PROMPT_LABELS = {'unguided': 'Unguided Solving', 'guided': 'Criteria-Guided Solving'}


def prompt_condition(value):
    """Read historical identifiers without rewriting their saved requests."""
    return {'P0': 'unguided', 'P1': 'guided'}.get(value, value)


def prompt_label(value):
    return PROMPT_LABELS.get(prompt_condition(value), value)


def prompt_file(directory, condition):
    """Resolve current names while preserving frozen historical definitions."""
    directory = Path(directory)
    condition = prompt_condition(condition)
    for name in (PROMPT_FILES[condition], LEGACY_PROMPT_FILES[condition]):
        path = directory / name
        if path.is_file():
            return path
    raise FileNotFoundError(f'PROMPT_FILE_MISSING: {directory / PROMPT_FILES[condition]}')


def split_config(value):
    if 'evaluation' in value:
        if 'experiments' in value:
            raise ValueError('AMBIGUOUS_EXPERIMENT_CONFIGURATION')
        evaluation = value['evaluation']
        analysis = value.get('analysis', {'enabled': False})
        if not isinstance(evaluation, dict) or not isinstance(analysis, dict):
            raise ValueError('EVALUATION_AND_ANALYSIS_MUST_BE_OBJECTS')
        return evaluation, analysis
    return value.get('experiments', value), {'enabled': False}


def saved_config(root):
    return json.loads((Path(root) / 'config.json').read_text())


def ordered(root):
    return (Path(root) / 'config.json').is_file() and saved_config(root).get('layout_version') == 2


def evaluation_config(root):
    return split_config(saved_config(root))[0]


def analysis_config(root):
    return split_config(saved_config(root))[1]


def inputs(root):
    return Path(root) / ('00_input' if ordered(root) else '01-input')


def preparation(root):
    return Path(root) / '01_evaluation/01_preparation'


def definition(root):
    return Path(root) / ('01_evaluation/02_request' if ordered(root) else '00-definition')


def requests(root, model):
    return (definition(root) / model if ordered(root) else Path(root) / model / '01-requests') / 'manifest.jsonl'


def execution(root, model):
    return Path(root) / ('01_evaluation/03_execution' if ordered(root) else '') / model


def batches(root, model):
    return execution(root, model) / ('batches' if ordered(root) else '02-batches')


def validation(root, model=None):
    if ordered(root):
        return Path(root) / '01_evaluation/04_validation' / (model or '')
    return Path(root) / model / '03-results' if model else Path(root)


def plan(root):
    return definition(root) / 'plan.json' if ordered(root) else Path(root) / 'plan.json'


def template(root, name):
    if ordered(root):
        return preparation(root) / name
    from finarch.paths import SOURCE
    return SOURCE / 'experiments/templates' / name


def request_manifest_for_execution(base):
    base = Path(base)
    if base.parent.name == '03_execution' and base.parent.parent.name == '01_evaluation':
        return requests(base.parents[2], base.name)
    return base / '01-requests/manifest.jsonl'


def diagnostics(root):
    return Path(root) / ('02_analysis/01_response_review' if ordered(root) else 'analysis')
