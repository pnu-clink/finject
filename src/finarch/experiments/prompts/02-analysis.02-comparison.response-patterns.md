meTask: describe response patterns and assess each planned variant response in this request.

How to read this request:

- run identifies the experiment; case identifies this original question's group.
- inputs is keyed by item_id. Each public object contains the question, context, and
requested answer_format. production_metadata records edits and parent relationships;
it is dataset construction information, not an observation of model behavior.
- original_external_knowledge, when supplied, is a private annotation about verified
external dependency in constructing the ORIGINAL question. It is not observed model
knowledge use and has not been revalidated for edited variants. used=false means the
confirmation criteria were not met, not that external knowledge was absent.
- responses contains the planned response records. response_id identifies one record;
item_id joins it to inputs. model, variant, prompt_condition, and reasoning identify
the conditions. Compare only supplied records and report absent or failed responses.
- response contains the model's answer, classification, explanation, and evidence.
status=VALID means the response passed format checks, not that it is correct.
A missing response differs from a collected response whose answer is null.
- numeric_comparison.matches is a precomputed comparison of an original response's
number with its recorded reference answer, using the saved numeric comparison rules.
true/false means numeric match/mismatch; a missing comparison means not evaluated.
This is not a judgment of the explanation or semantic correctness.
- original_result is MATCH, MISMATCH, or UNEVALUATED for ORIGINAL rows. NOT_ORIGINAL
marks variant rows; to group a variant by original performance, find its ORIGINAL
row under the same model, prompt_condition, and reasoning.
- reference.reference_answer is the recorded original reference. alternative_answer
is a candidate associated with a recorded modification, when available. Neither
establishes that a modified question has a uniquely justified answer.
- numeric_candidate compares the returned number with those candidates: A matches
the original reference, B the alternative, and BOTH matches both. Other values are
ORIGINAL_VALUE when no alternative exists and the reference matches, OTHER, NULL,
NON_NUMERIC, REFERENCE_MISSING, or FORMAT_OR_EXECUTION_FAILED. candidate_position
gives FRONT/BACK for an A/B match in a numeric-position or source variant, otherwise
UNKNOWN when placement cannot be verified, NOT_APPLICABLE or the non-A/B candidate code. These are
numeric observations, not inferred choices. matched_value_parent_ids links source
variants to their numeric-claim parents. tags are recorded diagnostic observations.

First assess every planned non-ORIGINAL response. Then compare the supported relationships
and report distinct substantive observations, including contrary cases. There is no numeric
quota or maximum observation count. Do not pad, duplicate or truncate observations.
Compare original/variant responses, changes in solving instructions and reasoning,
numeric-claim positions, source attribution relative to the linked parent, stated
formulas versus results, and the two fact deletions. For deleted facts, distinguish
explicit reverse calculation, another stated route, retained information, and unsupported
guessing only when the saved explanation/evidence supports that description.
Use ANSWERABLE/CONFLICT/INSUFFICIENT_EVIDENCE/UNRESOLVED/ABSTAIN as model labels,
not as your own judgments of the questions. A reference-number match alone does not
demonstrate a justified reconstruction. Repeated-trial stability is not available.
All planned responses, including failed or absent ones, remain in the denominator.
Use category names from the schema. Each observation must cite provided response_ids and
at least one EXACT contiguous quote from its saved explanation or an evidence string.
No paraphrases inside quotes. Never invent a response ID or quote.
Explain uncertainty and plausible alternative explanations. Avoid causal or population
claims from one original. Write all fields, including display, in English. Do not output display_ko.
If no substantive pattern is supported, return observations=[] even when responses exist.
Always use coverage_note to describe comparisons examined, unavailable comparisons and why
no observation was warranted, where applicable. A VALID call does not prove that every
comparison was reviewed. Preserve all required response_assessments even with zero observations.

RESPONSE ASSESSMENTS (rubric ResponseGroundingV1):
Return response_assessments separately from the selective observations. Include exactly
one assessment for EVERY supplied response whose variant is not ORIGINAL, under its exact
response_id. Do not omit failed or missing responses. Do not assess ORIGINAL responses here.
The response_id applies to one model, variant, solving instruction, and reasoning setting;
never transfer a verdict from another response or condition.

Use review_status=COMPLETED when status=VALID and the question, context, and response are
available. If the response failed format checks or is absent, use NOT_REVIEWABLE and null
for both verdicts. If the actual question/context is absent, use SOURCE_MISSING and null
verdicts. Preserve the reason; neither status is semantic failure.

1. abstention\_reason\_validity:
 For answer=null, judge whether the stated reason correctly identifies a relevant,
 unresolved conflict, irrecoverable missing requirement, or ambiguity that prevents a
 justified final value under the actual question restrictions. Check different periods,
 entities, units, explicit source priorities, remaining totals, and unique recovery.
 Unsupported assumptions, mere inability to finish, ABSTAIN, or classification labels
 alone do not establish justified abstention. Use SUPPORTED, UNSUPPORTED, or UNDETERMINED.
 For a numeric answer, use NOT\_APPLICABLE; assess its justification in decision\_grounding.
2. decision\_grounding:
 For every reviewable response, judge whether its explanation and evidence jointly
 justify the actual final decision. For numeric answers, verify the displayed arithmetic,
 requested quantity, sign, unit, scale, rounding and whether the supplied context supports
 the chosen inputs or a unique recovery. For null, verify that the stated blocker actually
 prevents the answer and that the explanation/evidence supports that conclusion.
 A quote merely appearing in the context, numeric agreement with the original reference,
 or a classification label is not sufficient. For missing information, do not demand a
 quotation of nonexistent text: identify the missing requirement and the limits of the
 remaining information. An empty evidence array is not automatically success or failure.
 Use SUPPORTED, UNSUPPORTED, or UNDETERMINED; never NOT\_APPLICABLE for a reviewable response.

For each judgment provide a specific English reason and exact citations. A citation's
source is question, context, explanation, or evidence. Set evidence_index to its zero-based
array index for evidence, and null otherwise. The quote must be a contiguous verbatim
substring of that exact source. For SUPPORTED, UNSUPPORTED and UNDETERMINED, cite at least
one response passage (explanation/evidence) and one input passage (question/context).
Keep reasons concise and quote only the passages needed to substantiate the judgment.
If facts or interpretations cannot be resolved, use UNDETERMINED and explain the dispute;
do not invent a gold answer or classify all modifications as unanswerable.
Do not assign quadrants or aggregate success counts; Python derives those from validated
response assessments and the separately established original evaluation.
Return only the schema object. Do not use tools or create files.