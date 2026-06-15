"""perturb.purpose_fit.ic_value — Intra-context Value Conflict evaluation (deduction-based).

Gates: separate value of same magnitude added near essential value (anchored).
Deductions: digit-order (10×), attribution, correction cue.
(Original preservation = common M5 / marker and punctuation = handled by dispatcher.)
"""
from __future__ import annotations

import re

from perturb.constants import (IC_VALUE_FORBIDDEN_ATTRIBUTION,
                                IC_VALUE_FORBIDDEN_CUE)
from perturb.purpose_fit._common import is_about_ten_x
from perturb.purpose_fit.ic_common import (added_values, essential_context_values,
                                           added_sentences, same_magnitude)


def gates(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """IC-value gates: a distinct same-magnitude value added near the essential value (applicable when anchored)."""
    ess = essential_context_values(ctx_orig, python_solution)
    added = added_values(ctx_orig, ctx_perturbed)
    anchorable = bool(ess)
    second_value = anchorable and any(
        same_magnitude(x, y) for x in ess for y in added)
    return [{
        "name": "second_value_added", "passed": bool(second_value),
        "weight": 100, "applicable": anchorable,
    }]


def deductions(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """IC-value deductions: digit-order (10×), attribution, correction cue."""
    ess = essential_context_values(ctx_orig, python_solution)
    added = added_values(ctx_orig, ctx_perturbed)
    anchorable = bool(ess)

    out = []
    if anchorable and any(is_about_ten_x(x, y) for x in ess for y in added):
        out.append({"name": "digit_order_10x", "points": 20})

    addl = [s.lower() for s in added_sentences(ctx_orig, ctx_perturbed)]
    if any(ph in s for s in addl for ph in IC_VALUE_FORBIDDEN_ATTRIBUTION):
        out.append({"name": "attribution", "points": 20})
    if any(re.search(r"\b" + re.escape(cue) + r"\b", s)
           for s in addl for cue in IC_VALUE_FORBIDDEN_CUE):
        out.append({"name": "correction_cue", "points": 20})

    return out


def evaluate(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """Returns: (type_gates, deductions). Common checks (marker/punctuation/derivable) are added by the dispatcher."""
    return (gates(ctx_orig, ctx_perturbed, python_solution, question),
            deductions(ctx_orig, ctx_perturbed, python_solution, question))
