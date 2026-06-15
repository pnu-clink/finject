"""perturb.purpose_fit.ic_source — Inter-source Value Conflict evaluation.

Gates: add a plausible conflicting value for an answer-critical quantity and
attribute the disagreement to financial sources. Deductions flag one-sided
authority or recency cues that would make the conflict resolvable.
"""
from __future__ import annotations

from perturb.constants import (AUTHORITY_WORDS, ASYMMETRIC_AUTHORITY_MARKERS,
                               RECENCY_CUE_RE)
from perturb.purpose_fit.ic_common import (added_values, essential_context_values,
                                           same_magnitude)


def gates(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """IC-source gates: conflicting value plus source attribution cues."""
    ess = essential_context_values(ctx_orig, python_solution)
    added = added_values(ctx_orig, ctx_perturbed)
    anchorable = bool(ess)

    conflict = anchorable and any(
        same_magnitude(x, y) for x in ess for y in added)
    source_cues = len(AUTHORITY_WORDS.findall(ctx_perturbed or "")) >= 2

    return [
        {"name": "source_conflict_value", "passed": bool(conflict),
         "weight": 50, "applicable": anchorable},
        {"name": "source_attribution_present", "passed": bool(source_cues),
         "weight": 50},
    ]


def deductions(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """IC-source deductions: asymmetric authority (-10), recency cue (-10)."""
    out = []
    if ASYMMETRIC_AUTHORITY_MARKERS.search(ctx_perturbed or ""):
        out.append({"name": "asymmetric_authority", "points": 10})
    if RECENCY_CUE_RE.search(ctx_perturbed or ""):
        out.append({"name": "recency_cue", "points": 10})

    return out


def evaluate(ctx_orig, ctx_perturbed, python_solution="", question=""):
    return (gates(ctx_orig, ctx_perturbed, python_solution, question),
            deductions(ctx_orig, ctx_perturbed, python_solution, question))
