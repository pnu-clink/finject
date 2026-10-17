# Experiment Viewer  Brief answer  numerical comparison  error reason

## Reading order

1. [Number matching example](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006&variant=ORIGINAL&prompt=P0&reasoning=off)inspect `The answer that the model returned (FinancialAnswerV6 · negative=false · scale=million)` Next time, answer me. **20**Under the same box. **Comparison of stored numbers: 20 ↔ 20 · Matching**The number is shown in the brown box and the repeated no-scale processing method is removed.
2. [Examples of numerical inequality](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0052&variant=ORIGINAL&prompt=P0&reasoning=on) **0.5 ↔ 12.1 • Disagreements**So we've made the backdrop of the answer brighter, and we've put a golden background and a highlight line on the explanation, and the undervaluer uses a bright background, but it keeps the actual undervaluer phrase.
3. [Examples of power cuts](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0168&variant=IC_VALUE_01_AFTER&prompt=P1&reasoning=off)Some are deep red. **Output truncated** And the badge. **Output token limit** So the answer is that the completed answer is the same as the answer. **Null**And the received cutting source is verified in the existing JSON viewer.
4. [Confirmation of the record](checks.json)[Examining logs](tests.log)[current operation: file-by-file responsibility: order](../../docs/02-experiments/README.md)I'll check it out.

The brown is a match of the stored number comparison and not a meaningful answer judgment. Null is a screen value. Real return null, no answer field, no completed response text, distinguishes it from tooltip, proximity explanation and resource records. 0 0The output token limits the sentence to save the diagnostic `OUTPUT_TRUNCATED` Or the termination of the cause `max_tokens`It only shows the output cutoff response.

## File responsibilities

|File|Role|
|---|---|
|[app.js](../../viewer/experiments/app.js)|Placing the metadata in the title row, combining the numbers in the answer box, zeroing, highlighting the description quarter, cutting the link to the private|
|[styles.css](../../viewer/experiments/styles.css)|JULI SU-KGY-HY-HUMAN reductions, matching numbers brown, bright answers and explanatory emphasis, deep red cutting badges|
|[checks.json](checks.json)|The data base and the browser match; inconsistency; error; fact null; fact 0 Check, file hash.|
|[tests.log](tests.log)|With the existing HTML Export checker, check the latest screen code's grammar and density and CSP hash|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|Central template creation and document linkage; custodial source hashing|

The HTML Export that you generate afterwards also includes the same code-style. There are no model calls and experimental re-enactments, and the agent's authentication is not shown as a user review completed.

This README is a `src/finarch/documentation/templates/viewer-experiments-answer-summary.md`in `python3 src/finarch/documentation/manage.py refresh`So we're going to generate a
