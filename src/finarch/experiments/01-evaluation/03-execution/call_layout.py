"""Readable call files with immutable attempt records nested under each type."""
import re
from pathlib import Path

run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])

read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write

TYPE_FOLDERS = {
    'ORIGINAL': '00-Original',
    'IC_VALUE_01_BEFORE': '01-IC-value-before',
    'IC_VALUE_01_AFTER': '02-IC-value-after',
    'IC_SOURCE_A_ONLY': '03-IC-source-before',
    'IC_SOURCE_B_ONLY': '04-IC-source-after',
    'IC_RELATION_01': '05-IC-relation',
    'EA_01': '06-EA-01',
    'EA_02': '07-EA-02',
}


def component(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('UNSAFE_CALL_PATH_COMPONENT')
    return value


def call_path(base, request):
    case = component(request['case'])
    prompt, reasoning = request['prompt_condition'], request['reasoning']
    if run_layout.prompt_condition(prompt) not in run_layout.PROMPT_FILES or reasoning not in ('off', 'on'):
        raise ValueError('UNKNOWN_CALL_CONDITION')
    folder = TYPE_FOLDERS[request['variant']]
    return Path(base) / 'calls' / case / folder / f'{case}-{prompt}-R-{reasoning}.json'


def record_dir(base, request):
    return call_path(base, request).parent / '_records' / component(request['trial_id'])


def attempt_dirs(base, request):
    """Read both layouts, rejecting ambiguity instead of counting a call twice."""
    old = Path(base) / '02-calls' / component(request['trial_id'])
    new = record_dir(base, request)
    if old.exists() and new.exists():
        raise ValueError('DUPLICATE_CALL_RECORD_LAYOUT:' + request['trial_id'])
    return sorted((old if old.exists() else new).glob('attempt-[0-9]*'),
                  key=lambda p: int(p.name.removeprefix('attempt-')))


def result_paths(base, request):
    return [p / 'result.json' for p in attempt_dirs(base, request) if (p / 'result.json').exists()]


def attempt_path(base, request, number):
    # Revalidation of an unmigrated run must not create a second copy of a call.
    old = Path(base) / '02-calls' / component(request['trial_id'])
    new = record_dir(base, request)
    if old.exists() and new.exists():
        raise ValueError('DUPLICATE_CALL_RECORD_LAYOUT:' + request['trial_id'])
    return (old if old.exists() else new) / f'attempt-{number:03d}'


def all_results(base):
    return [path for request in rows(run_layout.request_manifest_for_execution(base))
            for path in result_paths(base, request)]


def check_manifest(base, requests):
    paths, ids = set(), set()
    for request in requests:
        path = call_path(base, request)
        if path in paths or request['trial_id'] in ids:
            raise ValueError('CALL_IDENTITY_COLLISION:' + str(path))
        paths.add(path)
        ids.add(component(request['trial_id']))


def response_text(raw):
    """Extract saved provider text for inspection, including broken JSON."""
    if isinstance(raw, dict):
        body = raw.get('response', raw)
        if isinstance(body, dict) and isinstance(body.get('body'), dict):
            body = body['body']
        if isinstance(body, dict) and isinstance(body.get('output'), list):
            messages = [item for item in body['output'] if item.get('type') == 'message']
            finals = [item for item in messages if item.get('phase') == 'final_answer']
            return ''.join(part.get('text', '') for item in finals or messages
                           for part in item.get('content', []) if part.get('type') == 'output_text')
        if isinstance(body, dict) and 'candidates' in body:
            return ''.join(p.get('text', '') for c in body.get('candidates', [])
                           for p in c.get('content', {}).get('parts', []) if not p.get('thought'))
        if isinstance(body, dict) and isinstance(body.get('choices'), list):
            return ''.join(choice.get('message', {}).get('content') or '' for choice in body['choices'])
        return raw.get('result') if isinstance(raw.get('result'), str) else None
    if isinstance(raw, list):
        messages = [x.get('item', {}).get('text') for x in raw if isinstance(x, dict)
                    and x.get('type') == 'item.completed' and x.get('item', {}).get('type') == 'agent_message']
        if messages:
            return messages[-1]
        return next((x.get('result') for x in reversed(raw)
                     if isinstance(x, dict) and isinstance(x.get('result'), str)), None)
    return None


def publish(root, base, request, checked):
    """Build a convenience view; cost and resume always use attempt records."""
    attempts = attempt_dirs(base, request)
    if not attempts:
        return None
    latest = attempts[-1]
    result = read(latest / 'result.json', {'status': 'UNKNOWN_DELIVERY', 'usage': None})
    raw_path = latest / 'raw-response.json'
    records = []
    for attempt in attempts:
        item = read(attempt / 'result.json', {'status': 'UNKNOWN_DELIVERY'})
        records.append({'attempt': attempt.name, 'status': item['status'],
                        'directory': str(attempt.relative_to(root)),
                        'result_path': str((attempt / 'result.json').relative_to(root))
                                       if (attempt / 'result.json').exists() else None})
    raw = None
    if raw_path.exists():
        try:
            raw = response_text(read(raw_path))
        except ValueError:
            raw = raw_path.read_text()
    payload = {'case': request['case'], 'type': TYPE_FOLDERS[request['variant']],
               'variant': request['variant'], 'prompt_condition': request['prompt_condition'],
               'reasoning': request['reasoning'], 'status': result['status'],
               'response': result.get('response'), 'response_text': raw,
               'checks': checked.get('checks'), 'request': read(latest / 'request.json', request),
               'result': {k: v for k, v in result.items() if k != 'response'},
               'records': {'trial_id': request['trial_id'], 'paths_relative_to': 'EXPERIMENT_RUN_ROOT',
                           'raw_response_path': str(raw_path.relative_to(root)) if raw_path.exists() else None,
                           'attempts': records}}
    path = call_path(base, request)
    if read(path) != payload:
        write(path, payload)
    return str(path.relative_to(root))
