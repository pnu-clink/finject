# Bounded production feedback

One run contains 01-round, 02-round and 03-round. Later rounds exist only when failed cases need a retry. The initial round starts from prepared source inputs with fresh model calls. Each later round processes failed variants and any dependent variants invalidated by a changed value claim. Passing inputs from the same run are frozen snapshots, identified by inherited-inputs.json with hashes; they are not counted as new calls. No other run is reused.

The cumulative supplements live only in feedback/{target-role}/{type}.json outside rounds. Every round reads this directory, never a chain of previous guidance files. LLM requests preserve the exact common, type-specific and supplemental instruction parts with hashes. Feedback generation records include input failures, schema, raw response and merged cumulative output.

Read each round's 05-text/03-final-validator/03-result.json, then 05-text/04-LLM-build-feedback, followed by the next round's case stages. Final validation uses existing checks; it does not invent a new correctness judgment. First pass ends retry for that item. Three rounds is the hard limit. Failures remain visible. Infrastructure errors block the loop instead of being interpreted as text defects. Human review is prepared after loop termination, with decisions pending.

Logs mirror round/case/stage under log/run/{run-id}; default.log merges the entire run and each round has its own default.log. The central viewer selects the run and round; loop-summary.json records transitions and final case locations. Historical run records remain readable.

## Result report

In the viewer, open the result report after the three round counters. It compares completed validator snapshots by case and variant, with failure reasons, resolved failures, guidance changes, and upstream exclusions. Pending rounds are not counted as successful.

## Time and output

`timing.json`The execution command and start; completion; total time, each variable `timing.json`It's the time of the variable. `timing-report.json`and `TIMING-README.md`The time, LLM usage button on the viewer will check the full, numeric, and intersectional chart. `log/cli.log`You can also see it in the
