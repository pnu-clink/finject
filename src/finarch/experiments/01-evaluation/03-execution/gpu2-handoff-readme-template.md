# GPU-2 · FinanceReasoning 1,080The phrase experiment sequence

Running ID: **$run_id**This is a remote test file, which doesn't mean you've run vLLM locally.](state.json)And [the human log](events.jsonl)Check it out.

In order of reading:

1. [Range of assignment and execution/acquisition criteria](PLAN.md)
2. [Input: Luna identity verification](verification.json)
3. [GPU search model is set to candidate](config.json)
4. [Record and Transmission Log](events.jsonl)[Hash file for identity transfer](manifest.json): The linking of the case is read in the model-by-model request manifest of the source run and put it on the list of run conditions above.

| File | Role |
|---|---|
| `00-definition/` | exp-006English prompt v4 response scheme copied in byte |
| `01-input/public.jsonl` | Frozen 1,080The original.7,560Q/C of variation. Does not include previous raw response |
| `01-input/model-inputs.jsonl` | And Q/Cs to send to the model. `answer_format.decimal_places`Only the input. |
| `01-input/private.jsonl` | Correct answer, error, output source. Use only for evaluation, not for model requests. |
| `01-input/trial-matrix.jsonl` | The two conditions of inference 32,400The toggle sub-support model removes the corresponding axis and confirms the denominator of the denominator. |
| `provenance/` | Past input-date hash, current production copy and difference, model call-free verification record |
| `support/legacy-source-snapshot.json` | Read-only copy of existing check-in, collection, folder code. Not expressed as a remote new implementation |
| `support/exporter-source.txt` | A copy of the source program that can scan the transfer file in standard Python. |

**Requested number:** So if you have two conditions, the source items $originals x 2 = 2,160, the variance $variants × P0/P1 × 2 = 30,240For each model. **32,400entries**So if you have one condition, **16,200entries**That's the way the call for placement search, flip-up, and flip-down verification separates from the test. The exact total sum is determined by the model-by-model supporting conditions chart of the remote.

The goal is to **GPU 4And you can actually see how fast you can complete the whole experiment in the bowl.**We don't call pre-browse candidates the optimum for all, recording the loading, searching, and copy time of each, and we don't create the time or GPU cost before the actual measurement.

The existing exp-006 before 100The article and the corresponding data in this document 800The items Q/C-correct-response metadata is the same. 1,080The items was a very close-knit exp-002 It uses input. 8,640The items Q/C is the same, but the item_id that you re-calculate after clearing the EA label is different, so it keeps the existing ID.](provenance/current-vs-frozen.json)Check that past responses are not reused as experimental inputs or results.

The title of the work: **vllm gpu-2From Qwen3.8 27B Drive the car.**The remote main task is to set up the server, search, test, fail, and analyze the data, and the local task is to verify data transmission and integrity. `reports/experiments-run`And in the existing experimental viewer, you read the Markdown document in this folder.
