"""Publish audited working QCA with an immutable comparison reference."""
import difflib
import hashlib
import json


def qca(sample):
    return {key: sample[key] for key in ('question', 'context', 'reference_answer')}


def publish(ctx, original, working, audit):
    if audit.get('status') != 'PASS':
        raise ValueError('WORKING_DATA_REQUIRES_PASSED_AUDIT')
    changes = {}
    for key in ('question', 'context', 'reference_answer'):
        before, after = str(original[key]), str(working[key])
        changes[key] = [{'operation': tag, 'before_start': i, 'before_end': j,
                         'after_start': a, 'after_end': b, 'before': before[i:j], 'after': after[a:b]}
                        for tag, i, j, a, b in difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes()]
    changed = qca(original) != qca(working)
    write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
    def publish_file(name, value):
        path = ctx.root/name
        if path.exists():
            previous = json.loads(path.read_text())
            if previous == value:return
            history = ctx.root/'data-history'
            history.mkdir(exist_ok=True)
            write(history/(str(len(list(history.glob('*.json')))+1).zfill(3)+'-'+name), previous)
            write(path, value)
            ctx.trace.artifact(name,value)
        else:ctx.save(name,value)
    if changed:publish_file('reference-data.json', original)
    publish_file('data.json', working)
    if not changed:return
    publish_file('data-comparison.json', {'reference': 'reference-data.json', 'current': 'data.json',
             'reference_qca': qca(original), 'current_qca': qca(working), 'fields': changes,
             'reason': 'Original source audit followed by correction and re-audit',
             'audit_status': audit['status'], 'human_decision': 'PENDING',
             'working_sha256': hashlib.sha256(json.dumps(working, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
