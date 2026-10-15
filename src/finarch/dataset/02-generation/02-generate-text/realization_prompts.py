"""R16P: common serialization contract plus exactly one perturbation objective."""
import hashlib
from pathlib import Path
from finarch.paths import SOURCE

ROOT = SOURCE / 'dataset' / 'prompts'
FILES = {'IC_VALUE': '02-generation.02-generate-text.ic-value.md', 'IC_SOURCE': '02-generation.02-generate-text.ic-source.md',
         'IC_RELATION': '02-generation.02-generate-text.ic-relation.md', 'EA': '02-generation.02-generate-text.ea.md'}


def describe_prompt(axis):
    """Select by validated axis, never by free text or a user-supplied path."""
    if axis not in FILES:
        raise ValueError('UNKNOWN_REALIZATION_PROMPT_AXIS')
    parts = []
    for filename in ('02-generation.02-generate-text.common.md', FILES[axis]):
        text = (ROOT / filename).read_text(encoding='utf-8')
        if not text.strip():
            raise ValueError('EMPTY_REALIZATION_PROMPT')
        parts.append({'file': 'src/finarch/dataset/prompts/' + filename,
                      'sha256': hashlib.sha256(text.encode()).hexdigest(), 'text': text})
    instruction = '\n\n'.join(part['text'].strip() for part in parts)
    return {'id': 'dtt.realize.' + axis.lower(), 'version': 4 if axis == 'IC_RELATION' else 2, 'axis': axis,
            'parts': parts, 'instruction': instruction,
            'sha256': hashlib.sha256(instruction.encode()).hexdigest()}
