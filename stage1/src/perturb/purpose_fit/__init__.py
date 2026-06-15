"""perturb.purpose_fit — per-category Stage 1 structural predicates.

Entry point: `scoring.score(ttype, ctx_orig, ctx_perturbed, python_solution, question)`.
The unified handler dispatches across six categories to each submodule's required
gates and forbidden-pattern deductions. The public CLI treats a candidate as a
Stage 1 pass when all applicable gates pass; forbidden-pattern deductions lower
the diagnostic score.

Unified scoring interface: `scoring` (credit/penalty/score) collects gates and deductions
in one view. All 6 submodules expose the same signature `gates(...)` / `deductions(...)`.
(`evaluate()` is a backward-compatible shim returning `(gates(...), deductions(...))`).

Submodules (provide evaluate)
- ea_partial : EA-partial  (exactly one [DATA MISSING] marker, no new number)
- ea_full    : EA-full     (no gate, essential-not-deleted −40, etc.) + _split_sentences etc.
- sa         : SA          (removal-occurred gate, trace/over-removal deductions) + content_removed
- ic_value   : Intra-context Value Conflict (digit-order/attribution/cue deductions)
- ic_source  : Inter-source Value Conflict  (source conflict value, source cues, priority-cue deductions)
- ic_premise : Mutually-Exclusive Premise   (no-deletion/statement-added gates, authority/hedging deductions)

Shared
- system_common : M3a(new punctuation)·M4(context-only)·M5(original preserved)·M6·total_score
- ic_common     : IC value-check anchor (solution literals ↔ context values), diff-scope, masking
- _common       : _expand_units / is_about_ten_x / is_within_multiplier_range / _build_score_dict

Forbidden terms and patterns are all stored in perturb.constants.
"""
