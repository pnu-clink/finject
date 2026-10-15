"""Read Phi-two records on demand without executing candidate code."""
from pathlib import Path
import json


def read(path):
    if not path.is_file() or path.is_symlink():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as error:
        return {'read_error': str(error)}


# [VP04] docs/55-viewer-speed-and-phi-two.md — selected records only.
def load(root, run=None, case=None):
    candidates = [p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and (read(p/'config.json') or {}).get('workflow') == 'phi_two']
    selected = next((p for p in candidates if p.name == run), None) if run else max(candidates, key=lambda p:p.name, default=None)
    if selected is None:
        raise ValueError('UNKNOWN_PHI_TWO_RUN')
    selection = read(selected/'selection.json') or []
    result = {'runs': sorted(p.name for p in candidates), 'selected': selected.name, 'path': str(selected), 'progress': read(selected/'progress.json'), 'graph_execution': 'NOT_EXECUTED'}
    if case is None:
        result['cases'] = [{'id': item['id']} for item in selection]
        return result
    if case not in {item['id'] for item in selection}:
        raise ValueError('UNKNOWN_PHI_TWO_CASE')
    folder = selected/'cases'/case
    if not folder.resolve().is_relative_to((selected/'cases').resolve()) or any(p.is_symlink() for p in [folder, *folder.parents] if p.is_relative_to(selected)):
        raise ValueError('INVALID_PHI_TWO_PATH')
    result.update(case=case, input=read(folder/'input.json'), result=read(folder/'result.json'), files={})
    for relative in ('python-validation.json', 'attempt-01/response.json', 'attempt-01/web-activity.json', 'attempt-01/validation.json'):
        result['files'][str(folder/relative)] = read(folder/relative)
    result['case_path'] = str(folder)
    return result
