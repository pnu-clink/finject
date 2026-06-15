"""perturb.purpose_fit.ic_common — helpers shared across the three IC types.

Value-check is anchored to python_solution essential literals, but the comparison
is performed between 'original context value X that unit-matches the solution' and
'added value Y' (same notation → avoids % ↔ decimal mismatches, reduces
cross-quantity false positives). Source labels (10-K) are excluded from extraction.
"""
from __future__ import annotations

from collections import Counter

from perturb.constants import SOURCE_LABEL_RE
from perturb.textops import number_only_floats
from perturb.purpose_fit._common import _expand_units
from perturb.purpose_fit.ea_full import _split_sentences


def clean_floats(text: str):
    """Removes source labels (10-K/8-K/10-Q) before RE_NUM extraction to prevent mislabeled-number false positives."""
    return number_only_floats(SOURCE_LABEL_RE.sub(" ", text or ""))


def added_values(ctx_orig: str, ctx_perturbed: str):
    """Numeric values newly appearing in perturbed (labels excluded, multiset diff)."""
    o = Counter(number_only_floats(ctx_orig or ""))
    p = Counter(clean_floats(ctx_perturbed))
    return list((p - o).elements())


def essential_context_values(ctx_orig: str, python_solution: str):
    """Original context values that unit-match the solution's essential literals (anchor basis).

    Returns an empty list if no literals exist (variable-only solution) →
    value-check cannot be applied (Stage 2).
    """
    lits = number_only_floats(python_solution or "")
    if not lits:
        return []
    sol_exp = set()
    for v in lits:
        sol_exp |= _expand_units(v)
    return [x for x in number_only_floats(ctx_orig or "") if _expand_units(x) & sol_exp]


def added_sentences(ctx_orig: str, ctx_perturbed: str):
    """Sentences present only in perturbed (diff-scope). Limits attribution/cue checks to added content."""
    so = {s.strip() for s in _split_sentences(ctx_orig or "")}
    return [s for s in _split_sentences(ctx_perturbed or "") if s.strip() not in so]


def same_magnitude(x: float, y: float) -> bool:
    """Returns True if y is a same-magnitude variant of x (0.5~2×, but not equal) — IC-value second value check."""
    if x == 0:
        return False
    r = y / x
    return 0.5 <= r <= 2.0 and abs(r - 1.0) > 1e-6
