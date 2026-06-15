"""perturb.purpose_fit.ea_full — EA-full evaluation helpers.

EA-full removes a carrier sentence, clause, table row, cell, or entry without an
explicit marker.
"""
from __future__ import annotations

import re

from perturb.textops import number_only_floats, _fmt_num_seq
from perturb.purpose_fit._common import _expand_units, _norm_unit


def _ea_full_essential_warning(ctx_orig: str, ctx_perturbed: str,
                               python_solution: str):
    """Soft signal check for EA-full guide #1 (deleted block must be essential).

    Returns a WARNING if none of the removed numeric values match a numeric literal
    in python_solution. Unlike EA-partial (which substitutes), EA-full deletes
    multiple values, so a single match is sufficient to accept the deletion as
    essential and pass. Reliability ~90%.
    """
    if not python_solution:
        return None
    removed = sorted(set(number_only_floats(ctx_orig))
                     - set(number_only_floats(ctx_perturbed)))
    if not removed:
        return None  # no numeric values removed — no signal to check
    sol_nums = number_only_floats(python_solution)
    if not sol_nums:
        return ("WARNING: python_solution contains no numeric literals; "
                "cannot verify essential deletion (solution uses variables only)")
    sol_expanded = set()
    for s in sol_nums:
        sol_expanded |= _expand_units(s)
    matched = [r for r in removed if _expand_units(r) & sol_expanded]
    if not matched:
        return ("WARNING: removed values " + ", ".join(_fmt_num_seq(removed)) +
                " do not match any python_solution literal "
                "(including unit correction) — may not be an essential data deletion")
    return None


# Guard against treating decimal points (digit.digit) or abbreviation periods as sentence boundaries.
_SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def _split_sentences(text: str):
    """Splits text into a list of sentences (for EA-full #3 sentence-level deletion verification).

    Decimal points (e.g. '9.5%') are not treated as sentence boundaries. The splitter
    need not be perfect — as long as orig and perturbed are split by the same rules,
    over-splitting occurs equally on both sides and the subset check still holds.
    """
    if not text:
        return []
    protected = re.sub(r'(?<=\d)\.(?=\d)', '\x00', text)
    parts = _SENT_SPLIT_RE.split(protected)
    return [p.replace('\x00', '.').strip() for p in parts if p.strip()]


def _is_markdown_table(text: str) -> bool:
    """Returns True if the context contains a markdown table (pipe-delimited rows)."""
    pipe_rows = [l for l in text.splitlines() if l.count("|") >= 2]
    return len(pipe_rows) >= 2


def _table_rows(text: str):
    """Extracts only the pipe-delimited rows from a markdown table (normalized)."""
    return [_norm_unit(l) for l in text.splitlines() if l.count("|") >= 2]


def gates(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """EA-full gates: none (pure deduction-based)."""
    return []


def deductions(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """EA-full deductions: essential not deleted (-40), new number (-20), padding (-20)."""
    from perturb.textops import number_only_floats
    from perturb.purpose_fit._common import _expand_units
    orig = set(number_only_floats(ctx_orig or ""))
    pert = set(number_only_floats(ctx_perturbed or ""))
    ess = number_only_floats(python_solution or "")
    out = []
    if ess:
        def _present(v):
            ve = _expand_units(v)
            return any(_expand_units(x) & ve for x in pert)
        if all(_present(v) for v in ess):
            out.append({"name": "essential_not_deleted", "points": 40})
    if pert - orig:
        out.append({"name": "new_number", "points": 20})
    if len(_split_sentences(ctx_perturbed or "")) > len(_split_sentences(ctx_orig or "")):
        out.append({"name": "padding", "points": 20})
    return out


def evaluate(ctx_orig, ctx_perturbed, python_solution="", question=""):
    return (gates(ctx_orig, ctx_perturbed, python_solution, question),
            deductions(ctx_orig, ctx_perturbed, python_solution, question))
