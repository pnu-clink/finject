# 100Newly made case {run_name}

Input: [{input_name}]({input_link}/README.md). TAT-QA 10 · easy 20 · medium 30 · hard 40I'm going to get it. 1 → easy 2 → medium 3 → hard 4 And then we're going to put it back in order. 100Except for Q/Cs like the source ID in the case, we don't reuse the existing LLM response.

## Run and verify

Preparation Full → Passing case of Generation 7Type → Characteristic Excel report → results are in the order of aggregation. 3The failure interpretation and object model Evaluation/Analysis are not included in this production run.

POT is the gpt-6.1-sol/medium, original review, field creation, verification, EA feedback, feedback is gpt-6-luna/max. The current common API is the parallel mode and the API simultaneous request limit is 200The actual model, effort, prompt, schema token is verified as an individual call record. 1,900Call, expect $8~15The former 100It's a calculation based on the usage of the case, not the actual charge or the maximum cost.

The wait time for the new API call is the existing 300The run settings do not change without user permission. This temporary change in the run and the user's commands will be returned to [Time Recovery Record](runtime-adjustments/001-api-wait/README.md)Some requests sent before the return are subject to waiting times at the time of transmission.

In order of reading:

1. [Planning plan](selection-plan.json) and input selection-manifest.json: subject; purity; source; exclusion reason.
2. [Checking the history](preflight.json)Schema: Current model: Prompt Check the hash key settings. It's not a paid call.
3. [Full status](full-pipeline-status.json) → [Acts log](pipeline.log) → [Proses information](process.json).
4. [Preparation is in place](01-preparation/summary.json) → By case run.json;01/02/03-round.
5. [Generation state](02-generation/summary.json) → The final-validator.json. 7The type.
6. After you've finished [the latest copy](results/README.md): 00-input.json and type by type 01~07 JSON, manifest, outside log.
7. [API usage](api-usage/README.md)The estimated cost of call, including failure, incident, token, and publicity. Calls with no response and no usage are marked as uncertain.

The files that haven't been created yet are generated as the execution progresses. The undervalued and undervalued aren't PASS. The automatic PASS of the results distinguishes from the human judgement. The explicit person Reject is excluded from Export.

Common viewer: http://127.0.0.1:8893/?run={run_name}. You select this execution from the common screen, and you don't create HTML for run folders, but you identify the elementary, the tab conversion, the computation graph, the correction relationship phrase, the numerical stress and the calculation of the EA inverse as the storage material.
