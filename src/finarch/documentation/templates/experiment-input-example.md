# New public/private input example

[Operating records](../README.md) · [E01 Input separation](../../../../docs/02-experiments/01_evaluation/01_preparation/README.md) · [E02 Request](../../../../docs/02-experiments/01_evaluation/02_request/README.md)

The stored dataset `20260917-002/results`The original text that met the selection criteria 1and 7Read the variation. **The data is now in the ready code.**So this is Luna's P0/P1 -- the OFF/ON combination. 30items requests are prepared and no LLM calls are subject to.

**The problem data that we send to the LLM is just questions from the public, Q, C, Precision.** `item_id`Excluding case connection, test condition, prompt scheme, is verified in the model request manifest. `input-selection.json`Remove the silver and select the races of the existing way `events.jsonl`I moved it to the right.

|File|Role|
|---|---|
|[public.jsonl](public.jsonl)|Q/Cs that the model will use to solve problems. `answer_format.decimal_places`.item_id is for connecting|
|[private.jsonl](private.jsonl)|Answer evaluation, type, base of the product, source and variable connection|
|[luna-api/01-requests/manifest.jsonl](luna-api/01-requests/manifest.jsonl)|Execution criteria: case connection; model; P0/P1; reference conditions; prompt; schema; input. 30Line, specific case 8items|
|[events.jsonl](events.jsonl)|INPUT_SELECTION: Select order, rules, private sources, verify. Do not write the run as a separate input to restore the object|
|[request-inputs.jsonl](request-inputs.jsonl)|Real transmission input except for item_id from public. No private reference|
|[checks.json](checks.json)|8items public/request input matches; digit content; source file hash preservation verified|

Precision is stored in the public from the raw data set when the input is separated. Private's reference_precision is kept as an evaluation reference but not read in the request writing. If public has no precision, it stops preparing and is not replenished with private.

This README generates from the template, leaving detailed raw material hashes and processing quantities in the checks, and execution power in the top events.
