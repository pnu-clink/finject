"""Read-only endpoints for the shared viewer's experiments panel."""
import re

PROJECT = __import__('finarch.experiments.90-operations.storage', fromlist=['PROJECT']).PROJECT
path_in = __import__('finarch.experiments.90-operations.storage', fromlist=['path_in']).path_in
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows

ROOT = PROJECT / 'reports/experiments-run'


def view(route, query):
    if route.endswith('/runs'):
        return [read(p / 'summary.json', {'run_id': p.name, 'status': 'PREPARING'})
                for p in sorted(ROOT.glob('*-exp-*'), reverse=True) if p.is_dir() and not p.is_symlink()]
    name = query.get('name', [''])[0]
    if not re.fullmatch(r'\d{8}-exp-\d{3,}(?:-\d{8})?', name):
        raise ValueError('INVALID_EXPERIMENT_RUN')
    folder = path_in(ROOT, name)
    if route.endswith('/run'):
        return {'summary': read(folder / 'summary.json'), 'plan': read(folder / 'plan.json'),
                'report': (folder / 'REPORT.md').read_text(), 'state': read(folder / 'state.json')}
    model = query.get('model', [''])[0]
    if model not in [m['key'] for m in read(folder / 'config.json')['models']]:
        raise ValueError('UNKNOWN_EXPERIMENT_MODEL')
    offset = max(0, int(query.get('offset', ['0'])[0]))
    limit = min(100, max(1, int(query.get('limit', ['25'])[0])))
    data = rows(folder / model / '03-results/results.jsonl')
    return {'rows': data[offset:offset + limit], 'total': len(data), 'offset': offset}
