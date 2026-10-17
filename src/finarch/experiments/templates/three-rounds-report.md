# Luna · the same 100Source text 3The record of the car experiment.

Updated: {{updated}}

**The working state: {{completion}}**

User confirmation: **Same 100The original.700The variation, P0/P1, the inference OFF/ON, GPT-6- Luna, OpenAI Native Batch, no charge**The original is P0's OFF/ON. 200The rotation, the transformation, the 4Condition 2,800Circuit by circuit. 3,000calls. 2·3The car goes after the test of the front wheel -- strong critical analysis -- paper update -- change decision.

## Reading order

1. [Experimental Viewer](http://127.0.0.1:8894/?run=20260927-exp-001&tab=overview)And then I'm going to use the variable button. 1·2·3Turn the car around.
2. **00 Input → 01 Evaluation → 02 Analysis** Check the input sequence, the actual request-response, format validation, content judgment-condition comparison.
3. In this article, the three variables change the reason, result, cost, and other limits together. No report HTML is generated.
4. [Draft of discussion](../20260924-paper-draft/PAPER-KO.md) 8.1The sections only reflect the graphs collected and analyzed.

## Conditions and scope of interpretation

- The data is `20260917-002/results`In the original order of preparation PASS and 7The first one that satisfies all the transformation PASS 100source text. 100And the first thing I'm gonna do is get the items ready. 20, 7The transformation is incomplete. 159I jumped over the items. 1round `events.jsonl`It's not a random sample or a representative sample of the entire dataset. 100The items's human judgment record is all pending, so we don't call automatic inspection passes human approval.
- The pool input is public's Q/C. Precision, private answer-production labels don't deliver to the pool. Connection information and conditions are integrated into the model manifest and the ranking is placed in the events log.
- 1The car has now synchronized the common/P0/P1 and common response schema. 8,192No token, cache specified mode breakpoint. The variable changes are verified as the record below and each config.
- Check the input 800The rotating grass is the Luna max batch that does not see the response. 4Answer, up to 800So it's a call/calculator, and the analytical results are maximal. 8The response is independently re-examined with Luna max. 12,000tokens 203Cut the hole and then analyze it. 32,768It's been increased to tokens, but the technical and formatting failures are not enough to re-introduce it as a batch, and if necessary, it's a lot more like a batch. 65,536It's raised to tokens, preserving the original failure and cost, and not re-issuing because of the low significance score.
- We use the same analytical agreement as a three-dimensional comparison of the first probability of the same input, and if the next response rejects it, it's silently not changing the criteria, and it's not solving anything.
- The response review does not give the model name;P0/P1;OFF/ON identifier, but it can guess the condition by the classification phrase and description length of P1. It therefore does not claim to be a complete condition cover-up.
- Accuracy, intent appropriateness, response stability are different. 100The correction in items is not a developmental experiment, it's not an independent verification, and we don't call the variance in the number of variables that the instruction changes the uncertainty of the same repetition of the request.
- The original P1 summit counterparts, the whole semantic assessment of the independent model array, the method of production comparisons are outside this range, and they don't write as if they've validated the hypothesis in the paper.

## The cost per unit

OpenAI has applied the official batch limit to the input and output tokens returned. **Estimated use**This is not the receipt.0.05- Million, $500,000 is coming out.0.25/million and the inference tokens are already included in the output. 1I'm just going to be in the car. 2·3The amount of use collected includes failure, failure, and accident costs.](https://developers.openai.com/api/docs/models/gpt-6-luna), [Batch 50% Price: Finished window](https://developers.openai.com/api/docs/guides/batch)

|Round|Status|The grass.|Analysis and re-examination|Total|Unknown cost record|
|---|---|---:|---:|---:|---:|
{{costs}}

## The key of the three digits.

The original is **Number matching / plan 100items**And the variation is **Subject appropriate/content determined**The difference is that the denominator is different and the evaluation failure and the misresolution is preserved in the detailed table below. The P1 contradiction is a response that is in opposition to the declared manner and the actual number/null and is different from the common schema passage.

|Round|The original numbers match.|The change is P0 OFF|The change is P0 ON.|Transform P1 off|Transformed P1 ON|Declaration of P1 - numerical contradiction|
|---|---|---:|---:|---:|---:|---:|
{{outcomes}}

{{rounds}}

## Execution and Preservation

1Read the first passing of the car together with the second commentary and the final answer. 1So the actual final JSON was valid, so the collector modified the format and the data was stored in the JSON file. **No further calls. 3,000/3,000 Format valid**So we re-examined the original test file and the raw response, which is not calculated as the error rate of the target model. 800Pass the form-use test in the circuit 567Cutting through the argument. 203Accurate citation inconsistency 30And we're going to check the results of the follow-up.

`src/finarch/experiments/90-operations/three_rounds.py`Collect and analyze the completed batch → paper tables → update this document. The next parameter change decision is recorded after reading the actual response and analysis basis. If the call delivery is uncertain, the same batch ID is first checked and not submitted. OpenAI Batch is up to the maximum 24So the time window is the finished view, and the provider's procedure is followed.

Preserves the original input and prompt/schema·manifest, batch transfer file ID, raw response·use. Doesn't quietly fix the failure response or change the understatement to an incorrect response. The reason for subsequent study judgments and improvements on each variable is left to the improvement and events of the config.

## Final confirmation

{{verification}}
