"""On-demand compact usage series from original Preparation call records."""
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def build(bundle, phase='preparation'):
    if phase not in ('preparation', 'generation'):
        raise ValueError('INVALID_REPORT_PHASE')
    bundle = Path(bundle)
    series = defaultdict(lambda: defaultdict(int))
    seen = set()
    missing = invalid = 0
    root = bundle / ('01-preparation' if phase == 'preparation' else '02-generation')
    paths = root.glob('test-*/*-round/*/*/03-result/usage.json') if phase == 'preparation' else root.glob('0*-round/test-*/*/*/**/usage.json')
    for path in paths:
        parts = path.relative_to(root).parts
        stage = parts[2 if phase == 'preparation' else 3][:2]
        if phase == 'generation' and any(p in ('stage-history', 'failure-analysis') for p in parts):
            continue
        if stage not in (('02', '03', '05', '06') if phase == 'preparation' else ('01', '02', '03', '04', '05')):
            continue
        try:
            value = json.loads(path.read_text())
        except (OSError, ValueError):
            invalid += 1
            continue
        identity = value.get('response_id') or value.get('attempt_id') or str(path)
        if identity in seen:
            continue
        seen.add(identity)
        tokens = value.get('tokens') or {}
        total = tokens.get('total_tokens')
        if total is None:
            usage = value.get('reported_usage') or {}
            total = usage.get('total_tokens')
            if total is None and isinstance(usage.get('input_tokens'), int) and isinstance(usage.get('output_tokens'), int):
                total = usage['input_tokens'] + usage['output_tokens']
        if not isinstance(total, (int, float)) or total < 0:
            missing += 1
            continue
        match = re.fullmatch(r'test-(\d+)', parts[0 if phase == 'preparation' else 1])
        if match:
            series[(stage, value.get('model') or '모델 기록 없음')][int(match[1])] += total
    return {'run': bundle.name, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'missing_usage': missing, 'unreadable_records': invalid, 'call_records': len(seen),
            'series': [{'stage': stage, 'model': model, 'points': sorted(points.items())}
                       for (stage, model), points in sorted(series.items())]}
