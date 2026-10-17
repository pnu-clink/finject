# EA tag changes and execution of the original

This task is to get the EA number of the project first EA_01Second, EA_02It reflects the user instruction to set the star to the call folder before the run metadata is sorted.

Previously on EA_02 → Currently EA_01Previously on EA_03 → Currently EA_02So, we've done this one time, and we've only applied it to the original before the change, and we haven't done that twice. `variant`And the trial_id, the actual Q/C format scheme, was maintained.

## Reading order

1. [Exam results](verification.json)SHA-256The current manifest reflects only the newest version of verified metadata.
2. [Previous manifest](manifest-before.json): The hash of the file fixed at run time.
3. [Pre-modified copy](originals.zip): Original metadata and exact bytes of the request at the time as opposed to the previous manifest.
4. [Exit folder move verification](../layout/README.md)EA: The task of changing the path of the save only after the number is sorted.

Currently, JSON and statistics for read calls use a specified EA number. The metadata is stored in the ZIP above at run time. The input to the provider is the same as the raw response model.

This document is `src/finarch/experiments/templates/ea-label-readme-template.md`It's generated from.
