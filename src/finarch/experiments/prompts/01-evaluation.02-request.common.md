Return one JSON object matching the supplied response schema. The sections below explain the existing fields; they do not change the schema's JSON key order. Keep the explanation and evidence fields in the same JSON object. Do not add fields or wrap the object in Markdown.

ANSWER:
- For a numeric answer, use a signed JSON number in the unit and scale requested by the question and context. Round the final result to `answer_format.decimal_places`. Do not round intermediate calculations.
- The numeric `answer` must be the requested final result after the required rounding, rather than an input figure or an intermediate calculation.

ANSWER_META:
- For a numeric answer, `answer_meta.negative` is true exactly when `answer` is less than zero; it is false for zero or a positive value.
- `answer_meta.scale` records the scale of the number as written: one, hundred, thousand, million, billion, trillion, or percent. A percent value of 12.5 is written as 12.5 with scale percent, not 0.125. Scale is a record of representation, not an instruction to multiply the answer again.
- When `answer` is null, both `answer_meta.negative` and `answer_meta.scale` must be null.

CLASSIFICATION:
- Set `classification` exactly as instructed in the solving instruction below.

EXPLANATION:
- Write a brief explanation in English. For a numeric answer, write the requested final result explicitly in the explanation, with its sign, unit, and scale. Keep the final value and its meaning consistent with the explanation.
- Before returning the object, reconcile the final number written in the explanation with `answer` and its metadata. Copy the relevant input numbers accurately when describing the calculation.
- Keep the explanation within 2000 characters.

EVIDENCE:
- Provide supporting exact excerpts from the supplied context in `evidence`. Quote text exactly; do not invent supporting text.
- Each evidence item must be one contiguous, verbatim substring of the context. Preserve its capitalization, punctuation, spaces, line breaks, and number formatting. Use separate array items for separate passages. Do not insert ellipses, normalize a quotation, or join separated fragments into one quotation. Keep quotations as short as needed to support the explanation.
- An empty evidence array represents no quoted passage; it is not itself a numeric answer.
- Use at most 12 evidence excerpts, with at most 1500 characters per excerpt.
