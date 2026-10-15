Solve the question using the supplied context. Set `classification` to exactly one of the following five labels; never set it to null.

- ANSWERABLE: The requested quantity has one justified final value. Apply the question's stated restrictions and check the relevant values and relations, including whether an absent value can be uniquely recovered. Put the final number in `answer`.
- CONFLICT: Relevant, incompatible claims imply different final values, with no explicit rule that resolves their disagreement. Set `answer` to null.
- INSUFFICIENT_EVIDENCE: A required value or relation is absent and cannot be uniquely recovered from the supplied information. Set `answer` to null.
- UNRESOLVED: The meaning of the question or a stated relation has multiple plausible interpretations that change the result. Set `answer` to null.
- ABSTAIN: You cannot complete or verify the solution, but have not established a specific conflict, missing requirement, or ambiguity above. Set `answer` to null. This reports your inability to finish, not a defect established in the input.

Choose the specific supported reason. If multiple input problems remain, use UNRESOLVED before CONFLICT before INSUFFICIENT_EVIDENCE. Use ABSTAIN only when you cannot establish one of the other classifications; do not invent an input problem to justify it.

In `explanation`, state why the classification applies and show the calculation or exact blocker. For CONFLICT or UNRESOLVED, include any final values you can calculate, each with its explicit condition and requested precision. Do not invent missing facts or select an unsupported branch as the answer. In `evidence`, quote the context passages supporting your explanation.

Use the shared numeric metadata rules. Do not select a separate response mode or repeat classification labels in a fixed explanation prefix. ANSWERABLE reports your judgment that one value is justified; it does not certify agreement with a reference answer.
