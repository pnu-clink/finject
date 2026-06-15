"""perturb.purpose_fit.sa — SA (Silent Absence) evaluation helpers.

SA removes or neutralizes a value without an explicit marker or deletion trace.
"""
from __future__ import annotations

import re
from collections import Counter


_WORD_RE = re.compile(r"\w[\w'-]*")


def content_removed(ctx_orig: str, ctx_perturbed: str) -> bool:
    """Returns True if any original token is missing or reduced in count in perturbed.

    SA deletes not just numbers but non-numeric essential information at various
    granularities: entire sentences (e.g. a depreciation method sentence),
    individual words within a sentence (e.g. 'semi-annually'), etc.
    Word multiset difference catches deletions at any granularity; the difference
    is empty only when perturbed is identical to original (no change → FAIL).
    """
    orig_w = Counter(_WORD_RE.findall(ctx_orig.lower()))
    pert_w = Counter(_WORD_RE.findall(ctx_perturbed.lower()))
    return bool(orig_w - pert_w)


def gates(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """SA gates: removal occurred (numeric multiset diff or non-numeric word deletion)."""
    from collections import Counter as _Counter
    from perturb.textops import number_only_floats
    orig = number_only_floats(ctx_orig or "")
    pert = number_only_floats(ctx_perturbed or "")
    removed = list((_Counter(orig) - _Counter(pert)).elements())
    any_removal = bool(removed) or content_removed(ctx_orig or "", ctx_perturbed or "")
    return [{"name": "removal_occurred", "passed": bool(any_removal), "weight": 100}]


def deductions(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """SA deductions: over-removal of numbers (>1), new number, deletion-trace expression."""
    import re as _re
    from collections import Counter as _Counter
    from perturb.textops import number_only_floats
    orig = number_only_floats(ctx_orig or "")
    pert = number_only_floats(ctx_perturbed or "")
    removed = list((_Counter(orig) - _Counter(pert)).elements())
    out = []
    if len(removed) > 1:
        out.append({"name": "over_removal_numbers", "points": 20})
    if set(pert) - set(orig):
        out.append({"name": "new_number", "points": 20})
    _tr = _re.compile(r"\bmissing\b|\bunknown\b|\bnot\s+(?:provided|given|specified)\b", _re.I)
    if len(_tr.findall(ctx_perturbed or "")) > len(_tr.findall(ctx_orig or "")):
        out.append({"name": "trace_expression", "points": 20})
    return out


def evaluate(ctx_orig, ctx_perturbed, python_solution="", question=""):
    return (gates(ctx_orig, ctx_perturbed, python_solution, question),
            deductions(ctx_orig, ctx_perturbed, python_solution, question))
