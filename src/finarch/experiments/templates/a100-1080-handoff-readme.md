# GPU-2 FinanceReasoning 1,080The case Delivery

Running: **$run_id** · Model: **$model** · Original selection run: **$source_run**.

[Situation](state.json) → [Transmission log](events.jsonl) → [source prompted by hash](source-provenance.json) → [Set the action](config.json) → [Plans](01_evaluation/02_request/plan.json) → [Real request](01_evaluation/02_request/).

| File | Role |
|---|---|
| `00_input/public.jsonl` | Public question, context, number of digits. 1,080and variants 7,560items |
| `00_input/private.jsonl` | A1 - A1 - The only local answer.00 There's no file in the transmission. |
| `01_evaluation/02_request/common.md` | The current common root is a prompt. |
| `01_evaluation/02_request/prompt-unguided.md` | The model. `classification=null`Directly directed |
| `01_evaluation/02_request/prompt-guided.md` | I'm going to direct you to choose one of the five categories. |
| `01_evaluation/02_request/response.schema.json` | FinancialAnswerV7 response scheme |
| `01_evaluation/02_request/$model_key/manifest.jsonl` | For each model. 34,560Ask questions, prompt, and save the conditions together. |
| `a100-runtime.json` | The existing measurement candidate setting. Token length of the remote; not confirmed as executable before GPU checking |
| `transfer-manifest.json` | A100The file you send to SHA-256Private files are not included. |

Original and modified 8,640items × Unguided/Criteria-Guided × Reasoning OFF/ON = **For each model. 34,560entries**This preparation is only for file creation and hashing, and the model request is for the model to be used to create the file. 0That's the thing. 557The raw response is not reused.

GPU-2 The responsible session runs after verifying the length of the token entry, current GPU storage, model revision, format constraints and cache index.00 `remote.py`and `collect.py`In some cases 17,824It's a fixed value, so you have to check it for the new request number, and if the request is unclear whether it's being sent, it leaves a record and doesn't automatically be sent back.

Running state and results `http://127.0.0.1:8894/`Select this run and check. `TRANSFER_READY`It's not the results, it's the file ready.
