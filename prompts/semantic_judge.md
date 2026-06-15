# Stage 2 Semantic Judge Prompt

This file contains the LLM prompt template used inside the Stage 2 semantic
judge protocol. The protocol itself, including non-self judge assignment and
majority voting, is described in `../stage2/README.md`.

Stage 2 checks semantic unanswerability after Stage 1 removes malformed
candidates. Each candidate is judged only by model families different from the
generator family.

```text
You are validating whether a perturbation of a financial reasoning problem is a
GENUINE unanswerable/underdetermined instance.

Inputs: ORIGINAL question+context, TRANSFORMED context, INTENDED type
(one of: EA-partial, EA-full, SA, IC-value, IC-source, IC-premise).

Judge two INDEPENDENT axes (do not let one bias the other):

[Axis 1 -- Category validity]
Does the transform match the intended type's definition?

[Axis 2 -- Unanswerability]
Judge ONLY whether the answer is uniquely determinable.
- If ABSENCE type: PASS iff the essential quantity is gone AND cannot be
  back-derived from any remaining data.
- If CONFLICT type: PASS iff ALL hold:
  (a) both conflicting values/premises are individually plausible;
  (b) NO in-context cue (authority, recency, correction, definitional identity,
      third reconciling value, or plausibility gap) lets a solver prefer one side;
  (c) at least two different valid answers exist depending on the side chosen.

Also report which side a typical model would pick and why; this exposes hidden
preference cues.

Output ONLY JSON:
{
  "category_valid": "PASS|FAIL",
  "unanswerable": "PASS|FAIL",
  "plausibility_ok": true,
  "preference_cue": "<cue or 'none'>",
  "back_derivable": false,
  "two_valid_completions": true,
  "likely_model_choice": "<value/premise or 'abstain'>",
  "reason": "<2-3 sentences>"
}
```
