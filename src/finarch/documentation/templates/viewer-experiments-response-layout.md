# Experiment viewer shell model first read the answer

## Reading order

1. [Compare the problems](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006&variant=IC_VALUE_01_AFTER&prompt=P0)Select the case type conditions.
2. Top **Responses by model**In the model name, the half-reverse answer, the explanation, the roundup. The answer, the contract information, the number comparison is in one box, and the number is in brown, except for the bright background and the explanatory emphasis.
3. Down there. **Testing source code  current input  see string difference**It's open, and the input panel is a separate area, and it compares the deleted/extended row of the left, and it shows only the variations that have the experimental origin to compare, and the folding and folding options are saved.
4. Down the hall. **Input sent to the model**In the prompt → JSON schema → Add input → Request setting → Q/C sequence, click the base of the answer card, and this area and Q/C are opened and moved to the exact string position.
5. [First placement verification record](checks.json)[Automatic HTML Export checking log](tests.log)[Subsequent reply](../viewer-experiments-answer-summary/README.md)[Compare, responsibility, and sanctity](../../docs/02-experiments/README.md)I'll check it out.

The original type does not have any distinct variations to compare, so the model-by-model response shows the next input. The emphasis is for ease of reading, not the accurate judgement of the model response. The stored response, source score, model input does not change. The HTML Export generated later also includes the same screen code and style.

## File responsibilities

|File|Role|
|---|---|
|[app.js](../../viewer/experiments/app.js)|Placing the model response upwards, the difference in a separate area, the actual input downwards. Keep the base clicks and folding state.|
|[styles.css](../../viewer/experiments/styles.css)|Returns: Background, model name/explanation, emphasis, difference of view|
|[checks.json](checks.json)|Original/modified placement, rounding emphasis, condition selection, browser display and file hash verification|
|[tests.log](tests.log)|Conventional single HTML checker to check the latest screen code for the syntax, formatting or CSP hash|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|Central template creation and document linkage; custodial source hashing|

This change is to change the display order and the emphasis. There is no actual model call and experiment re-enactment, and the browser's agent verification does not show a user review completed.

This README is a `src/finarch/documentation/templates/viewer-experiments-response-layout.md`in `python3 src/finarch/documentation/manage.py refresh`So we're going to generate a
