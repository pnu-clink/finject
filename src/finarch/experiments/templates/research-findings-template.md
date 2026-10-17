# {run} · File flow verification and analysis

Original {originals}· variants {variants}items, targeted model pool. {planned}calls. {analysis_model} · {effort} · {backend}It's a small implementation of verifying file flows and default observations, and it's a user review and development that's going to help us get the most out of our data. **Waiting**.

## Step by step.

|Stage|Input → process → output|The current results|
|---|---|---|
|00 Input|Data set results → Q/C·precision / evaluation references separated|Original {originals}· Variable {variants}|
|E01–E02|The test conditions, profile, prompt, schema, model manifest|{planned}requests frozen|
|E03–E04|{solver_models} → raw response preservation; format validation|Format valid {valid}/{planned}|
|A01|Comparison of the original numbers. Independent case review.|The number matches the original response {numeric_matches}/{numeric_compared}|
|A02|Comparison of the correspondence by condition|The content is verifiable. {assessed}/{planned} · Underrated {unassessed}|
|A03|The whole statistics, the case of the election → critical review|[Analysis of the trial](results.jsonl)· This report|

The validity of the correspondence determined by the analyst is different. The original response that does not submit a number does not fit into the number comparison denominator, so the above ratio is not used as the total original answer rate. The unresolved response is excluded from the denominator of the validity ratio, but is displayed along with the total plan denominator.

## The original.7Type × 4Condition

Each cell is **The appropriate response/content judgement (misreported)**The variations and conditions that are connected to the same source are not independent samples.

{matrix}

## Observations, measurements and improvements

{notes}

## Conditions and costs of execution

- The actual output of this fold is: **{run_output_limit}tokens**The new basic API profile is **65,536tokens**And it didn't apply to requests that were already executed.
- `thinking_budget: 2048`The data is not applied to the Luna transmission text.`none` / ON=`medium`Set to.
- Analysis of the data: **{analysis_model} · {effort} · {backend}**The Codex analysis doesn't show that the API has an output limit.
- The estimated cost of the Native Batch grass: **${cost:.8f}**The return is calculated as a token and denominator, not a bill counter value.
- {analysis_billing} The detailed case studies for interpretation were deliberately selected and the overall ratio was A0.2 And it's only the whole statistic.

## The order of the files.

1. [Action setting](../../config.json)[Input guidance](../../00_input/README.md).
2. [E02 prompt schema request](../../01_evaluation/02_request/README.md) → [E03 Raw response](../../01_evaluation/03_execution/README.md) → [E04 Format validation](../../01_evaluation/04_validation/README.md).
3. [A01 The following is a list of the most common types of cancer:](../01_response_review/README.md) → [A02 Conditions and models](../02_comparison/README.md).
4. [A03 Request and provided basis](manifest.jsonl) → [English translation](results.jsonl) → This Korean review guide.

[See this run on the viewer](http://127.0.0.1:8894/?run={run}&tab=analysis)The raw response preserves the existence of the judgment, and the application of the improvement proposal and the adoption of subsequent experimental and discussion conclusions is after user input.
