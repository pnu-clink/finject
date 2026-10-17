# Viewer directory separation check

This document is `src/finarch/dataset/viewer/workspace-validation-readme-template.md`It's generated from.

1. [Role-by-folder sequence of actions](../../viewer/README.md)
2. [http verification log](validation.json)
3. [Real data set screen](http://127.0.0.1:8893/dataset/?run=20260917-003&case=test-0001)

The existing HTML-action file `viewer/dataset`And then we moved to the existing experimental modules. `viewer/experiments`So we've changed the path of the build output, the server template, the execution script, the test file, and we've kept the Python code under src.

I'm going to go with Python. 26Pass the items, the menu. 9Pass the items scan. 003 717The list of cases and the test-0001 I checked the calculation graph and there was no error on the console. 2items: Experiment JS Two addresses are HTTP 200.

Existing `test_live_logs.cjs`The log LLM filter is expected 3entries / actual 2It failed because of inconsistencies. The contents of the live.html were not changed, and this test corrected only the file path, and it supplemented the line that generated the temporary test directory that was missing from the Mathematical Viewer test, but neither the model call nor the actual judgement log.
