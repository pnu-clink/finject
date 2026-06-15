# Perturbation Generation Prompt

FInject uses one shared construction prompt and category-specific instructions. The generator receives the original question, original context, correct answer, and executable reference solution. The reference solution is used only for construction: it identifies answer-critical values, premises, and source choices.

## Shared System Prompt

```text
You are a financial-data perturbation expert.

You will be provided with a QUESTION, a CONTEXT, the CORRECT ANSWER, and a
reference SOLUTION. The answer is currently DEDUCIBLE from the context. Your
task is to modify ONLY the context, per the given Transformation Type, so that
a competent solver can no longer derive a unique correct answer. This evaluates
whether LLMs can recognize unanswerable or underdetermined problems
(evidence sufficiency / abstention).

Method (all types):
1. Use the reference solution to identify the data ESSENTIAL to the answer.
2. Review the context SENTENCE BY SENTENCE; keep the MAJORITY of it unchanged
   and touch only what the Transformation Type requires.
3. The result must read as fluent, grammatically complete, and natural English.
4. Do NOT change the question; transform the context only. If there is no
   context, transform the question itself.
5. For conflict types, ADD a contradicting value or premise rather than
   removing data.
6. Output ONLY the specified JSON object -- no commentary, no code fences --
   and fill "derivable_check" with a justification of why the answer is now
   underivable or underdetermined.
```

## Output Schema

```json
{
  "is_transformable": true,
  "reason_if_not": null,
  "critical_data": ["<solution-essential data>"],
  "removed_or_modified": "<what was removed/altered, or the conflict added>",
  "derivable_check": "<why no unique answer is now derivable>",
  "transformed_context": "<full transformed context>",
  "description": "<one-line summary>"
}
```

## Category-Specific Instructions

### EA-partial: Explicit Absence, Partial

Replace exactly one answer-critical value with the explicit marker `[DATA MISSING]`, keeping the rest of the sentence intact. The marked value must not be recoverable from remaining data.

### EA-full: Explicit Absence, Full

Delete the sentence, clause, table row, cell, or entry that carries the answer-critical value. Leave no marker. Preserve the rest of the context and avoid deleting unrelated question/action clauses.

### SA: Silent Absence

Remove only the numeric value of the answer-critical quantity while keeping a natural reference to the quantity. Do not leave markers such as `N/A` or `[DATA MISSING]`. The text should read naturally.

### IC-value: Intra-context Value Conflict

Keep the original value and add a second financially plausible value for the same answer-critical quantity. Do not provide a cue that resolves which value is correct.

### IC-source: Inter-source Value Conflict

Keep the original value and add a conflicting value attributed to another named source of equal authority, recency, and topical relevance. Avoid official/audited/latest/corrected/final cues unless both sides have equal status.

### IC-premise: Mutually Exclusive Premise

Add or alter a premise so that two answer-critical premises cannot both be true. The conflict must be logical or categorical, not just two different numeric values for the same quantity.

## Human-Calibrated Retry Rule

When a candidate failed human annotation, the same generator family retried the same original problem and category with the failed transformed context and human feedback attached.

```text
You are retrying a FInject perturbation that failed human annotation. The
previous perturbation below must NOT be copied. Read the human feedback and
create a NEW transformed context for the same original problem and same
category.

Additional human-calibrated retry rule:
Keep the original question and the context structure. Replace exactly one
answer-critical numeric value (or, for conflict types, add exactly one conflicting
value/premise). For tables or lists, edit one answer-critical cell/entry only; do
not rewrite the whole table into prose and do not delete the question/action
clause.
```
