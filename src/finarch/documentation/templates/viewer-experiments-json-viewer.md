# Exam JSON Viewer pop-up close

## Reading order

1. [Compare the problems](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006)in **Input to model → JSON schema**And then we're going to open it up.
2. You fold or unfold an object array as a triangle in a JSON viewer. **Full folding / full folding/ original view / copy of the original**You can use it.
3. The answer card. **Exact request/response JSON/check team**And we use the same viewer in the original file, the same as the cost, the state, the usage, the event.
4. [Confirmation of the record](checks.json)and [Exam Log](tests.log)In the real screen checks and automatic checks, the results are displayed.](../../docs/02-experiments/README.md)is the location.

The save log and the HTML Export pop-up are **Click outside the window.**The inside click and drag that started inside is not the closing action. When you close the Export window while you're exporting, you cancel the request.

## File responsibilities

|File|Role|
|---|---|
|[json-viewer.mjs](../../viewer/experiments/json-viewer.mjs)|JSON/JSONL grammar test, the original token tree, 200Line pages, folding, folded, and folded|
|[app.js](../../viewer/experiments/app.js)|Schema requests, responses, checks, source records, documents, events are linked to a common viewer.|
|[styles.css](../../viewer/experiments/styles.css)|Brown theme, color by type of value, keyboard focus.|
|[server.mjs](../../src/finarch/experiments/viewer/server.mjs)|Allowed JSON Viewer provides static modules|
|[export-html.mjs](../../src/finarch/experiments/viewer/export-html.mjs)|Including the same JSON viewer and CSS in a single HTML|
|[checks.json](checks.json)|The actual browser verification of the case, automatic check results, change file hash.|
|[tests.log](tests.log)|Viewer: Data logs: HTML output and return checks|
|[tests-sandbox.log](tests-sandbox.log)|Check the localhost HTTP in the first run 2The items is restricted by the authorization of the record.|
|[server.log](server.log)|Read logs of the updated local viewer server, including JSON modules|
|[token-limit-review.json](token-limit-review.json)|To answer the user's most troubling questions, we need to expose007The stored 3,000Output tokens distribution and alignment confirmed by results 1The location of the original file. No setup changes.|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|Central template creation, text connection, and the custodian's original hashing.|

The large integer, duplicate key, and the iscale and numeric notation of the source file are not recreated. The API shows the values already received as objects as JSON, and opens the linked source to compare to the original file's void. JSONL shows the original row number. 200You can check it all the way down the line.

The general phrasing and base emphasis of prompt·Q/C, maintains the region-by-region folding status cache. The HTML Export that is generated afterwards also has the same JSON viewer and does not overwrite the existing copy. It does not modify the results of the stored experiment or add a model call. It doesn't show the authentication of the agent as a completed user review.

This README is a `src/finarch/documentation/templates/viewer-experiments-json-viewer.md`in `python3 src/finarch/documentation/manage.py refresh`So we're going to generate a
