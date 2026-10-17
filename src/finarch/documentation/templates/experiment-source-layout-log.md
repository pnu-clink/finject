# The test source is set to

[Sous entrance](../../../src/finarch/experiments/README.md) • [Setting instructions](../../../config/experiments/README.md) · [Writing Viewer](http://127.0.0.1:8893/?run=20260927-experiment-source-layout)

So, if you suspended the experiment, you could use the source of the `00-input → 01-evaluation → 02-analysis`The internal stages correspond to the run's number and range, and provide the entire pipeline and the step-by-step pipeline. Analysis chooses Codex CLI from TOML or OpenAI Batch.

## File roles and reading order

|In order.|File|Confirmation of the|
|---|---|---|
|1|[migration.json](migration.json)|Post-moving route source hash position watch list changes|
|2|[baseline-checks.json](baseline-checks.json)|Before moving, local inspection status.|
|3|[validation.json](validation.json)|After modification, local inspection, adjustment switching, center state, documentation, screen checks|
|4|[events.jsonl](events.jsonl)|The order of work, the results of the analysis, the call model|
|5|[documentation.json](documentation.json)|List of source guide documents read by common viewer|
|6|[Analysis prompted the solution](prompt-clarity/README.md)|The pre-post-primary examination that transforms the expression of the internal stages into the actual input-computing system description|
|7|[Time recording local inspection](analysis-timing-checks.log) · [Blood check](analysis-timing-viewer-checks.log)|Step: Complete call time, stop-down record, screen transmission check|
|8|[Time-recorded results](analysis-timing-verification.json) · [Skyma recovery check](analysis-schema-recovery-checks.log) · [Check the progress](analysis-progress-checks.log)|First real call, source, schema, preservation, cancellation, record, preservation and re-recovery|
|9|[Calling simultaneously checks](analysis-scheduler-checks.log) · [Check the action](analysis-scheduler-verification.json)|20It starts.60Increase CPU condition per second; call presence; save; screen check|
|10|[Response to unidentified ID check](analysis-unresolved-ids-checks.log) · [Requested by the re-opening of the case](analysis-unsent-resume-verification.json)|The time override that occurred in this run also included in the list of errors. 4It's the archives. 359Just start again.|
|11|[Exercise board inspection](progress-dashboard-checks.log) · [Real API: screen checking](progress-dashboard-verification.json) · [Graph screen](progress-dashboard-graphs.png)|Complete; execute; run; run; down; dry match, unfinished; fail, excluding average, simultaneous call number; limited stepwise graphs and CPU 60% reference, 5Secondary automated monitoring|

[Luna progresses to the dashboard](http://127.0.0.1:8894/?run=20260927-exp-007-luna&tab=progress)The CPU graph uses the same timeframe, showing the current value and the end-to-end attribution criteria on the upper bar. The dashboard verification only reads the runtime record of the existing analysis and does not create a new model call.

We added the time recording feature and then re-launched Luna's existing Batch Collection Analysis on user instructions.](../../experiments-run/20260927-exp-007-luna/02_analysis/timing.md)and check in the experiment viewer. 0It distinguishes between the recording and the subsequent run.

The original was written by [Minister Folder].](../../../archive/20260927-experiment-source-layout/)In the current execution, the prompt/schema; raw response is not included in the modification of the object of this task.4So, we have a 0.1And then we're going to summarize the results.

In the Common Document Viewer, `20260927-experiment-source-layout` If you select the execution, you read the current file.](http://127.0.0.1:8894/)Select the run and check. It doesn't generate any HTML for each result.

This record is a record of a code structure and local test. It doesn't imply actual API/Codex analysis completion or meaningful verification of correct answers. New model calls, batch submissions and identity status consultations have not been done, and it's unclear whether the previously submitted remote batch will continue from the provider.

This README is generated from `src/finarch/documentation/templates/experiment-source-layout-log.md`.
