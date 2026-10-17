# {{run}} · A01 LLM content review

We first review the possibility of input responses with the Q/C-precision that the pool delivers to the object, then we review the actual response of the subject model anonymously, and the judgement is the preliminary judgment of the analytical LLM and distinguishes it from the gold-man approval.

|Stage|Status|Analysis call number|Estimated cost based on usage USD|
|---|---|---:|---:|
{{states}}

## Reading order

1. `00-definition`Each analysis step is an English prompt, a response JSON schema, a hash. 2·3Cars use the same standards.
2. `01-LLM-input`: The input review that didn't see the model response. `manifest.jsonl`It's a request that includes Q/C precision. `results.jsonl`Silver is the judgment, the judgment, and the use. 2·3The car. 1They share the same input judgment and failure records on the car, so they don't rebuild this folder or recalculate the cost.
3. `02-LLM-response`It reviews the actual responses that have passed the form in phrases, hides the condition name, mixes the response number sequence, and records the number and the link to the experimental condition only in the manifest. The separate correct answer information needed for the evaluation is not passed on to the target model.
4. `03-LLM-audit`The first analysis is the maximum. 8We re-calculate the items response and re-examine the judgement. The first response judgement doesn't show it. If the judgement is different, it's not deleted, but it's marked as a misjudgment at the default appropriate rate.
5. `../02_comparison/summary.json`Type: ×P0/P1×OFF/ON, result of the matching of the source numbers, corresponding transitions and the source items re-collection interval. `rows.jsonl`and `counterexamples.jsonl`Link it to the original file.

Each LLM folder is `batch-001/input.jsonl`It's an OpenAI batch transmission format. `job.json`The batch ID of the provider, the status, `output.jsonl`·`errors.jsonl`The input is the input input and does not override the raw response. `state.json`The run log is the run log of the run. `events.jsonl`So let's just leave it there.

The execution file is `src/finarch/experiments/02-analysis/legacy/content-analysis/semantic_review.py`The response test. `semantic_contract.py`And that's the view from the viewpoint of the viewer. **02 Analysis**In the same storage results read: form failure; analysis failure; judgment unresolved does not change the force to mean a misrepresentation.
