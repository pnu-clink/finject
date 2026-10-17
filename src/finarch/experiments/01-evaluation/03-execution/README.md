# E03 Execution

[The whole sauce](../../README.md) · [Experimental documentation](../../../../../docs/02-experiments/README.md) · [Setting up](../../../../../config/experiments/README.md)

Run is a response: `01_evaluation/03_execution`.

E03.01 Check the run conditions → E03.02 LLM grass → E03.03 Try to preserve.

First verify the small response and usage, then submit a follow-up batch. Separate the status, failure, or transmission anonymity, and save the raw response and error when it fails. Separately verify the provider process completed; locally collected completed; format validation.

## Usage

The next command runs from the project root. `RUN_PATH` `prepare`It's an experimental folder that G.O.A. has created, and it uses the same path as the experiment that he's already created.

```sh
RUN_PATH=reports/experiments-run/20261003-exp-004-tatqa-luna
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline run --evaluation-only --run "$RUN_PATH"
tail -f "$RUN_PATH/pipeline.log"
```

E03 Instead of starting a new dedicated CLI, we use the top pipeline. `I'm going to be working on this.`Batch ID of the public status, completed/failed tooth check, and collect `calls/`Read the raw response and attempt records. Do not submit duplicates of the same running process or existing batch.

`OPENAI_BATCH_SUBMITTED`is submitted, `OPENAI_BATCH_PROGRESS`The process of handling the provider, `OPENAI_BATCH_VALIDATION_PROGRESS`The dryer completed the dryer is not going to be a local format dryer. `PIPELINE_EXIT`The entire end of the cycle is the root of the `full_pipeline.status`Check both the cache settings and the actual usage check and check the usage gap. 0It's not considered.

## File responsibility and reading order

|File|Get in there.|Input → process → output|
|---|---|---|
|[providers.py](providers.py)|`preflight / validate_request / call`|Request, set up, and check conditions, Haiku 5.5The effort·thinking_type·output limit and OFF/xhigh·max unchecked → provider selection·raw response ·form state|
|[orca_api.py](orca_api.py)|`validate_model / body_for / call / parse_response / accepted_returned_models / configure_returned_model / revalidate_returned_models`|DeepSeek V4 is coming.1 Flash request → R− disabled / R+ enabled·max, run-by-run cache; half-replacement model name authorization check; HTTP 1Retransmission → raw·reference trace·cache usage·semi-repayment cost. Only approved date-type response names are allowed to be added on the respective run and the request model and raw response are maintained.4 Re-check and not re-record. Unknown_DELIVERY·usage is stored as uncertain and not automatically retransmitted.|
|[anthropic_api.py](anthropic_api.py)|`body_for / call`|Request for a settlement 4.5 budget or 5.5 effort·adaptive/disabled·JSON schema for transmission → actual Messages body· raw response|
|[openai_batch.py](openai_batch.py)|`process`|Fixed requests → OpenAI Batch submission; syndication; collection → Batch ID; raw response|
|[anthropic_batch.py](anthropic_batch.py)|`split_requests / process_chunk / process`|Fixed request → set set set of conditions;2/4Verify all conditions are valid → Subsequent batch submission; such as ID inspection; collection; raw response retention.|
|[gemini_batch.py](gemini_batch.py)|`process / collect / collect_submitted`|Fixed request; cache inspection → Native Gemini Batch submission;30Secondary search; collection → Batch name; movement log; raw response ·use volume. `submit_all_before_poll=true`is collected by storing the split assignment in sequence after submitting it to the ID. `collect_submitted`The new ID is not re-filled.|
|[call_layout.py](call_layout.py)|`publish`|Try out the result → case → condition by path → raw response link|
|[output_budget.py](output_budget.py)|`configure / policy_for / prepare_attempt / retry_truncated`|Run-by-run approval, confirmation request, previous attempt, default default default, only the actual length end 2Ship expansion → attempt cap-out. Common form failure; transmission unnamed does not re-emerge and terminates at maximum limit|

```mermaid
flowchart LR
 IN["Input and set"]
 subgraph F0["01-evaluation/03-execution/providers.py"]
  S0["E03.01 Same schema definition check · Changed definition is new check"] --> N0["Enter conditions every request check / preflight / call · Haiku 5.5 OFF/xhigh·max blockage · Gemini level testing"]
 end
 subgraph F1["01-evaluation/03-execution/openai_batch.py"]
  N1["process"]
 end
 subgraph F2["01-evaluation/03-execution/anthropic_batch.py"]
  N2["E03.A02 split_requests · Set the forward set of the conditions"] --> A1["E03.A03 When you're ready to work,"]
  A1 --> A2["E03.A04 Submit · Batch ID storage"] --> A3{"E03.A05 Poll · Finished the same ID?"}
  A3 -->|Waiting| A3
  A3 -->|Complete| A4["E03.A06 raw. use volume. E04 The inspection preservation"] --> A5{"Are all the conditions valid?"}
  A5 -->|Passage · Following group| A1
  A5 -->|Failure to follow-up| ERR
  A4 --> OUT
 end
 subgraph F5["01-evaluation/03-execution/anthropic_api.py"]
  H0["E03.A01 body_for · 5.5 adaptive/disabled + output_config.effort · transmission schema"]
 end
 subgraph F6["01-evaluation/03-execution/orca_api.py"]
  O1["E03.O01~02 The end result model, the OFF/max schema, the run cache approval test"] --> O2["E03.O03 The real HTTP 1Redirect is prohibited"]
  O2 --> OM{"E03.O07 Returns model name · default identifier or date-shaped approval of the corresponding run?"}
  OM -->|Allow me.| O3["E03.O04 raw; use volume; reason trace conservation · E04 Format validation"] --> OP{"OFF/ON forward response valid?"}
  OM -->|Unused · raw response conservation| ERR
  OS["E03.O07.1 Configure_returned_model · runtime authorization record"] --> OM
  OR["E03.O07.2 revalidate_returned_models · HTTP 200·Transmission request contrast · Original result and raw preservation · New call 0entries"] --> OM
  OP -->|Passage · Following group| O1
  OP -->|Failure to do so| ERR
  O2 -->|429 · Stored maximum turnaround·Retry-After| O1
  O2 -->|Disconnect.| OD["E03.O06 Unknown_Delivery · HTTP view; request hash; orange storage"]
  O2 -->|Other transfers anonymous, identity, and| ERR
  O3 --> O4["E03.O05 UTC unit estimate: cost of return of the manufacturer separated"] --> OUT
 end
 subgraph F7["01-evaluation/pipeline.py"]
  OD --> DC{"E03.D01 Run by run continue to run confirmation of OFF/ON receive the same set of responses?"}
  DC -->|Yes · No requested forwarding| DN["E03.D02 Just a request for a forwarding."] --> O1
  DC -->|No. Includes unanswered sets| ERR
 end
 subgraph F8["01-evaluation/03-execution/output_budget.py"]
  L1["E03.L01 Configure · Approval·run·conclusion manifest hashing"] --> L2["E03.L02 Prepare_attempt · Default / stored expansion · requested copy"] --> O1
  O3 --> L3{"E03.L03 The actual length of the end of the maximum perpendicular meridian?"}
  L3 -->|Yes · of the previous boundary 2The ship · New attempt| L2
  L3 -->|No. · Preservation of the condition| OUT
 end
 subgraph F3["01-evaluation/03-execution/call_layout.py"]
  N3["publish"]
 end
 subgraph F4["01-evaluation/03-execution/gemini_batch.py"]
  G1["E03.G01 Request for a settlement. cache approval check."] --> G2["E03.G02 Batch submission; name preservation"]
  G2 --> GA{"Set up a full submission after consultation?"}
  GA -->|Yes · Remaining PREPARED placement| G2
  GA -->|Complete submission or basic order processing| G3{"E03.G03 See the action log with the same name."}
  G3 -->|Waiting.30Seconds.| G3
  G3 -->|Complete| G4["E03.G04 Raw storage, form, and cache usage testing"] --> OUT
  G2 -->|Transmit anonymously| ERR
  G2 -->|Rejection of the Provider · Suspension of Additional Submission| ERR
  CS["Collect-gemini-batches · Select only existing name · Rejected status Preservation"] --> G3
 end
 IN --> S0
 S0 -->|The wrong scheme.| ERR
 N0 --> OUT["Storage data and status"]
 N0 -->|Fail| ERR["Error and underestimated record"]
 N0 -->|Gemini Batch| G1
 N0 -->|Anthropic Batch| H0 --> N2
 N0 -->|Orca API| O1
 classDef python fill:#e3f2fd,stroke:#1565c0;
 classDef file fill:#eceff1,stroke:#607d8b;
 class S0,N0,N1,N2,N3,G1,G3,G4,CS,H0,A1,A3,A4,A5,O1,O3,O4,OP,OM,OS,OR python;
 class L1,L2,L3 python;
 classDef llm fill:#ede7f6,stroke:#673ab7;
 class G2,A2,O2 llm;
 class IN,OUT,ERR file;
```

The gray is the input-output file, and the blue is the Python function of the file. The function in the table is responsible for that.](../../../../../docs/02-experiments/README.md)Read the same number of steps.

This README is generated from `src/finarch/documentation/templates/source-layout/experiments/01-evaluation/03-execution.md`.

In the authorized Orca run. `configure-output-budget --model-key <key> --authorization '< real instructions>' --base-output-tokens 8194`And then, after writing down the policy, `run --evaluation-only --resume-limits`I'm going to restart the evaluation that was stopped. `runtime-overrides.json`It separates the actual cap-source request from the synchronized configuration and saves it to the request-started-result of the new attempt. `publish`The actual request for the latest attempt is displayed. `OUTPUT_BUDGET_INCREASED`The next length is also infinite, and the actual transmission is `OUTPUT_BUDGET_ATTEMPT`Check it out at provider-request-wire.json.
