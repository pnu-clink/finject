# Stage 2: Semantic Judge Gate

Stage 2 validates semantic unanswerability after Stage 1 removes malformed or wrong-shape perturbations.

This file explains the Stage 2 protocol. The actual LLM prompt template used by
the protocol is in `../prompts/semantic_judge.md`.

## Purpose

Stage 1 only checks whether a candidate has the intended structural form. Stage 2 asks whether the transformed problem actually lacks a uniquely supported answer.

Each candidate is judged on two independent axes:

- **Category validity**: whether the perturbation still matches the intended category.
- **Unanswerability**: whether the perturbed context lacks a uniquely supported answer.

The main automatic pass rule uses non-self majority over the unanswerability label:

```text
Stage2Pass(x) = 1 if at least two eligible non-self judges mark unanswerable = PASS
```

Category-validity votes are retained for strict sensitivity analysis.

## Non-Self Judging

To reduce generator-family bias, a candidate is judged only by model families different from the generator family. The judge sees:

- original question and context;
- transformed context;
- intended perturbation category;
- category-specific rule.

The judge does not receive human labels, release sampling decisions, downstream results, or generator self-judgments.

## Judge Prompt

The prompt file is not a separate protocol; it is the reusable template sent to
each eligible non-self judge within this Stage 2 protocol:

- `../prompts/semantic_judge.md`

## Output Schema

```json
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

## Reported Outputs

The paper reports:

- Stage 2 FinalPass matrix by generator and category;
- StrictPass sensitivity matrix;
- human verification and repair counts after release sampling.

The submitted paper and supplementary material are available under `../paper/`.
