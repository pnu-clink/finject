"""Immutable retry feedback and verifiable references; no model calls."""
import hashlib
import json
from pathlib import Path


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def publish(path, *, case, variant, source_round, target_round, target_role, axis, guidance, source, target_step=None):
    if source_round == target_round:
        raise ValueError('FEEDBACK_ROUNDS_MUST_DIFFER')
    if not guidance.strip():
        raise ValueError('EMPTY_FEEDBACK')
    record = {'version': 1, 'case': case, 'variant': variant,
              'source_round': source_round, 'target_round': target_round,
              'target_role': target_role, 'target_step': target_step or target_role.split('.')[1],
              'axis': axis, 'guidance': guidance, 'source': str(source)}
    text = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x') as stream: stream.write(text)
    except FileExistsError:
        if path.read_text() != text: raise ValueError('FEEDBACK_RECORD_CHANGED')
    readme = path.parent/'README.md'
    if not readme.exists():
        with readme.open('x') as stream:
            stream.write(Path(__file__).with_name('feedback-record-readme.md').read_text())
    return {'path': str(path.resolve()), 'sha256': sha(text),
            'guidance_sha256': sha(guidance), 'case': case, 'variant': variant,
            'source_round': source_round, 'target_round': target_round,
            'target_role': target_role, 'target_step': record['target_step']}


def load(ref, *, case=None, target_round=None):
    text = Path(ref['path']).read_text()
    if sha(text) != ref['sha256']: raise ValueError('FEEDBACK_HASH_MISMATCH')
    record = json.loads(text)
    for key in ('case', 'variant', 'source_round', 'target_round', 'target_role', 'target_step'):
        if record[key] != ref[key]: raise ValueError('FEEDBACK_SCOPE_MISMATCH')
    if case is not None and record['case'] != case: raise ValueError('FEEDBACK_CASE_MISMATCH')
    if target_round is not None and record['target_round'] != target_round: raise ValueError('FEEDBACK_ROUND_MISMATCH')
    if sha(record['guidance']) != ref['guidance_sha256']: raise ValueError('FEEDBACK_GUIDANCE_MISMATCH')
    return record


def record_application(instruction, definition, role, save):
    parts = [p for p in definition.get('parts', []) if p.get('feedback_ref') or p.get('scope') == 'cumulative failure guidance']
    references = []
    for part in parts:
        text = part['text']
        if not text or text not in instruction: raise ValueError('FEEDBACK_NOT_IN_PROMPT')
        ref = part.get('feedback_ref')
        if ref:
            record = load(ref)
            if record['target_role'] != role or record['guidance'] != text:
                raise ValueError('FEEDBACK_ROLE_OR_TEXT_MISMATCH')
        else:
            # Legacy feedback remains readable, explicitly without round guarantees.
            path = Path(part['file'])
            original = path.read_text()
            if json.loads(original).get('guidance') != text: raise ValueError('LEGACY_FEEDBACK_CHANGED')
            ref = {'path': str(path.resolve()), 'sha256': sha(original), 'legacy': True}
        references.append({**ref, 'applied': True})
    save('01-input/feedback-ref.json', {'applied': bool(references), 'role': role,
        'reason': 'MATCHED_FEEDBACK' if references else 'NO_MATCHING_FEEDBACK',
        'references': references, 'rendered_prompt_sha256': sha(instruction)})
    save('01-input/rendered-prompt.json', {'instruction': instruction, 'sha256': sha(instruction)})
