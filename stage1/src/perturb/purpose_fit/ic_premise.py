"""perturb.purpose_fit.ic_premise — Mutually-Exclusive Premise evaluation (deduction-based).

Gates: original core sentences not deleted + contradictory statement added.
Deductions: authority attribution + hedging cue.
(No dependency on value extraction — keyword/sentence based.)
"""
from __future__ import annotations

from perturb.constants import (IC_PREMISE_FORBIDDEN_ATTRIBUTION,
                                IC_PREMISE_FORBIDDEN_HEDGING)
from perturb.purpose_fit.ea_full import _split_sentences


def gates(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """IC-premise gates: original core sentences not deleted (50) + contradictory statement added (50)."""
    orig_s = [s.strip() for s in _split_sentences(ctx_orig or "")]
    pert_s = [s.strip() for s in _split_sentences(ctx_perturbed or "")]
    pert_set = set(pert_s)

    no_deletion = all(s in pert_set for s in orig_s) if orig_s else True
    statement_added = len(pert_s) > len(orig_s)

    return [
        {"name": "no_deletion", "passed": bool(no_deletion), "weight": 50},
        {"name": "statement_added", "passed": bool(statement_added), "weight": 50},
    ]


def deductions(ctx_orig, ctx_perturbed, python_solution="", question=""):
    """IC-premise deductions: authority attribution (-20) + hedging cue (-20)."""
    low = (ctx_perturbed or "").lower()
    out = []
    if any(ph in low for ph in IC_PREMISE_FORBIDDEN_ATTRIBUTION):
        out.append({"name": "authority_attribution", "points": 20})
    if any(ph in low for ph in IC_PREMISE_FORBIDDEN_HEDGING):
        out.append({"name": "hedging_cue", "points": 20})

    return out


def evaluate(ctx_orig, ctx_perturbed, python_solution="", question=""):
    return (gates(ctx_orig, ctx_perturbed, python_solution, question),
            deductions(ctx_orig, ctx_perturbed, python_solution, question))
