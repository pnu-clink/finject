# {run_id} Call the folder

Verified status: **{status}** · Check-in time: {verified_at}

The call was only identified by the hash. `Calls/<Help>/<type>/<Helping>-P0-R-off.json`The original is two conditions, the variation is P0/P1 × R-off/R-on four conditions. 06-EA-01, 07-EA-02.

## Reading order

1. [Exam results](verification.json): JSON for reading {readable_call_files}items, moved call folder {moved_trial_folders}items, the original file. {preserved_files}Check the items's hatch.
2. [Running counterpoint](mapping.jsonl)Previous: previous hash path → current source path → JSON for reading.
3. [Make a note](record-hashes.jsonl)Previous: Current file path and move before SHA-256I checked the same hash after moving.
4. [Act plan](plan.json)Type response verification and pre-movement request number; condition; volume of use; cost.
5. `before/`So the path remains the same as it was then. The current results are in the REPORT.md and calls of the execution folder and you read the old path and you find it in mapping.jsonl.
6. [Acts log](../events.jsonl): CALL_LAYOUT_STARTED and CALL_LYOUT_VERIFIED records.

The actual model call is {new_model_calls}So the request, schema, response, raw response during the folder move was unchanged, and the request number, status, usage token, estimated cost was in contrast to before the move. `_records`The source code is used only for cost-cutting judgments and does not count JSON for reading as a star call. It does not generate a call file for untryed requests.

The execution of the entire project reflected the change of EA number together with the separation of the `label-migration/` There's a record.2/EA_03as EA_01/EA_02The original and pre-most manifests before the metadata changes are stored in that folder, and the hash of the folder moves after the metadatha is sorted.

This document is `src/finarch/experiments/templates/call-layout-readme-template.md`Screen implementation and HTML creation are not included in this task.
