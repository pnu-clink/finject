"""R17P: select one semantic-audit type with the unchanged three-finding contract."""
import hashlib
from pathlib import Path
from finarch.paths import SOURCE

ROOT = SOURCE / 'dataset' / 'prompts'
FILES = {'ANSWER': '01-preparation.02-review-and-correct.answer.md', 'IC_VALUE': 'shared.01-02.02-03.review-and-validation.ic-value.md', 'IC_SOURCE': 'shared.01-02.02-03.review-and-validation.ic-source.md',
         'IC_RELATION': 'shared.01-02.02-03.review-and-validation.ic-relation.md', 'EA': 'shared.01-02.02-03.review-and-validation.ea.md'}


def describe_prompt(axis):
    if axis not in FILES:
        raise ValueError('UNKNOWN_AUDIT_PROMPT_AXIS')
    parts = []
    for filename in ('shared.01-02.02-03.review-and-validation.common.md', FILES[axis]):
        text = (ROOT / filename).read_text(encoding='utf-8')
        if not text.strip():
            raise ValueError('EMPTY_AUDIT_PROMPT')
        parts.append({'file': 'src/finarch/dataset/prompts/' + filename,
                      'sha256': hashlib.sha256(text.encode()).hexdigest(), 'text': text})
    instruction = '\n\n'.join(part['text'].strip() for part in parts)
    return {'id': 'dtt.audit.' + axis.lower(), 'version': 4 if axis == 'IC_RELATION' else 2, 'axis': axis,
            'parts': parts, 'instruction': instruction,
            'sha256': hashlib.sha256(instruction.encode()).hexdigest()}
