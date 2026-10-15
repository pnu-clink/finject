
Task: synthesize the supplied response-pattern observations into 1-4 research findings.

How to read this request:
- run identifies the experiment and must be copied unchanged to the output run field.
- category identifies the observation topic. partition and partitions_in_category
  identify this subset of notes; do not assume notes from other subsets were supplied.
- interpretations contains case-level analyst observations grounded in saved responses,
  with IDs, response references, excerpts, interpretations, and limitations. They are
  evidence to assess critically, not independent samples or additional success counts.
- response_assessment_summary, when supplied, contains fixed Python counts from validated
  A02 response reviews. response_assessments contains only the response reviews linked to
  this partition's cited examples; this subset is not the whole population or a sample
  representing it. Use the summary's explicit denominators, preserve unknown and failed
  reviews, and do not rejudge or overwrite saved verdicts. These are LLM judgments, not
  human-verified gold. Report concerns as discussion proposals with the response IDs.
- aggregates contains programmatically computed experiment counts. overall covers
  all planned response rows; matrix groups them by model, variant, prompt_condition,
  and reasoning. original_groups describes variant responses grouped by the ORIGINAL
  response's numeric result under the same conditions: MATCH, MISMATCH, UNEVALUATED,
  or ORIGINAL_MISSING. These are not correctness labels for the variants.
- aggregates.original_external_knowledge, when present, stratifies responses by a
  private annotation of the ORIGINAL question's production dependency. The label is
  not model behavior or a revalidated property of edited variants. CRITERIA_NOT_MET
  does not establish absence of external knowledge. Do not infer causation from these
  descriptive strata.
- paired_groups summarizes comparisons changing one named axis: PROMPT, REASONING,
  MODEL, VALUE_POSITION, SOURCE_A, SOURCE_B, or EA_DELETION. planned_pairs is the planned
  count, complete_pairs have both records, and comparable_pairs have two format-valid
  responses. Missing and failed pairs remain separately recorded. A complete pair need
  not contain two successfully collected or correct answers.
- Numeric candidate and position counts describe number matches and claim locations,
  not established preferences. model_comparison_available and repeat_comparison_available
  state which comparison evidence exists. interpretation_boundaries records limitations.

Use overall and grouped counts only from aggregates. The same aggregates can accompany
multiple partitions; never sum them across partitions or treat this note subset as the
entire study. Support findings with IDs from the supplied interpretations in the output
interpretation_ids field. Do not invent new citations or observations outside this input.
Include contrary evidence, alternative explanations, and limits; distinguish descriptive
patterns from causal identification. Any follow-up separating source attribution from
claim position is a discussion proposal, conditional on a clear full-experiment pattern;
it has not been approved or executed.
All original successes, failures and unevaluated cases remain in the recorded population.
Do not infer repeated-trial stability from differences between reasoning settings.
Return only the response schema object. Do not use tools or create files.
