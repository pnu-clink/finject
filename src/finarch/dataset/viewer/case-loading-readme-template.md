# Check the performance of the problem-by-problem inspection

Run `{run}` · Selection of the variable `03-round`. . . . read the stored results and no LLM calls and production data changes.

## Reading order

1. `measurement.json`: same HTTP time for execution, transmission size, number of cases returned.
2. `checks.log`: case separation; cross-continuation; cache invalidation; past response blocking inspection.
   `profile-before.txt`The cost of the profile itself is not directly compared to HTTP time.
3. [Custom Viewer](http://127.0.0.1:8893/?run={run}&round=03-round&case=test-2028): Change the number to search and check the individual loading.

The detailed response is 2,050entries ·62,349,147Only one byte and one selection was complete detail, and the rest was a summary, so it wasn't a form that could only be stored in a cache and changed to a screen.

The first request after modification reads the list; search information and the list of selected cases. The request to change cases reads only one, and the browser keeps the list already received. The previous case details are returned to the summary, so no detailed data is accumulated in proportion to the number of cases visited. The question-text search and the ER/ED-mismatch-person judgement tags remain.

{measurements}

The time is this measurement of this computer. The OS file cache is not empty, and the load of other tasks may be affected. The original detailed request is non-compressed, and after modification is a gzip request, like a browser, so the data size is compared between JSONs before compression. The server processing and transmission time and does not include screen time.

The server shares a set of overlays and a large generation summary of the `latest` Prepare to avoid the creation of objects. The stored Preparation check results read the input selection, problem state, authentication basis, verification judgment file only when it is the same, and perform the existing verification when it is changed and deleted. The completed report is reused after checking the change, deleted and gate changes of the base file. During the process, the state cache is compiled from the original. The file identifier, key, correction/conversion view is invalidated if changed, and the state-report only is up to a maximum of 20,000Item / Inline 8MiBThe actual memory size of a Python object is different from this.

[Responsibility for the recording and file-sharing](../../docs/55-viewer-speed-and-phi-two.md#2026-09-17-%EB%AC%B8%EC%A0%9C%EB%B3%84-%EC%83%81%EC%84%B8-%EC%A1%B0%ED%9A%8C)

## Follow-up execution 003 Check

`measurement-003.json` `20260917-003`It's the actual HTTP response and the result of the browser navigation check. `checks-003.log`And that's the record of the follow-up.003 Common Viewer](http://127.0.0.1:8893/?run=20260917-003&case=test-0001)You can check the same function in.

The code is not broken down by execution number. 003And at first, 717List of items and details 1I'm getting a message, and I'm going to change the case in detail. 1I'm just getting a test.0002 → test-0003 List of cities to move 717I kept the tab and finished reading the individual records. 1.381It was a second.

{measurements_003}

003The Generation is in progress at the time of verification so the complete report reused the entire statistics instead of the restart. 9.393Second, after the change. 15.081There's still a bit of delay and discrepancy, and this little change doesn't necessarily mean that it's accelerated until the first load, and it's not a performance comparison on the same load, but different from other viewer requests in progress.
