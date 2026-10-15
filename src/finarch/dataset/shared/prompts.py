"""Load immutable prompt text from the shared source prompt directory."""
from pathlib import Path
from finarch.paths import SOURCE
ROOT = SOURCE / 'dataset' / 'prompts'

def read_prompt(filename):
    if Path(filename).name != filename:
        raise ValueError('INVALID_PROMPT_FILENAME')
    text = (ROOT / filename).read_text(encoding='utf-8')
    if not text.strip():
        raise ValueError('EMPTY_PROMPT')
    return text
