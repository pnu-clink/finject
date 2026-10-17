# A100 Data evaluation and local analysis are generated

The state and execution order `evaluation-plan.json`The server is moving. `remote-queue-state.json`(Recovery time signals), and the recall and local analysis is `recovery-state.json`Prepare and transport verification is not evaluation completed.

- Data: The TAT-QA code 291That's it, the FinanceReasoning principle. 1,260And each of the elements. 7We apply Unguided/Guided × reasoning OFF/ON to the transformation.
- Qwen-3 is the order.8B Two sets of data → Qwen3-14B Two datasets → Qwen3.8-27B Two sets of data.
- Requested by: 148,896External appraisal API excess 0The cost of GPU infrastructure is uncertain.
- The exact revision, run ID, and number of each model. `evaluation-plan.json`I'm going to write it down.
- Distant root: `/home/clink-wooix/workspace/finarch/experiments`It maintains the data/generated, src/finarch, config/experiments, reports/experiment-run structure.

In order of reading:

1. `transfer-manifest.json`·`archive-sha256.json`·`transfer-receipt.json`The first: 1,070File transfer and hashing verification. Additional execution modules. `sync-release.json`• Discrimination in the conduct of others `sync-input.json`·`manifest.json`This is the standard.
2. `evaluation-plan.json`: 6Can request a fixed order of items execution.
3. Each run `00_input/selection.json`Selection: Exclusive reasons and metaphysical analysis. `public.jsonl`and `private.jsonl`It connects to item_id and only sends the question/context/answer_format to the model.
4. Server `preflight.log`Run each one. `01_evaluation/01_preparation/token-preflight.json`The real model is a token sniffer that checks all the input and output.
5. Server `queue-state.json`Running by run. `server.log`, `01_evaluation/03_execution/<model>/remote-state.json`Server startup, operation and failure.
6. Each request `remote-results/<trial_id>/provider-request.json`, `raw-response.json`, `delivery.json`, `format-check.json`Requests: actual; raw response; usage; reason for completion; format validation. Uncertain transmissions do not automatically reset.
7. Server `recovery/<run>.ready.json`, local `recovery-manifest.json`: Seal compressed SHA and previous file hash. Refuses to overwrite other contents of existing files.
8. Local E04And the comparison of numbers `02_analysis`I'm looking for the original answer in the existing experiment viewer and reading the results.

The default runtime is TP4, bfloat1.6- You're asking for it. 16, max_num_seqs 32, batched tokens 8,192, context 40,960Maximum power. 8,192This is not an optimization result, it's an initial setup. It doesn't successfully hide the response to the output limit, including reasoning, but it saves it to raw response /finish_reason. 0It's not going to reduce the denominator except for the failure, the addition of the subset, the form error.

The absence of some auxiliary metaphors, such as the nominee value of the copy and the scope of the production test, is different from the transmission gap. `selection.json.analysis_metadata_gaps`Q/C and answer-based judgments can be done, but we don't claim candidate A/B comparisons without data as a complete analysis.
