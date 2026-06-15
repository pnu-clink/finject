# FInject Stage 1 Structural Conformance Specification

Stage 1 is a deterministic structural gate. It is not an LLM judge and it does
not decide whether a candidate is semantically unanswerable. Its role is to
remove malformed or wrong-shape perturbations before Stage 2 semantic judging.

The public implementation is exposed through:

```bash
PYTHONPATH=stage1/src python3 stage1/src/stage1_structural_gate.py --input candidates.jsonl
```

## Decision Rule

A candidate passes Stage 1 when:

1. required structural predicates for the intended category hold.

Forbidden structural patterns are reported as deductions and lower the
diagnostic score, but they do not flip PASS by themselves. This follows the
submitted supplementary material's Stage 1 algorithm.

```text
stage1_pass = all_required_predicates_hold
diagnostic_score = gate_score - forbidden_pattern_deductions
```

## Category Predicates

| Category | Required structural form |
| --- | --- |
| `EA-partial` | Exactly one `[DATA MISSING]` marker appears in place of a numeric value. |
| `EA-full` | A carrier sentence, clause, table row, cell, or entry is removed; no explicit marker remains. |
| `SA` | A numeric value is removed or neutralized while the context stays marker-free. |
| `IC-value` | A different plausible numeric value is added for the same quantity. |
| `IC-source` | A conflicting value is attributed to financial source cues for the same quantity. |
| `IC-premise` | A premise is added as a condition on the same calculation rather than as a replacement answer. |

## Forbidden Structural Patterns

The reference checker flags patterns that contradict the category contract as
deductions:

- non-canonical absence markers such as `N/A` for `EA-partial`;
- explicit markers in `EA-full`, `SA`, or conflict categories;
- added numeric values in absence categories;
- deletion traces such as "missing" or "not provided" in `SA`;
- correction, recency, or authority cues that resolve a conflict;
- premise conflict edits that delete original core sentences instead of adding a
  conflicting premise.

## Relation to Stage 2

Stage 1 intentionally leaves semantic questions open. Stage 2 checks whether the
edited evidence is answer-critical, whether the remaining context still supports
a unique answer, and whether source or premise conflicts are resolvable.

The paper reports 1,690 Stage 1 passes out of 1,872 generated candidates using
the full internal construction pool. That raw construction pool is not included
in this public release; this folder contains the reference structural logic and
the final released dataset. Running this reference script over the final release
is therefore not expected to reproduce the Stage 1 table, because the final
release has already passed later semantic judging, human review, and repair.
