# Experimental viewer w/s half screen scroll

[Experimental Viewer use](../../viewer/experiments/README.md) · [Activate file flow](../../docs/02-experiments/README.md)

## Check the order.

1. [Compare the problems](http://127.0.0.1:8894/?run=20260923-exp-008&tab=case&case=test-0006)in **Keyboard shortcuts**Open the W/S key to check the description.
2. I'm out of the input and pop-up. **S**And then you press down, **W**And if you click on that, it moves upwards to half the current screen height, and it's the same thing on other screens like fail-safe analysis.
3. [Real screenshot checked](checks.json)[Auto-testing](tests.log)[ Letter renewed ](documentation-refresh.log)[Certification of the letter](documentation-validate.log)is read.

## Changes and scope

The previous W/S moved directly from the case comparison to the case title and Q/C, and S expanded the input area. The current W/S only moves the location. The folded item, question, pattern, filter URL does not change. When using the input/selection box or pop-up is open, the combination key repeat input applies the same protection conditions as it does for all newly-released single HTML on all screens. `app.js`and `index.html`This goes in.

|File|Role|
|---|---|
|[app.js](../../viewer/experiments/app.js)|After the key entry check, the screen is half as high as the `scrollBy` Calls|
|[index.html](../../viewer/experiments/index.html)|Keyboard shape and W/S description|
|[viewer-experiments.md](../../src/finarch/documentation/templates/viewer-experiments.md)|Central source of the use of README|
|[experiments-operations.md](../../src/finarch/documentation/templates/experiments.md)|Central source of the operating manual README|
|[checks.json](checks.json)|Actual browser movement distance, access protection, and resource state preservation|
|[tests.log](tests.log)|Experimental viewer full return test|

This log is a screen-code and document change verification, not a saved test result or model response, but a browser verification and a user review.

This README is a `src/finarch/documentation/templates/viewer-experiments-scroll-shortcut.md`in `python3 src/finarch/documentation/manage.py refresh`So we're going to generate a
