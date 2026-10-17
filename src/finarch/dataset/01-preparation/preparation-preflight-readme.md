# Preparation small check {run_id}

With the latest code formats and new API responses. {case_count}I processed the case at the same time. {passed}passed, {failed}It's the generation and the whole target assignment didn't run.

|Case|Identified subject|Running value / gold|Graph|The final result.|
|---|---|---|---|---|
{case_rows}

The GDP clause is in the first PoT. `10`And I quote the value of `-10`And it failed to match the source numbers. 06- The exception-handler is a 03And then we did a feedback loop on the calculation, and then we did the next graph. `10`After reading the negative sign, I passed it by calculating the stars, preserving the original gold-first failure response.

## Execution and cost

PoT: Sol-medium API. Original review; verification of intent; feedback: Luna-max API. Combined tokens are limited by request 500,000The output limit is Sol. 128,000 / Luna 32,768.

Running time **{elapsed}Seconds.**Request to create an actual API **{calls}times**The estimated cost of the **${cost}**It's the API usage and public billboard, including the cache-promotional tokens, and it's not the bill confirmation amount.

|Purpose|Number of calls|Average input tokens|Average output tokens|Average sum of|Estimated cost USD|
|---|---:|---:|---:|---:|---:|
{usage_rows}

```bash
{command}
```

## Check the range

- The original review -- PoT -- Python execution -- graph -- meaning verification -- verified the actual API until the final state.
- Python gold matches and graph comparison {case_count}And it's all gone through. {case_count}entries. 200The file collision-detail statistics of the items simultaneous worker are not local checks.
- API response cut {incomplete}That's a communication failure. {transport_errors}That's the maximum actual combined usage per request. {max_tokens}tokens. 50But the limit reach and the output cut are different errors and the boundary conditions are checked as a response to the mutation.
- Stop ID re-registration, file storage, complete case preservation, verified as a local mo check, didn't force the actual paid call to stop. `--resume`If you run it, `NO_UNFINISHED_CASES`Add API to call 0It was a circle.
- Small passing is the meaning of the entire case validity API 200We don't guarantee the external service handling of the building. 429There's no automatic re-schedule for disconnection yet. 01-Run it from the source.

## Full input corrected

Existing 2,171And then there's the text string. `[]` 121It included a customized blank text exclusion standard that would complement the check log and add new input. **2,050entries**The Q.C.A. of the saved case is the same. 6The ID of the product in the case is maintained.

Enter the following full run: `data/prepared/finance-reasoning/full-20260917-v2/input.json`So, you can just delete the new entry and then re-enter the number. `input-correction.json`Check the old/new ID from the raw_id standard.

## The file and the reading order.

1. This article `preflight-summary.json`: case by case results; scope of examination.
2. `scheduler.log`, `checks.log`, `resume-check.json`Running: local inspection: re-opening after completion.
3. `input-correction.json`: empty text exclusion list; input hash; bird ID correspondence.
4. `01-preparation/test-xxxx/NN-round/`The answer is: the source code, the prompt, the response, the code, the graph, the verification. 01-round/06-exception-handler, the actual transmission record is 02-round/03-calculation/02- It's in the LLM-generate code.
5. `api-usage/summary.json`: Calling, Token, and usage-specific costs excluding translations.

[Custom Viewer](http://127.0.0.1:8892/?run={run_id}&case=test-0458&round=02-round&stage=03-calculation) · [Re-check the whole input](http://127.0.0.1:8892/?run=20260917-finance-preflight-v2)
