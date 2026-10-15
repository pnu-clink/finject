# EA inverse review — annotation only

You receive only the question and the remaining context after evidence removal.
Identify a quantity needed to answer the question that is no longer stated.
Decide whether the remaining Q/C uniquely determines that quantity by direct
calculation. Do not use a deleted value, original context, gold answer, another
conversation, or invented data. Do not expand the question's meaning.

Look for explicit totals/subtotals, differences, exhaustive percentages,
direct ratios, and growth rates. A familiar formula alone is insufficient:
the necessary values and their applicable relationship must remain in Q/C.
For example, if a table states total 100 and component B 40, and A and B are
the only components, A = 100 - 40 = 60. If completeness is not established,
do not assume there are no other components. A 10% increase to 110 permits
previous = 110 / 1.10 = 100 only when the period and quantity match.

Return the supplied schema:
- `inverse_possible`: true if the missing quantity can be recovered; otherwise
  false. This is an LLM judgment, not a proof of all possible solutions.
- `missing_quantity`: the quantity and its entity/period/unit, or a short
  explanation that no needed missing quantity can be identified.
- `reason`: one or two concise sentences explaining the judgment.
- `evidence`: exact quotes of the remaining numerical operands and relationship
  evidence, with zero-based Unicode character offsets [start, end) in the
  indicated question/context. Never cite a removed value. Use [] if there is
  no useful evidence. Prefer short numerical quotes for highlighting.
- `formula`: for true, a readable equation with substituted operands and the
  recovered value; for false, null. Do not return executable code.

Do not score or reject the EA item. Both true and false are recorded for later
analysis and continue through the pipeline. Do not produce a new perturbation.
