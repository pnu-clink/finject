"""Build the V5 review from current definitions and recorded offline checks."""
import difflib
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

TITLE = __import__('finarch.experiments.01-evaluation.02-request.answer_contract', fromlist=['TITLE']).TITLE
validate_request = __import__('finarch.experiments.01-evaluation.02-request.answer_contract', fromlist=['validate_request']).validate_request


def build():
    from finarch.paths import PROJECT as project
    run = project / 'reports/experiments-run/20260920-exp-006'
    output = run / 'revision-v5'
    source = project / 'src/finarch/experiments/checks/fixtures/experiment-v5/00-definition'
    names = {'common.md': 'common.md', 'p0-standard.md': 'p0-standard.md',
             'p1-abstention-aware.md': 'p1-abstention-aware.md',
             'response.schema.json': 'response.schema.json'}
    (output / 'after').mkdir(exist_ok=True)
    changes = []
    hashes = {}
    for name, relative in names.items():
        raw = (source / relative).read_bytes()
        (output / 'after' / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
        before = (output / 'before' / name).read_text()
        changes.extend(difflib.unified_diff(before.splitlines(True), raw.decode().splitlines(True),
                                          fromfile='before/' + name, tofile='after/' + name))
    (output / 'definition.diff').write_text(''.join(changes))
    schema = json.loads((output / 'after/response.schema.json').read_text())
    if schema['title'] != TITLE:
        raise ValueError('V5_REQUIRED')
    common = (output / 'after/common.md').read_text()
    for condition, name in [('P0', 'p0-standard.md'), ('P1', 'p1-abstention-aware.md')]:
        validate_request({'response_schema': schema, 'prompt_condition': condition,
                          'prompt': common + '\n' + (output / 'after' / name).read_text()})
    expected = json.loads((output / 'preserved-hashes.json').read_text())
    preserved = {name: hashlib.sha256((run / name).read_bytes()).hexdigest() == sha
                 for name, sha in expected.items()}
    if not all(preserved.values()):
        raise ValueError('PRESERVED_RECORD_CHANGED')
    pylog = (output / 'python-checks.log').read_text()
    jslog = (output / 'viewer-checks.log').read_text()
    if not re.search(r'\nOK\s*$', pylog) or not re.search(r'fail 0\b', jslog):
        raise ValueError('OFFLINE_CHECKS_NOT_PASSING')
    python_count = int(re.search(r'Ran (\d+) tests', pylog)[1])
    viewer_count = int(re.search(r'tests (\d+)', jslog)[1])
    verification = {'at': datetime.now(timezone.utc).isoformat(), 'contract': TITLE,
                    'python_tests': python_count, 'viewer_tests': viewer_count,
                    'status': 'LOCAL_CHECKS_PASSED', 'actual_model_calls': 0,
                    'source_sha256': hashes, 'preserved_files_match': preserved,
                    'browser_verified': False,
                    'limits': ['No live provider call', 'No semantic abstention scoring',
                               'No remote GPU definition update', 'Precision conflicts remain separate']}
    path = output / 'verification.json'
    if path.exists():
        previous = json.loads(path.read_text())
        if previous.get('source_sha256') == hashes:
            verification['browser_verified'] = previous.get('browser_verified', False)
            if previous.get('browser_checks'):
                verification['browser_checks'] = previous['browser_checks']
    path.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')
    template = Path(__file__).with_name('response-v5-readme-template.md').read_text()
    checks = (f"Python {python_count}items and Viewer. {viewer_count}Pass the items local exam. "
              f"The existing core record {len(preserved)}The items file is a correction of the pre-harness matching. "
              + ('Completed verification of the agent\'s actual browser display.' if verification['browser_verified']
                 else 'The browser display verification is not complete yet.'))
    (output / 'README.md').write_text(template.replace('{{date}}', '2026-09-22')
        .replace('{{schema}}', json.dumps(schema, ensure_ascii=False, indent=2))
        .replace('{{checks}}', checks))
    with (output / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'at': verification['at'], 'event': 'LOCAL_REVIEW_BUILT',
                                 'contract': TITLE, 'actual_model_calls': 0}) + '\n')
    return verification


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False))
