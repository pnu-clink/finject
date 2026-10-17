# Experiment Viewer Keyboard Move-Combination Selection

This document is a record of the W/S's phrase number, Q/C position shift, and now W/S scrolls up and down halfway across all the screens.](../viewer-experiments-scroll-shortcut/README.md)Check first.

## Reading order

1. [Compare the problems](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006&variant=IC_VALUE_01_AFTER)in **Keyboard shortcuts**In a keyboard layout like the Dataset Viewer, the cases are blue, the type is orange, the conditions are blue, and the screen and text are in green.
2. **Q/E**The previous/next case, **A/D or B**From the original to the EA-02Move the type up to the type. **W/S**And the key is the number of phrases/Q·C position. **1–6**The top screen is from the full result to the report power. 25It moves along the items list page and stops at the end of the pack.
3. In front of the condition line. **(Unguided Solving, ) (Unguid Solving,) (Criteria-Guided Solving) (Cryeria-Guidated Solving, ??)**Here's the thing. **When you get to this four combination with Z/C, select immediately**The rear Unuided Solving/Criteria-Guided Solving-Reasoning OFF/Reasoning ON button is on the back, and then the focus is on Z/C. **Space/Enter**We use Tab/Shift+Tab, and the front/back selection tabs synchronize with each other, and we distinguish the brown concentration of the selected color from the focused threshold.
4. Below each combination, the corresponding case, type, model, **The last time of the trial is saved**The multiple models each show time-out, read error, no request and actual 0Criteria-Guided Solving in the original is not planned, and you can't choose.
5. [Confirmation of the record](checks.json)[Examining logs](tests.log)[Company: file-by-file responsibility: also](../../docs/02-experiments/README.md)inspect

The Move Shortcut is not working when using the Input/Options box or when the pop-up is open, except for Ctrl/Alt/Meta combination; and the Hanks combination input key. 1 The whole result is initializing the view filter like a click, and then it's going to include the same functionality in a single HTML Export that you're going to create.

## File responsibilities

|File|Role|
|---|---|
|[model.mjs](../../viewer/experiments/model.mjs)|The neighboring page of the entire case after the filter, 4The combination of the items, the time value and the missing state|
|[repository.mjs](../../src/finarch/experiments/viewer/repository.mjs)|Save the time reading of the result/call. Separate the damaged files from the current response monitoring of other combinations|
|[app.js](../../viewer/experiments/app.js)|Shortcut key, input protection, button sync, time sign, focus recovery after screen refresh|
|[index.html](../../viewer/experiments/index.html) / [styles.css](../../viewer/experiments/styles.css)|Keyboard shape, functional guidance color, combination/individual selection color, starting point thedry|
|[offline.mjs](../../viewer/experiments/offline.mjs)|Select the same case, syntax, time in a single HTML.|
|[checks.json](checks.json)|Actual browser verification, return check results, change file hash|
|[tests.log](tests.log)|Article page filter move, time drop/down/0Second, offline data match and existing viewer return checks|
|[tests-sandbox.log](tests-sandbox.log)|The first one. 39HTTP is in items testing. 2The items stopped recording with localhost permission restrictions.|
|[server.log](server.log)|The read log of the changed Viewer server|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|Central template creation and document linkage; custodial source hashing|

Processing time is not the time to re-load or re-load. `result.elapsed_seconds`If you don't read it first, `call.result.elapsed_seconds`Verify. Do not change the raw response and save results or call the model add. Browser verification is an agent verification and does not mean the user has completed the review.

This README is a `src/finarch/documentation/templates/viewer-experiments-keyboard.md`in `python3 src/finarch/documentation/manage.py refresh`So we're going to generate a
