"""Read case-local rounds and bridge historical display keys without disk writes."""
import re
from pathlib import Path

ROUND = re.compile(r'^\d{2,}-round$')


def round_names(case):
    case = Path(case)
    return sorted(p.name for p in case.iterdir() if p.is_dir() and not p.is_symlink() and ROUND.fullmatch(p.name)) if case.is_dir() else []


def select_round(case, requested=None, report=None):
    rounds = round_names(case)
    if not rounds:
        return Path(case), None
    active = (report or {}).get('active_round')
    if isinstance(active, int):
        active = f'{active:02d}-round'
    selected = requested or (active if active in rounds else rounds[-1])
    if selected not in rounds:
        # An earlier successful case may have no new retry in the selected batch round.
        earlier = [r for r in rounds if r <= selected]
        if not earlier:
            return None, None
        selected = earlier[-1]
    return Path(case)/selected, selected


def add_read_aliases(artifacts, aliases):
    """Only aliases: physical names remain visible and values are never rewritten."""
    pairs = [
        ('02-review/', '02-review-and-correct/'),
        ('03-calculation/02-LLM-generate-code/', '03-calculation/01-LLM-generate-code/'),
        ('03-calculation/03-preserve-response-and-code/', '03-calculation/02-prepare-code/'),
        ('03-calculation/04-execute-python/', '03-calculation/03-execute-python/'),
        ('03-calculation/05-record-calculation-artifacts/', '03-calculation/04-compare-answer/'),
        ('04-graph/05-save-graph/', '04-graph/04-save-graph/'),
        ('07-human-review/01-collect-review-package/', '07-human-review/01-collect-results/'),
        ('07-human-review/03-record-decision/', '07-human-review/02-record-decision/'),
    ]
    for original, value in list(artifacts.items()):
        for current, historical in pairs:
            if original.startswith(current):
                alias = historical+original[len(current):]
                if alias not in artifacts:
                    artifacts[alias] = value
                    aliases[alias] = aliases.get(original, original)
    exact = {
        '03-calculation/05-record-calculation-artifacts/03-program.json': '03-calculation/02-prepare-code/03-program.json',
        '03-calculation/03-preserve-response-and-code/08-program.json': '03-calculation/02-prepare-code/03-program.json',
        '03-calculation/05-record-calculation-artifacts/01-stage-output.json': '03-calculation/05-stage-output.json',
        '03-calculation/05-record-calculation-artifacts/02-comparison.json': '03-calculation/04-compare-answer/01-comparison.json',
        '03-calculation/03-preserve-response-and-code/07-transformation.json': '03-calculation/02-prepare-code/01-transformation.json',
        '05-verification/08-record-verdict/01-result.json': '05-verification/08-verdict.json',
    }
    for original, alias in exact.items():
        if original in artifacts and alias not in artifacts:
            artifacts[alias] = artifacts[original]
            aliases[alias] = aliases.get(original, original)
    # Rejected POT still has a preserved response/code; show it as diagnostic data.
    diagnostic = '03-calculation/03-preserve-response-and-code/'
    for original, value in list(artifacts.items()):
        if original.startswith(diagnostic):
            alias = '03-calculation/01-LLM-generate-code/04-diagnostics/'+original[len(diagnostic):]
            if alias not in artifacts:
                artifacts[alias] = value
                aliases[alias] = original
        # Historical stage names are exposed under the current menu without changing files.
    for original, value in list(artifacts.items()):
        if original.startswith(('02-review-and-correct/', '02-audit-meaning/')):
            alias = '02-review/'+original.split('/', 1)[1]
            if alias not in artifacts:
                artifacts[alias] = value
                aliases[alias] = aliases.get(original, original)


def feedback_sources(case_root, artifacts):
    """Resolve referenced feedback within this case only; expose integrity explicitly."""
    import hashlib
    import json
    root = Path(case_root).resolve()
    result = {}
    for path, record in artifacts.items():
        if not path.endswith('/feedback-ref.json') or not isinstance(record, dict):
            continue
        sources = []
        for ref in record.get('references', []):
            source = Path(ref.get('path', ''))
            if not source.is_absolute():
                source = root/source
            if not source.resolve().is_relative_to(root) or source.is_symlink() or any(
                    p.is_symlink() for p in source.parents if p.is_relative_to(root)):
                sources.append({'path': str(source), 'error': 'FEEDBACK_OUTSIDE_CASE'})
                continue
            try:
                raw = source.read_bytes()
                sources.append({'path': str(source), 'sha256': hashlib.sha256(raw).hexdigest(),
                    'hash_matches': hashlib.sha256(raw).hexdigest() == ref.get('sha256'),
                    'content': json.loads(raw)})
            except (ValueError, OSError) as error:
                sources.append({'path': str(source), 'error': str(error)})
        result[path] = sources
    return result
