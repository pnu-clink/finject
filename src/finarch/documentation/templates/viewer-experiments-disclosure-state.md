# Keeping the experimental target area folded

## Reading order

1. [Experimental Viewer](http://127.0.0.1:8894/?run=20260923-exp-008&tab=overview) **What does this experiment confirm?**Click on the button. Change the filter, tap repeat, read again, check if the browser is in the same state after you have re-opened.
2. [Confirmation of the record](checks.json)I read the actual actions and scope of the verification.
3. [File responsibility and flow](../../docs/02-experiments/README.md)is read.

## File responsibilities

|File|Role|
|---|---|
|[app.js](../../viewer/experiments/app.js)|Fixed keys of the destination area, selected state storage, recovery, change during renewal preservation|
|[checks.json](checks.json)|The original phenomenon and the actual browser verification after correction|
|[Letter renewal log](documentation-refresh.log)|Recorded in the central template that generated the README and document code|
|[Lessons verified log](documentation-validate.log)|Currently, the document link, the original file, the data|

It runs by default only when there's no saved option. In the same browser, like the same viewer address, it runs but uses the last option. In an environment where the storage is blocked, it's only stored in the current page. The HTML Export that you generate later contains the same screen code, and the previously downloaded copy doesn't change.

It's not an experimental input; it's not a modification of the raw response or a call to model.

This README is a `src/finarch/documentation/templates/viewer-experiments-disclosure-state.md`To create again `python3 src/finarch/documentation/manage.py refresh`Run the program.
