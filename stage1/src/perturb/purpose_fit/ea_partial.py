"""perturb.purpose_fit.ea_partial — EA-partial evaluation helpers.

EA-partial requires exactly one canonical explicit missing marker:
`[DATA MISSING]`.
"""
from __future__ import annotations

from collections import Counter

from perturb.textops import number_only_floats, _fmt_num_seq
from perturb.purpose_fit._common import _expand_units


def _ea_partial_essential_warning(ctx_orig: str, ctx_perturbed: str,
                                  python_solution: str):
    """Soft signal check for EA-partial guide #2 (ESSENTIAL value).

    Returns a WARNING string if the numeric value removed by substitution does not
    match (including unit correction) any numeric literal in python_solution.
    Deterministic reliability is ~90%, so this is exposed only as a WARNING and
    not reflected in PASS/FAIL — false signals occur for cosmetic values,
    variable-only solutions, and complex unit conversions.
    """
    if not python_solution:
        return None  # no solution — cannot check
    removed = sorted(Counter(number_only_floats(ctx_orig))
                     - Counter(number_only_floats(ctx_perturbed)))
    if not removed:
        return None  # no numeric value disappeared — non-numeric substitution or no signal
    sol_nums = number_only_floats(python_solution)
    if not sol_nums:
        # solution uses variables only — no literals to compare essentiality against
        return ("WARNING: python_solution contains no numeric literals; "
                "cannot verify ESSENTIAL value (solution uses variables only)")
    sol_expanded = set()
    for s in sol_nums:
        sol_expanded |= _expand_units(s)
    unmatched = [r for r in removed if not (_expand_units(r) & sol_expanded)]
    if unmatched:
        return ("WARNING: substituted value(s) " + ", ".join(_fmt_num_seq(unmatched)) +
                " do not match any python_solution numeric literal "
                "(including unit correction) — may not be an ESSENTIAL value")
    return None


def gates(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """EA-partial gates: exactly one `[DATA MISSING]` marker is mandatory."""
    from perturb.constants import DATA_MISSING_RE
    marker_count = len(DATA_MISSING_RE.findall(ctx_perturbed or ""))
    return [{"name": "marker_count_1", "passed": marker_count == 1, "weight": 100}]


def deductions(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """EA-partial deductions: new number (pert-orig), N/A marker (marker present but not [DATA MISSING])."""
    import re as _re
    from perturb.constants import MARKER_RE
    from perturb.textops import number_only_floats
    marker_count = len(MARKER_RE.findall(ctx_perturbed or ""))
    orig = set(number_only_floats(ctx_orig or ""))
    pert = set(number_only_floats(ctx_perturbed or ""))
    out = []
    if pert - orig:
        out.append({"name": "new_number", "points": 20})
    if marker_count and not _re.search(r"\[DATA\s*MISSING\]", ctx_perturbed or "", _re.I):
        out.append({"name": "na_marker", "points": 20})
    return out


def evaluate(ctx_orig, ctx_perturbed, python_solution="", question=""):
    return (gates(ctx_orig, ctx_perturbed, python_solution, question),
            deductions(ctx_orig, ctx_perturbed, python_solution, question))
