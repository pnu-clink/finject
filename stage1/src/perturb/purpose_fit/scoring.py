"""perturb.purpose_fit.scoring — unified scoring entry point (gates and deductions at a glance).

  credit(ttype, ...)  → all gates (credit) = type (category) + common (global), with scope tags.
  penalty(ttype, ...) → all deductions     = type (category) + common (global), with scope tags.
  score(ttype, ...)   → (passed, reasons, warnings, score_dict)
                        = total_score(common_gates, type_gates, deductions) + reasons/warnings assembly.

All category evaluators follow the same interface (gates/deductions) and are dispatched via REGISTRY.
"""
from __future__ import annotations

from perturb.purpose_fit import (system_common as _sc, ea_partial, ea_full, sa,
                                  ic_value, ic_source, ic_premise)
from perturb.purpose_fit._common import _build_score_dict

REGISTRY = {
    "EA-partial": ea_partial, "EA-full": ea_full, "SA": sa,
    "IC-value": ic_value, "IC-source": ic_source, "IC-premise": ic_premise,
}


def credit(ttype, ctx_orig, ctx_perturbed, python_solution="", question=""):
    """All gates (credit). Return order: category first, global last. Each item tagged with scope."""
    cat = REGISTRY[ttype].gates(ctx_orig, ctx_perturbed, python_solution, question)
    glob = _sc.global_gates(ttype, ctx_orig, ctx_perturbed, python_solution, question)
    for g in cat:
        g["scope"] = "category"
    for g in glob:
        g["scope"] = "global"
    return cat + glob


def penalty(ttype, ctx_orig, ctx_perturbed, python_solution="", question=""):
    """All deductions. Return order: category first, then global (new_punctuation, marker_added)."""
    cat = REGISTRY[ttype].deductions(ctx_orig, ctx_perturbed, python_solution, question)
    glob = _sc.global_deductions(ttype, ctx_orig, ctx_perturbed, python_solution, question)
    for d in cat:
        d["scope"] = "category"
    for d in glob:
        d["scope"] = "global"
    return cat + glob


def score(ttype, ctx_orig, ctx_perturbed, python_solution="", question=""):
    """Derives score, PASS/FAIL status, and reasons via the credit/penalty functions."""
    gates = credit(ttype, ctx_orig, ctx_perturbed, python_solution, question)
    deds = penalty(ttype, ctx_orig, ctx_perturbed, python_solution, question)
    type_gates = [g for g in gates if g.get("scope") == "category"]
    common_gates = [g for g in gates if g.get("scope") == "global"]
    s, breakdown = _sc.total_score(common_gates, type_gates, deds)
    gate_fail = [g["name"] for g in (type_gates + common_gates)
                 if g.get("applicable", True) and not g["passed"]]
    reasons = [_sc.gate_fail_message(n) for n in gate_fail]
    warnings = [_sc.deduction_message(d["name"], d["points"]) for d in deds]
    return (len(reasons) == 0), reasons, warnings, _build_score_dict(
        s, breakdown, [], bool(warnings))
