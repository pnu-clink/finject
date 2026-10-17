# Experiment Viewer Failure analysis sort filter automatically open the browser

## Check the order.

1. [Experimental Viewer Running Guide](../../viewer/experiments/README.md) `start.command`The server is ready and the browser opens.
2. 20260923-exp-007Choose the one. **04 Failure analysis**Open the return state. **All statuses**If you change it to 3,000Requested100You can check the case.
3. You select the diagnostic private button above, and then you check the response list below, and you change the sorting by pressing the case, type, model, prompt, promotion, half-reverse state, group private column title.
4. [checks.json](checks.json)In fact, the check item is [tests.log].](tests.log)in 52The items automatically checks the results, [server.log](server.log)Check the server-ready browser heater and screen request.
5. [Letter renewal log](documentation-refresh.log)[Where is the verification log](documentation-validate.log)[Worldwide Responsibility](../../docs/02-experiments/README.md)is read.

## Change the screen

- We moved the left-hand diagnostic list to the cross-sectional button above the text, where the selection is displayed in the check mark, brown background, and then clicked again or removed as the diagnostic selection debug.
- The drives are sorted by the number of drives, the drives by the buttons are based on the basic conditions before the drives are selected, and the actual result number is shown separately below.
- The answer is the default case number sequence. 30And we divide by one, and we keep the same value in a fixed, auxiliary order.
- The column title and the response sort box indicate the same state. When you change the sorting and assignment, you go back to the first page. The blank result is the filter resolution.
- `start.command`The address of the server that is prepared is opened to the default browser. The same port-like resulting folder is reused by the viewer, leaving the other service/end folder as an error.

## File responsibilities

|File|Role|
|---|---|
|`viewer/experiments/model.mjs`|Sequence of numbers, sorting, sorting and page scope, sorting by specification|
|`viewer/experiments/app.js`, `styles.css`|Upper diagnostic filter, water/selection mark, response column and sorting direction, query preview|
|`viewer/experiments/start.command`, `server.mjs`|Server readiness, like server verification and event handling|
|`src/finarch/experiments/viewer/export-html.mjs`|Including the alignment status and tying the same app/model/CSS to a single HTML|
|`tests/failure-sorting.test.mjs`, `tests/launcher.test.mjs`|Natural sorting, duplicating, filtering, server preparation, reuse, and load testing of pages.|
|`src/finarch/documentation/templates/viewer-experiments.md`|Running: Screenshot Guide to the current version of README|

Ex-ex-ex-007To move the sorting page, combine diagnostic selection/resolution and AND/OR, and check the output cut prioritization. As an actual start script, Chrome leaves the open record in server.log and checks.json. 43items return and new alignment/initial testing. 9items included 52The items passed. Then the displayed phrase supplement is checked in the browser.

The same set and alignment of the new HTML Export automatically verifies the contrast between the output files and the output files. `file://` Browser execution is not the verification scope of this task, there is no recalculation of new model call and test results, and it does not mean a user review is completed.

This README is generated from `src/finarch/documentation/templates/viewer-experiments-failures.md`.
