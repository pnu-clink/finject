"""perturb.purpose_fit.system_common — FInject Global Guideline (System Prompt)
shared checks + Stage 1 deterministic structural conformance score calculation.

Per FInject_stage1_conformance_spec.md:
  total score = clamp(s_global × α + s_category × (1−α) − sum_p, 0, 100)
  - s_global:   weighted pass score for global guidelines (System Prompt)
  - s_category: weighted pass score for per-category individual guidelines
  - sum_p:      sum of penalty deductions
  - α default 0.2 (weight of s_global)
Similarity (ratio_orig) is not used.
"""
from __future__ import annotations

from perturb.constants import MARKER_RE

DEFAULT_ALPHA = 0.2

# ---------------------------------------------------------------------------
# Reason labels — maps gate/deduction machine names to human-readable messages
# (self-documenting so code does not need to be consulted again).
# Single source of truth for both purpose_fit and report. 1:1 with evaluate()/dispatcher names.
# ---------------------------------------------------------------------------
GATE_LABELS = {
    "M4_context_only":    "New context/info not present in the question was added (external info injection forbidden)",
    "M5_preserved":       "An original conflicting numeric value is not preserved (IC-value/source: one original value must be kept)",
    "marker_count_1":     "[DATA MISSING] marker count is not exactly 1 (EA-partial: exactly 1 marker required)",
    "removal_occurred":   "No numeric removal occurred (SA: keep the quantity mention, remove only the number)",
    "second_value_added": "A conflicting (same-magnitude) value was not added (IC-value)",
    "source_conflict_value": "A plausible conflicting value was not detected (IC-source)",
    "source_attribution_present": "Two financial source cues were not detected (IC-source)",
    "no_deletion":        "A deletion occurred (IC-premise: add only a contradictory premise, no deletion)",
    "statement_added":    "A contradictory premise sentence was not added (IC-premise)",
}

DEDUCTION_LABELS = {
    "new_punctuation":       "New punctuation added (;/—)",
    "marker_added":          "Marker added",
    "new_number":            "New numeric value added",
    "na_marker":             "Non-canonical marker added; use [DATA MISSING]",
    "over_removal_numbers":  "Excessive numeric removal",
    "trace_expression":      "Deletion-trace expression remains",
    "padding":               "Excessive neutral-sentence padding",
    "essential_not_deleted": "Essential numeric value not deleted",
    "digit_order_10x":       "10x digit-order change",
    "attribution":           "Source-attribution expression",
    "authority_attribution": "Authority-attribution expression",
    "correction_cue":        "Correction/revision cue",
    "hedging_cue":           "Hedging/reservation expression",
    "asymmetric_authority":  "One-sided authority assignment (asymmetric)",
    "recency_cue":           "Recency cue",
    "reconcile_not_separate":"Reconcile sentence not separated (merged)",
}


def gate_fail_message(name: str) -> str:
    """Returns a human-readable gate-not-met reason. Unknown names are returned as-is."""
    return GATE_LABELS.get(name, name)


def deduction_message(name: str, points) -> str:
    """Returns a deduction reason in '-points: reason' form. Unknown names are returned as-is."""
    return f"-{points}: {DEDUCTION_LABELS.get(name, name)}"

# M3a: semicolon / em-dash / '--' newly appearing in perturbed (not present in original) — delta check.
_PUNCT = {"semicolon": ";", "em_dash": "—", "double_dash": "--"}


def new_punctuation_delta(ctx_orig: str, ctx_perturbed: str):
    """M3a: List of forbidden punctuation newly appearing in perturbed compared to original.

    Only the delta (excess over the count already present in original) is checked,
    so em-dashes that were already in the original style are harmless.
    """
    o, p = ctx_orig or "", ctx_perturbed or ""
    return [name for name, ch in _PUNCT.items() if p.count(ch) > o.count(ch)]


def marker_added(ctx_orig: str, ctx_perturbed: str) -> bool:
    """absence/conflict types: whether a marker ([DATA MISSING]/N/A) absent in original
    newly appears (delta) in perturbed. Avoids false positives from pre-existing 'N/A'
    (e.g. 'Dividend yield: N/A').
    EA-partial treats the marker as mandatory and therefore uses present (count==1)
    rather than this delta check.
    """
    o = len(MARKER_RE.findall(ctx_orig or ""))
    p = len(MARKER_RE.findall(ctx_perturbed or ""))
    return p > o


def is_q_transform(ctx_orig: str, question: str) -> bool:
    """Returns True if context is empty/placeholder or identical to question → question-itself-transform case."""
    c = (ctx_orig or "").strip().lower()
    if c in {"", "[]", "{}", "()", "null", "none", "n/a", "-", "—"}:
        return True
    return (ctx_orig or "").strip() == (question or "").strip()


def m4_context_only(ctx_orig: str = "", question: str = "") -> bool:
    """M4 gate: context-only (question unchanged).

    The pipeline only modifies the context, so the question is inherently unchanged
    — this gate always passes as a guard.
    (Skipping Type A branches for Q-transform is handled by _values_in_question.)
    """
    return True


def _present(v: float, pert_set, rel: float = 1e-3, tol: float = 1e-9) -> bool:
    return any(abs(v - x) <= tol or (x != 0 and abs(v - x) / abs(x) <= rel)
               for x in pert_set)


def m5_original_preserved(orig_nums, pert_nums, anchor_values=None) -> bool:
    """M5 gate (conflict): original essential values preserved (ADD, not REMOVE).

    If anchor_values (python_solution essential literals) are provided, only checks
    that those values remain in perturbed (does not enforce full preservation →
    avoids false positives from paraphrasing). Otherwise conservatively checks that
    all original numeric values are preserved.
    """
    pert = set(pert_nums)
    if anchor_values:
        return all(_present(v, pert) for v in anchor_values)
    return not (set(orig_nums) - pert)


def derivable_check_filled(parsed, min_len: int = 10) -> bool:
    """M6a: whether parsed.derivable_check is filled with a meaningful length."""
    if not isinstance(parsed, dict):
        return False
    v = parsed.get("derivable_check")
    return isinstance(v, str) and len(v.strip()) >= min_len


def json_only(raw_response: str) -> bool:
    """M6b: whether output is pure JSON with no code fences or extraneous text (strict parsing is the parser's job)."""
    if not raw_response:
        return True
    return "```" not in raw_response


# --- Score calculation -------------------------------------------------------
def gate_score(gates) -> float:
    """Gate score (0~100). gates: [{passed, weight, applicable?}].

    Weighted pass ratio × 100 over applicable gates. Returns 100 if no gates apply.
    """
    appl = [g for g in gates if g.get("applicable", True)]
    if not appl:
        return 100.0
    tw = sum(g["weight"] for g in appl)
    if tw <= 0:
        return 100.0
    pw = sum(g["weight"] for g in appl if g["passed"])
    return 100.0 * pw / tw


def total_score(common_gates, type_gates, deductions, alpha: float = DEFAULT_ALPHA):
    """Total score = clamp(s_global×α + s_category×(1−α) − sum_p, 0, 100).

    deductions: [{name, points}]. Returns (score, breakdown).
    """
    s_global = gate_score(common_gates)
    s_category = gate_score(type_gates)
    fidelity_base = s_global * alpha + s_category * (1.0 - alpha)
    sum_p = sum(d["points"] for d in deductions)
    score = max(0.0, min(100.0, fidelity_base - sum_p))
    return round(score, 1), {
        "common": round(s_global, 1), "type": round(s_category, 1), "base": round(fidelity_base, 1),
        "deduction_total": sum_p, "alpha": alpha, "deductions": deductions,
    }


# --- Global (System Prompt) gates/deductions — same interface as category modules ---
def global_gates(ttype, ctx_orig, ctx_perturbed, python_solution="", question=""):
    """System Prompt global gates (credit): M4 context-only + M5 original-preserved (conflict types only).

    M5 applies only to IC-value/IC-source and only when python_solution essential anchors exist.
    """
    from perturb.purpose_fit.ic_common import essential_context_values  # deferred import (avoid cycle)
    from perturb.textops import number_only_floats
    is_conflict = ttype in ("IC-value", "IC-source")
    anchor = essential_context_values(ctx_orig, python_solution) if is_conflict else []
    m5_appl = is_conflict and bool(anchor)
    orig_nums = number_only_floats(ctx_orig or "")
    pert_nums = number_only_floats(ctx_perturbed or "")
    return [
        {"name": "M4_context_only", "passed": m4_context_only(ctx_orig, question), "weight": 50},
        {"name": "M5_preserved", "weight": 50, "applicable": m5_appl,
         "passed": (m5_original_preserved(orig_nums, pert_nums, anchor) if m5_appl else True)},
    ]


def global_deductions(ttype, ctx_orig, ctx_perturbed, python_solution="", question=""):
    """System Prompt global deductions: M3a new punctuation + marker added (except EA-partial).

    M6a (derivable_check empty) / M6b (JSON-only) require parsed/raw_response and
    cannot be called through this (ctx_orig, ctx_perturbed, ...) interface — they are
    under the parsing layer and are intentionally left unwired here (behavior-preserving).
    """
    out = []
    if new_punctuation_delta(ctx_orig, ctx_perturbed):
        out.append({"name": "new_punctuation", "points": 20})
    if ttype != "EA-partial" and marker_added(ctx_orig, ctx_perturbed):
        out.append({"name": "marker_added", "points": 20})
    return out
