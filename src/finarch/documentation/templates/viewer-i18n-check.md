# Check the screen language; HTML Export

[Reporting the authentication](../../outputs/viewer-i18n-20261002/README.md) → [verification.json](verification.json) → [Auto check log](checks.log) → [Examining the letter](documentation-check.log).

Applying the same screen language dictionary to Dataset: Experiments, including assets to the evaluator: Experiment: Annotation HTML. Modeling calls and output judgments were not saved. Verifying that the selection values, the reason for the mixer, the checkbox judgments are maintained on the live screen, and removing the test drafts without saving them.

`source-before.json`and `source-after.json`This is the actual creation of the Dataset statement that you have verified. `checks.log`This is the release of the Pre-Return, Block, Restored One/One Explanation, Offline Review, CSP, Dataset Export test. `dataset-server.log`, `experiments-server.log`The detailed responsibilities and flow are [common code guide](../../viewer/shared/README.md)is the location.

The browser tool is `file://`The verification that opens the file directly without allowing the user to access it is unverified. The offline data consultation verifies it in an automatic verification and distinguishes it from the live UI verification. If there's no translation in the original description, it doesn't generate a new translation, but it shows it as it is.
