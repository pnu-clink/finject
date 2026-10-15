"""Serve registered dashboard pages and read-only project or experiment data."""
import json
from pathlib import Path

PROJECT = (Path(__file__).resolve().parent / '../../../..').resolve()
ASSETS = {
    '/dashboard/common.css': 'common.css',
    '/dashboard/03-project/': '03-project/index.html',
    '/dashboard/03-project/index.html': '03-project/index.html',
    '/dashboard/03-project/project.css': '03-project/project.css',
    '/dashboard/03-project/project.js': '03-project/project.js',
    '/dashboard/01-overview/': '01-overview/index.html',
    '/dashboard/01-overview/index.html': '01-overview/index.html',
    '/dashboard/01-overview/overview.css': '01-overview/overview.css',
    '/dashboard/01-overview/overview.js': '01-overview/overview.js',
    '/dashboard/02-explorer/': '02-explorer/index.html',
    '/dashboard/02-explorer/index.html': '02-explorer/index.html',
    '/dashboard/02-explorer/explorer.css': '02-explorer/explorer.css',
    '/dashboard/02-explorer/explorer.js': '02-explorer/explorer.js',
}
CONTENT_TYPES = {'.html': 'text/html; charset=utf-8',
                 '.css': 'text/css; charset=utf-8',
                 '.js': 'text/javascript; charset=utf-8'}


def resource(route, query=None, project=PROJECT):
    """Return a registered asset or saved-data payload; never accept a file path."""
    query = query or {}
    if route in ASSETS:
        root = Path(project) / 'viewer' / 'dashboard'
        target = root / ASSETS[route]
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            raise ValueError('INVALID_DASHBOARD_ASSET')
        return target.read_bytes(), CONTENT_TYPES[target.suffix]
    if route == '/api/project/status':
        loader = __import__('finarch.dashboard.03-project.monitor',
                            fromlist=['load_project_data']).load_project_data
        payload = loader(project=Path(project))
        return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8'
    if route == '/api/project/source':
        source = __import__('finarch.dashboard.03-project.monitor',
                            fromlist=['source_bytes']).source_bytes
        ref = query.get('ref', [''])[0]
        if not ref or len(ref) > 100:
            raise ValueError('INVALID_PROJECT_SOURCE_REF')
        return source(ref, project=Path(project))
    load_data = __import__('finarch.dashboard.01-data.data', fromlist=['load_data']).load_data
    response_detail = __import__('finarch.dashboard.01-data.data', fromlist=['response_detail']).response_detail
    if route == '/api/dashboard/data':
        payload = load_data(project=Path(project), refresh=query.get('refresh', ['0'])[0] == '1')
    elif route == '/api/dashboard/response':
        trial_id = query.get('trial_id', [''])[0]
        if not trial_id or len(trial_id) > 128:
            raise ValueError('INVALID_DASHBOARD_TRIAL')
        try:
            payload = response_detail(trial_id, project=Path(project))
        except KeyError as error:
            raise ValueError('UNKNOWN_DASHBOARD_TRIAL') from error
    else:
        raise ValueError('UNKNOWN_DASHBOARD_RESOURCE')
    return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8'
