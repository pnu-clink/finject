# Set the input of the case. Returns the result of the entire filter.

## Reading order

1. [The overall result is](http://127.0.0.1:8894/?run=20260923-exp-007&tab=overview)In the original number matching → diagnosis private selection → **01 Overview** I'll check it in order. 3,000Requested100So we're going back to the basics.
2. [Compare the problems](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006)in **prompt → JSON schema → Added input; request setting → Q/C**The prompt/schema is the basic folding, the Q/C is the basic unfolding.
3. [Confirmation of the record](checks.json)I see the results of the diagnostic selection and resolution of the two pathways and the actual request content contrast.
4. [Document from the beginning](../../docs/02-experiments/README.md)I see the requirements, file responsibilities, actual flow.

## File responsibilities

|File|Role|
|---|---|
|[app.js](../../viewer/experiments/app.js)|Full result return time filter initialization, input configuration, folding state by region|
|[styles.css](../../viewer/experiments/styles.css)|Type the input line, the subject, the Q/C label.|
|[checks.json](checks.json)|Check the movement, input, counter-clocking of the actual browser|
|[tests.log](tests.log)|The data storage and HTML output return checks|
|[tests-sandbox.log](tests-sandbox.log)|HTTP checks on the first run 2The items is blocked by localhost permission restrictions.|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|Central template creation, text connection, and the custodian's original hashing.|

**Clear diagnostics**To remove all conditions up to the top, such as the number matching, **01 Overview** Or **Reset filters**It keeps the function of selecting a filter directly from the entire result.

Additional input `answer_format`And the model of the request, the promotion, the token, the caching policy, the specification information is separated above Q/C. The English prompt/schema/Q/C is displayed as stored. The analyst's correct answer is separated from the information that was not sent to the model. When the user folds or unfolds it, it stays that way for the next update, and the base selection highlights the Q/C unfolded.

The experimental input didn't modify the raw response or call the model. Verification of the agent doesn't mean that the user review is complete. The HTML Export generated afterwards also enters the same screen code and doesn't overwrite the existing copy.

This README is a `src/finarch/documentation/templates/viewer-experiments-input-and-filters.md`in `python3 src/finarch/documentation/manage.py refresh`So we're going to generate a
