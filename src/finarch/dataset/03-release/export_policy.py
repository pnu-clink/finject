"""Exclude explicit current human rejections without treating failures as rejection."""
import hashlib
import json
from pathlib import Path

POLICY = 'EXCLUDE_EXPLICIT_HUMAN_REJECTIONS'
REJECTED = frozenset({'REJECT', 'REJECTED', 'EXCLUDE', 'EXCLUDED'})


def decision(record):
    for key in ('decision', 'human_decision', 'disposition'):
        value = (record or {}).get(key)
        if isinstance(value, dict):
            value = decision(value)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def review(folder, phase):
    folder = Path(folder)
    names = (('07-human-review/03-record-decision/decision.json',
              '07-human-review/02-record-decision/decision.json',
              '07-human-review/decision.json') if phase == 'preparation' else
             ('05-human-review/02-record-decision/decision.json',
              '05-human-review/decision.json',
              '04-human-review/02-record-decision/decision.json'))
    for name in names:
        path = folder / name
        if path.is_file():
            return json.loads(path.read_text()), path
    return {}, None


def current_decision(state, recorded):
    return decision(recorded) or decision(state)


def exclusion(run, case, phase, state, recorded, source, *, variant=None):
    value = current_decision(state, recorded)
    if value not in REJECTED:
        return None
    path = Path(source) if source else None
    return {'case': case, 'phase': phase, 'scope': 'variant' if variant else 'original',
            'variant': variant, 'decision': value, 'reason': 'EXPLICIT_HUMAN_REJECTION',
            'human_reason': recorded.get('reason') or state.get('human_reason', ''),
            'source': str(path.relative_to(run)) if path else None,
            'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path else None}


def aligned_ids(rows, original_ids, *, sparse=False):
    ids = [row['id'] for row in rows]
    kept = set(ids)
    if len(ids) != len(kept):
        return False
    return ids == ([case for case in original_ids if case in kept] if sparse else original_ids)
