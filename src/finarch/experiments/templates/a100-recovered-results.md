# $model recovery results

Run `$run`: **$responses collected**Pass the local full response agreement **$valid_rate**.

Read the order: This report → [structured statistics](recovered-summary.json) → [E04 Form report](01_evaluation/04_validation/REPORT.md) → [Compare the original numbers](01_evaluation/04_validation/numeric-comparisons.jsonl) → [Failure case](01_evaluation/04_validation/failure-details.jsonl) → [Recovery of the hash record](recovery-receipt.json)The actual request-response is [Experiment Viewer].](http://127.0.0.1:8894/?run=$run&tab=conditions)I read it.

## The results are conditional.

$conditions

Remote schema pass is a JSON structural check. Local whole contract pass additionally verifies the classification, digit/null, sign/scale, decimal digit rule. The numerical unit compares only the fixed reference to the number of the original, not the meaning of the correct answer. 1,080The comparison denominator uses only the original that compares the numerical answer after passing the form.

## Type-in format pass

$types

Each cell is the local total contract pass/plan response number. It doesn't subtract the failure clause from the denominator.

## No number of answers for type of input

$null_answers

Each cell is `answer=null`It's a valid response number, an observation of a valid response, and we haven't determined whether the absence of a response is correct or if we've detected an error correctly.

## Classification records

$classifications

The above classification is a model declaration of the response that passed the contract.

## Failure and Limitations

$failures

If one response violates multiple rules, the number of rules is overridden. The cutoff is in a standstill and the raw response is not corrected.](01_evaluation/04_validation/failure-details.jsonl)And you can see the actual content in the same case in the viewer.

The cut-off response is remote. `delivery.json`There are instances where the usage·finish_reason is missing. `raw-response.json`The record of making a local estimate and the leakage of the 0The first local judgment is that the attempted `result-before-delivery-metadata-repair.json`The remote raw response ·request record is not overwritten.

## Time, time, and time.

The total time of the evaluation **$wall**The processing is **$throughput per second**So this is A1.00 4The scope of the assessment of the allocation criteria is **$gpu_hours GPU time**The time before the model is loaded and the evaluation is not included in this figure.

$latency

The time per session is from sending requests to receiving responses, which is processed simultaneously, so the time of the session is separated from the time of observation, and not measured separately from the time in the provider's internal atmosphere and the time of inference.

The actual server settings and start-and-end cache index are `remote-evidence/`Prefix caching is OFF and start-finish hit is 0The cache token field of each response is missing. **UNKNOWN_NOT_ZERO**The cost of an external API call is 0The amount of the GPU is USD, and the amount of the token is USD, token, promotional token, condition, time, type, and statistics.](recovered-summary.json)is the location.

## File storage and analysis

- `remote-results/`The following are the remote transmission requests: raw response: call recording: source verification source.
- `collection/responses.jsonl`Remotely generated response duplicates. Preserves the raw response's supplier field.
- `remote-evidence/`Remote state, runtime, log format copies. The local files that are closed when ready will not be overwritten.
- `01_evaluation/03_execution/`: raw response attempts linked to existing viewers · local checks; problem-based consultation files.
- `_recovery/manifest.json`The recovery file is SHA-256 The list.

This theory verified and integrated the existing responses in Python. 0entries, and A02·A03 LLM Analysis has not started.
