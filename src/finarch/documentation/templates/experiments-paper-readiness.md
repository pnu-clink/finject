# The paper's test-tested preparation 2026-10-03

Check view: $checked_at · Call new model: **0entries**This is a reading and quantification of the original and archival files, and no experimental run, no re-recording, no original editing.

## Reading order

1. [readiness.json](readiness.json): Path-sharing of papers and data, actual selection ID, verification scope and follow-up work.
2. [events.jsonl](events.jsonl): Check visual; quantity; model call.
3. Currently, the review paper: `$paper_path` 3.5, 4, 5.1–5.2And the Evaluation/Analysis add-on.
4. FinanceReasoning: `$finance_path`The manifest of 00-input → 01–07.
5. TAT-QA: `$tat_path`The manifest of 00-input → 01–07The whole thing. 437Preparation and the latest in the row 7Type PASS, corresponding to the absence of explicit Reject 291Select the case.

## The real data.

|Bundle|Selected original|The original + 7Variant|Your condition request number / model|
|---|---:|---:|---:|
|FinanceReasoning|1,260|10,080|40,320|
|TAT-QA|291|2,328|9,312|
|Total|1,551|12,408|49,632|

This is the pre-human test. 16The SHA of the items-result file--256This corresponds to the corresponding manifest. The TAT-QA selection ID matches the export record saved after the transcription is excluded. Automatic PASS and mean correct; the last person approval is separate.

The internal source of the FinanceReasoning set is FinQA. 404, CodeTAT-QA 260, FinanceReasoning 565, FinanceMath 31It's easy. 609, medium 578, hard 73The TAT-QA is a certified copy of the code. 280I use the record except for the case. 7The case is not proof that there is no overdub.

## The evaluation required in the paper

- **RQ1:** Answer: The appropriateness of the authority. Original: The correctness of the possible cases, the excess authority rate, the authority Precision/Recall/F1, the authority for reasons, the authority for the change of the authority, the authority of the authority for change of the source, the authority to change the authority, and the authority for a change of the original.
- **RQ2:** Changes in response to base changes: candidate A/B/guita/null, front and back placement, source addition against parent IC-value, relational conflict, EA restoration, answer, classification, explanation, usage complexity, four condition differences.
- The same original and seven variations are a single set of cases. Types alone do not determine the impossible. Failure, failure, and form error are not counted as a subset, nor hidden in the denominator.
- Public input is Q/C: the required response format, the correct answer, the model, the calculation graph, the product, and the human judgment, the external classification, the private assessment/analysis data.
- external_knowledge.used=true is an external user verification of a stored reference file. false is not validated by the verification conditions, and is not whether the target model actually uses external knowledge.

## Adjusted before running

1. The current default config.toml is past TAT-QA 557This experiment is going to have to combine the selection ID and the hash of the two sets of data into the star setting.
2. The same test ID for both runs. 191The key to the case has to be linked to the source run + case ID, which is not the number of duplicates of the case.
3. Some of the existing A03 RQ/SQ connection is 20260924 It's based on the original, and it's supposed to be linked to the RQ1/RQ2 definition of the new paper, and it doesn't overlap past results.
4. The existing E04 Compare the numbers to A0.2 The distribution of candidate values does not replace the entire semantic assessment of RQ1. It must link the final answer possibilities, recoverable EA rights, reason for the judgment and the scope of the assessment of the response compatibility.
5. The previous person key can only be used to the extent that the same case version is verified. 260The previous case was not automatically updated.
6. The four conditions for each target model are support, actual reasoning options, sampling, output budget, cache checks, call volume and cost before running.

## The screen is actually looking at the data.

[FinanceReasoning data set](http://127.0.0.1:8893/?run=20261003-concat-002) · [TAT-QA data set](http://127.0.0.1:8893/?run=20261003-003) · [Public research viewer](http://127.0.0.1:8896/viewer/research/)

The entire row count and the number of experiment selections in the dataset viewer can be different. This README is generated from documentation/templates and does not create any resulting HTML.
