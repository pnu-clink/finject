"""perturb.textops — text normalization, tokenization, and diff utilities.

Numeric tokenization and diff computation form the deterministic common foundation
that the Stage 1 structural predicates depend on.
"""
from __future__ import annotations

import difflib

from perturb.constants import (
    RE_WS, RE_NUM, RE_NUM_PCT, RE_TOKEN,
)


# ---------------------------------------------------------------------------
# Normalization / tokenization
# ---------------------------------------------------------------------------
def normalize(s: str) -> str:
    return RE_WS.sub(" ", (s or "")).strip()


def number_tokens(s: str):
    """Extract numeric tokens from text (percentages included, thousands commas stripped)."""
    return [m.group(0).replace(",", "") for m in RE_NUM_PCT.finditer(s or "")]


def number_only_floats(s: str):
    """Float sequence for comparison (percentage sign stripped). Duplicates are preserved."""
    out = []
    for m in RE_NUM.finditer(s or ""):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return out


def tokenize(s: str):
    return RE_TOKEN.findall(s or "")


# ---------------------------------------------------------------------------
# diff (changed tokens / character positions of changed tokens in source)
# ---------------------------------------------------------------------------
def diff_change_tokens(orig: str, mod: str):
    a, b = tokenize(orig), tokenize(mod)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    added = []
    for tag, _, _, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            added.extend(b[j1:j2])
    return added


def diff_change_token_positions(orig: str, mod: str):
    a = tokenize(orig)
    b_pos = [(m.group(0), m.start(), m.end()) for m in RE_TOKEN.finditer(mod or "")]
    b = [t[0] for t in b_pos]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    spans = []
    for tag, _, _, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            for k in range(j1, j2):
                _, s, e = b_pos[k]
                spans.append((s, e))
    return spans


def merge_spans(spans, gap=2):
    if not spans:
        return []
    spans = sorted(spans)
    out = [list(spans[0])]
    for s, e in spans[1:]:
        if s <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [tuple(x) for x in out]


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------
def _fmt_num(n):
    """800.0 → '800', 10.5 → '10.5' — strips the trailing .0 from integer-valued floats for readability."""
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return str(n)


def _fmt_num_seq(seq):
    return [_fmt_num(n) for n in seq]


def _fmt_num_list(items):
    return ", ".join(items) if items else "—"


def _fmt_token_list(items, limit=10):
    items = [t for t in items if not RE_NUM_PCT.fullmatch(t)]
    seen = []
    for t in items:
        if t not in seen:
            seen.append(t)
        if len(seen) >= limit:
            seen.append("…")
            break
    return ", ".join(seen) if seen else "—"
