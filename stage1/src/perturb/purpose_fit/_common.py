"""perturb.purpose_fit._common — helpers shared across per-category evaluation.

The score-building helper (_build_score_dict) and numeric comparison utilities are
called by every type branch. The Type A check (_values_in_question) applies to all
6 types as well. The remaining helpers (_expand_units, is_about_ten_x,
is_within_multiplier_range) are numeric utilities consolidated in one place.
"""
from __future__ import annotations

import re

from perturb.textops import number_only_floats


# ---------------------------------------------------------------------------
# Score calculation (docs/purpose_score_design.md §3)
# ---------------------------------------------------------------------------
# 100 points distributed across only the hard, verifiable checks for each type.
# Unimplemented instructions,


def _build_score_dict(purpose_score, breakdown, type_a_reasons,
                       warnings_present, is_transformable=True):
    """Builds the 4th return value of purpose_fit() (docs/purpose_score_design.md §2)."""
    return {
        "purpose_score":    float(purpose_score),
        "max_possible":     100.0,
        "type_a_violated":  bool(type_a_reasons),
        "type_a_reasons":   list(type_a_reasons),
        "warnings_present": bool(warnings_present),
        "is_transformable": bool(is_transformable),
        "breakdown":        breakdown,
    }


# ---------------------------------------------------------------------------
# Numeric comparison utilities (used by IC value-check, EA, and SA)
# ---------------------------------------------------------------------------
def is_about_ten_x(orig_val: float, new_val: float, tol=0.05):
    """Returns True if new_val is approximately 10× or 1/10× of orig_val."""
    if orig_val == 0:
        return False
    r = new_val / orig_val
    return any(abs(r - target) / target <= tol for target in (10.0, 0.1))


def is_within_multiplier_range(orig_val: float, new_val: float, lo=1.3, hi=1.7, tol=0.05):
    if orig_val == 0 or new_val == 0:
        return False
    r = new_val / orig_val
    if r < 1:
        r = 1 / r
    return (lo - tol) <= r <= (hi + tol)


def _expand_units(v: float) -> set:
    """Candidate set that absorbs unit and notation differences for numeric value v.

    Covers % ↔ decimal (×100) and thousand/million/billion scale differences.
    Example: 9 → {9, 0.09, 900, 9000, ...}, 150 → {..., 150_000_000, ...}.
    Both sides are expanded; a non-empty intersection means 'same value after unit correction'.
    """
    factors = [1, 1e2, 1e3, 1e6, 1e9, 1e-2, 1e-3, 1e-6, 1e-9]
    out = set()
    for f in factors:
        for r in (round(v * f, 6), round(v / f, 6)):
            if abs(r) > 1e-9:        # prevent round(v/1e9) → 0.0 collision (all values sharing 0)
                out.add(r)
    return out


# ---------------------------------------------------------------------------
# Normalization (used by _values_in_question and EA-full auxiliary comparison)
# ---------------------------------------------------------------------------
def _norm_unit(s: str) -> str:
    """Normalization for sentence/table-row comparison — collapse whitespace + lowercase."""
    return re.sub(r"\s+", " ", s).strip().lower()


# ---------------------------------------------------------------------------
# Type A — common to all types
# ---------------------------------------------------------------------------
def _values_in_question(values, question: str, ctx_orig: str = ""):
    """Returns those numeric values that also appear verbatim in the question text.

    Used to detect 'Type A — question duplication' for EA-partial/EA-full.
    If a value removed from the context is still present in the question, a
    context-only perturbation cannot make the problem unsolvable
    (SYSTEM rule 5: the question must not be modified).

    For Q-transform problems (the question itself is the perturbation target),
    ctx_orig equals question, making Type A meaningless — an empty list is
    returned in that case.
    """
    if not question or not values:
        return []
    if ctx_orig and _norm_unit(ctx_orig) == _norm_unit(question):
        return []  # Q-transform — question is itself the perturbation target; Type A is irrelevant
    # Numbers attached to letters like 'Q3', 'L1', 'H2' are labels, not data values.
    # Remove them before extracting numbers from the question to avoid false matches
    # (e.g. the '3' in 'Q3' incorrectly matching '3.0%').
    q_clean = re.sub(r"[A-Za-z]\d[\d.,]*", " ", question)
    qnums = set(number_only_floats(q_clean))
    return [v for v in values if v in qnums]
